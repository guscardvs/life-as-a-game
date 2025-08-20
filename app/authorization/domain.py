from uuid import UUID

from escudeiro.context import atomic
from escudeiro.data import data
from escudeiro.misc import next_or

from app.authorization import schemas
from app.authorization.repository import GroupRepository, RoleRepository
from app.users.repository import UserRepository
from app.authorization.typedef import ADMIN_ROLE_NAME
from app.users.schemas import UserOutSchema
from app.utils.database import (
    AlwaysTrue,
    BindClause,
    SessionContext,
    Where,
    and_,
    comparison,
)
from app.utils.database.query.order_by import OrderBy
from app.utils.server import (
    FieldError,
    Page,
    already_exists,
    does_not_exist,
    unexpected_error,
)
from app.utils.server.exceptions import unauthorized_error


@data
class CreateRoleUseCase:
    context: SessionContext
    payload: schemas.CreateRoleSchema

    async def execute(self) -> schemas.RoleSchema:
        self._deny_new_admin_role()
        context = atomic(self.context)
        repository = RoleRepository(context)
        async with context:
            await self._check_codename_exists(repository)
            return await repository.create(self._make_role())

    def _deny_new_admin_role(self):
        if self.payload.codename == ADMIN_ROLE_NAME:
            raise unauthorized_error()

    def _make_role(self) -> schemas.RoleSchema:
        return schemas.RoleSchema(
            codename=self.payload.codename,
            description=self.payload.description,
            **schemas.RoleSchema.make_create_content(),
        )

    async def _check_codename_exists(self, repository: RoleRepository):
        if await repository.exists(Where("codename", self.payload.codename)):
            raise already_exists(
                "Role",
                [
                    FieldError(
                        "codename",
                        f"Codename {self.payload.codename} already exists",
                    )
                ],
            )


@data
class ListRolesUseCase:
    context: SessionContext
    page: Page
    clause: BindClause = AlwaysTrue()

    async def execute(self) -> tuple[list[schemas.RoleSchema], int]:
        repository = RoleRepository(self.context)
        results = await repository.fetch(
            repository.make_paged_query(self.page),
            self.clause,
        )
        total = await repository.count(self.clause)
        return results, total


@data
class GetRoleUseCase:
    context: SessionContext
    clause: BindClause

    async def execute(self) -> schemas.RoleSchema:
        return await RoleRepository(self.context).get(self.clause)


@data
class UpdateRoleUseCase:
    context: SessionContext
    role_id: UUID
    payload: schemas.UpdateRoleSchema

    async def execute(self) -> schemas.RoleSchema:
        context = atomic(self.context)
        repository = RoleRepository(context)
        async with context:
            role = await self._check_role_exists(repository)
            self._deny_update_admin_role(role)
            await self._check_codename_exists(repository, role)
            return await repository.update(
                Where("id", self.role_id), self._merge_content(role)
            )

    def _deny_update_admin_role(self, role: schemas.RoleSchema):
        if (
            role.codename == ADMIN_ROLE_NAME
            or self.payload.codename == ADMIN_ROLE_NAME
        ):
            raise unauthorized_error()

    def _merge_content(self, role: schemas.RoleSchema) -> schemas.RoleSchema:
        if self.payload.codename is not None:
            role.codename = self.payload.codename
        if self.payload.description is not None:
            role.description = self.payload.description
        return role

    async def _check_role_exists(self, repository: RoleRepository):
        return await repository.get(Where("id", self.role_id))

    async def _check_codename_exists(
        self, repository: RoleRepository, in_db: schemas.RoleSchema
    ):
        if (
            self.payload.codename
            and in_db.codename != self.payload.codename
            and await repository.exists(
                and_(
                    Where("codename", self.payload.codename),
                    Where("id", self.role_id, comparison.not_equals),
                ),
            )
        ):
            raise already_exists(
                "Role",
                [
                    FieldError(
                        "codename",
                        f"Codename {self.payload.codename} already exists",
                    )
                ],
            )


@data
class DeleteRoleUseCase:
    context: SessionContext
    clause: BindClause

    async def execute(self) -> None:
        context = atomic(self.context)
        repository = RoleRepository(context)
        async with context:
            await self._check_delete_impacts(repository)
            await repository.delete(self.clause)

    async def _check_delete_impacts(self, repository: RoleRepository):
        count = await repository.count(self.clause)
        if count == 0:
            raise does_not_exist("Role")
        if count > 1:
            raise unexpected_error("Multiple roles found for deletion")


