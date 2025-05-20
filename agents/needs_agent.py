import os
import redis
import json
from datetime import datetime, timedelta

# Streams and sets for tracking need status
SATISFIED_SET      = "needs:satisfied"
UNSATISFIED_SET    = "needs:unsatisfied"
UNSATISFIED_STREAM = "needs_unsatisfied_stream"
# Redis set for tracking registered users
USERS_SET          = "users:all"

# Read Redis connection info from env (set in docker-compose.yml)
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

r = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=0,
    decode_responses=True
)

# Default TTL for needs (seconds)
DEFAULT_NEED_TTL = 5

def process_user_preferences(user_id, prefs, ttl=DEFAULT_NEED_TTL):
    """
    Store a user need with TTL and publish to Redis
    """
    # Ensure the user actually exists
    if not r.sismember(USERS_SET, user_id):
        raise ValueError(f"Cannot create need: user '{user_id}' is not registered.")
    
    need = {
        "need_id": f"need_{user_id}_{int(datetime.utcnow().timestamp())}",
        "user_id": user_id,
        "preferences": prefs,
        "timestamp": datetime.utcnow().isoformat()
    }
    key = f"need:{need['need_id']}"
    r.setex(key, ttl, json.dumps(need))
    r.publish("needs_stream", json.dumps(need))
    return need


def get_need(need_id):
    """
    Retrieve a specific need by its ID
    """
    data = r.get(f"need:{need_id}")
    return json.loads(data) if data else None


def get_current_needs():
    """
    List all active (non-expired) needs
    """
    needs = []
    for key in r.keys("need:*"):
        data = r.get(key)
        if data:
            needs.append(json.loads(data))
    return needs


def remove_need(need_id):
    """
    Remove a need before TTL expires and notify
    """
    key = f"need:{need_id}"
    if r.exists(key):
        r.delete(key)
        r.publish("needs_removed_stream", json.dumps({"need_id": need_id}))
        # Mark this need as satisfied
        r.sadd(SATISFIED_SET, need_id)
        return True
    return False


# Detect and publish unsatisfied needs
def detect_unsatisfied(threshold_secs):
    """
    Scan active needs older than threshold_secs that have not been satisfied,
    mark them, and publish an unsatisfied event.
    """
    now_ts = datetime.utcnow().timestamp()
    for need in get_current_needs():
        nid = need["need_id"]
        # Skip if already satisfied or already flagged unsatisfied
        if r.sismember(SATISFIED_SET, nid) or r.sismember(UNSATISFIED_SET, nid):
            continue
        created_ts = datetime.fromisoformat(need["timestamp"]).timestamp()
        if now_ts - created_ts > threshold_secs:
            # Mark and publish unsatisfied
            r.sadd(UNSATISFIED_SET, nid)
            r.publish(UNSATISFIED_STREAM, json.dumps({
                "need_id": nid,
                "age_s": round(now_ts - created_ts, 1)
            }))
