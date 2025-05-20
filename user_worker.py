import os
import time
import random

from agents.users_agent import create_user, list_users, process_user_preferences

# Interval and batch size
USER_INTERVAL = 30  # seconds between batches
USERS_PER_CYCLE = 5

def run_user_worker():
    print("▶️ User worker starting…")
    while True:
        for i in range(USERS_PER_CYCLE):

            existing = list_users()
            if len(existing) >= 10:
                print(f"😴 User limit reached ({len(existing)}). Skipping creation this cycle.")
            else:
                to_create = min(USERS_PER_CYCLE, 10 - len(existing))
                for i in range(to_create):
                    uid = f"user_{int(time.time())}_{i}"
                    attrs = {"segment": random.choice(["A", "B", "C"])}
                    user = create_user(uid, attrs)
                    print(f"   🆕 Created user: {user['user_id']}")

                    # Immediately create an initial need for this user
                    tags = random.sample(["eco-friendly", "quiet", "budget", "fast-delivery"], 2)
                    max_price = random.choice([200, 300, 400])
                    need = process_user_preferences(uid, {"tags": tags, "price_max": max_price})
                    print(f"      ➡ Created need {need['need_id']} for user {uid}")

        time.sleep(USER_INTERVAL)

if __name__ == "__main__":
    run_user_worker()