@data
class CreateGroupUseCase:
    context: SessionContext
    payload: schemas.CreateGroupSchema

    async def execute(self) -> schemas.ExtendedGroupSchema:
        context = atomic(self.context)
        repository = GroupRepository(context)
        async with context:
            await self._check_name_exists(repository)
            return await repository.create(self._make_group())

    def _make_group(self) -> schemas.ExtendedGroupSchema:
        return schemas.ExtendedGroupSchema(
            name=self.payload.name,
            description=self.payload.description,
            roles=[],
            **schemas.GroupSchema.make_create_content(),
        )

    async def _check_name_exists(self, repository: GroupRepository):
        if await repository.exists(Where("name", self.payload.name)):
            raise already_exists(
                "Group",
                [
                    FieldError(
                        "name",
                        f"Name {self.payload.name} already exists",
                    )
                ],
            )


@data
class GetGroupUseCase:
    context: SessionContext
    clause: BindClause

    async def execute(self) -> schemas.ExtendedGroupSchema:
        return await GroupRepository(self.context).get(self.clause)


@data
class ListGroupsUseCase:
    context: SessionContext
    page: Page
    clause: BindClause = AlwaysTrue()

    async def execute(self) -> tuple[list[schemas.ExtendedGroupSchema], int]:
        repository = GroupRepository(self.context)
        results = await repository.fetch(
            repository.make_paged_query(self.page),
            self.clause,
        )
        total = await repository.count(self.clause)
        return results, total


@data
class UpdateGroupUseCase:
    context: SessionContext
    group_id: UUID
    payload: schemas.UpdateGroupSchema

    async def execute(self) -> schemas.ExtendedGroupSchema:
        context = atomic(self.context)
        repository = GroupRepository(context)
        async with context:
            await self._check_name_exists(repository)
            group = await self._check_group_exists(repository)
            return await repository.update(
                Where("id", self.group_id), self._merge_content(group)
            )

    def _merge_content(
        self, group: schemas.ExtendedGroupSchema
    ) -> schemas.ExtendedGroupSchema:
        if self.payload.name is not None:
            group.name = self.payload.name
        if self.payload.description is not None:
            group.description = self.payload.description
        return group

    async def _check_group_exists(self, repository: GroupRepository):
        return await repository.get(Where("id", self.group_id))

    async def _check_name_exists(self, repository: GroupRepository):
        if await repository.exists(Where("name", self.payload.name)):
            raise already_exists(
                "Group",
                [
                    FieldError(
                        "name",
                        f"Name {self.payload.name} already exists",
                    )
                ],
            )


@data
class DeleteGroupUseCase:
    context: SessionContext
    user: UserOutSchema
    group_id: UUID

    async def execute(self) -> None:
        context = atomic(self.context)
        repository = GroupRepository(context)
        async with context:
            await self._check_group_exists(repository)
            await self._check_admin_permission(repository)
            await repository.delete(Where("id", self.group_id))

    async def _check_group_exists(self, repository: GroupRepository):
        if not await repository.exists(Where("id", self.group_id)):
            raise does_not_exist("Group")

    async def _check_admin_permission(self, repository: GroupRepository):
        role_repository = RoleRepository(self.context)
        admin_role = next_or(
            await role_repository.fetch(
                OrderBy.none(),
                Where("codename", ADMIN_ROLE_NAME),
            )
        )
        if not admin_role:
            return
        if not self.user.is_superuser and await repository.has_roles(
            self.group_id, [admin_role.id_]
        ):
            raise unauthorized_error()


@data
class AttachRolesToGroup:
    context: SessionContext
    user: UserOutSchema
    group_id: UUID
    role_ids: list[UUID]

    async def execute(self) -> None:
        context = atomic(self.context)
        repository = GroupRepository(context)
        role_repository = RoleRepository(context)
        async with context:
            await self._check_group_exists(repository)
            await self._check_admin_permissions(repository, role_repository)
            await self._check_roles_exist(role_repository)
            await self._check_roles_already_attached(repository)
            await repository.attach_roles(self.group_id, self.role_ids)

    async def _check_admin_permissions(
        self,
        group_repository: GroupRepository,
        role_repository: RoleRepository,
    ):
        admin_role = next_or(
            await role_repository.fetch(
                OrderBy.none(),
                and_(
                    Where("id", self.role_ids, comparison.includes),
                    Where("codename", ADMIN_ROLE_NAME),
                ),
            )
        )
        if admin_role is None:
            return
        if not self.user.is_superuser:
            raise unauthorized_error()
        if await group_repository.is_role_attached(admin_role.id_):
            raise unauthorized_error()

    async def _check_group_exists(self, repository: GroupRepository):
        if not await repository.exists(Where("id", self.group_id)):
            raise does_not_exist("Group")

    async def _check_roles_exist(self, repository: RoleRepository) -> None:
        roles = await repository.fetch(
            OrderBy.none(),
            and_(
                Where("id", self.role_ids, comparison.includes),
                Where("deleted_at", True, comparison.isnull),
            ),
        )
        if not roles:
            raise does_not_exist("Role")
        if len(roles) != len(self.role_ids):
            raise does_not_exist("Role")

    async def _check_roles_already_attached(
        self, repository: GroupRepository
    ) -> None:
        if await repository.has_roles(self.group_id, self.role_ids):
            raise already_exists(
                "Role",
                [
                    FieldError(
                        "id",
                        f"Roles {self.role_ids} are already attached to the group",
                    )
                ],
            )


