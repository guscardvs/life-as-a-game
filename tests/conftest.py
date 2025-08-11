from contextlib import asynccontextmanager
from typing import cast

import pytest
from blacksheep import Application
from blacksheep.testing import TestClient
from rodi import Container

from app.main import app
from app.utils.database import AbstractEntity, DatabaseAdapter


@asynccontextmanager
async def setup_database_state(services: Container):
    adapter = services.resolve(DatabaseAdapter)
    context = adapter.context()
    async with context as conn:
        object.__setattr__(adapter, "context", lambda: context)
        await conn.run_sync(AbstractEntity.metadata.create_all)
        yield
        await conn.run_sync(AbstractEntity.metadata.drop_all)


@pytest.fixture(scope="session")
async def api():
    await app.start()
    yield app
    await app.stop()


@pytest.fixture
async def test_client(api: Application):
    services = cast(Container, api.services)
    async with setup_database_state(services):
        yield TestClient(api)
