import os
import redis
import json
from datetime import datetime

# Provider Manager: dynamic registration of offer providers (merchants)

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)

# Redis key for storing provider IDs
PROVIDERS_KEY = "providers:set"

# Redis channel to notify provider changes
PROVIDERS_STREAM = "providers_stream"


def register_provider(provider_id, metadata=None):
    """
    Dynamically register a new offer provider with optional metadata.
    Stores provider_id in a Redis set and publishes an event.
    """
    added = r.sadd(PROVIDERS_KEY, provider_id)
    event = {"provider_id": provider_id, "action": "registered", "timestamp": datetime.utcnow().isoformat()}
    if metadata:
        event["metadata"] = metadata
    r.publish(PROVIDERS_STREAM, json.dumps(event))
    return bool(added)


def unregister_provider(provider_id):
    """
    Remove a provider and publish removal event.
    """
    removed = r.srem(PROVIDERS_KEY, provider_id)
    event = {"provider_id": provider_id, "action": "unregistered", "timestamp": datetime.utcnow().isoformat()}
    r.publish(PROVIDERS_STREAM, json.dumps(event))
    return bool(removed)


def list_providers():
    """
    List all currently registered providers.
    """
    return list(r.smembers(PROVIDERS_KEY))


def set_provider_metadata(provider_id, metadata):
    """
    Store metadata under key 'provider:<id>:metadata' and publish update.
    """
    key = f"provider:{provider_id}:metadata"
    r.set(key, json.dumps(metadata))
    event = {"provider_id": provider_id, "action": "metadata_updated", "metadata": metadata, "timestamp": datetime.utcnow().isoformat()}
    r.publish(PROVIDERS_STREAM, json.dumps(event))
    return True


def get_provider_metadata(provider_id):
    """
    Retrieve stored metadata for a provider.
    """
    data = r.get(f"provider:{provider_id}:metadata")
    return json.loads(data) if data else None