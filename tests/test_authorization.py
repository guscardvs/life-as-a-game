from typing import cast
from uuid import uuid4

import msgspec
import pytest
from blacksheep import Application, Content
from blacksheep.testing import TestClient
from escudeiro.context import atomic
from rodi import Container

from app.authorization.repository import GroupRepository, RoleRepository
from app.authorization.schemas import (
    ExtendedGroupSchema,
    RoleSchema,
)
from app.authorization.typedef import ADMIN_ROLE_NAME
from app.users.repository import UserRepository
from app.users.schemas import CreateUserSchema, UserOutSchema, UserSchema
from app.utils.database import SessionContext
from app.utils.database.query.where import Where
from app.utils.server.page import PagedResponse


@pytest.fixture
async def setup_admin_group(
    user: tuple[CreateUserSchema, UserOutSchema],
    api: Application,
) -> None:
    _, created_user = user
    services = cast(Container, api.services)
    context = atomic(services.resolve(SessionContext))
    async with context:
        role_repository = RoleRepository(context)
        role = await role_repository.create(
            RoleSchema(
                codename=ADMIN_ROLE_NAME,
                description="Administrator role",
                **RoleSchema.make_create_content(),
            )
        )
        group_repository = GroupRepository(context)
        group = await group_repository.create(
            ExtendedGroupSchema(
                name="admin",
                description="Administrator group",
                roles=[],
                **ExtendedGroupSchema.make_create_content(),
            )
        )
        await group_repository.attach_roles(group.id_, [role.id_])
        await group_repository.join_group(group.id_, [created_user.id_])


@pytest.fixture
async def new_role(
    setup_admin_group: None,
    test_client: TestClient,
    auth_headers: dict[str, str],
) -> RoleSchema:
    _ = setup_admin_group
    payload = {
        "codename": "Example role",
        "description": "Example role description",
    }
    response = await test_client.post(
        "/roles",
        headers=auth_headers,
        content=Content(b"application/json", msgspec.json.encode(payload)),
    )
    content = await response.read()
    assert content is not None
    data = msgspec.json.decode(content, type=RoleSchema)
    data.created_at = data.created_at.replace(
        tzinfo=None
    )  # sqlite does not support timezone, unlike postgres
    if data.updated_at:
        data.updated_at = data.updated_at.replace(tzinfo=None)
    assert response.status == 201
    return data


@pytest.fixture
async def as_superuser(
    api: Application,
    user: tuple[CreateUserSchema, UserOutSchema],
):
    services = cast(Container, api.services)
    _, user_out = user
    context = atomic(services.resolve(SessionContext))
    async with context:
        user_repository = UserRepository(context)
        user_in = await user_repository.get(Where("id", user_out.id_))
        user_in.is_superuser = True
        _ = await user_repository.update(Where("id", user_out.id_), user_in)


class TestGetMyRoles:
    @pytest.mark.usefixtures("setup_admin_group")
    async def test_get_my_roles_success(
        self,
        auth_headers: dict[str, str],
        test_client: TestClient,
    ):
        response = await test_client.get("/roles/me", headers=auth_headers)
        assert response.status == 200
        content = await response.read()
        assert content is not None
        data = msgspec.json.decode(
            content,
            type=PagedResponse[RoleSchema],
        )
        assert data.total == 1
        assert data.data[0].codename == ADMIN_ROLE_NAME
        assert data.data[0].description == "Administrator role"

    async def test_get_my_roles_no_role_added(
        self, auth_headers: dict[str, str], test_client: TestClient
    ):
        response = await test_client.get("/roles/me", headers=auth_headers)
        assert response.status == 200
        content = await response.read()
        assert content is not None
        data = msgspec.json.decode(
            content,
            type=PagedResponse[RoleSchema],
        )
        assert data.total == 0
        assert data.data == []


class TestGetRoles:
    @pytest.mark.usefixtures("setup_admin_group")
    async def test_roles_success(
        self, test_client: TestClient, auth_headers: dict[str, str]
    ):
        response = await test_client.get("/roles", headers=auth_headers)
        assert response.status == 200
        content = await response.read()
        assert content is not None
        data = msgspec.json.decode(content, type=PagedResponse[RoleSchema])
        assert data.total == 1
        assert data.data[0].codename == ADMIN_ROLE_NAME
        assert data.data[0].description == "Administrator role"

    async def test_roles_no_role_added(
        self, test_client: TestClient, auth_headers: dict[str, str]
    ):
        response = await test_client.get("/roles", headers=auth_headers)
        assert response.status == 200
        content = await response.read()
        assert content is not None
        data = msgspec.json.decode(content, type=PagedResponse[RoleSchema])
        assert data.total == 0
        assert data.data == []


class TestGetRoleByCodename:
    @pytest.mark.usefixtures("setup_admin_group")
    async def test_get_role_by_codename_success(
        self, test_client: TestClient, auth_headers: dict[str, str]
    ):
        response = await test_client.get(
            f"/roles/find-by-codename/{ADMIN_ROLE_NAME}",
            headers=auth_headers,
        )
        assert response.status == 200
        content = await response.read()
        assert content is not None
        data = msgspec.json.decode(content, type=RoleSchema)
        assert data.codename == ADMIN_ROLE_NAME
        assert data.description == "Administrator role"

    async def test_get_role_by_codename_not_found(
        self, test_client: TestClient, auth_headers: dict[str, str]
    ):
        response = await test_client.get(
            "/roles/find-by-codename/nonexistent", headers=auth_headers
        )
        assert response.status == 404
        content = await response.read()
        assert content is not None
        data = msgspec.json.decode(content, type=dict)
        assert data["message"] == "Role not found"


