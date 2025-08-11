from escudeiro.context import atomic
from escudeiro.data import data

from app.roles import schemas
from app.roles.repository import RoleRepository
from app.utils.database import (
    AlwaysTrue,
    BindClause,
    SessionContext,
    Where,
    and_,
    comparison,
)
from app.utils.server import (
    FieldError,
    Page,
    already_exists,
    does_not_exist,
    unexpected_error,
)


@data
class CreateRoleUseCase:
    context: SessionContext
    payload: schemas.CreateRoleSchema

    async def execute(self) -> schemas.RoleSchema:
        context = atomic(self.context)
        repository = RoleRepository(context)
        async with context:
            await self._check_codename_exists(repository)
            return await repository.create(self._make_role())

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

    async def execute(self) -> tuple[list[schemas.RoleSchema], int]:
        repository = RoleRepository(self.context)
        results = await repository.fetch(
            repository.make_paged_query(self.page),
            AlwaysTrue(),  # TODO: add filters if needed
        )
        total = await repository.count(AlwaysTrue())
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
    role_id: int
    payload: schemas.UpdateRoleSchema

    async def execute(self) -> schemas.RoleSchema:
        context = atomic(self.context)
        repository = RoleRepository(context)
        async with context:
            role = await self._check_role_exists(repository)
            await self._check_codename_exists(repository)
            return await repository.update(
                Where("id", self.role_id), self._merge_content(role)
            )

    def _merge_content(self, role: schemas.RoleSchema) -> schemas.RoleSchema:
        if self.payload.codename is not None:
            role.codename = self.payload.codename
        if self.payload.description is not None:
            role.description = self.payload.description
        return role

    async def _check_role_exists(self, repository: RoleRepository):
        return await repository.get(Where("id", self.role_id))

    async def _check_codename_exists(self, repository: RoleRepository):
        if self.payload.codename and await repository.exists(
            and_(
                Where("codename", self.payload.codename),
                Where("id", self.role_id, comparison.not_equals),
            ),
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
