# match_worker.py

import os
import json
import time
import redis

from db.redis_store import list_objects
from agents.insight_agent import process_match
from agents.opportunity_agent import negotiate_price, adjust_offer_price
from agents.needs_agent import remove_need

# Read Redis connection info from env
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)

def run_match_worker():
    """
    Subscribes to offers_stream, then for each new offer:
      1) Scores the match against all active needs
      2) Negotiates price (accept / counter-offer / reject)
      3) If counter-offer: adjusts the offer price and re-publishes
      4) If accepted: removes the satisfied need
      5) Records a unified trace for UI/debug
    """
    pubsub = r.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe("offers_stream")
    print("▶️ Match worker listening for new offers…")

    for msg in pubsub.listen():
        if msg.get("type") != "message":
            continue

        offer = json.loads(msg["data"])
        offer_id = offer["offer_id"]
        print(f"🆕 New offer: {offer_id}")

        # Fetch all active needs
        needs = list_objects("need")
        for need in needs:
            user_id = need["user_id"]
            need_id = need["need_id"]

            # ===== Tag-based filtering guard =====
            need_tags  = set(need.get("preferences", {}).get("tags", []))
            offer_tags = set(offer.get("product", {}).get("tags", []))
            if need_tags and not (need_tags & offer_tags):
                print(f"   ↳ Skipping need {need_id}: no overlapping tags {need_tags} ∩ {offer_tags}")
                continue

            # 1) Score the match
            match = process_match(user_id, offer_id)
            score = match["score"]
            print(f"   ↳ Score for {user_id}/{need_id}: {score}")

            # Skip negotiation if no match score
            if score <= 0:
                continue

            # 2) Negotiate price
            negotiation = negotiate_price(need, offer)
            status = negotiation["status"]
            print(f"   ↳ Negotiation status for {user_id}/{need_id}: {status}")

            # 3) Handle counter-offer by adjusting the offer's price
            if status == "counter-offer":
                new_price = need["preferences"]["price_max"]
                updated = adjust_offer_price(offer_id, new_price)
                if updated:
                    offer = updated  # use the updated price for any subsequent logic
                    print(f"   ↳ Counter-offer republished: {offer_id} @ {new_price}")

            # 4) Remove the need if accepted
            need_removed = False
            if status == "accepted":
                if remove_need(need_id):
                    need_removed = True
                    print(f"   ✅ Removed satisfied need {need_id}")

            # 5) Save a unified trace for UI/debug
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

        # small throttle to avoid a busy loop
        time.sleep(0.1)

if __name__ == "__main__":
    run_match_worker()