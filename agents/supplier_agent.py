import os
import redis
import json
from datetime import datetime

# Redis connection
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)

# Redis set key for tracking registered suppliers
SUPPLIERS_SET = "suppliers"

# Stream name for new products
PRODUCTS_STREAM = "products_stream"


def register_supplier(supplier_id):
    """Register a new supplier ID into the system."""
    r.sadd(SUPPLIERS_SET, supplier_id)


def list_suppliers():
    """List all registered suppliers."""
    return list(r.smembers(SUPPLIERS_SET))


def generate_product(supplier_id, attrs):
    """
    Create a new product with attributes and publish to Redis.
    attrs should be a dict with keys like 'name', 'category', 'price', etc.
    """
    timestamp = int(datetime.utcnow().timestamp())
    product_id = f"product_{supplier_id}_{timestamp}"
    product = {
        "product_id": product_id,
        "supplier_id": supplier_id,
        "attributes": attrs,
        "timestamp": datetime.utcnow().isoformat()
    }
    # Persist product indefinitely
    key = f"product:{product_id}"
    r.set(key, json.dumps(product))
    # Publish an event on the products stream
    r.publish(PRODUCTS_STREAM, json.dumps(product))
    # ─── Metrics ─────────────────────────────────────────────────────────────
    # count how many products have been created
    r.incr("metrics:products_created")
    # count product publications
    r.incr("metrics:products_streamed")
    return product


def get_current_products():
    """Retrieve all stored products."""
    products = []
    for key in r.keys("product:*"):
        data = r.get(key)
        if data:
            products.append(json.loads(data))
    return products