class TestCreateRole:
    @pytest.mark.usefixtures("setup_admin_group")
    async def test_create_role_success(
        self, test_client: TestClient, auth_headers: dict[str, str]
    ):
        payload = {
            "codename": "new_role",
            "description": "New role description",
        }
        response = await test_client.post(
            "/roles",
            headers=auth_headers,
            content=Content(b"application/json", msgspec.json.encode(payload)),
        )
        assert response.status == 201
        content = await response.read()
        assert content is not None
        data = msgspec.json.decode(content, type=RoleSchema)
        assert data.codename == "new_role"
        assert data.description == "New role description"

    @pytest.mark.usefixtures("as_superuser")
    async def test_create_role_success_for_superuser(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
    ):
        response = await test_client.post(
            "/roles",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "codename": "superuser_role",
                        "description": "Superuser role description",
                    }
                ),
            ),
        )
        assert response.status == 201
        content = await response.read()
        assert content is not None
        data = msgspec.json.decode(content, type=RoleSchema)
        assert data.codename == "superuser_role"
        assert data.description == "Superuser role description"

    async def test_create_role_fails_for_normal_user(
        self, test_client: TestClient, auth_headers: dict[str, str]
    ):
        payload = {
            "codename": "new_role",
            "description": "New role description",
        }
        response = await test_client.post(
            "/roles",
            headers=auth_headers,
            content=Content(b"application/json", msgspec.json.encode(payload)),
        )

        assert response.status == 403
        content = await response.read()
        assert content == b"Forbidden"

    @pytest.mark.usefixtures("setup_admin_group")
    async def test_create_role_cannot_recreate_admin_role(
        self, test_client: TestClient, auth_headers: dict[str, str]
    ):
        payload = {
            "codename": ADMIN_ROLE_NAME,
            "description": "New admin role description",
        }
        response = await test_client.post(
            "/roles",
            headers=auth_headers,
            content=Content(b"application/json", msgspec.json.encode(payload)),
        )

        assert response.status == 403
        content = await response.read()
        assert content is not None
        data = msgspec.json.decode(content, type=dict)
        assert (
            data["message"] == "You do not have permission to use this route"
        )

    @pytest.mark.usefixtures("as_superuser")
    async def test_admin_role_cannot_be_created_by_route(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
    ):
        payload = {
            "codename": ADMIN_ROLE_NAME,
            "description": "New admin role description",
        }
        response = await test_client.post(
            "/roles",
            headers=auth_headers,
            content=Content(b"application/json", msgspec.json.encode(payload)),
        )

        assert response.status == 403
        content = await response.read()
        assert content is not None
        data = msgspec.json.decode(content, type=dict)
        assert (
            data["message"] == "You do not have permission to use this route"
        )

    @pytest.mark.usefixtures("setup_admin_group")
    async def test_cannot_create_duplicated_route(
        self, test_client: TestClient, auth_headers: dict[str, str]
    ):
        payload = {
            "codename": "Example role",
            "description": "Example role description",
        }
        _ = await test_client.post(
            "/roles",
            headers=auth_headers,
            content=Content(b"application/json", msgspec.json.encode(payload)),
        )

        response = await test_client.post(
            "/roles",
            headers=auth_headers,
            content=Content(b"application/json", msgspec.json.encode(payload)),
        )
        content = await response.read()
        assert content is not None
        data = msgspec.json.decode(content, type=dict)
        assert data["message"] == "Role already exists"
        assert response.status == data["status_code"] == 409
        assert data["fields"] == [
            {
                "name": "codename",
                "detail": f"Codename {payload['codename']} already exists",
            }
        ]


class TestUpdateRole:
    async def test_update_role_success(
        self,
        new_role: RoleSchema,
        test_client: TestClient,
        auth_headers: dict[str, str],
    ):
        payload = {
            "codename": "Updated role",
            "description": "Updated role description",
        }
        response = await test_client.patch(
            f"/roles/{new_role.id_}",
            headers=auth_headers,
            content=Content(b"application/json", msgspec.json.encode(payload)),
        )
        content = await response.read()
        assert content is not None
        data = msgspec.json.decode(content, type=RoleSchema)
        assert response.status == 200
        assert data.id_ == new_role.id_
        assert data.codename == payload["codename"]
        assert data.description == payload["description"]

    @pytest.mark.usefixtures("setup_admin_group")
    async def test_update_role_not_found(
        self, test_client: TestClient, auth_headers: dict[str, str]
    ):
        payload = {
            "codename": "Updated role",
            "description": "Updated role description",
        }
        response = await test_client.patch(
            f"/roles/{uuid4()}",
            headers=auth_headers,
            content=Content(b"application/json", msgspec.json.encode(payload)),
        )
        content = await response.read()
        assert content is not None
        data = msgspec.json.decode(content, type=dict)
        assert response.status == 404
        assert data["message"] == "Role not found"

    @pytest.mark.usefixtures("setup_admin_group")
    async def test_update_role_duplicate(
        self, test_client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        new_role_a = {
            "codename": "New Role A",
            "description": "New Role A description",
        }
        new_role_b = {
            "codename": "New Role B",
            "description": "New Role B description",
        }

        _ = await test_client.post(
            "/roles",
            headers=auth_headers,
            content=Content(
                b"application/json", msgspec.json.encode(new_role_a)
            ),
        )

        create_roleb_response = await test_client.post(
            "/roles",
            headers=auth_headers,
            content=Content(
                b"application/json", msgspec.json.encode(new_role_b)
            ),
        )

        content = await create_roleb_response.read()
        assert content is not None
        role_b = msgspec.json.decode(content, type=RoleSchema)
        role_b.codename = new_role_a["codename"]

        response = await test_client.patch(
            f"/roles/{role_b.id_}",
            headers=auth_headers,
            content=Content(b"application/json", msgspec.json.encode(role_b)),
        )

        content = await response.read()
        assert content is not None
        data = msgspec.json.decode(content, type=dict)
        assert response.status == 409
        assert data["message"] == "Role already exists"
        assert data["fields"] == [
            {
                "name": "codename",
                "detail": f"Codename {role_b.codename} already exists",
            }
        ]

    @pytest.mark.parametrize(
        "payload, attribute",
        [
            ({"description": "Updated role description"}, "description"),
            ({"codename": "Updated role codename"}, "codename"),
        ],
    )
    async def test_update_role_only_updates_sent_value(
        self,
        payload: dict[str, str],
        attribute: str,
        new_role: RoleSchema,
        test_client: TestClient,
        auth_headers: dict[str, str],
    ):
        response = await test_client.patch(
            f"/roles/{new_role.id_}",
            headers=auth_headers,
            content=Content(b"application/json", msgspec.json.encode(payload)),
        )
        content = await response.read()
        assert content is not None
        data = msgspec.json.decode(content, type=RoleSchema)
        assert response.status == 200
        for field in RoleSchema.__struct_fields__:
            if field == attribute:
                assert getattr(data, field) == payload[field]
            elif field != "updated_at":
                assert getattr(data, field) == getattr(new_role, field)

    async def test_update_role_does_not_work_for_normal_user(
        self,
        api: Application,
        test_client: TestClient,
        auth_headers: dict[str, str],
        user: tuple[CreateUserSchema, UserOutSchema],
    ):
        services = cast(Container, api.services)
        _, user_out = user
        context = atomic(services.resolve(SessionContext))
        async with context:
            user_repository = UserRepository(context)
            user_in = await user_repository.get(Where("id", user_out.id_))
            user_in.is_superuser = True
            _ = await user_repository.update(
                Where("id", user_out.id_), user_in
            )

        response = await test_client.post(
            "/roles",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "codename": "superuser_role",
                        "description": "Superuser role description",
                    }
                ),
            ),
        )
        assert response.status == 201
        content = await response.read()
        assert content is not None
        data = msgspec.json.decode(content, type=RoleSchema)

        async with context:
            user_in.is_superuser = False
            _ = await user_repository.update(
                Where("id", user_out.id_), user_in
            )

        response = await test_client.patch(
            f"/roles/{data.id_}",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {"description": "Updated role description"}
                ),
            ),
        )

        assert response.status == 403
        content = await response.read()
        assert content == b"Forbidden"

    @pytest.mark.usefixtures("setup_admin_group")
    async def test_update_role_does_not_work_for_admin_role(
        self, test_client: TestClient, auth_headers: dict[str, str]
    ):
        admin_role_response = await test_client.get(
            f"/roles/find-by-codename/{ADMIN_ROLE_NAME}", headers=auth_headers
        )
        content = await admin_role_response.read()
        assert content is not None
        admin_role = msgspec.json.decode(content, type=RoleSchema)

        payload = {
            "description": "Updated role description",
        }
        response = await test_client.patch(
            f"/roles/{admin_role.id_}",
            headers=auth_headers,
            content=Content(b"application/json", msgspec.json.encode(payload)),
        )
        content = await response.read()
        assert content is not None
        data = msgspec.json.decode(content, type=dict)
        assert response.status == 403
        assert (
            data["message"] == "You do not have permission to use this route"
        )

    @pytest.mark.usefixtures("setup_admin_group")
    async def test_cannot_update_role_to_be_admin_role(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
        new_role: RoleSchema,
    ):
        response = await test_client.patch(
            f"/roles/{new_role.id_}",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode({"codename": ADMIN_ROLE_NAME}),
            ),
        )
        content = await response.read()
        assert content is not None
        data = msgspec.json.decode(content, type=dict)
        assert response.status == 403
        assert (
            data["message"] == "You do not have permission to use this route"
        )


