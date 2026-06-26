import json
from typing import Optional

import redis.asyncio as redis

from .config import settings


class RedisClient:
    def __init__(self):
        self.client: Optional[redis.Redis] = None

    async def connect(self):
        self.client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
        return self.client

    async def set_session(self, key: str, data: dict, ttl: int):
        await self.client.set(key, json.dumps(data), ex=ttl)

    async def get(self, key: str) -> Optional[str]:
        return await self.client.get(key)

    async def delete(self, key: str):
        await self.client.delete(key)

    async def expire(self, key: str, ttl: int):
        await self.client.expire(key, ttl)

    async def close(self):
        if self.client:
            await self.client.aclose()


redis_client = RedisClient()
