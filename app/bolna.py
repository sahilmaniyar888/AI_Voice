"""Thin Bolna REST client.

Verified against docs (Oct 2026):
  POST {BASE}/call  body: agent_id, recipient_phone_number (E.164),
                          from_phone_number (optional), user_data (prompt variables)
                    200 -> {"message": ..., "status": "queued", "execution_id": "<uuid>"}
  GET  {BASE}/executions/{execution_id} -> execution object (same shape as webhook payload)
"""
from typing import Any, Optional

import httpx

from . import config


class BolnaError(RuntimeError):
    pass


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {config.BOLNA_API_KEY}",
        "Content-Type": "application/json",
    }


async def make_call(
    agent_id: str,
    to_number: str,
    user_data: dict[str, Any],
    from_number: Optional[str] = None,
) -> str:
    """Place one outbound call. Returns Bolna execution_id."""
    if not config.BOLNA_API_KEY:
        raise BolnaError("BOLNA_API_KEY is not set")
    if not agent_id:
        raise BolnaError("agent_id is empty - set the agent id in .env")
    body: dict[str, Any] = {
        "agent_id": agent_id,
        "recipient_phone_number": to_number,
        # Prompt variables must be strings for clean substitution.
        "user_data": {k: ("" if v is None else str(v)) for k, v in user_data.items()},
    }
    sender = from_number or config.FROM_NUMBER
    if sender:
        body["from_phone_number"] = sender
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(f"{config.BOLNA_API_BASE}/call", json=body, headers=_headers())
    if r.status_code >= 300:
        raise BolnaError(f"Bolna /call {r.status_code}: {r.text[:300]}")
    data = r.json()
    exec_id = data.get("execution_id") or data.get("id") or data.get("call_id")
    if not exec_id:
        raise BolnaError(f"Bolna /call returned no execution_id: {data}")
    return str(exec_id)


async def get_execution(execution_id: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(
            f"{config.BOLNA_API_BASE}/executions/{execution_id}", headers=_headers()
        )
    if r.status_code >= 300:
        raise BolnaError(f"Bolna /executions {r.status_code}: {r.text[:300]}")
    return r.json()
