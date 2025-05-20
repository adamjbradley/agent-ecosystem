import os
import redis
import json
from datetime import datetime
from agents.needs_agent import process_user_preferences

# Redis setup (same env vars you already use)
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)

USERS_STREAM = "users_stream"
USERS_SET    = "users:all"

def create_user(user_id, attrs=None):
    """
    Register a new user with optional attributes, publish to Redis,
    and track in a Redis set.
    """
    user = {
        "user_id":  user_id,
        "attrs":    attrs or {},
        "timestamp": datetime.utcnow().isoformat()
    }
    r.publish(USERS_STREAM, json.dumps(user))
    r.sadd(USERS_SET, user_id)
    return user

def list_users():
    """
    Return a sorted list of all user IDs that have been created.
    """
    return sorted(r.smembers(USERS_SET))