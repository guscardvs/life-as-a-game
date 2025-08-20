from typing import Any, override
from uuid import UUID

import sqlalchemy as sa
from escudeiro.context import atomic

from app.authorization import schemas
from app.authorization.entities import (
    GroupEntity,
    RoleEntity,
    RolesGroups,
    UsersGroups,
)
from app.users.entities import UserEntity
from app.utils.database import Repository, SessionContext
from app.utils.database.tables import get_entity_column_name
from app.utils.server.exceptions import unexpected_error


class RoleRepository(Repository[RoleEntity, schemas.RoleSchema]):
    """
    Repository for RoleEntity.
    """

    def __init__(self, context: SessionContext):
        super().__init__(
            context=context,
            entity=RoleEntity,
            to_schema=schemas.RoleSchema.to_schema,
            to_entity=self._to_entity,
        )

    def _to_entity(self, schema: schemas.RoleSchema) -> RoleEntity:
        return RoleEntity(
            id_=schema.id_,
            created_at=schema.created_at,
            updated_at=schema.updated_at,
            deleted_at=schema.deleted_at,
            codename=schema.codename,
            description=schema.description,
        )


class GroupRepository(Repository[GroupEntity, schemas.ExtendedGroupSchema]):
    """
    Repository for GroupEntity.
    """

    def __init__(self, context: SessionContext):
        super().__init__(
            context=context,
            entity=GroupEntity,
            to_schema=schemas.ExtendedGroupSchema.to_schema,
            to_entity=self._to_entity,
        )

    def _to_entity(self, schema: schemas.ExtendedGroupSchema) -> GroupEntity:
        return GroupEntity(
            id_=schema.id_,
            created_at=schema.created_at,
            updated_at=schema.updated_at,
            deleted_at=schema.deleted_at,
            name=schema.name,
            description=schema.description,
        )

    async def attach_roles(self, group_id: UUID, role_ids: list[UUID]) -> None:
        statement = sa.insert(RolesGroups).values(
            [
                {
                    get_entity_column_name(
                        GroupEntity.__tablename__
                    ): group_id,
                    get_entity_column_name(RoleEntity.__tablename__): role_id,
                }
                for role_id in role_ids
            ]
        )
        async with atomic(self.context) as session:
            result = await session.execute(statement)
            if not result.rowcount:
                raise unexpected_error()

    async def detach_roles(self, group_id: UUID, role_ids: list[UUID]) -> None:
        statement = sa.delete(RolesGroups).where(
            sa.and_(
                getattr(
                    RolesGroups.c,
                    get_entity_column_name(GroupEntity.__tablename__),
                )
                == group_id,
                getattr(
                    RolesGroups.c,
                    get_entity_column_name(RoleEntity.__tablename__),
                ).in_(role_ids),
            )
        )
        async with atomic(self.context) as session:
            result = await session.execute(statement)
            if not result.rowcount:
                raise unexpected_error()
            if result.rowcount != len(role_ids):
                raise unexpected_error()

    async def has_roles(self, group_id: UUID, role_ids: list[UUID]) -> bool:
        statement = sa.select(
            sa.exists().where(
                sa.and_(
                    getattr(
                        RolesGroups.c,
                        get_entity_column_name(GroupEntity.__tablename__),
                    )
                    == group_id,
                    getattr(
                        RolesGroups.c,
                        get_entity_column_name(RoleEntity.__tablename__),
                    ).in_(role_ids),
                )
            )
        )
        async with atomic(self.context) as session:
            result = await session.execute(statement)
            return result.unique().scalar_one()

    async def is_role_attached(self, role_id: UUID) -> bool:
        statement = sa.select(
            sa.exists().where(
                getattr(
                    RolesGroups.c,
                    get_entity_column_name(RoleEntity.__tablename__),
                )
                == role_id
            )
        )
        async with atomic(self.context) as session:
            result = await session.execute(statement)
            return result.unique().scalar_one()

    @override
    def get_base_select(self) -> sa.Select[Any]:
        return super().get_base_select().outerjoin(GroupEntity.users)

    async def join_group(self, group_id: UUID, users: list[UUID]) -> None:
        statement = sa.insert(UsersGroups).values(
            [
                {
                    get_entity_column_name(UserEntity.__tablename__): user_id,
                    get_entity_column_name(
                        GroupEntity.__tablename__
                    ): group_id,
                }
                for user_id in users
            ]
        )
        async with atomic(self.context) as session:
            result = await session.execute(statement)
            if not result.rowcount:
                raise unexpected_error()

    async def leave_group(self, group_id: UUID, users: list[UUID]) -> None:
        statement = sa.delete(UsersGroups).where(
            sa.and_(
                getattr(
                    UsersGroups.c,
                    get_entity_column_name(GroupEntity.__tablename__),
                )
                == group_id,
                getattr(
                    UsersGroups.c,
                    get_entity_column_name(UserEntity.__tablename__),
                ).in_(users),
            )
        )
        async with atomic(self.context) as session:
            result = await session.execute(statement)
            if not result.rowcount:
                raise unexpected_error()
            if result.rowcount != len(users):
                raise unexpected_error()

    async def are_users_in_group(
        self, group_id: UUID, user_ids: list[UUID]
    ) -> bool:
        statement = sa.select(
            sa.exists().where(
                sa.and_(
                    getattr(
                        UsersGroups.c,
                        get_entity_column_name(GroupEntity.__tablename__),
                    )
                    == group_id,
                    getattr(
                        UsersGroups.c,
                        get_entity_column_name(UserEntity.__tablename__),
                    ).in_(user_ids),
                )
            )
        )
        async with atomic(self.context) as session:
            result = await session.execute(statement)
            return result.unique().scalar_one()