class TestDeleteRole:
    @pytest.mark.usefixtures("setup_admin_group")
    async def test_delete_role_filters_out_admin_role_automatically(
        self, test_client: TestClient, auth_headers: dict[str, str]
    ):
        admin_role_response = await test_client.get(
            f"/roles/find-by-codename/{ADMIN_ROLE_NAME}", headers=auth_headers
        )
        content = await admin_role_response.read()
        assert content is not None
        admin_role = msgspec.json.decode(content, type=RoleSchema)

        response = await test_client.delete(
            f"/roles/{admin_role.id_}",
            headers=auth_headers,
        )
        content = await response.read()
        assert content is not None
        data = msgspec.json.decode(content, type=dict)
        assert response.status == 404
        assert data["message"] == "Role not found"

    @pytest.mark.usefixtures("setup_admin_group")
    async def test_delete_role_success(
        self,
        test_client: TestClient,
        auth_headers: dict[str, str],
        new_role: RoleSchema,
    ):
        response = await test_client.delete(
            f"/roles/{new_role.id_}",
            headers=auth_headers,
        )
        assert response.status == 204

        get_response = await test_client.get(
            f"/roles/find/{new_role.id_}",
            headers=auth_headers,
        )

        assert get_response.status == 404
        content = await get_response.read()
        assert content is not None
        data = msgspec.json.decode(content, type=dict)
        assert data["message"] == "Role not found"


class TestGetMyGroups:
    @pytest.mark.usefixtures("setup_admin_group")
    async def test_get_my_groups_success(
        self, auth_headers: dict[str, str], test_client: TestClient
    ):
        response = await test_client.get("/groups/me", headers=auth_headers)
        assert response.status == 200
        content = await response.read()
        assert content is not None
        data = msgspec.json.decode(
            content, type=PagedResponse[ExtendedGroupSchema]
        )
        assert data.total == 1
        assert data.data[0].name == "admin"
        assert data.data[0].description == "Administrator group"

    async def test_get_my_groups_no_groups(
        self, auth_headers: dict[str, str], test_client: TestClient
    ):
        response = await test_client.get("/groups/me", headers=auth_headers)
        assert response.status == 200
        content = await response.read()
        assert content is not None
        data = msgspec.json.decode(
            content, type=PagedResponse[ExtendedGroupSchema]
        )
        assert data.total == 0
        assert data.data == []


class TestGetGroupByName:
    @pytest.mark.usefixtures("setup_admin_group")
    async def test_get_group_by_name_success(
        self, auth_headers: dict[str, str], test_client: TestClient
    ):
        response = await test_client.get(
            "/groups/find-by-name/admin", headers=auth_headers
        )
        assert response.status == 200
        content = await response.read()
        assert content is not None
        data = msgspec.json.decode(content, type=ExtendedGroupSchema)
        assert data.name == "admin"
        assert data.description == "Administrator group"

    async def test_get_group_by_name_not_found(
        self, auth_headers: dict[str, str], test_client: TestClient
    ):
        response = await test_client.get(
            "/groups/find-by-name/nonexistent", headers=auth_headers
        )
        assert response.status == 404
        content = await response.read()
        assert content is not None
        data = msgspec.json.decode(content, type=dict)
        assert data["message"] == "Group not found"


