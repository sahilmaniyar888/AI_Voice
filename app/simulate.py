"""SIMULATE=1: fake calls so the whole product runs with zero cost and zero risk.

Use it to build the UI, to rehearse, and as a backup if the live demo phone line fails.
Clearly labelled as SIMULATION on the dashboard - never present simulated calls as real.
"""
import asyncio
import random
import time

from . import core, db

LOCATIONS = ["Pimpalgaon", "Lasalgaon", "Ozar", "Sinnar", "Manmad", "Niphad", "Dindori", "Igatpuri",
             "Chandwad", "Yeola"]
DECLINE_REASONS = ["gaadi Pune mein khaali hogi, kal tak", "abhi load bhara hua hai", "driver chutti par hai",
                   "rate kam hai is route ke liye"]


def _transcript(load, t, ask, final, loc, eta, available, reason):
    name = t["name"].split()[0]
    lines = [
        f"Agent: Namaste {name} ji, main Bhaada se AI assistant bol rahi hoon, {load['broker_name']} ki taraf se. "
        f"{load['origin']} se {load['destination']} ka load hai, {load['weight_tons']:g} ton {load['material']}. "
        f"{load['pickup_time']} loading hai. Gaadi khaali hai?",
    ]
    if not available:
        lines += [f"{name}: Nahi ji, {reason}.", "Agent: Koi baat nahi, dhanyavaad. Agle load par call karenge."]
        return "\n".join(lines)
    lines += [f"{name}: Haan khaali hai.", "Agent: Gaadi abhi kahan hai, aur loading point tak kitni der lagegi?",
              f"{name}: {loc} mein hai, {eta:g} ghante mein pahunch jayegi.", "Agent: Bhaada kitna lagega?",
              f"{name}: {ask:,} lagega."]
    if final < ask:
        lines += [f"Agent: Thoda kam kijiye, {load['target_rate']:,} mein ho jayega?",
                  f"{name}: {final:,} final, isse kam nahi."]
    lines += ["Agent: Theek hai, broker sahab 15 minute mein confirm karenge. Dhanyavaad!"]
    return "\n".join(lines)


async def _status(call_id: str, load_id: str, status: str) -> None:
    db.update("calls", call_id, {"call_status": status, "updated_at": time.time()})
    core.notify(load_id)


async def run_quote_call(call_id: str, load: dict, t: dict) -> None:
    await asyncio.sleep(random.uniform(0.5, 2.0))
    await _status(call_id, load["id"], "ringing")
    await asyncio.sleep(random.uniform(2.0, 5.0))
    if random.random() < 0.12:
        await _status(call_id, load["id"], "no-answer")
        db.update("calls", call_id, {"outcome": "no_answer"})
        core.event(load["id"], "no_answer", f"{t['name']} did not pick up")
        return
    await _status(call_id, load["id"], "in-progress")
    await asyncio.sleep(random.uniform(6.0, 20.0))

    available = random.random() < 0.8
    target = load["target_rate"] or 30000
    ceiling = load["max_rate"] or int(target * 1.1)
    ask = core.round_to(random.uniform(target * 0.95, ceiling * 1.06))
    if ask <= target:
        final = ask
    elif ask <= ceiling:
        final = core.round_to((ask + target) / 2)
    else:
        final = core.round_to(ask * 0.96)
    loc = random.choice(LOCATIONS)
    eta = round(random.choice([0.5, 1, 1.5, 2, 3, 4, 6]), 1)
    reason = random.choice(DECLINE_REASONS)
    params = {"load_id": load["id"], "trucker_id": t["id"], "available": "yes" if available else "no"}
    if available:
        params.update({"quoted_rate": ask, "final_rate": final, "truck_location": loc, "eta_hours": eta,
                       "truck_number": f"MH15 {random.choice('ABCDEFGH')}{random.choice('JKLMNPQR')} "
                                       f"{random.randint(1000, 9999)}"})
    else:
        params["notes"] = reason
    core.record_quote(params)
    db.update("calls", call_id, {
        "transcript": _transcript(load, t, ask, final, loc, eta, available, reason),
        "call_status": "completed", "updated_at": time.time()})
    core.notify(load["id"])


async def run_simple_call(load_id: str, trucker_id, kind: str) -> None:
    call_id = db.new_id("C", 5)
    now = time.time()
    db.insert("calls", {"id": call_id, "load_id": load_id, "trucker_id": trucker_id, "kind": kind,
                        "call_status": "ringing", "outcome": "pending", "created_at": now, "updated_at": now})
    core.notify(load_id)
    await asyncio.sleep(3)
    await _status(call_id, load_id, "in-progress")
    await asyncio.sleep(6)
    db.update("calls", call_id, {"call_status": "completed", "outcome": "done", "updated_at": time.time()})
    if kind == "broker_callback":
        core.event(load_id, "callback", "Broker heard the top 3 options and chose option 1 (simulated)")
        await core.book(load_id, "1")
    elif kind == "confirm":
        t = db.one("SELECT name FROM truckers WHERE id=?", (trucker_id,))
        core.event(load_id, "confirmed", f"{t['name'] if t else 'Trucker'} confirmed the booking on call (simulated)")
    core.notify(load_id)
