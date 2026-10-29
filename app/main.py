"""Bhaada - AI dispatcher that phones truck owners in parallel and negotiates freight.

Run:  uvicorn app.main:app --reload --port 8000
"""
import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from . import config, core, db

log = logging.getLogger("bhaada")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
STATIC = os.path.join(os.path.dirname(__file__), "static")


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.conn()
    added = db.seed_truckers_from_csv(config.SEED_CSV)
    if added:
        log.info("Seeded %d truckers from %s", added, config.SEED_CSV)
    mode = "SIMULATE" if config.SIMULATE else ("LIVE" if config.live_ready() else "LIVE (NOT CONFIGURED!)")
    log.info("Bhaada running in %s mode. Public URL: %s", mode, config.PUBLIC_BASE_URL)
    yield


app = FastAPI(title="Bhaada", lifespan=lifespan)


async def read_params(request: Request) -> dict[str, Any]:
    """Bolna custom functions may send args as JSON body, form, or query string.
    Accept all three so the integration works first time."""
    params: dict[str, Any] = dict(request.query_params)
    body = await request.body()
    if body:
        try:
            data = json.loads(body)
            if isinstance(data, str):  # double-encoded JSON
                data = json.loads(data)
        except (json.JSONDecodeError, ValueError):
            from urllib.parse import parse_qsl

            data = dict(parse_qsl(body.decode(errors="ignore")))
        if isinstance(data, dict):
            for wrapper in ("arguments", "args", "params", "parameters", "data"):
                inner = data.get(wrapper)
                if isinstance(inner, str):
                    try:
                        inner = json.loads(inner)
                    except ValueError:
                        inner = None
                if isinstance(inner, dict):
                    data = {**data, **inner}
            params.update(data)
    params.pop("secret", None)
    return params


def check_secret(request: Request) -> None:
    if not config.TOOL_SECRET:
        return
    supplied = (
        request.query_params.get("secret")
        or request.headers.get("x-tool-secret")
        or request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    )
    if supplied != config.TOOL_SECRET:
        raise HTTPException(status_code=401, detail="bad secret")


# ---------------------------------------------------------------------------
# Dashboard + API
# ---------------------------------------------------------------------------
@app.get("/")
async def index() -> FileResponse:
    return FileResponse(os.path.join(STATIC, "index.html"))


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "mode": "simulate" if config.SIMULATE else "live", "live_ready": config.live_ready(),
            "callback_agent": bool(config.CALLBACK_AGENT_ID), "confirm_agent": bool(config.CONFIRM_AGENT_ID),
            "public_base_url": config.PUBLIC_BASE_URL}


@app.get("/api/truckers")
async def list_truckers() -> list[dict[str, Any]]:
    rows = db.q("SELECT * FROM truckers ORDER BY created_at")
    for r in rows:
        p = r["phone"]
        r["phone_masked"] = (p[:-6] + "••••" + p[-2:]) if len(p) > 8 else p
        r.pop("phone")
    return rows


@app.post("/api/truckers")
async def add_trucker(request: Request) -> dict[str, Any]:
    return core.register_truck(await read_params(request))


@app.delete("/api/truckers/{trucker_id}")
async def delete_trucker(trucker_id: str) -> dict[str, Any]:
    db.q("DELETE FROM truckers WHERE id=?", (trucker_id,))
    core.notify(None)
    return {"ok": True}


@app.get("/api/loads")
async def list_loads() -> list[dict[str, Any]]:
    return db.q("SELECT * FROM loads ORDER BY created_at DESC LIMIT 20")


@app.post("/api/loads")
async def create_and_dispatch(request: Request) -> dict[str, Any]:
    params = await read_params(request)
    if not params.get("origin") or not params.get("destination"):
        raise HTTPException(400, "origin and destination are required")
    if not config.SIMULATE and not config.live_ready():
        raise HTTPException(400, "Live mode needs BOLNA_API_KEY and BOLNA_DISPATCHER_AGENT_ID in .env")
    load = core.create_load(params, source="dashboard")
    count = await core.dispatch(load["id"])
    return {"load_id": load["id"], "truckers_called": count}


@app.get("/api/loads/{load_id}")
async def get_load(load_id: str) -> dict[str, Any]:
    snap = core.snapshot(load_id)
    if not snap:
        raise HTTPException(404, "load not found")
    return snap


@app.post("/api/loads/{load_id}/book")
async def book_from_dashboard(load_id: str, request: Request) -> dict[str, Any]:
    params = await read_params(request)
    return await core.book(load_id, str(params.get("trucker_id") or params.get("option") or "1"))


@app.post("/api/loads/{load_id}/callback")
async def callback_broker(load_id: str) -> dict[str, Any]:
    return await core.call_broker_back(load_id)


@app.get("/api/stream")
async def stream(request: Request) -> StreamingResponse:
    qu = core.subscribe()

    async def gen():
        try:
            yield "retry: 2000\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(qu.get(), timeout=15)
                    yield f"data: {msg}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            core.unsubscribe(qu)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---------------------------------------------------------------------------
# Tools: Bolna custom functions call these DURING a live call
# ---------------------------------------------------------------------------
@app.api_route("/tools/submit_quote", methods=["GET", "POST"])
async def tool_submit_quote(request: Request) -> JSONResponse:
    check_secret(request)
    params = await read_params(request)
    log.info("submit_quote %s", params)
    return JSONResponse(core.record_quote(params))


@app.api_route("/tools/post_load", methods=["GET", "POST"])
async def tool_post_load(request: Request) -> JSONResponse:
    check_secret(request)
    params = await read_params(request)
    log.info("post_load %s", params)
    return JSONResponse(await core.post_load_from_voice(params))


@app.api_route("/tools/confirm_booking", methods=["GET", "POST"])
async def tool_confirm_booking(request: Request) -> JSONResponse:
    check_secret(request)
    params = await read_params(request)
    log.info("confirm_booking %s", params)
    choice = params.get("trucker_id") or params.get("option") or "1"
    return JSONResponse(await core.book(str(params.get("load_id", "")), str(choice)))


@app.api_route("/tools/register_truck", methods=["GET", "POST"])
async def tool_register_truck(request: Request) -> JSONResponse:
    check_secret(request)
    params = await read_params(request)
    log.info("register_truck %s", params)
    return JSONResponse(core.register_truck(params))


# ---------------------------------------------------------------------------
# Bolna execution webhook (set in each agent's Analytics tab)
# ---------------------------------------------------------------------------
@app.post("/webhooks/bolna")
async def bolna_webhook(request: Request) -> JSONResponse:
    try:
        payload = await request.json()
    except ValueError:
        return JSONResponse({"ok": False}, status_code=400)
    log.info("webhook id=%s status=%s", payload.get("id"), payload.get("status"))
    return JSONResponse(core.handle_webhook(payload))