class TestGetGroupById:
    @pytest.fixture
    async def group(
        self,
        auth_headers: dict[str, str],
        test_client: TestClient,
        setup_admin_group: None,
    ) -> ExtendedGroupSchema:
        _ = setup_admin_group
        response = await test_client.get(
            "/groups/find-by-name/admin", headers=auth_headers
        )
        assert response.status == 200
        content = await response.read()
        assert content is not None
        return msgspec.json.decode(content, type=ExtendedGroupSchema)

    async def test_get_group_by_id_success(
        self,
        auth_headers: dict[str, str],
        test_client: TestClient,
        group: ExtendedGroupSchema,
    ):
        response = await test_client.get(
            f"/groups/find/{group.id_}", headers=auth_headers
        )
        assert response.status == 200
        content = await response.read()
        assert content is not None
        data = msgspec.json.decode(content, type=ExtendedGroupSchema)
        assert data.id_ == group.id_
        assert data.name == group.name
        assert data.description == group.description

    async def test_get_group_by_id_not_found(
        self, auth_headers: dict[str, str], test_client: TestClient
    ):
        response = await test_client.get(
            f"/groups/find/{uuid4()}", headers=auth_headers
        )
        assert response.status == 404
        content = await response.read()
        assert content is not None
        data = msgspec.json.decode(content, type=dict)
        assert data["message"] == "Group not found"


class TestCreateGroup:
    @pytest.mark.usefixtures("setup_admin_group")
    async def test_create_group_success_for_admin_user(
        self, auth_headers: dict[str, str], test_client: TestClient
    ):
        response = await test_client.post(
            "/groups",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "name": "new_group",
                        "description": "New group description",
                    }
                ),
            ),
        )
        assert response.status == 201
        content = await response.read()
        assert content is not None
        data = msgspec.json.decode(content, type=ExtendedGroupSchema)
        assert data.name == "new_group"
        assert data.description == "New group description"

    @pytest.mark.usefixtures("as_superuser")
    async def test_create_group_success_for_superuser(
        self, auth_headers: dict[str, str], test_client: TestClient
    ):
        response = await test_client.post(
            "/groups",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "name": "new_group",
                        "description": "New group description",
                    }
                ),
            ),
        )
        assert response.status == 201
        content = await response.read()
        assert content is not None
        data = msgspec.json.decode(content, type=ExtendedGroupSchema)
        assert data.name == "new_group"
        assert data.description == "New group description"

    async def test_create_group_fails_for_normal_user(
        self, auth_headers: dict[str, str], test_client: TestClient
    ):
        response = await test_client.post(
            "/groups",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "name": "new_group",
                        "description": "New group description",
                    }
                ),
            ),
        )
        assert response.status == 403
        content = await response.read()
        assert content == b"Forbidden"

    @pytest.mark.usefixtures("setup_admin_group")
    async def test_create_group_duplicate_name(
        self, auth_headers: dict[str, str], test_client: TestClient
    ):
        response = await test_client.post(
            "/groups",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "name": "new_group",
                        "description": "New group description",
                    }
                ),
            ),
        )
        assert response.status == 201
        content = await response.read()
        assert content is not None
        data = msgspec.json.decode(content, type=ExtendedGroupSchema)
        assert data.name == "new_group"
        assert data.description == "New group description"

        response = await test_client.post(
            "/groups",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "name": "new_group",
                        "description": "New group description",
                    }
                ),
            ),
        )
        assert response.status == 409
        content = await response.read()
        assert content is not None
        data = msgspec.json.decode(content, type=dict)
        assert data["message"] == "Group already exists"
        assert data["status_code"] == 409
        assert data["fields"] == [
            {"name": "name", "detail": "Name new_group already exists"}
        ]


class TestUpdateGroup:
    @pytest.mark.usefixtures("setup_admin_group")
    async def test_update_group_success_for_admin_user(
        self, auth_headers: dict[str, str], test_client: TestClient
    ):
        admin_group_response = await test_client.get(
            "/groups/find-by-name/admin", headers=auth_headers
        )
        content = await admin_group_response.read()
        assert content is not None
        admin_group = msgspec.json.decode(content, type=ExtendedGroupSchema)
        response = await test_client.patch(
            f"/groups/{admin_group.id_}",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "name": "updated_group",
                        "description": "Updated group description",
                    }
                ),
            ),
        )
        assert response.status == 200
        content = await response.read()
        assert content is not None
        data = msgspec.json.decode(content, type=ExtendedGroupSchema)
        assert data.name == "updated_group"
        assert data.description == "Updated group description"

    @pytest.mark.usefixtures("as_superuser")
    async def test_update_group_success_for_superuser(
        self, auth_headers: dict[str, str], test_client: TestClient
    ):
        new_group_response = await test_client.post(
            "/groups",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "name": "new_group",
                        "description": "New group description",
                    }
                ),
            ),
        )
        content = await new_group_response.read()
        assert content is not None
        data = msgspec.json.decode(content, type=ExtendedGroupSchema)

        response = await test_client.patch(
            f"/groups/{data.id_}",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "name": "updated_group",
                        "description": "Updated group description",
                    }
                ),
            ),
        )
        assert response.status == 200
        content = await response.read()
        assert content is not None
        data = msgspec.json.decode(content, type=ExtendedGroupSchema)
        assert data.name == "updated_group"
        assert data.description == "Updated group description"

    async def test_update_group_fails_for_normal_user(
        self, auth_headers: dict[str, str], test_client: TestClient
    ):
        response = await test_client.patch(
            "/groups/{group_id}",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "name": "updated_group",
                        "description": "Updated group description",
                    }
                ),
            ),
        )
        assert response.status == 403
        content = await response.read()
        assert content == b"Forbidden"

    @pytest.mark.usefixtures("setup_admin_group")
    async def test_update_group_duplicate_name(
        self, auth_headers: dict[str, str], test_client: TestClient
    ):
        new_group_response = await test_client.post(
            "/groups",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "name": "new_group",
                        "description": "New group description",
                    }
                ),
            ),
        )
        content = await new_group_response.read()
        assert content is not None
        data = msgspec.json.decode(content, type=ExtendedGroupSchema)

        response = await test_client.patch(
            f"/groups/{data.id_}",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "name": "admin",
                        "description": "Updated group description",
                    }
                ),
            ),
        )
        assert response.status == 409
        content = await response.read()
        assert content is not None
        data = msgspec.json.decode(content, type=dict)
        assert data["message"] == "Group already exists"
        assert data["status_code"] == 409
        assert data["fields"] == [
            {"name": "name", "detail": "Name admin already exists"}
        ]


