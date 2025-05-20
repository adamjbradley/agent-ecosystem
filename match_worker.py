import os
import json
import time
import redis

from db.redis_store import list_objects
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

        # 0) Inventory guard
        merchant = offer.get("provided_by")
        if offer_pid not in list_stocked_products(merchant):
            print(f"   ⚠️ Skipping {offer_id}: '{offer_pid}' not in {merchant}'s stock")
            continue

        # fetch all active needs
        needs = list_objects("need")
        for need in needs:
            user_id, need_id = need["user_id"], need["need_id"]
            need_pid = need.get("product_id")

            # 1) Product-based filter
            if need_pid and offer_pid and need_pid != offer_pid:
                print(f"   ↳ Skipping need {need_id}: product mismatch {need_pid} ≠ {offer_pid}")
                continue

            # 2) Tag-based guard (only if both define tags)
            need_tags  = set(need.get("preferences", {}).get("tags", []))
            offer_tags = set(offer.get("tags", []))
            if need_tags and offer_tags and not (need_tags & offer_tags):
                print(f"   ↳ Skipping {need_id}: tags {need_tags} ∩ {offer_tags} → ∅")
                continue

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

        time.sleep(0.1)

if __name__ == "__main__":
    run_match_worker()