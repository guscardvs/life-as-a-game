import asyncio
from datetime import date
from unittest.mock import patch

import msgspec
import pytest
import sqlalchemy as sa
from blacksheep import Content
from blacksheep.testing import TestClient
from escudeiro.url import Query

from app.authentication.handler import REFRESH_URL, TOKEN_URL
from app.authentication.schemas import (
    RefreshTokenSchema,
    SessionResponse,
)
from app.users import schemas
from app.users.entities import UserEntity
from app.users.repository import UserRepository
from app.utils.cache import CacheContext, asserts_async
from app.utils.database import SessionContext, Where
from app.utils.msgspec import registry
from tests.mocks import resolve

type UserPair = tuple[schemas.CreateUserSchema, schemas.UserOutSchema]


class TestAuthenticate:
    async def test_authenticate_success(
        self, test_client: TestClient, user: UserPair
    ):
        create, _ = user
        query = Query("").add(username=create.email, password=create.password)
        response = await test_client.post(
            f"/auth{TOKEN_URL}",
            content=Content(
                b"application/x-www-form-urlencoded",
                query.encode().encode(),
            ),
        )
        assert response.status == 200
        token = registry.require_decoder(SessionResponse)(
            await response.read()
        )
        assert token.access_token
        assert token.token_type == "Bearer"

        context = resolve(test_client, SessionContext)
        async with context:
            user_repository = UserRepository(context)
            user_out = await user_repository.get(Where("email", create.email))
            assert user_out.last_login is not None
            assert user_out.last_login.date() == date.today()

    async def test_authenticate_invalid_credentials(
        self, test_client: TestClient, user: UserPair
    ):
        create, _ = user
        query = Query("").add(username=create.email, password="WrongPassword")
        response = await test_client.post(
            f"/auth{TOKEN_URL}",
            content=Content(
                b"application/x-www-form-urlencoded",
                query.encode().encode(),
            ),
        )
        assert response.status == 401
        assert await response.json() == {
            "message": "You are not authenticated",
            "status_code": 401,
            "fields": [],
        }

    async def test_authenticate_non_existent_user(
        self, test_client: TestClient
    ):
        query = Query("").add(
            username="nonexistent@example.com", password="WrongPassword"
        )
        response = await test_client.post(
            f"/auth{TOKEN_URL}",
            content=Content(
                b"application/x-www-form-urlencoded",
                query.encode().encode(),
            ),
        )
        assert response.status == 401
        assert await response.json() == {
            "message": "You are not authenticated",
            "status_code": 401,
            "fields": [],
        }

    async def test_authenticate_session_failure(
        self, test_client: TestClient, user: UserPair
    ):
        future = asyncio.Future()
        future.set_result(0)  # Simulate failure in cache operation
        with patch(
            "fakeredis.FakeAsyncRedis.hset",
            return_value=future,
        ):
            create, _ = user
            query = Query("").add(
                username=create.email, password=create.password
            )
            response = await test_client.post(
                f"/auth{TOKEN_URL}",
                content=Content(
                    b"application/x-www-form-urlencoded",
                    query.encode().encode(),
                ),
            )
            assert response.status == 500
            assert await response.json() == {
                "message": "An unexpected error occurred, talk to the tech team",
                "detail": "Could not create session.",
                "status_code": 500,
                "fields": [],
            }


