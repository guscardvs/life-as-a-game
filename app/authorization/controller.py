from http import HTTPStatus
from uuid import UUID

from blacksheep import Response, delete, get, json, patch, post
from blacksheep.server.openapi.common import ContentInfo, ResponseInfo

from app.authentication.handler import protected
from app.authentication.typedef import Authentication
from app.authorization import schemas
from app.authorization.domain import (
    AttachRolesToGroup,
    CreateGroupUseCase,
    CreateRoleUseCase,
    DeleteGroupUseCase,
    DeleteRoleUseCase,
    DetachRolesFromGroup,
    GetGroupUseCase,
    GetRoleUseCase,
    JoinGroup,
    LeaveGroup,
    ListGroupsUseCase,
    ListRolesUseCase,
    UpdateGroupUseCase,
    UpdateRoleUseCase,
)
from app.authorization.typedef import ADMIN_ROLE_NAME, Admin
from app.users.schemas import UserOutSchema
from app.utils.database import SessionContext, Where, and_, comparison
from app.utils.msgspec import FromMsgSpec, FromMsgSpecQuery
from app.utils.server import (
    DefaultController,
    Page,
    PagedResponse,
)


class RolesController(DefaultController):
    @get("/me")
    @protected
    async def get_my_roles(
        self,
        context: SessionContext,
        identity: Authentication,
        page: FromMsgSpecQuery[Page] = FromMsgSpecQuery(Page()),
    ) -> PagedResponse[schemas.RoleSchema]:
        """
        Get all roles for the current user.
        """
        use_case = ListRolesUseCase(
            context,
            page.value,
            Where("codename", identity.roles, comparison.includes),
        )
        result, count = await use_case.execute()
        return PagedResponse[schemas.RoleSchema].from_data(
            data=result, page=page.value, total=count
        )

    @get()
    @protected
    async def get_roles(
        self,
        context: SessionContext,
        page: FromMsgSpecQuery[Page] = FromMsgSpecQuery(Page()),
    ) -> PagedResponse[schemas.RoleSchema]:
        """
        Get all roles.
        """
        use_case = ListRolesUseCase(context, page.value)
        roles, total = await use_case.execute()
        return PagedResponse[schemas.RoleSchema].from_data(
            data=roles, page=page.value, total=total
        )

    @get(
        "/find/{role_id}"
    )  #  using find here to not conflict with potential get methods
    @protected
    async def get_role(
        self, role_id: UUID, context: SessionContext
    ) -> schemas.RoleSchema:
        """
        Get a specific role by ID.
        """
        # Implementation for fetching a role by ID would go here
        use_case = GetRoleUseCase(context, Where("id", role_id))
        return await use_case.execute()

    @get("/find-by-codename/{codename}")
    @protected
    async def get_role_by_codename(
        self, codename: str, context: SessionContext
    ) -> schemas.RoleSchema:
        """
        Get a specific role by codename.
        """
        use_case = GetRoleUseCase(context, Where("codename", codename))
        return await use_case.execute()

    @post()
    @protected(
        policy=Admin,
        responses={
            HTTPStatus.CREATED: ResponseInfo(
                content=[ContentInfo(schemas.RoleSchema)],
                description="Role created successfully",
            )
        },
    )
    async def create_role(
        self,
        payload: FromMsgSpec[schemas.CreateRoleSchema],
        context: SessionContext,
    ) -> Response:
        """
        Create a new role.
        """
        use_case = CreateRoleUseCase(
            context=context,
            payload=payload.value,
        )
        result = await use_case.execute()
        return json(
            result,
            status=HTTPStatus.CREATED,
        )

    @patch("/{role_id}")
    @protected(policy=Admin)
    async def update_role(
        self,
        role_id: UUID,
        payload: FromMsgSpec[schemas.UpdateRoleSchema],
        context: SessionContext,
    ) -> schemas.RoleSchema:
        """
        Update an existing role.
        """
        # Implementation for updating a role would go here
        use_case = UpdateRoleUseCase(
            context=context,
            role_id=role_id,
            payload=payload.value,
        )
        return await use_case.execute()

    @delete("/{role_id}")
    @protected(
        responses={HTTPStatus.NO_CONTENT: "Role deleted"},
        policy=Admin,
    )
    async def delete_role(
        self, role_id: UUID, context: SessionContext
    ) -> Response:
        """
        Delete a role by ID.
        """
        # Implementation for deleting a role would go here
        use_case = DeleteRoleUseCase(
            context=context,
            clause=and_(
                Where("id", role_id),
                Where("codename", ADMIN_ROLE_NAME, comparison.not_equals),
            ),
        )
        await use_case.execute()
        return Response(status=HTTPStatus.NO_CONTENT)


