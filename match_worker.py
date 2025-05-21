import os
import json
import time
import redis

# removed list_objects
from agents.needs_agent import get_current_needs
from agents.insight_agent import process_match
from agents.opportunity_agent import negotiate_price, adjust_offer_price, list_stocked_products
from agents.needs_agent import remove_need

# Redis connection
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)

def run_match_worker():
    pubsub = r.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe("offers_stream")
    print("▶️ Match worker listening for new offers…")

    for msg in pubsub.listen():
        if msg.get("type") != "message":
            continue

        offer = json.loads(msg["data"])
        offer_id, offer_pid = offer.get("offer_id"), offer.get("product_id")
        print(f"🆕 New offer: {offer_id} (product: {offer_pid})")

        # fetch all active needs (using agent helper)
        needs = get_current_needs()
        for need in needs:
            user_id, need_id = need["user_id"], need["need_id"]
            need_pid = need.get("product_id")

            # 3) Score
            match = process_match(user_id, offer_id)
            score = match.get("score", 0)
            if score <= 0:                
                continue
            print(f"   ↳ Score for {user_id}/{need_id}: {score}")

            # 4) Negotiate
            negotiation = negotiate_price(need, offer)
            status = negotiation.get("status")
            print(f"   ↳ Negotiation for {user_id}/{need_id}: {status}")

            # 5) Counter-offer
            if status == "counter-offer":
                new_price = need["preferences"]["price_max"]
                updated = adjust_offer_price(offer_id, new_price)
                if updated:
                    offer = updated
                    print(f"   ↳ Counter-offer republished: {offer_id} @ {new_price}")

            # 6) Accept
            removed_flag = False
            if status == "accepted" and remove_need(need_id):
                removed_flag = True
                print(f"   ✅ Removed satisfied need {need_id}")
                r.incr("metrics:needs_met")

            # 7) Trace for UI
            trace = {
                "user_id":      user_id,
                "need_id":      need_id,
                "offer_id":     offer_id,
                "score":        score,
                "negotiation":  negotiation,
                "need_removed": removed_flag,
                "timestamp":    time.time()
            }
            r.rpush(f"match_traces:{user_id}", json.dumps(trace))
            r.publish("match_traces_stream", json.dumps(trace))

        time.sleep(5)

if __name__ == "__main__":
    run_match_worker()