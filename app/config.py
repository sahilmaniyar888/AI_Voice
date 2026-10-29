"""Runtime configuration, read once from environment / .env."""
import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # dotenv is optional
    pass


def _bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None or v == "":
        return default
    return v.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


# --- Bolna -----------------------------------------------------------------
BOLNA_API_BASE = os.getenv("BOLNA_API_BASE", "https://api.bolna.ai").rstrip("/")
BOLNA_API_KEY = os.getenv("BOLNA_API_KEY", "")
# Agent that calls truck owners and collects quotes (P0, required for live mode)
DISPATCHER_AGENT_ID = os.getenv("BOLNA_DISPATCHER_AGENT_ID", "")
# Agent that calls the broker back with the shortlist (P2, optional)
CALLBACK_AGENT_ID = os.getenv("BOLNA_CALLBACK_AGENT_ID", "")
# Agent that tells the chosen trucker the booking is confirmed (P2, optional)
CONFIRM_AGENT_ID = os.getenv("BOLNA_CONFIRM_AGENT_ID", "")
# Optional caller ID (must be a number bought in your Bolna account). Empty = Bolna default.
FROM_NUMBER = os.getenv("BOLNA_FROM_NUMBER", "")

# --- App -------------------------------------------------------------------
# SIMULATE=1 fakes every call locally (no Bolna, no cost). Use for UI work + backup demo.
SIMULATE = _bool("SIMULATE", True)
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")
# Shared secret for /tools/* endpoints. Put ?secret=<value> in the Bolna tool URL.
TOOL_SECRET = os.getenv("TOOL_SECRET", "")
DB_PATH = os.getenv("DB_PATH", "data/bhaada.db")
SEED_CSV = os.getenv("SEED_CSV", "data/truckers.csv")

BROKER_NAME = os.getenv("BROKER_NAME", "Sharma Roadlines")
BROKER_PHONE = os.getenv("BROKER_PHONE", "")  # E.164, used for the callback call

MAX_PARALLEL_CALLS = _int("MAX_PARALLEL_CALLS", 10)
# After this many seconds, stop waiting for slow calls and shortlist what we have.
SHORTLIST_TIMEOUT_SECONDS = _int("SHORTLIST_TIMEOUT_SECONDS", 180)
# Auto-call the broker back with the top options when quoting finishes (needs CALLBACK_AGENT_ID)
AUTO_CALLBACK = _bool("AUTO_CALLBACK", True)
# Ranking: how many rupees one hour of extra ETA "costs" when comparing quotes
ETA_RUPEES_PER_HOUR = _int("ETA_RUPEES_PER_HOUR", 500)
# Assumption shown on the dashboard: minutes a human spends per manual call (incl. redials)
MANUAL_MINUTES_PER_CALL = _int("MANUAL_MINUTES_PER_CALL", 3)


def live_ready() -> bool:
    return bool(BOLNA_API_KEY and DISPATCHER_AGENT_ID)
