import os
import redis
import json
from datetime import datetime, timedelta

# Read Redis connection info from env (set in docker-compose.yml)
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

PENDING_OFFERS_STREAM = "pending_offers_stream"

r = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=0,
    decode_responses=True
)

# Default Time-To-Live (TTL) for offers, in seconds
DEFAULT_OFFER_TTL = 10


def generate_offer(agent_id, strategy, ttl=DEFAULT_OFFER_TTL):
    """
    Generate a new opportunity offer with TTL and publish to Redis
    """
    offer = {
        "offer_id": f"offer_{agent_id}_{int(datetime.utcnow().timestamp())}",
        "provided_by": agent_id,
        "strategy": strategy,
        "product": {
            "tags": ["eco-friendly", "fast-delivery"],
            "price": 480,
            "brand": "BrandX"
        },
        "timestamp": datetime.utcnow().isoformat()
    }
    key = f"offer:{offer['offer_id']}"
    # Store with TTL so it auto-expires
    r.setex(key, ttl, json.dumps(offer))
    # Publish new-offer event
    r.publish("offers_stream", json.dumps(offer))
    return offer

def stage_offer(agent_id, strategy):
    """
    Create a new offer and publish it to the pending stream.
    """
    offer = {
        "offer_id": f"offer_{agent_id}_{int(datetime.utcnow().timestamp())}",
        "provided_by": agent_id,
        "strategy": strategy,
        "product": {
            "tags": ["eco-friendly", "fast-delivery"],
            "price": 480,
            "brand": "BrandX"
        },
        "timestamp": datetime.utcnow().isoformat()
    }
    # Store it (optional TTL) so it can be audited
    r.set(f"pending_offer:{offer['offer_id']}", json.dumps(offer))
    # Publish to pending_offers_stream
    r.publish(PENDING_OFFERS_STREAM, json.dumps(offer))
    return offer

def get_offer(offer_id):
    """
    Retrieve an offer by ID from Redis
    """
    data = r.get(f"offer:{offer_id}")
    return json.loads(data) if data else None


def get_current_offers():
    """
    List all non-expired offers stored in Redis
    """
    offers = []
    for key in r.keys("offer:*"):
        data = r.get(key)
        if data:
            offers.append(json.loads(data))
    return offers


def remove_offer(offer_id):
    """
    Remove an existing offer before its TTL expires and notify
    """
    key = f"offer:{offer_id}"
    if r.exists(key):
        r.delete(key)
        # Notify removal event
        r.publish("offers_removed_stream", json.dumps({"offer_id": offer_id}))
        return True
    return False


def adjust_offer_price(offer_id, new_price, ttl=DEFAULT_OFFER_TTL):
    """
    Adjust an existing offer's price as a counter-offer and republish
    """
    key = f"offer:{offer_id}"
    raw = r.get(key)
    if not raw:
        return None
    offer = json.loads(raw)
    offer["product"]["price"] = new_price
    offer["timestamp"] = datetime.utcnow().isoformat()
    # Store the updated offer with fresh TTL
    r.setex(key, ttl, json.dumps(offer))
    # Republish the adjusted offer
    r.publish("offers_stream", json.dumps(offer))
    return offer


def negotiate_price(need, offer):
    """
    Negotiate price based on the agent's strategy and user need
    Returns negotiation status without side-effects.
    """
    price = offer["product"]["price"]
    max_price = need.get("price_max") or need.get("preferences", {}).get("price_max", 0)
    strategy = offer.get("strategy", "neutral")
    agent_id = offer.get("provided_by")

    # Strategy-driven negotiation
    if strategy == "match_score":
        if price <= max_price:
            status = "accepted"
        elif price - max_price <= 25:
            status = "counter-offer"
        else:
            status = "rejected"
    elif strategy == "budget_focus":
        if price <= max_price:
            status = "accepted"
        elif price - max_price <= 15:
            status = "counter-offer"
        else:
            status = "rejected"
    elif strategy == "high_margin":
        status = "accepted" if price <= max_price else "rejected"
    else:
        status = "accepted" if price <= max_price else "rejected"

    return {
        "offered_price": price,
        "max_user_price": max_price,
        "status": status,
        "strategy": strategy,
        "agent_id": agent_id
    }

