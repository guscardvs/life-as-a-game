from http import HTTPStatus

from blacksheep import Response, delete, get, patch, post

from app.authentication.handler import protected
from app.roles import schemas
from app.roles.domain import (
    CreateRoleUseCase,
    DeleteRoleUseCase,
    GetRoleUseCase,
    ListRolesUseCase,
    UpdateRoleUseCase,
)
from app.utils.database import SessionContext, Where
from app.utils.msgspec import FromMsgSpec, FromMsgSpecQuery
from app.utils.server import (
    DefaultController,
    Page,
    PagedResponse,
)


class RolesController(DefaultController):
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
        print(f"Fetching roles with pagination: {page.value}")
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
        self, role_id: int, context: SessionContext
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
    @protected
    async def create_role(
        self,
        payload: FromMsgSpec[schemas.CreateRoleSchema],
        context: SessionContext,
    ) -> schemas.RoleSchema:
        """
        Create a new role.
        """
        use_case = CreateRoleUseCase(
            context=context,
            payload=payload.value,
        )
        return await use_case.execute()

    @patch("/{role_id}")
    @protected
    async def update_role(
        self,
        role_id: int,
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
    @protected(responses={HTTPStatus.NO_CONTENT: "Role deleted"})
    async def delete_role(
        self, role_id: int, context: SessionContext
    ) -> Response:
        """
        Delete a role by ID.
        """
        # Implementation for deleting a role would go here
        use_case = DeleteRoleUseCase(
            context=context,
            clause=Where("id", role_id),
        )
        await use_case.execute()
        return Response(status=HTTPStatus.NO_CONTENT)
