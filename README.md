# Bhaada: one call from the broker, twenty calls to truck owners

Bhaada is an AI freight desk for Indian truck brokers. The broker speaks a load once, by phone or on the dashboard.
Bhaada then phones every matching truck owner **at the same time** in Hindi or Marathi. On each call it asks
where the truck is, gets a rate, counters once without revealing the broker's ceiling, and records the final price.
It ranks the quotes, calls the broker back with the best three, and books the one the broker picks.

Built on Bolna (calls, Indian telephony through Plivo, Indian-language speech) for the Bolna Buildathon, October 2026.

```
Broker ──call──▶ [Bhaada Desk agent] ──post_load──▶ server ──POST /call ×N──▶ [Dispatcher agent] ──▶ truck owners
                                                       ▲                                   │ submit_quote (mid-call)
dashboard (live) ◀── SSE ── server ◀── webhooks ───────┘◀──────────────────────────────────┘
Broker ◀──call── [Callback agent] ◀── shortlist ready     confirm_booking ──▶ [Confirm agent] ──▶ winning owner
```

## 1. Run it in 2 minutes (simulation, no cost)

```bash
python3 -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                     # SIMULATE=1 by default
uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000 and press **Call truck owners**. The calls are simulated and labelled that way on screen,
but everything else is the real code path: ranking, the shortlist, the callback, booking and the activity log.

## 2. Go live with Bolna (about 1 hour)

1. **Bolna account:** sign up at platform.bolna.ai. Reviews say new accounts get about $5 of credit, which I could not confirm.
   Top up $15–20 so you can run about 100 test calls.
2. **Public URL for your laptop** (Bolna must reach your tool endpoints and webhook):
   `cloudflared tunnel --url http://localhost:8000` gives you an `https://….trycloudflare.com` URL with no account needed.
   ngrok works too. Put that URL in `.env` as `PUBLIC_BASE_URL`.
3. **Create the Dispatcher agent**: follow `bolna/01_dispatcher_agent.md` (welcome message, prompt, voice, tool, webhook).
   - In the tool URLs, replace `https://YOUR-PUBLIC-URL` with your tunnel URL and `YOUR_TOOL_SECRET` with `TOOL_SECRET` from `.env`.
4. Copy the API key (Developers / API keys) and the agent ID into `.env`, then set `SIMULATE=0`. Restart the server.
5. **Put real people in `data/truckers.csv`**: friends, family or real truck owners who agreed to receive the calls.
   Use E.164 format (`+9198…`). Delete `data/bhaada.db` so the CSV is reloaded (or add owners from the dashboard).
6. Press **Call truck owners**. Their phones ring. Quotes land on the dashboard while the calls are still going.

P1/P2 agents (`02_desk_inbound_agent.md`, `03_broker_callback_agent.md`) add the "broker just phones Bhaada" loop.

## 3. Test the tool endpoints before a real call

```bash
bash bolna/tools/curl_for_bolna.sh   # after editing BASE and SECRET at the top
```

## Files

| Path | What it is |
|---|---|
| `app/main.py` | HTTP routes: dashboard API, Bolna tool endpoints, webhook, live stream |
| `app/core.py` | Dispatching, quote recording, ranking, callback and booking logic |
| `app/bolna.py` | Bolna REST client (`POST /call`, `GET /executions/{id}`) |
| `app/simulate.py` | Fake calls for development and as a demo fallback |
| `app/static/index.html` | The live dispatch board |
| `bolna/*.md` | Agent prompts and settings to paste into Bolna |
| `bolna/tools/*.json` | Custom function definitions |
| `docs/PLAN_48H.md` | Hour-by-hour plan to the 31 October deadline |
| `docs/DEMO_AND_PITCH.md` | Demo video script, submission text, pitch, interview answers |
| `CLAUDE.md` | Context for Claude Code: read automatically when you open this folder |

## Honest limits (know these before judges ask)
- Ranking is a simple rule: within-budget quotes first, then price plus ₹500 per hour of ETA. It is configurable in `.env`.
- Phone numbers are stored in plain text in SQLite. That is fine for a demo, not for production.
- Outbound AI calls in India are "A2P" calls under TRAI's September 2026 amendment and must be declared to the telecom operator.
  The design calls only owners who opted in, and owners register by calling in. Confirm the declaration steps with Bolna and Plivo before any real pilot.
