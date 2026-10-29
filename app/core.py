"""Business logic: dispatching loads, recording quotes, ranking, live updates."""
import asyncio
import json
import re
import time
from typing import Any, Optional

from . import bolna, config, db

# ---------------------------------------------------------------------------
# Live updates (Server-Sent Events hub)
# ---------------------------------------------------------------------------
_subscribers: set[asyncio.Queue] = set()


def subscribe() -> asyncio.Queue:
    qu: asyncio.Queue = asyncio.Queue(maxsize=100)
    _subscribers.add(qu)
    return qu


def unsubscribe(qu: asyncio.Queue) -> None:
    _subscribers.discard(qu)


def notify(load_id: Optional[str]) -> None:
    msg = json.dumps({"load_id": load_id, "ts": time.time()})
    for qu in list(_subscribers):
        try:
            qu.put_nowait(msg)
        except asyncio.QueueFull:
            pass


def event(load_id: str, kind: str, message: str) -> None:
    db.log_event(load_id, kind, message)
    notify(load_id)


# ---------------------------------------------------------------------------
# Parsing helpers (voice LLMs send messy values: "31,500", "31.5k", "haan")
# ---------------------------------------------------------------------------
TERMINAL_CALL_STATUSES = {
    "completed", "no-answer", "busy", "failed", "canceled", "cancelled",
    "stopped", "error", "balance-low",
}


def parse_rate(v: Any) -> Optional[int]:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return int(v) if v > 0 else None
    s = str(v).lower().replace(",", "").replace("₹", "").replace("rs", "").strip()
    m = re.search(r"(\d+(?:\.\d+)?)\s*(k|hazaar|hazar|thousand|lakh|lac)?", s)
    if not m:
        return None
    num = float(m.group(1))
    unit = m.group(2)
    if unit in {"k", "hazaar", "hazar", "thousand"}:
        num *= 1000
    elif unit in {"lakh", "lac"}:
        num *= 100000
    return int(round(num)) if num > 0 else None