class GroupsController(DefaultController):
    @get("/me")
    @protected
    async def get_my_groups(
        self,
        context: SessionContext,
        identity: Authentication,
        page: FromMsgSpecQuery[Page] = FromMsgSpecQuery(Page()),
    ) -> PagedResponse[schemas.ExtendedGroupSchema]:
        """
        Get all groups for the current user.
        """
        use_case = ListGroupsUseCase(
            context,
            page.value,
            Where("name", identity.groups, comparison.includes),
        )
        result, count = await use_case.execute()
        return PagedResponse[schemas.ExtendedGroupSchema].from_data(
            data=result, page=page.value, total=count
        )

    @get("/find-by-name/{name}")
    @protected
    async def get_group_by_name(
        self, name: str, context: SessionContext
    ) -> schemas.ExtendedGroupSchema:
        """
        Get a specific group by name.
        """
        use_case = GetGroupUseCase(context, Where("name", name))
        return await use_case.execute()

    @get("/find/{group_id}")
    @protected
    async def get_group_by_id(
        self, group_id: UUID, context: SessionContext
    ) -> schemas.ExtendedGroupSchema:
        """
        Get a specific group by ID.
        """
        use_case = GetGroupUseCase(context, Where("id", group_id))
        return await use_case.execute()

    @post()
    @protected(
        policy=Admin,
        responses={
            HTTPStatus.CREATED: ResponseInfo(
                content=[ContentInfo(schemas.ExtendedGroupSchema)],
                description="Group created successfully",
            )
        },
    )
    async def create_group(
        self,
        payload: FromMsgSpec[schemas.CreateGroupSchema],
        context: SessionContext,
    ) -> Response:
        """
        Create a new group.
        """
        use_case = CreateGroupUseCase(
            context=context,
            payload=payload.value,
        )
        result = await use_case.execute()
        return json(result, status=HTTPStatus.CREATED)

    @patch("/{group_id}")
    @protected(policy=Admin)
    async def update_group(
        self,
        group_id: UUID,
        payload: FromMsgSpec[schemas.UpdateGroupSchema],
        context: SessionContext,
    ) -> schemas.ExtendedGroupSchema:
        """
        Update an existing group.
        """
        use_case = UpdateGroupUseCase(
            context=context,
            group_id=group_id,
            payload=payload.value,
        )
        return await use_case.execute()

    @patch("/attach/{group_id}")
    @protected(
        responses={HTTPStatus.NO_CONTENT: "Roles attached"}, policy=Admin
    )
    async def attach_role_to_group(
        self,
        group_id: UUID,
        identity: Authentication,
        payload: FromMsgSpec[schemas.GroupRoleBindingSchema],
        context: SessionContext,
    ) -> Response:
        """
        Attach a role to a group.
        """
        use_case = AttachRolesToGroup(
            context=context,
            user=identity.user,
            group_id=group_id,
            role_ids=payload.value.role_ids,
        )
        await use_case.execute()
        return Response(status=HTTPStatus.NO_CONTENT)

    @patch("/detach/{group_id}")
    @protected(
        responses={HTTPStatus.NO_CONTENT: "Roles detached"}, policy=Admin
    )
    async def detach_role_from_group(
        self,
        group_id: UUID,
        identity: Authentication,
        payload: FromMsgSpec[schemas.GroupRoleBindingSchema],
        context: SessionContext,
    ) -> Response:
        """
        Detach a role from a group.
        """
        use_case = DetachRolesFromGroup(
            context=context,
            user=identity.user,
            group_id=group_id,
            role_ids=payload.value.role_ids,
        )
        await use_case.execute()
        return Response(status=HTTPStatus.NO_CONTENT)

    @patch("/join/{group_id}")
    @protected(policy=Admin)
    async def join_group(
        self,
        group_id: UUID,
        identity: Authentication,
        payload: FromMsgSpec[schemas.GroupUserBindingSchema],
        context: SessionContext,
    ) -> Response:
        """
        Attach users to a group.
        """
        use_case = JoinGroup(
            context=context,
            user=identity.user,
            group_id=group_id,
            user_ids=payload.value.user_ids,
        )
        await use_case.execute()
        return Response(status=HTTPStatus.NO_CONTENT)

    @patch("/leave/{group_id}")
    @protected(policy=Admin)
    async def leave_group(
        self,
        group_id: UUID,
        identity: Authentication,
        payload: FromMsgSpec[schemas.GroupUserBindingSchema],
        context: SessionContext,
    ) -> Response:
        """
        Detach users from a group.
        """
        use_case = LeaveGroup(
            context=context,
            user=identity.user,
            group_id=group_id,
            user_ids=payload.value.user_ids,
        )
        await use_case.execute()
        return Response(status=HTTPStatus.NO_CONTENT)

    @delete("/{group_id}")
    @protected(policy=Admin)
    async def delete_group(
        self,
        group_id: UUID,
        identity: Authentication,
        context: SessionContext,
    ) -> None:
        """
        Delete a group.
        """
        use_case = DeleteGroupUseCase(
            context=context,
            user=identity.user,
            group_id=group_id,
        )
        await use_case.execute()
