# CLAUDE.md: Bhaada (Bolna Buildathon entry, deadline 31 Oct 2026)

## What this is
Bhaada is an AI freight desk for Indian truck brokers. One load in leads to parallel Hindi or Marathi phone calls to truck owners
through Bolna. The calls produce live quotes with a single counter-offer, a ranked shortlist, a call back to the broker, and a booking.
The **live dashboard and real parallel phone calls are the demo**. Everything serves that.

## Architecture (read this instead of exploring)
- `app/main.py`: FastAPI routes. `/api/*` serves the dashboard, `/tools/*` serves Bolna custom functions called mid-call,
  `/webhooks/bolna` receives Bolna execution updates, and `/api/stream` is SSE (it pushes `{load_id}` and the client refetches).
- `app/core.py`: all business logic: `create_load`, `dispatch` (parallel `POST /call`), `record_quote`, `rank_quotes`,
  `snapshot`, `call_broker_back`, `book`, `handle_webhook`, `register_truck`.
- `app/bolna.py`: `make_call(agent_id, to, user_data)` returns `execution_id`.
- `app/simulate.py`: fake calls when `SIMULATE=1`. Never present simulated calls as real.
- `app/db.py`: SQLite. The tables are `truckers`, `loads`, `calls` (telephony `call_status` plus business `outcome`), and `events` (the activity log).
- `app/static/index.html`: a single-file vanilla JS dashboard. No build step. Fonts are Mukta and Rozha One.
- `bolna/`: agent prompts and tool JSON to paste into the Bolna dashboard. Agents are configured in Bolna's UI, not in code.

## Bolna facts (verified from docs, Oct 2026)
- `POST https://api.bolna.ai/call` takes `{agent_id, recipient_phone_number (E.164), from_phone_number?, user_data{}}` and returns `{execution_id, status:"queued"}`.
- `user_data` keys fill `{var}` placeholders in the prompt and welcome message. System variables include `agent_id`, `execution_id`, and `call_sid`.
- Custom functions use the OpenAI function schema plus `"key":"custom_task"` and `"value":{method,url,api_token,headers,param}` with `%(name)s` substitution.
  The tool's HTTP response is given back to the LLM. The exact body format is not documented, so `read_params()` accepts JSON, form, query, or wrapped `arguments`.
- Webhook payloads have the same shape as `GET /executions/{id}`: `id`, `status`, `transcript`, `extracted_data`, and `telephony_data.recording_url`.
  Status flow: queued → initiated → ringing → in-progress → call-disconnected → completed | no-answer | busy | failed.
- `extracted_data` is now nested: `{Category: {Name: {subjective, objective}}}`. `_flatten_extracted()` handles both the nested and the flat format.

## Rules for changes
1. Keep `SIMULATE=1` working at all times. It is the backup demo.
2. Do not add a frontend framework, a build step, or a new database. There is no time.
3. Every change must keep the dashboard readable on a projector from 5 m away (big rates, few words).
4. Test with `SIMULATE=1 uvicorn app.main:app --port 8000` and the curl commands in `bolna/tools/curl_for_bolna.sh`.
5. Never print or log full phone numbers in the UI. Use the masked fields.
6. Keep diffs small and targeted. Don't re-read files you have just edited.

## Backlog (in priority order; stop when time runs out)
- [ ] P0: First real call to my own phone with the Dispatcher agent, and fix whatever breaks (prompt, tool URL, secret).
- [ ] P0: 3–5 real phones in parallel (friends) and record the screen and the phone audio for the demo video.
- [ ] P1: Desk inbound agent: the broker phones in a load, and the dashboard auto-switches to it (already wired: `source='voice'`).
- [ ] P2: The broker callback agent plus booking confirmation call.
- [ ] P2: "Lane memory": store every final_rate by origin→destination and show "last 5 rates on this lane" on the load. This is the moat story.
- [ ] P3: WhatsApp or SMS summary to the broker after booking.
- [ ] P3: Per-broker phone numbers (map the inbound caller ID to the broker) for multi-tenant use.