class TestAttachRoleToGroup:
    @pytest.mark.usefixtures("setup_admin_group")
    async def test_attach_role_to_group_success_for_admin_user(
        self, auth_headers: dict[str, str], test_client: TestClient
    ):
        new_group_response = await test_client.post(
            "/groups",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "name": "new_group",
                        "description": "New group description",
                    }
                ),
            ),
        )
        content = await new_group_response.read()
        assert content is not None
        data = msgspec.json.decode(content, type=ExtendedGroupSchema)

        new_role_response = await test_client.post(
            "/roles",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "codename": "new_role",
                        "description": "New role description",
                    }
                ),
            ),
        )
        content = await new_role_response.read()
        assert content is not None
        role_data = msgspec.json.decode(content, type=RoleSchema)

        response = await test_client.patch(
            f"/groups/attach/{data.id_}",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "roleIds": [role_data.id_],
                    }
                ),
            ),
        )
        assert response.status == 204

    @pytest.mark.usefixtures("as_superuser")
    async def test_attach_role_to_group_success_for_super_user(
        self, auth_headers: dict[str, str], test_client: TestClient
    ):
        new_group_response = await test_client.post(
            "/groups",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "name": "new_group",
                        "description": "New group description",
                    }
                ),
            ),
        )
        content = await new_group_response.read()
        assert content is not None
        data = msgspec.json.decode(content, type=ExtendedGroupSchema)

        new_role_response = await test_client.post(
            "/roles",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "codename": "new_role",
                        "description": "New role description",
                    }
                ),
            ),
        )
        content = await new_role_response.read()
        assert content is not None
        role_data = msgspec.json.decode(content, type=RoleSchema)

        response = await test_client.patch(
            f"/groups/attach/{data.id_}",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "roleIds": [role_data.id_],
                    }
                ),
            ),
        )
        assert response.status == 204

    async def test_attach_role_to_group_fails_for_normal_user(
        self, auth_headers: dict[str, str], test_client: TestClient
    ):
        response = await test_client.patch(
            f"/groups/attach/{uuid4()}",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "roleIds": [uuid4()],
                    }
                ),
            ),
        )
        assert response.status == 403
        content = await response.read()
        assert content == b"Forbidden"

    @pytest.mark.usefixtures("setup_admin_group")
    async def test_attach_role_to_group_duplicate(
        self, auth_headers: dict[str, str], test_client: TestClient
    ):
        new_group_response = await test_client.post(
            "/groups",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "name": "new_group",
                        "description": "New group description",
                    }
                ),
            ),
        )
        content = await new_group_response.read()
        assert content is not None
        data = msgspec.json.decode(content, type=ExtendedGroupSchema)

        new_role_response = await test_client.post(
            "/roles",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "codename": "new_role",
                        "description": "New role description",
                    }
                ),
            ),
        )
        content = await new_role_response.read()
        assert content is not None
        role_data = msgspec.json.decode(content, type=RoleSchema)

        response = await test_client.patch(
            f"/groups/attach/{data.id_}",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "roleIds": [role_data.id_],
                    }
                ),
            ),
        )
        assert response.status == 204

        response = await test_client.patch(
            f"/groups/attach/{data.id_}",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "roleIds": [role_data.id_],
                    }
                ),
            ),
        )
        assert response.status == 409
        content = await response.read()
        assert content is not None
        data = msgspec.json.decode(content, type=dict)
        assert data["message"] == "Role already exists"
        assert data["status_code"] == 409
        assert data["fields"] == [
            {
                "name": "id",
                "detail": f"Roles {[role_data.id_]} are already attached to the group",
            }
        ]

    @pytest.mark.usefixtures("as_superuser", "setup_admin_group")
    async def test_cannot_attach_admin_role_to_multiple_groups(
        self, auth_headers: dict[str, str], test_client: TestClient
    ):
        new_group_response = await test_client.post(
            "/groups",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "name": "new_group",
                        "description": "New group description",
                    }
                ),
            ),
        )
        content = await new_group_response.read()
        assert content is not None
        data = msgspec.json.decode(content, type=ExtendedGroupSchema)

        admin_role_response = await test_client.get(
            f"/roles/find-by-codename/{ADMIN_ROLE_NAME}", headers=auth_headers
        )
        content = await admin_role_response.read()
        assert content is not None
        admin_role = msgspec.json.decode(content, type=RoleSchema)

        response = await test_client.patch(
            f"/groups/attach/{data.id_}",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "roleIds": [admin_role.id_],
                    }
                ),
            ),
        )
        assert response.status == 403
        content = await response.read()
        assert content is not None
        data = msgspec.json.decode(content, type=dict)
        assert (
            data["message"] == "You do not have permission to use this route"
        )

    @pytest.mark.usefixtures("setup_admin_group")
    async def test_cannot_attach_inexistent_group(
        self, auth_headers: dict[str, str], test_client: TestClient
    ) -> None:
        response = await test_client.patch(
            f"/groups/attach/{uuid4()}",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "roleIds": [uuid4()],
                    }
                ),
            ),
        )
        assert response.status == 404
        content = await response.read()
        assert content is not None
        data = msgspec.json.decode(content, type=dict)
        assert data["message"] == "Group not found"

    @pytest.mark.usefixtures("setup_admin_group")
    async def test_cannot_attach_inexistent_role(
        self, auth_headers: dict[str, str], test_client: TestClient
    ) -> None:
        admin_group_response = await test_client.get(
            "/groups/find-by-name/admin", headers=auth_headers
        )
        content = await admin_group_response.read()
        assert content is not None
        admin_group_data = msgspec.json.decode(
            content, type=ExtendedGroupSchema
        )

        response = await test_client.patch(
            f"/groups/attach/{admin_group_data.id_}",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "roleIds": [uuid4()],
                    }
                ),
            ),
        )
        assert response.status == 404
        content = await response.read()
        assert content is not None
        data = msgspec.json.decode(content, type=dict)
        assert data["message"] == "Role not found"


