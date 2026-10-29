#!/usr/bin/env bash
# Two uses for these commands:
#  1) Paste one into Bolna -> Tools tab -> "Generate from cURL". Bolna builds the function for you.
#     Then check the generated name, description and parameter descriptions against the matching .json file.
#  2) Run them yourself to test that your public URL and secret work before you make a real call.
#
# Replace BASE and SECRET first. The server accepts JSON body, form or query string, so whatever
# format Bolna sends, the arguments arrive.

BASE="https://YOUR-PUBLIC-URL"
SECRET="YOUR_TOOL_SECRET"

# submit_quote  (Dispatcher agent)
curl -X POST "$BASE/tools/submit_quote?secret=$SECRET" \
  -H 'Content-Type: application/json' \
  -d '{"load_id":"L4821","trucker_id":"T295","available":"yes","quoted_rate":"33000","final_rate":"31500","truck_location":"Ozar","eta_hours":"2","truck_number":"MH15 AB 1234","notes":""}'

# post_load  (Desk inbound agent)
curl -X POST "$BASE/tools/post_load?secret=$SECRET" \
  -H 'Content-Type: application/json' \
  -d '{"origin":"Lasalgaon","destination":"Surat","material":"onion","weight_tons":"20","truck_type":"open body","pickup_time":"kal subah 7 baje","max_rate":"33000","target_rate":"30000"}'

# register_truck  (Desk inbound agent)
curl -X POST "$BASE/tools/register_truck?secret=$SECRET" \
  -H 'Content-Type: application/json' \
  -d '{"name":"Ramesh Pawar","phone":"9876543210","city":"Pimpalgaon","truck_type":"open body","capacity_tons":"25"}'

# confirm_booking  (Broker callback agent)
curl -X POST "$BASE/tools/confirm_booking?secret=$SECRET" \
  -H 'Content-Type: application/json' \
  -d '{"load_id":"L4821","trucker_id":"T295"}'
