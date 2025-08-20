from contextlib import asynccontextmanager
from datetime import date
from typing import cast

import msgspec
import pytest
from blacksheep import Application, Content
from blacksheep.testing import TestClient
from escudeiro.url import Query
from rodi import Container

from app.main import app
from app.users.schemas import CreateUserSchema, UserOutSchema
from app.utils.database import AbstractEntity, DatabaseAdapter
from app.utils.msgspec import registry


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


@pytest.fixture
async def user(
    test_client: TestClient,
) -> tuple[CreateUserSchema, UserOutSchema]:
    payload = CreateUserSchema(
        email="testuser@example.com",
        password="Passw0rd!",
        full_name="Test User",
        birth_date=date(1990, 1, 1),
    )
    response = await test_client.post(
        "/users",
        content=Content(b"application/json", msgspec.json.encode(payload)),
    )
    return payload, registry.require_decoder(UserOutSchema)(
        await response.read()
    )




@pytest.fixture
async def auth_headers(
    test_client: TestClient, user: tuple[CreateUserSchema, UserOutSchema]
) -> dict[str, str]:
    payload, _ = user
    query = Query("").add(username=payload.email, password=payload.password)
    response = await test_client.post(
        "/auth/token",
        content=Content(
            b"application/x-www-form-urlencoded", query.encode().encode()
        ),
    )
    data = await response.json()
    return {"Authorization": f"Bearer {data['access_token']}"}