@data
class DetachRolesFromGroup:
    context: SessionContext
    user: UserOutSchema
    group_id: UUID
    role_ids: list[UUID]

    async def execute(self) -> None:
        context = atomic(self.context)
        repository = GroupRepository(context)
        role_repository = RoleRepository(context)
        async with context:
            await self._check_group_exists(repository)
            await self._check_admin_permission(repository, role_repository)
            await self._check_roles_exist(role_repository, repository)
            await repository.detach_roles(self.group_id, self.role_ids)

    async def _check_admin_permission(
        self,
        group_repository: GroupRepository,
        role_repository: RoleRepository,
    ):
        admin_role = next_or(
            await role_repository.fetch(
                OrderBy.none(),
                and_(
                    Where("id", self.role_ids, comparison.includes),
                    Where("codename", ADMIN_ROLE_NAME),
                ),
            )
        )
        if admin_role is None:
            return
        if not self.user.is_superuser:
            raise unauthorized_error()
        if await group_repository.is_role_attached(admin_role.id_):
            raise unauthorized_error()

    async def _check_group_exists(self, repository: GroupRepository):
        if not await repository.exists(Where("id", self.group_id)):
            raise does_not_exist("Group")

    async def _check_roles_exist(
        self, repository: RoleRepository, group_repository: GroupRepository
    ) -> None:
        roles = await repository.fetch(
            OrderBy.none(),
            and_(
                Where("id", self.role_ids, comparison.includes),
                Where("deleted_at", True, comparison.isnull),
            ),
        )
        if not roles:
            raise does_not_exist("Role")
        if not await group_repository.has_roles(self.group_id, self.role_ids):
            raise does_not_exist("Role")


@data
class JoinGroup:
    context: SessionContext
    user: UserOutSchema
    group_id: UUID
    user_ids: list[UUID]

    async def execute(self) -> None:
        context = atomic(self.context)
        repository = GroupRepository(context)
        async with context:
            await self._check_group_exists(repository)
            await self._check_users_exist(UserRepository(context))
            await self._check_duplicate_user(repository)
            await repository.join_group(self.group_id, self.user_ids)

    async def _check_duplicate_user(self, repository: GroupRepository):
        if await repository.are_users_in_group(self.group_id, self.user_ids):
            raise already_exists(
                "User",
                [
                    FieldError(
                        "id",
                        f"Users {self.user_ids} are already in the group",
                    )
                ],
            )

    async def _check_group_exists(self, repository: GroupRepository):
        if not await repository.exists(Where("id", self.group_id)):
            raise does_not_exist("Group")

    async def _check_users_exist(self, repository: UserRepository):
        users = await repository.fetch(
            OrderBy.none(),
            Where(
                "id",
                self.user_ids,
                comparison.includes,
            ),
        )
        if not users:
            raise does_not_exist("User")
        if len(users) != len(self.user_ids):
            raise does_not_exist("User")


@data
class LeaveGroup:
    context: SessionContext
    user: UserOutSchema
    group_id: UUID
    user_ids: list[UUID]

    async def execute(self) -> None:
        context = atomic(self.context)
        repository = GroupRepository(context)
        async with context:
            await self._check_group_exists(repository)
            await self._check_users_exist(UserRepository(context))
            await self._check_duplicate_user(repository)
            await repository.leave_group(self.group_id, self.user_ids)

    async def _check_duplicate_user(self, repository: GroupRepository):
        if not await repository.are_users_in_group(
            self.group_id, self.user_ids
        ):
            raise does_not_exist("User")

    async def _check_group_exists(self, repository: GroupRepository):
        if not await repository.exists(Where("id", self.group_id)):
            raise does_not_exist("Group")

    async def _check_users_exist(self, repository: UserRepository):
        users = await repository.fetch(
            OrderBy.none(),
            Where(
                "id",
                self.user_ids,
                comparison.includes,
            ),
        )
        if not users:
            raise does_not_exist("User")
        if len(users) != len(self.user_ids):
            raise does_not_exist("User")