class TestDetachRoleFromGroup:
    @pytest.mark.usefixtures("setup_admin_group")
    async def test_detach_role_as_admin_user(
        self, auth_headers: dict[str, str], test_client: TestClient
    ):
        new_group_response = await test_client.post(
            "/groups",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "name": "new_group",
                        "description": "New group description",
                    }
                ),
            ),
        )
        content = await new_group_response.read()
        assert content is not None
        data = msgspec.json.decode(content, type=ExtendedGroupSchema)

        new_role_response = await test_client.post(
            "/roles",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "codename": "new_role",
                        "description": "New role description",
                    }
                ),
            ),
        )
        content = await new_role_response.read()
        assert content is not None
        role_data = msgspec.json.decode(content, type=RoleSchema)

        _ = await test_client.patch(
            f"/groups/attach/{data.id_}",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "roleIds": [role_data.id_],
                    }
                ),
            ),
        )

        group_info = await test_client.get(
            f"/groups/find/{data.id_}", headers=auth_headers
        )
        content = await group_info.read()
        assert content is not None
        group_data_before = msgspec.json.decode(
            content, type=ExtendedGroupSchema
        )

        _ = await test_client.patch(
            f"/groups/detach/{data.id_}",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "roleIds": [role_data.id_],
                    }
                ),
            ),
        )

        group_info = await test_client.get(
            f"/groups/find/{data.id_}", headers=auth_headers
        )
        content = await group_info.read()
        assert content is not None
        group_data_after = msgspec.json.decode(
            content, type=ExtendedGroupSchema
        )

        assert group_data_before.roles
        assert not group_data_after.roles

    @pytest.mark.usefixtures("as_superuser")
    async def test_detach_role_as_superuser(
        self, auth_headers: dict[str, str], test_client: TestClient
    ):
        new_group_response = await test_client.post(
            "/groups",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "name": "new_group",
                        "description": "New group description",
                    }
                ),
            ),
        )
        content = await new_group_response.read()
        assert content is not None
        data = msgspec.json.decode(content, type=ExtendedGroupSchema)

        new_role_response = await test_client.post(
            "/roles",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "codename": "new_role",
                        "description": "New role description",
                    }
                ),
            ),
        )
        content = await new_role_response.read()
        assert content is not None
        role_data = msgspec.json.decode(content, type=RoleSchema)

        _ = await test_client.patch(
            f"/groups/attach/{data.id_}",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "roleIds": [role_data.id_],
                    }
                ),
            ),
        )

        group_info = await test_client.get(
            f"/groups/find/{data.id_}", headers=auth_headers
        )
        content = await group_info.read()
        assert content is not None
        group_data_before = msgspec.json.decode(
            content, type=ExtendedGroupSchema
        )

        _ = await test_client.patch(
            f"/groups/detach/{data.id_}",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "roleIds": [role_data.id_],
                    }
                ),
            ),
        )

        group_info = await test_client.get(
            f"/groups/find/{data.id_}", headers=auth_headers
        )
        content = await group_info.read()
        assert content is not None
        group_data_after = msgspec.json.decode(
            content, type=ExtendedGroupSchema
        )

        assert group_data_before.roles
        assert not group_data_after.roles

    @pytest.mark.usefixtures("setup_admin_group")
    async def test_admin_user_cannot_detach_admin_role(
        self, auth_headers: dict[str, str], test_client: TestClient
    ):
        admin_role_response = await test_client.get(
            f"/roles/find-by-codename/{ADMIN_ROLE_NAME}", headers=auth_headers
        )
        content = await admin_role_response.read()
        assert content is not None
        admin_role_data = msgspec.json.decode(content, type=RoleSchema)

        admin_group_response = await test_client.get(
            "/groups/find-by-name/admin", headers=auth_headers
        )
        content = await admin_group_response.read()
        assert content is not None
        admin_group_data = msgspec.json.decode(
            content, type=ExtendedGroupSchema
        )

        response = await test_client.patch(
            f"/groups/detach/{admin_group_data.id_}",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "roleIds": [admin_role_data.id_],
                    }
                ),
            ),
        )

        assert response.status == 403
        content = await response.read()
        assert content is not None
        data = msgspec.json.decode(content, type=dict)
        assert (
            data["message"] == "You do not have permission to use this route"
        )

    async def test_normal_user_cannot_detach_role(
        self, test_client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        response = await test_client.patch(
            f"/groups/detach/{uuid4()}",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "roleIds": [uuid4()],
                    }
                ),
            ),
        )
        assert response.status == 403
        content = await response.read()
        assert content == b"Forbidden"

    @pytest.mark.usefixtures("setup_admin_group")
    async def test_detach_not_found_group(
        self, test_client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        response = await test_client.patch(
            f"/groups/detach/{uuid4()}",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "roleIds": [uuid4()],
                    }
                ),
            ),
        )
        assert response.status == 404
        content = await response.read()
        assert content is not None
        data = msgspec.json.decode(content, type=dict)
        assert data["message"] == "Group not found"

    @pytest.mark.usefixtures("setup_admin_group")
    async def test_detach_not_found_role(
        self, test_client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        admin_group_response = await test_client.get(
            "/groups/find-by-name/admin", headers=auth_headers
        )
        content = await admin_group_response.read()
        assert content is not None
        admin_group_data = msgspec.json.decode(
            content, type=ExtendedGroupSchema
        )

        response = await test_client.patch(
            f"/groups/detach/{admin_group_data.id_}",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "roleIds": [uuid4()],
                    }
                ),
            ),
        )
        assert response.status == 404
        content = await response.read()
        assert content is not None
        data = msgspec.json.decode(content, type=dict)
        assert data["message"] == "Role not found"


