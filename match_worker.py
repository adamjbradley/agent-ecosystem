import os
import json
import time
import redis

# Import agent helpers for polling loop
from agents.needs_agent import get_current_needs
from agents.opportunity_agent import get_current_offers, negotiate_price, adjust_offer_price
from agents.needs_agent import remove_need
from agents.insight_agent import process_match

# Redis connection
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)

def run_match_worker(poll_interval: float = 1.0):
    """
    Polls all active needs and offers continuously:
      1) Fetch all needs and offers
      2) Score each need/offfer pair
      3) Negotiate, adjust prices, remove satisfied needs
      4) Publish traces
    """
    print(f"▶️ Match worker started — polling every {poll_interval}s…")
    while True:
        needs = get_current_needs()
        offers = get_current_offers()
        for offer in offers:
            offer_id = offer.get("offer_id")
            for need in needs:
                user_id = need.get("user_id")
                need_id = need.get("need_id")
                # 1) Score match
                match = process_match(user_id, offer_id)
                score = match.get("score", 0)
                if score <= 0:
                    continue
                # 2) Negotiate
                negotiation = negotiate_price(need, offer)
                status = negotiation.get("status")

                print(f"▶️ Negotiation status for {need_id}: {status} for {user_id}")

                # 3) Counter-offer
                if status == "counter-offer":
                    new_price = need.get("preferences", {}).get("price_max")
                    updated = adjust_offer_price(offer_id, new_price)
                    if updated:
                        offer = updated
                        print(f"▶️ Offer updated {need_id}: {updated} for {user_id}")

                # 4) Accept
                need_removed = False
                if status == "accepted":
                    if remove_need(need_id):
                        need_removed = True
                        r.incr("metrics:needs_met")
                        print(f"▶️ Offer approve, need removed {need_id} for {user_id}")

                # 5) Trace
                trace = {
                    "user_id":     user_id,
                    "need_id":     need_id,
                    "offer_id":    offer_id,
                    "score":       score,
                    "negotiation": negotiation,
                    "need_removed": need_removed,
                    "timestamp":   time.time()
                }
                r.rpush(f"match_traces:{user_id}", json.dumps(trace))
                r.publish("match_traces_stream", json.dumps(trace))
        time.sleep(poll_interval)

if __name__ == "__main__":
    run_match_worker(poll_interval=1.0)