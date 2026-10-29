# Plan to the deadline (Sat 31 Oct 2026)

The page gives the date but not a cutoff time. **Plan to submit by Sat 31 Oct, 4 pm IST**, and check the
submission form for the exact time tonight. After you submit, the work moves to real users before the shortlist (3 Nov)
and the interviews (5–7 Nov).

## Thursday 29 Oct, tonight (about 5 h)
| Time | Do | Done when |
|---|---|---|
| 20:00 | Run the kit in simulation (README §1). Push it to a **public GitHub repo**. | The dashboard shows simulated quotes |
| 20:30 | Create a Bolna account and the Dispatcher agent (paste `bolna/01_dispatcher_agent.md`) | "Test call" from the Bolna playground works |
| 21:30 | Start the cloudflared tunnel, set `.env`, add the tool and webhook with your tunnel URL, then `SIMULATE=0` | Running the curl tests prints `"saved"` |
| 22:00 | **First real call: put only your own number in truckers.csv** | Your phone rings and a quote lands on the dashboard |
| 22:30 | Fix the top three problems you hear (number pronunciation, a second counter-offer, the tool not being called) | 3 clean calls in a row |
| 23:30 | Message 4–5 friends: "Tomorrow 11 am, I'll call you from an AI. Pretend you own a truck." Give each one a role (see the demo script) | 5 yeses |

## Friday 30 Oct (the build day)
| Time | Do | Done when |
|---|---|---|
| 09:00 | Buy an Indian number in Bolna (for the inbound Desk). If KYC blocks it, skip it and use the playground web call for the inbound part | You have a number, or a decision |
| 10:00 | Desk inbound agent (`02_desk_inbound_agent.md`). Call it and speak a load | The dashboard auto-switches to the voice load |
| 11:00 | **Parallel run with 5 friends.** Record your screen (OBS or a phone on a tripod) | 5 phones ring at once and 4 or more quotes land |
| 12:30 | Broker callback agent (`03_...`) and `BROKER_PHONE` | Your phone rings with the top 3 and "pehli wali" books it |
| 14:00 | **Reality check, in person or by phone:** visit a transport office in Nashik (or Lasalgaon or Pimpalgaon), or call 2 brokers you know. Show the video. Ask the 5 questions below | 2 conversations written down, with quotes |
| 17:00 | Lane memory (CLAUDE.md backlog) **only if everything above works** | |
| 19:00 | Record the final 2-minute demo video (`DEMO_AND_PITCH.md`) | Uploaded unlisted on YouTube or Drive |
| 22:00 | Write the submission text (template in DEMO_AND_PITCH.md) | Draft ready |

**Questions to ask brokers:** (1) How many calls do you make to find one truck? (2) How long does that take on a busy day?
(3) Would you let an AI call your truck owners if it said it was calling for you? (4) What would you pay per truck found?
(5) Can I run 5 of your real loads through it next week?
Write their exact words down. One real broker quote beats any market-size slide.

## Saturday 31 Oct
| Time | Do |
|---|---|
| 09:00 | Fix whatever broke in the video. Re-record only if it is bad |
| 11:00 | README screenshots and repo cleanup (remove `.env`, keep `.env.example`) |
| 13:00 | **Submit.** Project name, idea, description, the video link, GitHub and LinkedIn |
| After | Keep running real loads with real brokers. Every real call before 5 Nov is interview ammunition |

## Money
- **Bolna:** third-party reviews say pay-as-you-go is about 6¢ a minute and new accounts get about $5 of credit. Check this on your own bill.
  At that rate, 100 two-minute test calls cost about $12. An Indian number is $5 a month (Bolna docs).
- **Claude:** `CLAUDE.md` gives Claude Code the full context, so it won't burn credit re-reading the repo.
  Give it **one backlog item per session**, paste the exact error or transcript line, and start a fresh session between features.
  Do UI work in `SIMULATE=1` so you don't pay for calls while you iterate.

## If something breaks
| Symptom | Likely cause and fix |
|---|---|
| The call happens but no quote appears | The tool URL is wrong or the secret is missing. Check `uvicorn` logs for `submit_quote`. Run the curl test against your tunnel URL |
| The dashboard stays on "Dialling" | The webhook is not set in the agent's Analytics tab, or the tunnel URL changed (quick tunnels change on every restart) |
| `401 bad secret` in the logs | The `?secret=` in the Bolna tool URL doesn't match `TOOL_SECRET` |
| The agent reads out "31500" as digits | Add an example to the prompt: "say ikattis hazaar paanch sau". Some TTS voices handle Hindi numbers better than others, so try the other sponsor voice |
| The agent negotiates twice | Lower the temperature and move the "exactly once" rule to the top of the prompt |
| Everything fails during a live demo | Set `SIMULATE=1`, say clearly "this is the simulation mode", and play the recorded video of the real calls |