class TestDeleteGroup:
    @pytest.mark.usefixtures("setup_admin_group")
    async def test_delete_group_as_admin_user(
        self, auth_headers: dict[str, str], test_client: TestClient
    ) -> None:
        new_group_response = await test_client.post(
            "/groups",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "name": "New Group",
                        "description": "A new group for testing",
                    }
                ),
            ),
        )
        content = await new_group_response.read()
        assert content is not None
        new_group_data = msgspec.json.decode(content, type=ExtendedGroupSchema)

        response = await test_client.delete(
            f"/groups/{new_group_data.id_}",
            headers=auth_headers,
        )
        assert response.status == 204

        get_group_response = await test_client.get(
            f"/groups/find/{new_group_data.id_}",
            headers=auth_headers,
        )
        assert get_group_response.status == 404
        content = await get_group_response.read()
        assert content is not None
        data = msgspec.json.decode(content, type=dict)
        assert data["message"] == "Group not found"

    @pytest.mark.usefixtures("as_superuser")
    async def test_delete_group_as_superuser(
        self, auth_headers: dict[str, str], test_client: TestClient
    ) -> None:
        new_group_response = await test_client.post(
            "/groups",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "name": "New Group",
                        "description": "A new group for testing",
                    }
                ),
            ),
        )
        content = await new_group_response.read()
        assert content is not None
        new_group_data = msgspec.json.decode(content, type=ExtendedGroupSchema)

        response = await test_client.delete(
            f"/groups/{new_group_data.id_}",
            headers=auth_headers,
        )
        assert response.status == 204

        get_group_response = await test_client.get(
            f"/groups/find/{new_group_data.id_}",
            headers=auth_headers,
        )
        assert get_group_response.status == 404
        content = await get_group_response.read()
        assert content is not None
        data = msgspec.json.decode(content, type=dict)
        assert data["message"] == "Group not found"

    async def test_normal_user_cannot_delete_group(
        self, auth_headers: dict[str, str], test_client: TestClient
    ) -> None:
        response = await test_client.delete(
            f"/groups/{uuid4()}",
            headers=auth_headers,
        )
        assert response.status == 403
        content = await response.read()
        assert content == b"Forbidden"

    @pytest.mark.usefixtures("setup_admin_group")
    async def test_cannot_delete_admin_group_if_not_superuser(
        self, auth_headers: dict[str, str], test_client: TestClient
    ) -> None:
        admin_group_response = await test_client.get(
            "/groups/find-by-name/admin", headers=auth_headers
        )
        assert admin_group_response.status == 200
        content = await admin_group_response.read()
        assert content is not None
        admin_group_data = msgspec.json.decode(
            content, type=ExtendedGroupSchema
        )

        response = await test_client.delete(
            f"/groups/{admin_group_data.id_}",
            headers=auth_headers,
        )
        assert response.status == 403
        content = await response.read()
        assert content is not None
        data = msgspec.json.decode(content, type=dict)
        assert (
            data["message"] == "You do not have permission to use this route"
        )


class TestJoinGroup:
    @pytest.mark.usefixtures("setup_admin_group")
    async def test_join_group_success_for_admin_user(
        self,
        auth_headers: dict[str, str],
        test_client: TestClient,
        user: tuple[CreateUserSchema, UserSchema],
    ) -> None:
        _, user_out = user
        new_group_response = await test_client.post(
            "/groups",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "name": "New Group",
                        "description": "A new group for testing",
                    }
                ),
            ),
        )
        content = await new_group_response.read()
        assert content is not None
        new_group_data = msgspec.json.decode(content, type=ExtendedGroupSchema)

        response = await test_client.patch(
            f"/groups/join/{new_group_data.id_}",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "userIds": [user_out.id_],
                    }
                ),
            ),
        )
        assert response.status == 204

        my_groups = await test_client.get(
            "/groups/me",
            headers=auth_headers,
        )
        assert my_groups.status == 200
        content = await my_groups.read()
        assert content is not None
        my_groups_data = msgspec.json.decode(
            content, type=PagedResponse[ExtendedGroupSchema]
        )
        assert any(
            group.id_ == new_group_data.id_ for group in my_groups_data.data
        )

    @pytest.mark.usefixtures("as_superuser")
    async def test_join_group_success_for_superuser(
        self,
        auth_headers: dict[str, str],
        test_client: TestClient,
        user: tuple[CreateUserSchema, UserSchema],
    ) -> None:
        _, user_out = user
        new_group_response = await test_client.post(
            "/groups",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "name": "New Group",
                        "description": "A new group for testing",
                    }
                ),
            ),
        )
        content = await new_group_response.read()
        assert content is not None
        new_group_data = msgspec.json.decode(content, type=ExtendedGroupSchema)

        response = await test_client.patch(
            f"/groups/join/{new_group_data.id_}",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "userIds": [user_out.id_],
                    }
                ),
            ),
        )
        assert response.status == 204

        my_groups = await test_client.get(
            "/groups/me",
            headers=auth_headers,
        )
        assert my_groups.status == 200
        content = await my_groups.read()
        assert content is not None
        my_groups_data = msgspec.json.decode(
            content, type=PagedResponse[ExtendedGroupSchema]
        )
        assert any(
            group.id_ == new_group_data.id_ for group in my_groups_data.data
        )

    async def test_join_group_fails_for_normal_user(
        self,
        auth_headers: dict[str, str],
        test_client: TestClient,
        user: tuple[CreateUserSchema, UserSchema],
    ) -> None:
        _, user_out = user

        response = await test_client.patch(
            f"/groups/join/{uuid4()}",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "userIds": [user_out.id_],
                    }
                ),
            ),
        )
        assert response.status == 403
        content = await response.read()
        assert content == b"Forbidden"

    @pytest.mark.usefixtures("setup_admin_group")
    async def test_join_group_duplicate(
        self,
        auth_headers: dict[str, str],
        test_client: TestClient,
        user: tuple[CreateUserSchema, UserSchema],
    ) -> None:
        _, user_out = user
        admin_group_response = await test_client.get(
            "/groups/find-by-name/admin", headers=auth_headers
        )
        content = await admin_group_response.read()
        assert content is not None
        admin_group_data = msgspec.json.decode(
            content, type=ExtendedGroupSchema
        )

        response = await test_client.patch(
            f"/groups/join/{admin_group_data.id_}",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "userIds": [user_out.id_],
                    }
                ),
            ),
        )
        assert response.status == 409
        content = await response.read()
        assert content is not None
        data = msgspec.json.decode(content, type=dict)
        assert data["message"] == "User already exists"
        assert data["status_code"] == 409
        assert data["fields"] == [
            {
                "name": "id",
                "detail": f"Users {[user_out.id_]} are already in the group",
            }
        ]

    @pytest.mark.usefixtures("setup_admin_group")
    async def test_join_group_fails_for_inexistent_group(
        self,
        auth_headers: dict[str, str],
        test_client: TestClient,
        user: tuple[CreateUserSchema, UserSchema],
    ) -> None:
        _, user_out = user

        response = await test_client.patch(
            f"/groups/join/{uuid4()}",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "userIds": [user_out.id_],
                    }
                ),
            ),
        )
        assert response.status == 404
        content = await response.read()
        assert content is not None
        data = msgspec.json.decode(content, type=dict)
        assert data["message"] == "Group not found"
        assert data["status_code"] == 404

    @pytest.mark.usefixtures("setup_admin_group")
    async def test_join_group_fails_for_inexistent_user(
        self,
        auth_headers: dict[str, str],
        test_client: TestClient,
    ) -> None:
        admin_group_response = await test_client.get(
            "/groups/find-by-name/admin", headers=auth_headers
        )
        content = await admin_group_response.read()
        assert content is not None
        admin_group_data = msgspec.json.decode(
            content, type=ExtendedGroupSchema
        )

        response = await test_client.patch(
            f"/groups/join/{admin_group_data.id_}",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "userIds": [uuid4()],
                    }
                ),
            ),
        )
        assert response.status == 404
        content = await response.read()
        assert content is not None
        data = msgspec.json.decode(content, type=dict)
        assert data["message"] == "User not found"
        assert data["status_code"] == 404