def parse_float(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        m = re.search(r"\d+(?:\.\d+)?", str(v))
        return float(m.group(0)) if m else None


def parse_bool(v: Any) -> Optional[bool]:
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s in {"yes", "true", "1", "haan", "ha", "han", "available", "y", "ho"}:
        return True
    if s in {"no", "false", "0", "nahi", "nahin", "na", "unavailable", "n", "nako"}:
        return False
    return None


def round_to(n: float, step: int = 500) -> int:
    return int(round(n / step) * step)


# ---------------------------------------------------------------------------
# Ranking + snapshot
# ---------------------------------------------------------------------------
def effective_rate(c: dict[str, Any]) -> Optional[int]:
    return c.get("final_rate") or c.get("quoted_rate")


def rank_quotes(load: dict[str, Any], calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = []
    for c in calls:
        if c["kind"] != "quote" or c["outcome"] != "quoted":
            continue
        rate = effective_rate(c)
        if not rate:
            continue
        eta = c.get("eta_hours") or 0
        score = rate + eta * config.ETA_RUPEES_PER_HOUR
        ranked.append(
            {
                "call_id": c["id"],
                "trucker_id": c["trucker_id"],
                "trucker_name": c.get("trucker_name"),
                "rate": rate,
                "eta_hours": c.get("eta_hours"),
                "truck_location": c.get("truck_location"),
                "truck_number": c.get("truck_number"),
                "within_budget": bool(load.get("max_rate")) and rate <= load["max_rate"],
                "score": score,
            }
        )
    # Within-budget quotes always outrank over-budget ones; then price + ETA penalty.
    ranked.sort(key=lambda r: (0 if (r["within_budget"] or not load.get("max_rate")) else 1, r["score"]))
    for i, r in enumerate(ranked, 1):
        r["rank"] = i
    return ranked


def snapshot(load_id: str) -> Optional[dict[str, Any]]:
    load = db.one("SELECT * FROM loads WHERE id=?", (load_id,))
    if not load:
        return None
    calls = db.q(
        """SELECT c.*, t.name AS trucker_name, t.phone AS trucker_phone, t.city AS trucker_city,
                  t.truck_type AS trucker_truck_type, t.language AS trucker_language
           FROM calls c LEFT JOIN truckers t ON t.id = c.trucker_id
           WHERE c.load_id=? ORDER BY c.created_at""",
        (load_id,),
    )
    events = db.q("SELECT * FROM events WHERE load_id=? ORDER BY id DESC LIMIT 40", (load_id,))
    quote_calls = [c for c in calls if c["kind"] == "quote"]
    ranked = rank_quotes(load, calls)
    finished = [c for c in quote_calls if c["outcome"] != "pending"]
    t0 = load["created_at"]
    metrics = {
        "calls_placed": len(quote_calls),
        "answered": len([c for c in quote_calls if c["outcome"] in {"quoted", "declined"}]),
        "quotes": len(ranked),
        "declined": len([c for c in quote_calls if c["outcome"] == "declined"]),
        "finished": len(finished),
        "best_rate": ranked[0]["rate"] if ranked else None,
        "seconds_to_first_quote": round(load["first_quote_at"] - t0) if load.get("first_quote_at") else None,
        "seconds_to_shortlist": round(load["shortlisted_at"] - t0) if load.get("shortlisted_at") else None,
        "elapsed_seconds": round(time.time() - t0),
        "manual_minutes_estimate": len(quote_calls) * config.MANUAL_MINUTES_PER_CALL,
        "manual_minutes_per_call": config.MANUAL_MINUTES_PER_CALL,
        "eta_rupees_per_hour": config.ETA_RUPEES_PER_HOUR,
    }
    if ranked and load.get("max_rate"):
        metrics["saved_vs_ceiling"] = load["max_rate"] - ranked[0]["rate"]
    # Never leak phone numbers fully to the UI
    for c in calls:
        p = c.get("trucker_phone") or ""
        c["trucker_phone_masked"] = (p[:-6] + "••••" + p[-2:]) if len(p) > 8 else p
        c.pop("trucker_phone", None)
    return {"load": load, "calls": calls, "ranked": ranked, "events": events, "metrics": metrics,
            "mode": "simulate" if config.SIMULATE else "live"}


# ---------------------------------------------------------------------------
# Creating loads + fan-out
# ---------------------------------------------------------------------------
def pick_truckers(load: dict[str, Any]) -> list[dict[str, Any]]:
    rows = db.q("SELECT * FROM truckers WHERE opted_in=1 ORDER BY created_at")
    want = (load.get("truck_type") or "any").lower()
    weight = load.get("weight_tons") or 0
    picked = []
    for t in rows:
        tt = (t["truck_type"] or "any").lower()
        if want not in {"any", ""} and tt not in {"any", ""} and want not in tt and tt not in want:
            continue
        if weight and t["capacity_tons"] and t["capacity_tons"] < weight:
            continue
        picked.append(t)
    return picked[: config.MAX_PARALLEL_CALLS]


def create_load(fields: dict[str, Any], source: str = "dashboard") -> dict[str, Any]:
    max_rate = parse_rate(fields.get("max_rate"))
    target_rate = parse_rate(fields.get("target_rate"))
    if max_rate and not target_rate:
        target_rate = round_to(max_rate * 0.92)
    if target_rate and not max_rate:
        max_rate = round_to(target_rate * 1.08)
    load = {
        "id": db.new_id("L"),
        "origin": (fields.get("origin") or "").strip().title(),
        "destination": (fields.get("destination") or "").strip().title(),
        "material": (fields.get("material") or "general goods").strip(),
        "weight_tons": parse_float(fields.get("weight_tons")) or 0,
        "truck_type": (fields.get("truck_type") or "any").strip().lower(),
        "pickup_time": (fields.get("pickup_time") or "as soon as possible").strip(),
        "target_rate": target_rate,
        "max_rate": max_rate,
        "broker_name": (fields.get("broker_name") or config.BROKER_NAME).strip(),
        "broker_phone": (fields.get("broker_phone") or config.BROKER_PHONE).strip(),
        "source": source,
        "status": "dispatching",
        "created_at": time.time(),
    }
    db.insert("loads", load)
    via = "a phone call" if source == "voice" else "the dashboard"
    event(load["id"], "load", f"New load {load['id']} via {via}: {load['origin']} → {load['destination']}, "
          f"{load['weight_tons']:g} t {load['material']}")
    return load


def dispatcher_user_data(load: dict[str, Any], t: dict[str, Any]) -> dict[str, Any]:
    """Variables injected into the Dispatcher agent prompt ({var} placeholders)."""
    return {
        "load_id": load["id"],
        "trucker_id": t["id"],
        "trucker_name": t["name"].split()[0] if t["name"] else "",
        "broker_name": load["broker_name"],
        "origin": load["origin"],
        "destination": load["destination"],
        "material": load["material"],
        "weight_tons": f"{load['weight_tons']:g}",
        "truck_type": load["truck_type"],
        "pickup_time": load["pickup_time"],
        "target_rate": load["target_rate"] or "",
        "max_rate": load["max_rate"] or "",
        "language": t.get("language") or "hindi",
    }


async def _place_quote_call(load: dict[str, Any], t: dict[str, Any]) -> None:
    from . import simulate  # local import avoids a cycle

    call_id = db.new_id("C", 5)
    now = time.time()
    db.insert("calls", {"id": call_id, "load_id": load["id"], "trucker_id": t["id"], "kind": "quote",
                        "call_status": "queued", "outcome": "pending", "created_at": now, "updated_at": now})
    notify(load["id"])
    if config.SIMULATE:
        asyncio.create_task(simulate.run_quote_call(call_id, load, t))
        return
    try:
        exec_id = await bolna.make_call(config.DISPATCHER_AGENT_ID, t["phone"], dispatcher_user_data(load, t))
        db.update("calls", call_id, {"execution_id": exec_id, "call_status": "queued", "updated_at": time.time()})
    except Exception as e:  # noqa: BLE001 - surface any provider error on the dashboard
        db.update("calls", call_id, {"call_status": "failed", "outcome": "failed", "error": str(e)[:300],
                                     "updated_at": time.time()})
        event(load["id"], "error", f"Could not call {t['name']}: {str(e)[:120]}")
    notify(load["id"])


async def dispatch(load_id: str) -> int:
    load = db.one("SELECT * FROM loads WHERE id=?", (load_id,))
    truckers = pick_truckers(load)
    if not truckers:
        event(load_id, "error", "No opted-in truckers match this load. Add truckers first.")
        return 0
    db.update("loads", load_id, {"status": "quoting"})
    event(load_id, "dispatch", f"Calling {len(truckers)} truck owners in parallel…")
    await asyncio.gather(*[_place_quote_call(load, t) for t in truckers])
    asyncio.create_task(_watch_until_shortlisted(load_id))
    return len(truckers)


async def _watch_until_shortlisted(load_id: str) -> None:
    start = time.time()
    while time.time() - start < config.SHORTLIST_TIMEOUT_SECONDS:
        await asyncio.sleep(2)
        calls = db.q("SELECT outcome FROM calls WHERE load_id=? AND kind='quote'", (load_id,))
        if calls and all(c["outcome"] != "pending" for c in calls):
            break
    load = db.one("SELECT * FROM loads WHERE id=?", (load_id,))
    if load["status"] in {"shortlisted", "booked"}:
        return
    db.update("loads", load_id, {"status": "shortlisted", "shortlisted_at": time.time()})
    snap = snapshot(load_id)
    n = len(snap["ranked"])
    best = snap["ranked"][0] if n else None
    msg = f"Shortlist ready: {n} quote(s)." + (
        f" Best ₹{best['rate']:,} from {best['trucker_name']}." if best else "")
    event(load_id, "shortlist", msg)
    # Broker posted by phone -> call them back. Posted on the dashboard -> they book on screen.
    if config.AUTO_CALLBACK and n and load["source"] == "voice":
        await call_broker_back(load_id)


# ---------------------------------------------------------------------------
# Tool handlers (called by Bolna custom functions mid-call)
# ---------------------------------------------------------------------------
def _find_call(params: dict[str, Any]) -> Optional[dict[str, Any]]:
    exec_id = params.get("execution_id")
    if exec_id:
        c = db.one("SELECT * FROM calls WHERE execution_id=?", (str(exec_id),))
        if c:
            return c
    load_id = str(params.get("load_id") or "").strip().upper().replace(" ", "")
    trucker_id = str(params.get("trucker_id") or "").strip().upper().replace(" ", "")
    if load_id and trucker_id:
        c = db.one("SELECT * FROM calls WHERE load_id=? AND trucker_id=? AND kind='quote' "
                   "ORDER BY created_at DESC", (load_id, trucker_id))
        if c:
            return c
    if trucker_id:  # LLM mangled the load id: fall back to the trucker's latest pending call
        return db.one("SELECT * FROM calls WHERE trucker_id=? AND kind='quote' ORDER BY created_at DESC",
                      (trucker_id,))
    return None


def record_quote(params: dict[str, Any]) -> dict[str, Any]:
    c = _find_call(params)
    if not c:
        return {"result": "error", "message": "Could not match this call. Thank the driver and end politely."}
    available = parse_bool(params.get("available"))
    quoted = parse_rate(params.get("quoted_rate"))
    final = parse_rate(params.get("final_rate")) or quoted
    fields: dict[str, Any] = {
        "available": None if available is None else int(available),
        "quoted_rate": quoted,
        "final_rate": final,
        "truck_location": (params.get("truck_location") or params.get("current_location") or "").strip() or None,
        "eta_hours": parse_float(params.get("eta_hours")),
        "truck_number": (params.get("truck_number") or "").strip().upper() or None,
        "notes": (params.get("notes") or "").strip() or None,
        "updated_at": time.time(),
    }
    if available is False or (available is None and not final):
        fields["outcome"] = "declined"
    else:
        fields["outcome"] = "quoted"
    db.update("calls", c["id"], {k: v for k, v in fields.items() if v is not None or k == "available"})
    t = db.one("SELECT name FROM truckers WHERE id=?", (c["trucker_id"],)) or {"name": c["trucker_id"]}
    load = db.one("SELECT * FROM loads WHERE id=?", (c["load_id"],))
    if fields["outcome"] == "quoted":
        if not load.get("first_quote_at"):
            db.update("loads", load["id"], {"first_quote_at": time.time()})
        where = f" · truck at {fields['truck_location']}" if fields["truck_location"] else ""
        neg = f" (asked ₹{quoted:,}, settled ₹{final:,})" if quoted and final and final < quoted else ""
        event(load["id"], "quote", f"{t['name']} quoted ₹{final:,}{neg}{where}")
    else:
        event(load["id"], "declined", f"{t['name']} not available" + (f": {fields['notes']}" if fields["notes"] else ""))
    return {"result": "saved",
            "message": "Saved. Tell the driver the broker will confirm within 15 minutes, thank them, and end the call."}


async def post_load_from_voice(params: dict[str, Any]) -> dict[str, Any]:
    missing = [k for k in ("origin", "destination") if not params.get(k)]
    if missing:
        return {"result": "error", "message": f"Ask the broker for: {', '.join(missing)}."}
    load = create_load(params, source="voice")
    count = len(pick_truckers(load))
    asyncio.create_task(dispatch(load["id"]))
    return {"result": "dispatching", "load_id": load["id"], "truckers_being_called": count,
            "message": f"Tell the broker: {count} truck owners are being called right now; "
                       f"you will call back with the best options in about 3 minutes. Then end the call."}


def register_truck(params: dict[str, Any]) -> dict[str, Any]:
    phone = (params.get("phone") or params.get("caller_number") or "").strip()
    if not phone:
        return {"result": "error", "message": "Ask for the mobile number."}
    if not phone.startswith("+"):
        digits = re.sub(r"\D", "", phone)
        phone = "+91" + digits[-10:]
    existing = db.one("SELECT * FROM truckers WHERE phone=?", (phone,))
    fields = {
        "name": (params.get("name") or "Truck owner").strip(),
        "city": (params.get("city") or params.get("current_location") or "").strip(),
        "truck_type": (params.get("truck_type") or "any").strip().lower(),
        "capacity_tons": parse_float(params.get("capacity_tons")) or 0,
        "language": (params.get("language") or "hindi").strip().lower(),
        "opted_in": 1,  # they called us themselves = explicit consent to be called with loads
    }
    if existing:
        db.update("truckers", existing["id"], fields)
        tid = existing["id"]
    else:
        tid = db.new_id("T", 3)
        db.insert("truckers", {"id": tid, "phone": phone, "created_at": time.time(), **fields})
    notify(None)
    return {"result": "registered", "trucker_id": tid,
            "message": "Registered. Tell them we will call when a matching load comes. Thank them and end."}


async def book(load_id: str, trucker_id: str) -> dict[str, Any]:
    from . import simulate

    load = db.one("SELECT * FROM loads WHERE id=?", (load_id.strip().upper(),))
    if not load:
        return {"result": "error", "message": "Unknown load."}
    snap = snapshot(load["id"])
    choice = None
    tid = str(trucker_id).strip().upper()
    if tid.isdigit():  # broker said "option 2"
        idx = int(tid) - 1
        choice = snap["ranked"][idx] if 0 <= idx < len(snap["ranked"]) else None
    else:
        choice = next((r for r in snap["ranked"] if r["trucker_id"] == tid), None)
    if not choice:
        return {"result": "error", "message": "That option was not found. Read the options again."}
    db.update("loads", load["id"], {"status": "booked", "booked_trucker_id": choice["trucker_id"],
                                    "booked_at": time.time()})
    event(load["id"], "booked", f"Booked {choice['trucker_name']} at ₹{choice['rate']:,}")
    t = db.one("SELECT * FROM truckers WHERE id=?", (choice["trucker_id"],))
    if config.SIMULATE:
        asyncio.create_task(simulate.run_simple_call(load["id"], t["id"], "confirm"))
    elif config.CONFIRM_AGENT_ID:
        await _place_simple_call(load, t, "confirm", config.CONFIRM_AGENT_ID, {
            "load_id": load["id"], "trucker_name": t["name"].split()[0], "broker_name": load["broker_name"],
            "origin": load["origin"], "destination": load["destination"], "pickup_time": load["pickup_time"],
            "final_rate": choice["rate"], "broker_phone": load["broker_phone"]})
    return {"result": "booked", "message": f"Booked {choice['trucker_name']} at {choice['rate']} rupees. "
                                           f"Confirm to the broker, thank them, and end the call."}


async def _place_simple_call(load, person, kind, agent_id, user_data, phone=None) -> None:
    call_id = db.new_id("C", 5)
    now = time.time()
    db.insert("calls", {"id": call_id, "load_id": load["id"], "trucker_id": person["id"] if person else None,
                        "kind": kind, "call_status": "queued", "outcome": "pending",
                        "created_at": now, "updated_at": now})
    try:
        exec_id = await bolna.make_call(agent_id, phone or person["phone"], user_data)
        db.update("calls", call_id, {"execution_id": exec_id})
    except Exception as e:  # noqa: BLE001
        db.update("calls", call_id, {"call_status": "failed", "outcome": "failed", "error": str(e)[:300]})
        event(load["id"], "error", f"{kind} call failed: {str(e)[:120]}")
    notify(load["id"])


def _option_text(r: dict[str, Any]) -> str:
    parts = [f"{r['trucker_name']}, {r['rate']} rupaye"]
    if r.get("truck_location"):
        parts.append(f"gaadi abhi {r['truck_location']} mein")
    if r.get("eta_hours"):
        parts.append(f"{r['eta_hours']:g} ghante mein pahunch jayegi")
    return ", ".join(parts)


async def call_broker_back(load_id: str) -> dict[str, Any]:
    from . import simulate

    snap = snapshot(load_id)
    load = snap["load"]
    top = snap["ranked"][:3]
    if not top:
        return {"result": "error", "message": "No quotes yet."}
    if config.SIMULATE:
        event(load_id, "callback", "Calling broker back with top options (simulated)…")
        asyncio.create_task(simulate.run_simple_call(load_id, None, "broker_callback"))
        return {"result": "ok"}
    if not (config.CALLBACK_AGENT_ID and load.get("broker_phone")):
        return {"result": "skipped", "message": "Set BOLNA_CALLBACK_AGENT_ID and BROKER_PHONE to enable."}
    ud = {"load_id": load_id, "broker_name": load["broker_name"], "origin": load["origin"],
          "destination": load["destination"], "quotes_count": len(snap["ranked"]),
          "calls_count": snap["metrics"]["calls_placed"]}
    for i in range(3):
        if i < len(top):
            ud[f"option{i + 1}"] = _option_text(top[i])
            ud[f"option{i + 1}_trucker_id"] = top[i]["trucker_id"]
        else:
            ud[f"option{i + 1}"] = "none"
            ud[f"option{i + 1}_trucker_id"] = ""
    event(load_id, "callback", f"Calling broker back with top {len(top)} options…")
    await _place_simple_call(load, None, "broker_callback", config.CALLBACK_AGENT_ID, ud, phone=load["broker_phone"])
    return {"result": "ok"}


# ---------------------------------------------------------------------------
# Webhook (Bolna execution updates)
# ---------------------------------------------------------------------------
def _dig(d: Any, *keys: str) -> Any:
    for k in keys:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def _flatten_extracted(x: Any) -> dict[str, Any]:
    """Accept both legacy flat extracted_data and the nested
    {Category: {Name: {subjective, objective}}} format."""
    out: dict[str, Any] = {}
    if not isinstance(x, dict):
        return out
    for k, v in x.items():
        key = re.sub(r"[^a-z0-9]+", "_", str(k).lower()).strip("_")
        if isinstance(v, dict) and ("subjective" in v or "objective" in v):
            out[key] = v.get("objective") if v.get("objective") not in (None, "", "null") else v.get("subjective")
        elif isinstance(v, dict):
            out.update(_flatten_extracted(v))
        else:
            out[key] = v
    return out


def handle_webhook(payload: dict[str, Any]) -> dict[str, Any]:
    exec_id = payload.get("id") or payload.get("execution_id")
    if not exec_id:
        return {"ok": False, "reason": "no execution id"}
    c = db.one("SELECT * FROM calls WHERE execution_id=?", (str(exec_id),))
    if not c:
        return {"ok": True, "ignored": True}
    status = (payload.get("status") or c["call_status"] or "").lower()
    fields: dict[str, Any] = {"call_status": status, "updated_at": time.time()}
    transcript = payload.get("transcript")
    if transcript:
        fields["transcript"] = transcript if isinstance(transcript, str) else json.dumps(transcript)[:20000]
    rec = _dig(payload, "telephony_data", "recording_url")
    if rec:
        fields["recording_url"] = rec
    if c["outcome"] == "pending" and status in TERMINAL_CALL_STATUSES:
        if status in {"no-answer", "busy"}:
            fields["outcome"] = "no_answer"
        elif status in {"failed", "error", "canceled", "cancelled", "stopped", "balance-low"}:
            fields["outcome"] = "failed"
            fields["error"] = status
        elif status == "completed" and c["kind"] == "quote":
            # Fallback: the agent never called submit_quote -> try post-call extraction
            ex = _flatten_extracted(payload.get("extracted_data"))
            if ex:
                ex.update({"load_id": c["load_id"], "trucker_id": c["trucker_id"], "execution_id": exec_id})
                db.update("calls", c["id"], fields)
                record_quote(ex)
                return {"ok": True, "via": "extraction"}
            fields["outcome"] = "declined"
            fields["notes"] = "Call ended without a quote"
        elif status == "completed":
            fields["outcome"] = "done"
    db.update("calls", c["id"], fields)
    if c["load_id"]:
        if fields.get("outcome") == "no_answer":
            t = db.one("SELECT name FROM truckers WHERE id=?", (c["trucker_id"],))
            event(c["load_id"], "no_answer", f"{t['name'] if t else 'Trucker'} did not pick up")
        else:
            notify(c["load_id"])
    return {"ok": True}
