from collections.abc import Callable
from datetime import date, datetime, time
from typing import Any
from uuid import UUID

import msgspec
import sqlalchemy as sa
from escudeiro.context import atomic
from escudeiro.data import data
from escudeiro.misc import exclude_none
from msgspec.structs import fields

from app.utils.server import Page, does_not_exist, validation_error

from .adapter import SessionContext
from .entity import AbstractEntity
from .query.interface import ApplyClause, BindClause
from .query.paginate import FieldPaginate


def to_builtins_noalias(schema: msgspec.Struct) -> dict[str, Any]:
    """
    Convert a msgspec schema to a dictionary without aliasing.
    """
    schema_type = type(schema)
    output = msgspec.to_builtins(
        schema, builtin_types=(datetime, date, time, UUID)
    )
    for field in fields(schema_type):
        output[field.name] = output.pop(
            field.encode_name, output.get(field.name)
        )
    return exclude_none(output)


@data
class Repository[T: AbstractEntity, S: msgspec.Struct]:
    """
    Repository for a specific entity.
    """

    context: SessionContext
    entity: type[T]
    to_schema: Callable[[T], S]
    to_entity: Callable[[S], T]

    def merge_entity(self, in_db: T, schema: S) -> T:
        for field in fields(schema):
            schema_value = getattr(schema, field.name)
            if not isinstance(schema_value, msgspec.Struct | list):
                # ignore relationships
                setattr(in_db, field.name, schema_value)

        return in_db

    @classmethod
    def make_paged_query(cls, page: Page) -> ApplyClause[sa.Select[Any]]:
        """
        Create a BindClause for pagination.
        """
        return FieldPaginate(limit=page.limit, offset=page.last_id)

    def get_base_select(self) -> sa.Select[Any]:
        return sa.select(self.entity)

    async def get(self, clause: BindClause) -> S:
        statement = (
            self.get_base_select().where(clause.bind(self.entity)).limit(1)
        )

        async with self.context as session:
            result = await session.execute(statement)
            first = result.scalars().first()
            if first is None:
                raise does_not_exist(
                    self.entity.__name__.removesuffix("Entity")
                )
            return self.to_schema(first)

    async def fetch(
        self, apply: ApplyClause[sa.Select[Any]], clause: BindClause
    ) -> list[S]:
        statement = apply.apply(self.get_base_select()).where(
            clause.bind(self.entity)
        )

        async with self.context as session:
            result = await session.execute(statement)
            return list(map(self.to_schema, result.scalars().all()))

    async def create(self, schema: S) -> S:
        async with atomic(self.context) as session:
            entity = self.to_entity(schema)
            session.add(entity)
        return schema

    async def update(self, clause: BindClause, schema: S) -> S:
        select_statement = (
            self.get_base_select().where(clause.bind(self.entity)).limit(1)
        )
        async with atomic(self.context) as session:
            entity = await session.execute(select_statement)
            entity = entity.scalars().first()
            if entity is None:
                raise does_not_exist(
                    self.entity.__name__.removesuffix("Entity")
                )
            _ = self.merge_entity(entity, schema)
            await session.flush([entity])

            return self.to_schema(entity)

    async def delete(self, clause: BindClause) -> None:
        async with atomic(self.context) as session:
            statement = sa.delete(self.entity).where(clause.bind(self.entity))
            result = await session.execute(statement)
            if result.rowcount == 0:
                raise does_not_exist(
                    self.entity.__name__.removesuffix("Entity")
                )
            if result.rowcount > 1:
                raise validation_error(
                    "Multiple entities deleted, expected only one."
                )

    async def count(self, clause: BindClause) -> int:
        statement = (
            sa.select(sa.func.count())
            .select_from(self.entity)
            .where(clause.bind(self.entity))
        )

        async with self.context as session:
            result = await session.execute(statement)
            return result.scalar_one()

    async def exists(self, clause: BindClause) -> bool:
        statement = sa.select(sa.exists().where(clause.bind(self.entity)))

        async with self.context as session:
            result = await session.execute(statement)
            return result.scalar_one()