class TestLeaveGroup:
    @pytest.mark.usefixtures("setup_admin_group")
    async def test_leave_group_success_for_admin_user(
        self,
        auth_headers: dict[str, str],
        test_client: TestClient,
        user: tuple[CreateUserSchema, UserSchema],
    ) -> None:
        _, user_out = user
        new_group_response = await test_client.post(
            "/groups",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "name": "New Group",
                        "description": "A new group for testing",
                    }
                ),
            ),
        )
        content = await new_group_response.read()
        assert content is not None
        new_group_data = msgspec.json.decode(content, type=ExtendedGroupSchema)

        _ = await test_client.patch(
            f"/groups/join/{new_group_data.id_}",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "userIds": [user_out.id_],
                    }
                ),
            ),
        )

        response = await test_client.patch(
            f"/groups/leave/{new_group_data.id_}",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "userIds": [user_out.id_],
                    }
                ),
            ),
        )
        assert response.status == 204

        get_my_groups_response = await test_client.get(
            "/groups/me",
            headers=auth_headers,
        )
        assert get_my_groups_response.status == 200
        content = await get_my_groups_response.read()
        assert content is not None
        data = msgspec.json.decode(
            content, type=PagedResponse[ExtendedGroupSchema]
        )
        assert not any(group.id_ == new_group_data.id_ for group in data.data)

    @pytest.mark.usefixtures("as_superuser")
    async def test_leave_group_success_for_super_user(
        self,
        auth_headers: dict[str, str],
        test_client: TestClient,
        user: tuple[CreateUserSchema, UserSchema],
    ) -> None:
        _, user_out = user
        new_group_response = await test_client.post(
            "/groups",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "name": "New Group",
                        "description": "A new group for testing",
                    }
                ),
            ),
        )
        content = await new_group_response.read()
        assert content is not None
        new_group_data = msgspec.json.decode(content, type=ExtendedGroupSchema)

        _ = await test_client.patch(
            f"/groups/join/{new_group_data.id_}",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "userIds": [user_out.id_],
                    }
                ),
            ),
        )

        response = await test_client.patch(
            f"/groups/leave/{new_group_data.id_}",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "userIds": [user_out.id_],
                    }
                ),
            ),
        )
        assert response.status == 204

        get_my_groups_response = await test_client.get(
            "/groups/me",
            headers=auth_headers,
        )
        assert get_my_groups_response.status == 200
        content = await get_my_groups_response.read()
        assert content is not None
        data = msgspec.json.decode(
            content, type=PagedResponse[ExtendedGroupSchema]
        )
        assert not any(group.id_ == new_group_data.id_ for group in data.data)

    async def test_leave_group_fails_for_normal_user(
        self,
        auth_headers: dict[str, str],
        test_client: TestClient,
        user: tuple[CreateUserSchema, UserSchema],
    ):
        _, user_out = user
        response = await test_client.patch(
            f"/groups/leave/{uuid4()}",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "userIds": [user_out.id_],
                    }
                ),
            ),
        )

        assert response.status == 403
        content = await response.read()
        assert content == b"Forbidden"

    @pytest.mark.usefixtures("as_superuser")
    async def test_leave_group_fails_for_inexistent_group(
        self,
        auth_headers: dict[str, str],
        test_client: TestClient,
        user: tuple[CreateUserSchema, UserSchema],
    ) -> None:
        _, user_out = user
        response = await test_client.patch(
            f"/groups/leave/{uuid4()}",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "userIds": [user_out.id_],
                    }
                ),
            ),
        )

        assert response.status == 404
        content = await response.read()
        assert content is not None
        data = msgspec.json.decode(content, type=dict)
        assert data["message"] == "Group not found"
        assert data["status_code"] == 404

    @pytest.mark.usefixtures("as_superuser")
    async def test_leave_group_fails_for_non_member(
        self,
        auth_headers: dict[str, str],
        test_client: TestClient,
        user: tuple[CreateUserSchema, UserSchema],
    ):
        _, user_out = user
        new_group_response = await test_client.post(
            "/groups",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "name": "New Group",
                        "description": "A new group for testing",
                    }
                ),
            ),
        )
        content = await new_group_response.read()
        assert content is not None
        new_group_data = msgspec.json.decode(content, type=ExtendedGroupSchema)

        response = await test_client.patch(
            f"/groups/leave/{new_group_data.id_}",
            headers=auth_headers,
            content=Content(
                b"application/json",
                msgspec.json.encode(
                    {
                        "userIds": [user_out.id_],
                    }
                ),
            ),
        )

        assert response.status == 404
        content = await response.read()
        assert content is not None
        data = msgspec.json.decode(content, type=dict)
        assert data["message"] == "User not found"
        assert data["status_code"] == 404
