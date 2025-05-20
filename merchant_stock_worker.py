# merchant_stock_worker.py

import os, json, time, redis
from provider_manager import list_providers
from agents.opportunity_agent import stock_product, MERCHANT_CATEGORIES
from agents.supplier_agent import get_current_products

# Redis connection
r = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    db=0,
    decode_responses=True
)

def run_merchant_stock_worker():
    # Initial catch-up: stock every existing product
    print("▶️ Merchant Stock Worker initial catch-up: stocking existing products…")
    for product in get_current_products():
        prod_id = product.get("product_id")
        category = product.get("attributes", {}).get("category")
        if not prod_id:
            continue
        for merchant in list_providers():
            allowed = MERCHANT_CATEGORIES.get(merchant)
            # Specialized merchants only stock matching categories
            if allowed:
                if category in allowed:
                    stock_product(merchant, prod_id)
                    print(f"   📦 [Init] Stocked {prod_id} into {merchant} (specialized)")
            else:
                # Generic merchant: stock everything
                stock_product(merchant, prod_id)
                print(f"   📦 [Init] Stocked {prod_id} into {merchant} (generic)")

    # Now listen for new product events
    pubsub = r.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe("products_stream")
    print("▶️ Merchant Stock Worker listening for new products…")

    for msg in pubsub.listen():
        if msg.get("type") != "message":
            continue
        try:
            product = json.loads(msg["data"])
        except json.JSONDecodeError:
            continue

        prod_id   = product.get("product_id")
        category  = product.get("attributes", {}).get("category")

        if not prod_id:
            continue

        for merchant in list_providers():
            allowed = MERCHANT_CATEGORIES.get(merchant)
            # If merchant is specialized, only stock matching category
            if allowed:
                if category in allowed:
                    stock_product(merchant, prod_id)
                    print(f"   📦 Stocked {prod_id} into {merchant} (specialized)")
            else:
                # Generic merchant: stock everything
                stock_product(merchant, prod_id)
                print(f"   📦 Stocked {prod_id} into {merchant} (generic)")

        time.sleep(0.01)

if __name__ == "__main__":
    run_merchant_stock_worker()