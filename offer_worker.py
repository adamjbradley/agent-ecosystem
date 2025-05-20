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
offer_interval    = 2  # seconds between new waves of offers
DEFAULT_OFFER_TTL = 5  # seconds before each offer auto-expires

# List of merchant/provider IDs to generate offers for
MERCHANT_IDS = ["merchant_1", "merchant_2", "merchant_3"]
STRATEGY     = "aggregated_offers"

print("▶️ Offer worker started — aggregating offers from providers every "
      f"{offer_interval}s with TTL={DEFAULT_OFFER_TTL}s…")

last_offer = time.time()

def run_offer_worker():
    global last_offer
    while True:
        now = time.time()
        # Time to generate a new batch?
        if now - last_offer >= offer_interval:
            for provider_id in MERCHANT_IDS:
                offer = generate_offer(provider_id, STRATEGY, ttl=DEFAULT_OFFER_TTL)
                print(f"  • Generated offer {offer['offer_id']} by provider {provider_id}")
            last_offer = now
        time.sleep(0.2)

if __name__ == "__main__":
    run_offer_worker()