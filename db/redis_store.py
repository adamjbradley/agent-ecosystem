# db/redis_store.py

import os
import redis
import json
from datetime import timedelta

# Read Redis connection info from env (set in docker-compose.yml)
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

r = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=0,
    decode_responses=True
)

def save_object(prefix, obj_id, data, ttl=None):
    key = f"{prefix}:{obj_id}"
    value = json.dumps(data)
    if ttl:
        r.setex(key, timedelta(seconds=ttl), value)
    else:
        r.set(key, value)

def get_object(prefix, obj_id):
    data = r.get(f"{prefix}:{obj_id}")
    return json.loads(data) if data else None

def list_objects(prefix):
    """
    Return all JSON‐decoded objects whose keys start with f"{prefix}:".
    Automatically skips expired or missing entries.
    """
    keys = r.keys(f"{prefix}:*")
    objects = []
    for k in keys:
        raw = r.get(k)
        if raw is None:
            continue  # skip expired/missing
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue  # or log a warning
        objects.append(obj)
    return objects