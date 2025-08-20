from collections.abc import Sequence
from datetime import date
from http import HTTPStatus

import msgspec
import pytest
from blacksheep import Content
from blacksheep.testing import TestClient
from escudeiro.url import Query

from app.users import schemas
from app.utils.msgspec import registry


class TestCreateUser:
    async def test_create_user_success(self, test_client: TestClient):
        payload = schemas.CreateUserSchema(
            email="testuser@example.com",
            password="Pas5$word",
            full_name="Test User",
            birth_date=date(1990, 1, 1),
        )
        response = await test_client.post(
            "/users",
            content=Content(b"application/json", msgspec.json.encode(payload)),
        )

        assert response.status == 201
        response_data = registry.require_decoder(schemas.UserOutSchema)(
            await response.read()
        )
        assert response_data.email == payload.email
        assert response_data.full_name == payload.full_name
        assert response_data.birth_date == payload.birth_date
        assert response_data.id_ is not None
        assert "password" not in await response.json()

    async def test_create_duplicate_email(self, test_client: TestClient):
        payload = schemas.CreateUserSchema(
            email="testuser@example.com",
            password="Pas5$word",
            full_name="Test User",
            birth_date=date(1990, 1, 1),
        )
        _ = await test_client.post(
            "/users",
            content=Content(b"application/json", msgspec.json.encode(payload)),
        )
        response = await test_client.post(
            "/users",
            content=Content(b"application/json", msgspec.json.encode(payload)),
        )
        assert response.status == 409
        assert await response.json() == {
            "message": "User already exists",
            "fields": [
                {
                    "name": "email",
                    "detail": f"Email {payload.email} already exists",
                }
            ],
            "status_code": 409,
        }

    @pytest.mark.parametrize(
        "payload, expected_detail",
        [
            (
                "password",
                [
                    "Password must contain at least one digit.",
                    "Password must contain at least one uppercase letter.",
                    "Password must contain at least one special character.",
                ],
            ),
            (
                "PASSWORD",
                [
                    "Password must contain at least one digit.",
                    "Password must contain at least one lowercase letter.",
                    "Password must contain at least one special character.",
                ],
            ),
            (
                "Passw0rd",
                [
                    "Password must contain at least one special character.",
                ],
            ),
            (
                "short",
                [
                    "Password must be at least 8 characters long.",
                    "Password must contain at least one digit.",
                    "Password must contain at least one uppercase letter.",
                    "Password must contain at least one special character.",
                ],
            ),
            (
                "12345678",
                [
                    "Password must contain at least one uppercase letter.",
                    "Password must contain at least one lowercase letter.",
                    "Password must contain at least one special character.",
                ],
            ),
            (
                "NoSpecial1",
                [
                    "Password must contain at least one special character.",
                ],
            ),
            (
                "NoNumber$",
                [
                    "Password must contain at least one digit.",
                ],
            ),
        ],
        ids=[
            "missing_lowercase",
            "missing_uppercase",
            "missing_number",
            "missing_special",
            "too_short",
            "only_numbers",
            "missing_number_special",
        ],
    )
    async def test_create_user_weak_password(
        self,
        test_client: TestClient,
        payload: str,
        expected_detail: Sequence[str],
    ):
        user_payload = {
            "email": "testuser@example.com",
            "password": payload,
            "fullName": "Test User",
            "birthDate": date(1990, 1, 1),
        }
        response = await test_client.post(
            "/users",
            content=Content(
                b"application/json", msgspec.json.encode(user_payload)
            ),
        )
        assert response.status == HTTPStatus.UNPROCESSABLE_CONTENT, (
            await response.read()
        )
        errors = await response.json()
        assert errors["message"] == "Invalid password"
        assert len(errors["fields"]) == len(expected_detail)
        for error in errors["fields"]:
            assert error["name"] == "password"
            assert error["detail"] in expected_detail
        assert sorted(error["detail"] for error in errors["fields"]) == sorted(
            expected_detail
        )
        assert errors["status_code"] == HTTPStatus.UNPROCESSABLE_CONTENT


class TestGetUser:
    async def test_get_user_success(
        self,
        test_client: TestClient,
        user: tuple[schemas.CreateUserSchema, schemas.UserOutSchema],
        auth_headers: dict[str, str],
    ):
        _, expected_user = user
        response = await test_client.get(
            "/users/me",
            headers=auth_headers,
        )
        assert response.status == 200
        user_data = registry.require_decoder(schemas.UserOutSchema)(
            await response.read()
        )
        assert user_data.id_ == expected_user.id_
        assert user_data.email == expected_user.email
        assert user_data.full_name == expected_user.full_name
        assert user_data.birth_date == expected_user.birth_date
        assert "password" not in await response.json()
        assert user_data.created_at is not None
        assert user_data.updated_at is not None
