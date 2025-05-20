# need_worker.py

import os
import time
import json
import random
import redis

from agents.needs_agent import process_user_preferences, detect_unsatisfied

# ───────────────────────────────────────────────────────────────────────────────
# Redis connection via environment variables
# ───────────────────────────────────────────────────────────────────────────────
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)

# ───────────────────────────────────────────────────────────────────────────────
# Configuration
# ───────────────────────────────────────────────────────────────────────────────
USER_IDS         = ["user_001", "user_002", "user_003"]
NEED_INTERVAL    = 2    # seconds between generating new needs
DEFAULT_NEED_TTL = 5    # seconds before each need auto-expires
UNSAT_THRESHOLD = DEFAULT_NEED_TTL  # seconds before flagging unsatisfied

last_need_time = time.time()

print(f"▶️ Need worker started — generating needs every {NEED_INTERVAL}s "
      f"with TTL={DEFAULT_NEED_TTL}s...")

# ───────────────────────────────────────────────────────────────────────────────
# Main loop: periodically generate new needs for all users
# ───────────────────────────────────────────────────────────────────────────────
def run_need_worker():
    global last_need_time
    while True:
        now = time.time()
        if now - last_need_time >= NEED_INTERVAL:
            for user_id in USER_IDS:
                # Randomly sample preferences for demonstration
                tags      = random.sample(
                    ["eco-friendly", "quiet", "budget", "fast-delivery"], k=2
                )
                max_price = random.choice([300, 400, 500, 600])
                prefs     = {"tags": tags, "price_max": max_price}

                # Store the need with TTL and publish via the Needs Agent
                need = process_user_preferences(user_id, prefs, ttl=DEFAULT_NEED_TTL)
                print(f"  • Generated need {need['need_id']} for {user_id}")

            last_need_time = now

            # After generating new needs, detect any unsatisfied ones past the threshold
            detect_unsatisfied(UNSAT_THRESHOLD)
            print(f"  • Checked for unsatisfied needs older than {UNSAT_THRESHOLD}s")

        # Small sleep to avoid busy-looping
        time.sleep(0.2)

if __name__ == "__main__":
    run_need_worker()