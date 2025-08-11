from collections.abc import Callable, Coroutine
from typing import Any, cast, override

import valkey.asyncio as valkey
from blacksheep import Application
from escudeiro.config import Env, get_env
from escudeiro.context import AsyncAdapter, AsyncContext
from escudeiro.data import data
from escudeiro.lazyfields import is_initialized, lazyfield
from loguru import logger
from rodi import Container

from app.utils.cache.config import CacheConfig

CacheContext = AsyncContext[valkey.Valkey]


@data
class CacheAdapter(AsyncAdapter[valkey.Valkey]):
    config: CacheConfig

    @lazyfield
    def pool(self) -> valkey.ConnectionPool:
        if get_env() is Env.TEST:
            import fakeredis

            return cast(
                valkey.ConnectionPool,
                fakeredis.FakeAsyncRedis(),
            )
        return valkey.ConnectionPool.from_url(
            self.config.make_uri().encode(),
            decode_responses=True,
        )

    async def aclose(self) -> None:
        if is_initialized(self, "pool"):
            await self.pool.aclose()

    @override
    async def new(self) -> valkey.Valkey:
        if get_env() is Env.TEST:
            return cast(valkey.Valkey, self.pool)
        return valkey.Valkey.from_pool(self.pool)

    @override
    async def release(self, client: valkey.Valkey) -> None:
        return await client.aclose()

    @override
    async def is_closed(self, client: valkey.Valkey) -> bool:
        return bool(client.connection)

    def context(self) -> CacheContext:
        return AsyncContext(self)


def make_cache_setup(
    config: CacheConfig,
) -> Callable[[Application], Coroutine[Any, Any, None]]:
    async def setup_cache(app: Application) -> None:
        with logger.contextualize(operation_id="cache_setup"):
            adapter = CacheAdapter(config)
            app.services.register(CacheAdapter, instance=adapter)
            services = cast(Container, app.services)
            _ = services.add_transient_by_factory(
                adapter.context, CacheContext
            )
            logger.info("Connecting to cache...")
            try:
                async with adapter.context() as client:
                    await client.ping()
            except valkey.ConnectionError as e:
                logger.error(f"Failed to connect to cache: {e}")
                raise
            logger.info("Cache connected successfully.")

    return setup_cache
