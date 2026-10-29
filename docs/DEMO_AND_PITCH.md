# Demo, submission and pitch

## The one line
**"The broker makes one call. Bhaada makes twenty, at the same time, in Hindi and Marathi, and calls back with the best truck in about three minutes."**

## 2-minute demo video (record on Friday evening)
Real calls only. Get each friend's consent and tell them their voice will be in the video.

| Time | Screen | Audio |
|---|---|---|
| 0:00–0:12 | Text card: "Lasalgaon, Nashik. Asia's largest onion market." Then a phone with a long call log | Voice-over: "When a trader here needs a truck, a broker starts dialling. One owner at a time." |
| 0:12–0:30 | You on camera dial the Bhaada Desk number and speak: "Lasalgaon se Surat, bees ton pyaaz, kal subah saat baje, taintees hazaar tak" | Bhaada reads it back and says it is calling the owners |
| 0:30–1:15 | **Hero shot:** the dashboard switches to the load and 5 tiles go Ringing and then On the call. Cut to the table with 5 phones ringing | Play one call's audio: owner "Tetees hazaar." Bhaada "Thoda kam kijiye, tees mein ho jayega?" Owner "Saade ikattis, final." |
| 1:15–1:35 | Quotes land with yellow plates, the best one is highlighted, and the clock reads about 2:30 | |
| 1:35–1:50 | Your phone rings: the callback reads the top 3, you say "pehli wali", and the dashboard shows Booked | |
| 1:50–2:00 | The story line on the dashboard: "called 5 at once, first quote in 0:40, ₹1,500 under your highest rate" | "One call in. Twenty calls out. Truck booked." |

**Friends' roles, so the video shows range:** 1 accepts the counter-offer, 1 holds a firm price, 1 is not available ("gaadi Pune mein hai"),
1 speaks Marathi, 1 doesn't pick up. That shows negotiation, the language switch and the failure handling in one take.

## Submission form (fields from the application page)
- **Project name:** Bhaada
- **Idea, one line:** An AI freight desk that phones every truck owner at once, negotiates in Hindi and Marathi, and books the best truck for the broker in minutes.
- **What you built and where voice fits:**
  > Indian road freight runs on phone calls. Most trucks belong to small owners, and brokers find a truck by dialling owners one by one.
  > Bhaada turns that into one call. A broker phones the Bhaada desk (a Bolna inbound agent) and speaks the load. Our server then
  > places parallel outbound calls through Bolna to every opted-in truck owner who matches. A Dispatcher agent asks for the truck's
  > location and arrival time, gets a rate, makes one counter-offer without revealing the broker's ceiling, and writes the quote
  > to our backend mid-call through a custom function. A live dashboard ranks the quotes as they land. A callback agent phones
  > the broker with the top three, and the broker books by voice. Voice is the whole product: truck owners don't use apps, but they
  > always answer the phone. Stack: Bolna orchestration and Plivo telephony, a Sarvam or Deepgram transcriber, a Sarvam or Cartesia
  > Hindi voice, FastAPI and SQLite.
- **Links:** public GitHub repo, demo video (unlisted YouTube), LinkedIn.

## Pitch (finale, about 3 minutes)
1. **Hook (20 s):** "In May this year, traders at Lasalgaon, Asia's largest onion market, threatened to stop auctions. A fuel shortage meant they couldn't find enough trucks."
2. **Problem (30 s):** India's trucks are mostly owned by small operators, and the brokers who match loads to them work by phone, one call at a time.
3. **Live demo (90 s):** the same flow as the video, with 3–4 teammates' phones on stage. Keep `SIMULATE=1` and the recorded video ready as backups.
4. **Why it will work (30 s):** the same playbook is working in the US. HappyRobot (YC S23) automates freight-broker calls and raised a $44M Series B.
   India needs it phone-first and in Indian languages, which is what Bolna makes possible.
5. **Business (20 s):** charge the broker per confirmed truck. At roughly ₹10 for each 2-minute call, ten calls per load cost about ₹100.
   *These are pricing hypotheses that I am testing with the brokers I spoke to.* Say so on stage.
6. **Traction (10 s):** only real numbers, for example "X brokers tried it, Y real loads, Z owners registered by calling in".

## Interview questions you will get
- **"Will truck owners talk to an AI?"** It says it is an AI at the start. Owners already take broker calls all day, and this call is shorter and gets them a load.
  Then give your measured pickup and completion rate from real calls. Measure it on Friday.
- **"What about TRAI spam rules?"** Under the 18 Sept 2026 amendment, automated (A2P) calls must be declared to the operator in advance.
  Bhaada calls only owners who opted in, and owners can register by calling in, which is consent by design. We will declare A2P usage through our telephony provider before any pilot.
- **"Why won't BlackBuck or Vahak do this?"** They are apps that ask owners to change their behaviour. Bhaada works on the broker's existing contact list,
  over the phone network everyone already uses, and the broker keeps the relationship.
- **"What's the moat?"** Every call produces a lane-level rate (Lasalgaon→Surat, 20 t, this week). Over time Bhaada knows the real market rate on each lane,
  plus which owners pick up and keep their word. That data makes the negotiation better, and nobody else collects it.
- **"Why you?"** You're from Nashik, next to the market that sets India's onion prices. You built and tested this with real calls in 48 hours.
  You're an ML engineer, so the next step (fine-tuned Hinglish rate extraction and lane price prediction) is your home ground.

## Sources for the numbers above
- HappyRobot $44M Series B (Reuters, via The Star): https://www.thestar.com.my/tech/tech-news/2025/09/03/happyrobot-raises-44-million-to-expand-ai-agents-for-freight-operators
- Lasalgaon fuel shortage, May 2026: https://www.mypunepulse.com/?p=200800
- Indian fleet fragmentation (Nexdigm, 2026): https://www.nexdigm.com/market-research/insights/blog/india-truck-aggregator-industry/
- Small operators depend on brokers (Deccan Herald, quoting Raaho's CEO): https://deccanherald.com/business/indian-truckers-caught-on-a-pot-holed-road-to-growth-aspirations-1218737.html
- TRAI A2P rules, 18 Sept 2026: https://www.deccanchronicle.com/amp/business/trai-tightens-anti-spam-rules-brings-ai-based-detection-automated-calls-under-framework-1988473
- Buildathon page: https://www.bolna.ai/symphony/buildathon
