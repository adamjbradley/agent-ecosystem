import os
import redis
import json
import random
from datetime import datetime

from agents.supplier_agent import get_current_products
from provider_manager import list_providers

from typing import Optional

# Redis connection setup (reads from environment)
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)

# Default Time-To-Live (TTL) for active offers, in seconds
DEFAULT_OFFER_TTL = 10

# Mapping of merchant IDs to the categories they specialize in
MERCHANT_CATEGORIES = {
    "merchant_travel":      ["Travel", "Events"],
    "merchant_electronics": ["Electronics", "Gadgets"],
    "merchant_financial":   ["Financial Services"],
    "merchant_clothing":    ["Clothing"],
    "merchant_home":        ["Home"],
    "merchant_books":       ["Books"],
    "merchant_food":        ["Food"],
    "merchant_health":      ["Health"],
    "merchant_automotive":  ["Automotive"],
    # merchants not listed here can offer any category
}

# Redis set key prefix for each merchant’s stock of supplier products
MERCHANT_STOCK_PREFIX = "merchant_stock:"


def generate_offer(agent_id:Optional[str], strategy: str="", ttl: int = DEFAULT_OFFER_TTL) -> Optional[dict]:
    """
    Generate a new active offer for a merchant by randomly choosing
    from that merchant’s stocked supplier products, apply specialization
    filters, persist with TTL, and publish to 'offers_stream'.
    """

    # If no products have been created yet, skip generating offers
    if not get_current_products():
        return None

    if agent_id is None:
        # grab all registered merchants
        all_merchants = list_providers()
        # filter to those who actually have stock
        stocked = [m for m in all_merchants if list_stocked_products(m)]
        if not stocked:
            return None  # no one has stock right now
        agent_id = random.choice(stocked)

    # 1) Load this merchant’s stocked product IDs
    stock_key   = f"{MERCHANT_STOCK_PREFIX}{agent_id}"
    stocked_ids = r.smembers(stock_key)
    if not stocked_ids:
        return None  # merchant has no inventory

    # 2) Fetch each stocked product record from Redis
    products = []
    for pid in stocked_ids:
        raw = r.get(f"product:{pid}")
        if raw:
            products.append(json.loads(raw))
    if not products:
        return None  # no valid product data

    # 3) Apply merchant specialization filter if defined
    allowed = MERCHANT_CATEGORIES.get(agent_id)
    if allowed:
        products = [
            p for p in products
            if p.get("attributes", {}).get("category") in allowed
        ]
        if not products:
            return None  # none match their category specialism

    # 4) Choose one at random
    product = random.choice(products)

    # 5) Build a “flattened” offer payload
    attrs = product.get("attributes", {})
    offer_id = f"offer_{agent_id}_{int(datetime.utcnow().timestamp())}"
    offer = {
        "offer_id":    offer_id,
        "provided_by": agent_id,
        "product_id":  product["product_id"],
        "product_name": product.get("attributes", {}).get("name"),
        "product":     product.get("attributes", {}),
        "supplier_id": product.get("supplier_id"),
        "category":    attrs.get("category"),
        "tags":        attrs.get("tags", []),
        "price":       attrs.get("price"),
        "brand":       attrs.get("brand"),
        "strategy":    strategy,
        "timestamp":   datetime.utcnow().isoformat()
    }

    # 6) Persist with TTL and publish
    key = f"offer:{offer_id}"
    r.setex(key, ttl, json.dumps(offer))
    r.publish("offers_stream", json.dumps(offer))
    return offer


def stage_offer(agent_id: str, strategy: str, ttl: int = DEFAULT_OFFER_TTL) -> dict | None:
    """
    Stage and immediately activate a real offer for UI/approval.
    Internally calls generate_offer so the result is fully formed.
    Also persists a pending copy for audit.
    """
    offer = generate_offer(agent_id, strategy, ttl)
    if not offer:
        return None

    r.set(f"pending_offer:{offer['offer_id']}", json.dumps(offer))
    r.publish("pending_offers_stream", json.dumps(offer))
    return offer


def get_offer(offer_id: str) -> dict | None:
    data = r.get(f"offer:{offer_id}")
    return json.loads(data) if data else None


def get_current_offers() -> list[dict]:
    offers = []
    for key in r.keys("offer:*"):
        raw = r.get(key)
        if raw:
            offers.append(json.loads(raw))
    return offers


def remove_offer(offer_id: str) -> bool:
    key = f"offer:{offer_id}"
    if r.exists(key):
        r.delete(key)
        r.publish("offers_removed_stream", json.dumps({"offer_id": offer_id}))
        return True
    return False


def adjust_offer_price(offer_id: str, new_price: float, ttl: int = DEFAULT_OFFER_TTL) -> dict | None:
    key = f"offer:{offer_id}"
    raw = r.get(key)
    if not raw:
        return None
    offer = json.loads(raw)
    offer["price"]     = new_price
    offer["timestamp"] = datetime.utcnow().isoformat()
    r.setex(key, ttl, json.dumps(offer))
    r.publish("offers_stream", json.dumps(offer))
    return offer


def negotiate_price(need: dict, offer: dict) -> dict:
    price     = offer.get("price", 0)
    max_price = need.get("preferences", {}).get("price_max", 0)
    strategy  = offer.get("strategy", "neutral")

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
        "offered_price":  price,
        "max_user_price": max_price,
        "status":         status,
        "strategy":       strategy,
        "agent_id":       offer.get("provided_by")
    }


def stock_product(merchant_id: str, product_id: str) -> bool:
    return r.sadd(f"{MERCHANT_STOCK_PREFIX}{merchant_id}", product_id) == 1


def list_stocked_products(merchant_id: str) -> list[str]:
    return list(r.smembers(f"{MERCHANT_STOCK_PREFIX}{merchant_id}"))


def list_merchant_products(merchant_id: str) -> list[str]:
    offers = get_current_offers()
    products = {
        o.get("product_id")
        for o in offers
        if o.get("provided_by") == merchant_id
    }
    return list(products)


def list_all_merchants_products() -> dict[str, list[str]]:
    offers = get_current_offers()
    merchant_map: dict[str, set[str]] = {}
    for o in offers:
        m   = o.get("provided_by")
        pid = o.get("product_id")
        if m and pid:
            merchant_map.setdefault(m, set()).add(pid)
    return {m: list(pids) for m, pids in merchant_map.items()}