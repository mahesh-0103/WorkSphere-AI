import redis
import json
import time
from typing import Optional
from ai.runtime_settings import settings

# Caching Observability Counters
CACHE_METRICS = {
    "hits": 0,
    "misses": 0
}

class WorkSphereCache:
    def __init__(self):
        self.redis_client = None
        self.in_memory_db = {}  # key -> (value_str, expire_at)
        
        try:
            self.redis_client = redis.from_url(
                settings.redis_url,
                socket_timeout=2.0,
                decode_responses=True
            )
            # Verify connection works
            self.redis_client.ping()
        except Exception:
            # Fallback to in-memory mode if Redis server is down/not installed
            self.redis_client = None

    async def get(self, key: str) -> Optional[dict]:
        """
        Retrieves JSON value from cache (Redis or in-memory fallback).
        """
        global CACHE_METRICS
        
        if self.redis_client:
            try:
                val = self.redis_client.get(key)
                if val:
                    CACHE_METRICS["hits"] += 1
                    return json.loads(val)
            except Exception:
                pass

        # Fallback to local memory dictionary
        if key in self.in_memory_db:
            val_str, expire_at = self.in_memory_db[key]
            if time.time() < expire_at:
                CACHE_METRICS["hits"] += 1
                return json.loads(val_str)
            else:
                # Remove expired cache entry
                del self.in_memory_db[key]

        CACHE_METRICS["misses"] += 1
        return None

    async def set(self, key: str, value: dict, ttl: int):
        """
        Saves key-value JSON into the cache with a Time-To-Live.
        """
        if self.redis_client:
            try:
                self.redis_client.set(key, json.dumps(value), ex=ttl)
                return
            except Exception:
                pass

        # Fallback to local memory dictionary
        self.in_memory_db[key] = (json.dumps(value), time.time() + ttl)

    async def delete(self, key: str):
        """
        Invalidates a cache key.
        """
        if self.redis_client:
            try:
                self.redis_client.delete(key)
                return
            except Exception:
                pass
        
        if key in self.in_memory_db:
            del self.in_memory_db[key]

# Shared Cache Singleton Instance
cache_client = WorkSphereCache()
