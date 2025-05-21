import redis, json, os
from agents.needs_agent import get_need, get_current_needs
from agents.opportunity_agent import get_offer

# Read Redis connection info from env (set in docker-compose.yml)
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

r = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=0,
    decode_responses=True
)

def process_match(user_id, offer_id):
    needs = get_current_needs()
    need = next((n for n in needs if n.get("user_id") == user_id), None)
    if not need:
        print(f"▶️ No active need for user {user_id}")
        return {"score": 0.0}

    offer = get_offer(offer_id)
    if not offer:
        print(f"▶️ Offer does not exist {offer_id}")
        return {"score": 0.0}

    # 1) Must be same product **name**
    need_name  = need.get("product_name")
    # Offers embed the product under "product": {..., "name": "..."}
    offer_name = offer.get("product", {}).get("name") or offer.get("product_name")
    if not need_name or need_name != offer_name:
        return {"score": 0.0}

    # 2) Price check: only match if offer price <= user's max
    price     = offer.get("product", {}).get("price", 0)
    max_price = need.get("preferences", {}).get("price_max", 0)
    score     = 1.0 if price <= max_price else 0.0

    return {"score": score}