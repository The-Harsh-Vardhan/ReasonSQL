"""
Query result caching — ReasonSQL 2.0

Two-tier cache:
  1. Upstash Redis (HTTP REST) — persistent, survives Render restarts
  2. In-memory dict fallback — if UPSTASH_REDIS_REST_URL is not set

Cache key: SHA-256(query.lower().strip() + ":" + database_id)
TTL: 300 seconds (5 minutes) by default

Why Upstash over redis-py:
    - No Redis server needed on Render free tier
    - HTTP REST API works anywhere (just needs httpx)
    - Free tier: 10k requests/day, 256MB storage
    - Latency: ~10-30ms from Render's US-East region
"""

import hashlib
import json
import logging
import os
import time
from typing import Any, Optional

logger = logging.getLogger("reasonsql.cache")

# ---------------------------------------------------------------------------
# In-memory fallback (dict + expiry timestamp)
# ---------------------------------------------------------------------------
_memory_cache: dict[str, tuple[Any, float]] = {}   # key → (value, expires_at)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
UPSTASH_URL = os.getenv("UPSTASH_REDIS_REST_URL", "")
UPSTASH_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN", "")
CACHE_ENABLED = os.getenv("CACHE_ENABLED", "true").lower() == "true"
DEFAULT_TTL = int(os.getenv("CACHE_TTL_SECONDS", "300"))

if UPSTASH_URL:
    logger.info("Cache: Upstash Redis enabled (%s…)", UPSTASH_URL[:40])
else:
    logger.info("Cache: In-memory fallback (set UPSTASH_REDIS_REST_URL for persistent cache)")


# =============================================================================
# HELPERS
# =============================================================================

def _make_key(query: str, database_id: str) -> str:
    """Stable SHA-256 cache key from query + database_id."""
    raw = f"{query.lower().strip()}:{database_id}"
    return "rsql:" + hashlib.sha256(raw.encode()).hexdigest()[:32]


async def _upstash_get(key: str) -> Optional[str]:
    """GET from Upstash Redis REST API."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get(
                f"{UPSTASH_URL}/get/{key}",
                headers={"Authorization": f"Bearer {UPSTASH_TOKEN}"},
            )
            data = r.json()
            return data.get("result")  # None if key doesn't exist
    except Exception as exc:
        logger.debug("Upstash GET failed (non-critical): %s", exc)
        return None


async def _upstash_set(key: str, value: str, ttl: int) -> None:
    """SET with EX in Upstash Redis REST API."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=2.0) as client:
            await client.get(
                f"{UPSTASH_URL}/set/{key}/{value}/ex/{ttl}",
                headers={"Authorization": f"Bearer {UPSTASH_TOKEN}"},
            )
    except Exception as exc:
        logger.debug("Upstash SET failed (non-critical): %s", exc)


# =============================================================================
# PUBLIC API
# =============================================================================

async def get_cached(query: str, database_id: str) -> Optional[dict]:
    """
    Return cached query result if available, else None.

    Checks Upstash first (if configured), falls back to in-memory.
    """
    if not CACHE_ENABLED:
        return None

    key = _make_key(query, database_id)

    # Try Upstash
    if UPSTASH_URL:
        raw = await _upstash_get(key)
        if raw:
            try:
                result = json.loads(raw)
                logger.info("Cache HIT (Upstash): %s…", query[:60])
                return result
            except Exception:
                pass

    # Try in-memory fallback
    entry = _memory_cache.get(key)
    if entry:
        value, expires_at = entry
        if time.time() < expires_at:
            logger.info("Cache HIT (memory): %s…", query[:60])
            return value
        else:
            del _memory_cache[key]

    logger.info("Cache MISS: %s…", query[:60])
    return None


async def set_cached(query: str, database_id: str, result: dict, ttl: int = DEFAULT_TTL) -> None:
    """
    Store a query result in the cache.

    Writes to Upstash (if configured) and always writes to in-memory.
    """
    if not CACHE_ENABLED:
        return

    key = _make_key(query, database_id)
    serialized = json.dumps(result, default=str)

    # Write to Upstash
    if UPSTASH_URL:
        # Upstash URL-encodes the value automatically when using /set/key/value/ex/ttl
        # For complex JSON, use POST to /pipeline instead
        try:
            import httpx
            async with httpx.AsyncClient(timeout=2.0) as client:
                await client.post(
                    f"{UPSTASH_URL}/pipeline",
                    headers={
                        "Authorization": f"Bearer {UPSTASH_TOKEN}",
                        "Content-Type": "application/json",
                    },
                    content=json.dumps([["SET", key, serialized, "EX", ttl]]),
                )
        except Exception as exc:
            logger.debug("Upstash pipeline SET failed (non-critical): %s", exc)

    # Always write to in-memory
    _memory_cache[key] = (result, time.time() + ttl)
    logger.info("Cache SET (TTL=%ds): %s…", ttl, query[:60])


def get_cache_stats() -> dict:
    """Return current in-memory cache stats."""
    now = time.time()
    live = sum(1 for _, (_, exp) in _memory_cache.items() if exp > now)
    return {
        "backend": "upstash" if UPSTASH_URL else "memory",
        "enabled": CACHE_ENABLED,
        "live_entries": live,
        "total_entries": len(_memory_cache),
    }
