import redis, json, os
from analytics.metrics import compute_trust
from datetime import datetime
from agents.needs_agent import get_need
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

def match_score(need, offer, user_profile=None):
    base = 0.5
    if 'eco-friendly' in offer['product']['tags']:
        base += 0.2
    if user_profile:
        base += (user_profile.get('price_sensitivity', 0.5) - 0.5) * 0.1
    # apply trust boost
    trust = compute_trust([5,4,5])  # sample feedback
    score = round(base + trust*0.01, 3)
    return score

def process_match(user_id, offer_id):
    need = get_need(user_id)           # pulls preferences and tags
    if not need:
        # No active need found; return zero score so no match
        return {"score": 0.0}
    
    offer = get_offer(offer_id)        # pulls product with tags
    
    need_tags  = set(need.get("preferences", {}).get("tags", []))
    offer_tags = set(offer.get("product", {}).get("tags", []))
    if need_tags and not (need_tags & offer_tags):
        # No common tags → zero score, skip negotiation
        return {"score": 0.0}

    # Compute a base match score
    score = match_score(need, offer)
    return {"score": score}