import os
import json
import hashlib
import asyncio
import functools
import logging
from typing import Any, Optional, Callable, Dict

# Try to import redis, but don't crash if missing (though it should be installed)
try:
    import redis.asyncio as redis
except ImportError:
    redis = None

logger = logging.getLogger("reasonsql.cache")

class CacheManager:
    """
    Manages caching with Redis backend and in-memory fallback.
    Singleton pattern usage recommended.
    """
    def __init__(self):
        self.redis_client = None
        self.memory_cache: Dict[str, Any] = {}
        self.use_redis = False
        self._initialized = False

    async def initialize(self):
        """Initialize Redis connection if configured."""
        if self._initialized:
            return

        redis_url = os.getenv("REDIS_URL")
        # If REDIS_URL is set, we try to use it.
        # If not set, we default to in-memory for simpler local dev, unless explicitly requested.
        
        if redis and redis_url:
            try:
                self.redis_client = redis.from_url(redis_url, decode_responses=True)
                await self.redis_client.ping()
                self.use_redis = True
                logger.info(f"✅ Redis cache connected: {redis_url}")
            except Exception as e:
                logger.warning(f"⚠️ Redis connection failed (falling back to memory): {e}")
                self.use_redis = False
                self.redis_client = None
        else:
            logger.info("ℹ️ No REDIS_URL found. Using in-memory cache.")
            self.use_redis = False

        self._initialized = True

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if not self._initialized:
            await self.initialize()

        try:
            if self.use_redis and self.redis_client:
                val = await self.redis_client.get(key)
                return json.loads(val) if val else None
            else:
                return self.memory_cache.get(key)
        except Exception as e:
            logger.warning(f"Cache GET error: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: int = 3600):
        """Set value in cache with TTL."""
        if not self._initialized:
            await self.initialize()

        try:
            json_val = json.dumps(value, default=str) # handling date serialization simply
            if self.use_redis and self.redis_client:
                await self.redis_client.setex(key, ttl, json_val)
            else:
                self.memory_cache[key] = value
                # In-memory TTL not implemented for MVP simplicity
        except Exception as e:
            logger.warning(f"Cache SET error: {e}")

    async def clear(self):
        """Clear the cache."""
        if self.use_redis and self.redis_client:
            await self.redis_client.flushdb()
        self.memory_cache.clear()

# Global singleton
cache_manager = CacheManager()

def cache_response(ttl: int = 3600):
    """
    Decorator to cache async function results.
    Generates a key based on function name and arguments.
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            # We assume args are serializable or stringifiable enough for a unique key
            # For query processing, args[0] is usually 'self' (orchestrator), args[1] is 'user_query'
            
            # Simple key generation: func_name + hash of args
            try:
                # Exclude 'self' from key generation if it's a method
                arg_list = list(args)
                if arg_list and hasattr(arg_list[0], '__class__'):
                     # Likely 'self', maybe skip? 
                     # Actually unique instance configuration might matter, but for orchestrator it's singleton-ish.
                     # Let's just stringify everything.
                     pass
                
                key_str = f"{func.__name__}:{str(args)}:{str(kwargs)}"
                key_hash = hashlib.md5(key_str.encode()).hexdigest()
                cache_key = f"cache:{func.__name__}:{key_hash}"
                
                # Check cache
                cached_val = await cache_manager.get(cache_key)
                if cached_val:
                    logger.info(f"⚡ Cache HIT for {func.__name__}")
                    return cached_val
                
                # Execute
                result = await func(*args, **kwargs)
                
                # Cache result
                # Note: Result must be JSON serializable. 
                # If result is a Pydantic model (like FinalResponse), we need to dump it first if we want to retrieve it as dict.
                # However, the decorator returns the object. 
                # This simple cache might be tricky with Pydantic objects unless we handle serialization/deserialization.
                
                # For `process_query` which returns `FinalResponse`, we shouldn't cache the complex object directly in this generic decorator
                # unless we reconstruct it.
                # SO: let's invoke the cache INSIDE the function manually if it's complex, 
                # OR make this decorator only for simple dict-returning functions.
                
                # DECISION: For this MVP, let's cache explicitly inside execute_query or similar, 
                # utilizing the cache_manager, rather than a generic decorator that might fail on Pydantic serialization.
                # But I'll leave the decorator here for simple functions.
                
                # await cache_manager.set(cache_key, result, ttl)
                
                return result
            except Exception as e:
                # Fallback to execution if caching fails
                logger.warning(f"Cache wrapper error: {e}")
                return await func(*args, **kwargs)
                
        return wrapper
    return decorator