class TestRefreshToken:
    async def test_refresh_token_success(
        self, test_client: TestClient, user: UserPair
    ):
        create, _ = user
        query = Query("").add(username=create.email, password=create.password)
        token_response = await test_client.post(
            f"/auth{TOKEN_URL}",
            content=Content(
                b"application/x-www-form-urlencoded",
                query.encode().encode(),
            ),
        )
        payload = await token_response.json()
        response = await test_client.post(
            f"/auth{REFRESH_URL}",
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    RefreshTokenSchema(token=payload["refresh_token"])
                ),
            ),
        )
        assert response.status == 200
        token = registry.require_decoder(SessionResponse)(
            await response.read()
        )
        assert token.access_token
        assert token.token_type == "Bearer"

    async def test_refresh_token_invalid(self, test_client: TestClient):
        response = await test_client.post(
            f"/auth{REFRESH_URL}",
            content=Content(
                b"application/json",
                msgspec.json.encode(RefreshTokenSchema(token="invalid_token")),
            ),
        )
        assert response.status == 401
        assert await response.json() == {
            "message": "Token is invalid or expired",
            "status_code": 401,
            "fields": [],
        }

    async def test_refresh_token_rejects_access_token(
        self, test_client: TestClient, user: UserPair
    ):
        create, _ = user
        query = Query("").add(username=create.email, password=create.password)
        token_response = await test_client.post(
            f"/auth{TOKEN_URL}",
            content=Content(
                b"application/x-www-form-urlencoded",
                query.encode().encode(),
            ),
        )
        payload = await token_response.json()
        response = await test_client.post(
            f"/auth{REFRESH_URL}",
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    RefreshTokenSchema(token=payload["access_token"])
                ),
            ),
        )
        assert response.status == 401
        assert await response.json() == {
            "message": "Token is invalid or expired",
            "status_code": 401,
            "fields": [],
        }

    async def test_refresh_token_with_invalid_session(
        self, test_client: TestClient, user: UserPair
    ):
        create, user_out = user
        query = Query("").add(username=create.email, password=create.password)
        token_response = await test_client.post(
            f"/auth{TOKEN_URL}",
            content=Content(
                b"application/x-www-form-urlencoded",
                query.encode().encode(),
            ),
        )
        payload = await token_response.json()
        # Simulate invalid session by deleting the cache entry
        cache_context = resolve(test_client, CacheContext)
        async with cache_context as cache:
            keys = await asserts_async(cache.hkeys)(user_out.id_.hex)
            _ = await asserts_async(cache.hdel)(user_out.id_.hex, *keys)

        response = await test_client.post(
            f"/auth{REFRESH_URL}",
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    RefreshTokenSchema(token=payload["refresh_token"])
                ),
            ),
        )
        assert response.status == 401
        assert await response.json() == {
            "message": "Token is invalid or expired",
            "status_code": 401,
            "fields": [],
        }

    async def test_refresh_token_for_no_longer_existent_user(
        self, test_client: TestClient, user: UserPair
    ):
        create, _ = user
        query = Query("").add(username=create.email, password=create.password)
        token_response = await test_client.post(
            f"/auth{TOKEN_URL}",
            content=Content(
                b"application/x-www-form-urlencoded",
                query.encode().encode(),
            ),
        )
        payload = await token_response.json()
        # Simulate user deletion by removing the user from the database
        context = resolve(test_client, SessionContext)
        async with context as session:
            _ = await session.execute(
                sa.delete(UserEntity).where(
                    Where("email", create.email).bind(UserEntity)
                )
            )

        response = await test_client.post(
            f"/auth{REFRESH_URL}",
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    RefreshTokenSchema(token=payload["refresh_token"])
                ),
            ),
        )
        assert response.status == 401
        assert await response.json() == {
            "message": "Token is invalid or expired",
            "status_code": 401,
            "fields": [],
        }


class TestLogout:
    async def test_logout_success(
        self, test_client: TestClient, user: UserPair
    ):
        create, _ = user
        query = Query("").add(username=create.email, password=create.password)
        token_response = await test_client.post(
            f"/auth{TOKEN_URL}",
            content=Content(
                b"application/x-www-form-urlencoded",
                query.encode().encode(),
            ),
        )
        payload = await token_response.json()
        response = await test_client.delete(
            "/auth/logout",
            headers={"Authorization": f"Bearer {payload['access_token']}"},
        )
        assert response.status == 204

    async def test_logout_without_authentication(
        self, test_client: TestClient
    ):
        response = await test_client.delete("/auth/logout")
        # We don't have control over the response and status code here
        # because the authentication response is handled by guardpost.
        assert response.status == 401

    async def test_logout_invalidates_session(
        self, test_client: TestClient, user: UserPair
    ):
        create, _ = user
        query = Query("").add(username=create.email, password=create.password)
        token_response = await test_client.post(
            f"/auth{TOKEN_URL}",
            content=Content(
                b"application/x-www-form-urlencoded",
                query.encode().encode(),
            ),
        )
        payload = await token_response.json()
        response = await test_client.delete(
            "/auth/logout",
            headers={"Authorization": f"Bearer {payload['access_token']}"},
        )
        assert response.status == 204

        # Verify that the session is invalidated
        response = await test_client.post(
            f"/auth{REFRESH_URL}",
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    RefreshTokenSchema(token=payload["refresh_token"])
                ),
            ),
        )
        assert response.status == 401
        assert await response.json() == {
            "message": "Token is invalid or expired",
            "status_code": 401,
            "fields": [],
        }

    async def test_logout_full_logout(
        self, test_client: TestClient, user: UserPair
    ):
        create, _ = user
        query = Query("").add(username=create.email, password=create.password)
        access = ""
        tokens: list[str] = []
        for _ in range(3):
            token_response = await test_client.post(
                f"/auth{TOKEN_URL}",
                content=Content(
                    b"application/x-www-form-urlencoded",
                    query.encode().encode(),
                ),
            )
            payload = await token_response.json()
            tokens.append(payload["refresh_token"])
            if not access:
                access = payload["access_token"]
        response = await test_client.delete(
            "/auth/logout",
            headers={
                "Authorization": f"Bearer {access}"
            },  # Use the first token for authentication
            query={"full_logout": "true"},
        )
        assert response.status == 204, await response.text()

        # Verify that the session is invalidated
        for token in tokens:
            response = await test_client.post(
                f"/auth{REFRESH_URL}",
                content=Content(
                    b"application/json",
                    msgspec.json.encode(RefreshTokenSchema(token=token)),
                ),
            )
            assert response.status == 401
            assert await response.json() == {
                "message": "Token is invalid or expired",
                "status_code": 401,
                "fields": [],
            }
