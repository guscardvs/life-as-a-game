from collections.abc import Awaitable, Callable, Coroutine
from typing import Any, cast, override

from escudeiro.config import Env, get_env
import sqlalchemy as sa
import sqlalchemy.ext.asyncio as sa_async
from blacksheep import Application
from escudeiro.context import AsyncAtomicContext, AtomicAsyncAdapter
from escudeiro.data import data
from escudeiro.lazyfields import lazyfield
from loguru import logger
from rodi import Container

from .config import DatabaseConfig


@data
class DatabaseAdapter(AtomicAsyncAdapter[sa_async.AsyncConnection]):
    """
    Database adapter for SQLAlchemy.
    """

    config: DatabaseConfig
    debug: bool = False
    test: bool = False

    @lazyfield
    def engine(self) -> sa_async.AsyncEngine:
        """Create a SQLAlchemy engine."""
        if self.test:
            return sa_async.create_async_engine("sqlite+aiosqlite:///:memory:")
        return sa_async.create_async_engine(
            self.config.make_uri(is_asyncio=True).encode(),
            pool_size=self.config.pool.size,
            echo=self.debug,
            pool_recycle=self.config.pool.recycle,
            max_overflow=self.config.pool.max_overflow,
        )

    @classmethod
    def for_test(cls) -> "DatabaseAdapter":
        """
        Create a DatabaseAdapter instance for testing.
        """
        config = DatabaseConfig(
            host="localhost",
            port=5432,
            user="postgres",
            password="postgres",
            name="test_db",
        )
        return cls(config=config, test=True)

    @override
    async def new(self) -> sa_async.AsyncConnection:
        """Create a new connection."""
        return await self.engine.connect()

    @override
    async def is_closed(self, client: sa_async.AsyncConnection) -> bool:
        return client.closed

    @override
    async def release(self, client: sa_async.AsyncConnection) -> None:
        return await client.close()

    async def aclose(self) -> None:
        await self.engine.dispose()

    async def _do_with_transaction(
        self,
        client: sa_async.AsyncConnection,
        callback: Callable[[sa_async.AsyncTransaction], Awaitable[Any]],
    ) -> None:
        if not client.in_transaction():
            return
        trx = (
            client.get_transaction()
            if not client.in_nested_transaction()
            else client.get_nested_transaction()
        )
        if trx and trx.is_valid:
            await callback(trx)

    @override
    async def commit(self, client: sa_async.AsyncConnection) -> None:
        await self._do_with_transaction(
            client, sa_async.AsyncTransaction.commit
        )

    @override
    async def rollback(self, client: sa_async.AsyncConnection) -> None:
        await self._do_with_transaction(
            client, sa_async.AsyncTransaction.rollback
        )

    @override
    async def begin(self, client: sa_async.AsyncConnection) -> None:
        if not client.in_transaction():
            _ = await client.begin()
        else:
            _ = await client.begin_nested()

    @override
    async def in_atomic(self, client: sa_async.AsyncConnection) -> bool:
        """
        Check if the connection is in a transaction.
        """
        return client.in_transaction() or client.in_nested_transaction()

    def context(self) -> AsyncAtomicContext[sa_async.AsyncConnection]:
        """
        Create a context manager for the database connection.
        """
        return AsyncAtomicContext(self)

    @lazyfield
    def session(self) -> "SessionAdapter":
        """
        Create a session adapter for the database connection.
        """
        return SessionAdapter(provider=self, debug=self.debug)


@data
class SessionAdapter(AtomicAsyncAdapter[sa_async.AsyncSession]):
    """
    Session adapter for SQLAlchemy.
    """

    provider: DatabaseAdapter
    debug: bool = False

    @override
    async def new(self) -> sa_async.AsyncSession:
        """
        Create a new session.
        """
        return sa_async.AsyncSession(bind=await self.provider.new())

    def _get_bind(
        self, session: sa_async.AsyncSession
    ) -> sa_async.AsyncConnection:
        """
        Get the bind for the session.
        """
        return cast(sa_async.AsyncConnection, session.bind)

    @override
    async def is_closed(self, client: sa_async.AsyncSession) -> bool:
        """
        Check if the session is closed.
        """
        return self._get_bind(client).closed

    @override
    async def release(self, client: sa_async.AsyncSession) -> None:
        """
        Release the session.
        """
        await self._get_bind(client).close()

    async def aclose(self) -> None:
        """
        Close the session.
        """
        await self.provider.aclose()

    async def _do_with_transaction(
        self,
        client: sa_async.AsyncSession,
        callback: Callable[[sa_async.AsyncSessionTransaction], Awaitable[Any]],
    ) -> None:
        """
        Do something with the transaction.
        """
        if not client.in_transaction():
            return
        trx = (
            client.get_transaction()
            if not client.in_nested_transaction()
            else client.get_nested_transaction()
        )
        if trx:
            await callback(trx)

    @override
    async def commit(self, client: sa_async.AsyncSession) -> None:
        """
        Commit the session.
        """
        await self._do_with_transaction(
            client, sa_async.AsyncSessionTransaction.commit
        )

    @override
    async def rollback(self, client: sa_async.AsyncSession) -> None:
        """
        Rollback the session.
        """
        await self._do_with_transaction(
            client, sa_async.AsyncSessionTransaction.rollback
        )

    @override
    async def begin(self, client: sa_async.AsyncSession) -> None:
        """
        Begin the session.
        """
        if not client.in_transaction():
            _ = await client.begin()
        else:
            _ = await client.begin_nested()

    @override
    async def in_atomic(self, client: sa_async.AsyncSession) -> bool:
        """
        Check if the session is in a transaction.
        """
        return client.in_transaction() or client.in_nested_transaction()

    def context(self) -> AsyncAtomicContext[sa_async.AsyncSession]:
        """
        Create a context manager for the session.
        """
        return AsyncAtomicContext(self)


# --- BlackSheep integration ---


def create_database_adapter(config: DatabaseConfig) -> DatabaseAdapter:
    """
    Create and return a DatabaseAdapter instance.
    """
    return DatabaseAdapter(config=config)


SessionContext = AsyncAtomicContext[sa_async.AsyncSession]

ConnectionContext = AsyncAtomicContext[sa_async.AsyncConnection]


def make_database_setup(
    config: DatabaseConfig, debug: bool
) -> Callable[..., Coroutine[Any, Any, None]]:
    async def setup_database(app: Application) -> None:
        """
        Setup the database adapter and attach it to the FastAPI app.
        """
        with logger.contextualize(operation_id="make_database_setup"):
            if get_env() is Env.TEST:
                adapter = DatabaseAdapter.for_test()
            else:
                adapter = DatabaseAdapter(config=config, debug=debug)
            app.services.register(DatabaseAdapter, instance=adapter)
            services = cast(Container, app.services)
            _ = services.add_transient_by_factory(
                adapter.session.context, SessionContext
            )
            _ = services.add_transient_by_factory(
                adapter.context, ConnectionContext
            )
            logger.info("Connecting to database...")
            try:
                async with adapter.context() as connection:
                    _ = await connection.execute(sa.text("SELECT 1"))
            except Exception as e:
                logger.exception("Failed to connect to database: {}", e)
                raise RuntimeError("Failed to connect to database") from e
            logger.info("Connected to database")

    return setup_database


async def teardown_database(app: Application) -> None:
    """
    Teardown the database adapter and close connections.
    """
    with logger.contextualize(operation_id="teardown_database"):
        adapter = app.services.resolve(DatabaseAdapter)
        if not adapter:
            return
        logger.info("Shutting down database connection...")
        await adapter.aclose()
        logger.info("Database connection shut down")
