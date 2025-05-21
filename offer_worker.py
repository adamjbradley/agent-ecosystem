# offer_worker.py

import os
import time
import json
import redis
from agents.opportunity_agent import generate_offer

# Single Opportunity Agent Worker aggregating offers from multiple providers
# Redis connection (via docker-compose env-vars)
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)

# ----- Configurable Parameters -----
offer_interval    = 60  # seconds between new waves of offers
DEFAULT_OFFER_TTL = 3600  # seconds before each offer auto-expires

# List of merchant/provider IDs to generate offers for
MERCHANT_IDS = ["merchant_1", "merchant_2", "merchant_3"]
STRATEGY     = "aggregated_offers"
PENDING_OFFERS_STREAM = "pending_offers_stream"

print("▶️ Offer worker started — aggregating offers from providers every "
      f"{offer_interval}s with TTL={DEFAULT_OFFER_TTL}s…")

last_offer = time.time()
ACTIVATION_INTERVAL = 0.5  # half‐second between activations

def run_offer_worker():
    pubsub = r.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(PENDING_OFFERS_STREAM)
    print("▶️ Offer worker listening for pending offers…")
    for msg in pubsub.listen():
        if msg.get("type") != "message":
            continue
        offer = json.loads(msg["data"])
        # publish as active
        r.setex(f"offer:{offer['offer_id']}", DEFAULT_OFFER_TTL, json.dumps(offer))
        r.publish("offers_stream", json.dumps(offer))
        print(f"   ✅ Activated pending offer {offer['offer_id']}")
        time.sleep(ACTIVATION_INTERVAL)

if __name__ == "__main__":
    run_offer_worker()