# provider_worker.py

import os
import time
import json
import redis
from provider_manager import register_provider, unregister_provider, list_providers
from agents.opportunity_agent import generate_offer, stage_offer

import random

# Default negotiation strategy for providers
STRATEGY = "aggregated_offers"

# Redis connection
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)

# Configuration
CANDIDATE_PROVIDERS = [f"merchant_{i}" for i in range(1, 6)]
REGISTER_INTERVAL   = 300   # seconds between registering a new provider
UNREGISTER_INTERVAL = 3600   # seconds between removing one
OFFER_INTERVAL      = 60    # seconds between offers per active provider
OFFER_TTL           = 120   # seconds TTL for each offer
OFFER_INTERVAL = 60  # seconds between staging new offers

# After your existing imports and constants
MIN_OFFER_DELAY = 0.5   # half‐second minimum
MAX_OFFER_DELAY = 3.0   # three‐second maximum

last_register   = time.time()
last_unregister = time.time()

print("▶️ Provider worker started…")

def run_provider_worker():
    global last_register, last_unregister
    while True:
        now = time.time()

        # 1) Register a new provider if any remaining
        if now - last_register >= REGISTER_INTERVAL:
            existing = list_providers()
            to_register = [p for p in CANDIDATE_PROVIDERS if p not in existing]
            if to_register:
                pid = to_register[0]
                register_provider(pid)
                print(f"  • Registered provider {pid}")
            last_register = now

        # 2) Unregister the oldest provider occasionally
        if now - last_unregister >= UNREGISTER_INTERVAL:
            existing = list_providers()
            if existing:
                pid = existing[0]
                unregister_provider(pid)
                # Also delete its offers and publish removal events
                for key in r.keys(f"offer:{pid}_*"):
                    offer_id = key.split(":", 1)[1]
                    r.delete(key)
                    r.publish("offers_removed_stream", json.dumps({"offer_id": offer_id}))
                print(f"  • Unregistered provider {pid} and removed its offers")
            last_unregister = now

        # 3) For each currently registered provider, generate an offer
        providers = list_providers()
        for provider_id in providers:
            offer = stage_offer(provider_id, STRATEGY)
            if offer is not None:
                print(f"   ⏱ Staged offer {offer['offer_id']} from {provider_id}")
            else:
                print(f"   ⚠️ No offer staged for {provider_id}")

        # After staging offers for all providers…
        delay = random.uniform(MIN_OFFER_DELAY, MAX_OFFER_DELAY)
        print(f"⏱ Sleeping {delay:.2f}s before staging next batch")
        time.sleep(delay)        

if __name__ == "__main__":
    run_provider_worker()

