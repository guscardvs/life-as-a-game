from collections.abc import Callable
from typing import Any

import msgspec
import sqlalchemy as sa
from escudeiro.context import atomic
from escudeiro.data import data

from app.utils.server import Page, does_not_exist, validation_error

from .adapter import SessionContext
from .entity import AbstractEntity
from .query.interface import ApplyClause, BindClause
from .query.paginate import FieldPaginate


@data
class Repository[T: AbstractEntity, S: msgspec.Struct]:
    """
    Repository for a specific entity.
    """

    context: SessionContext
    entity: type[T]
    to_schema: Callable[[T], S]
    to_entity: Callable[[S], T]

    @classmethod
    def make_paged_query(cls, page: Page) -> ApplyClause[sa.Select[Any]]:
        """
        Create a BindClause for pagination.
        """
        return FieldPaginate(limit=page.limit, offset=page.last_id)

    async def get(self, clause: BindClause) -> S:
        statement = (
            sa.select(self.entity).where(clause.bind(self.entity)).limit(1)
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
        statement = apply.apply(sa.select(self.entity)).where(
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
        async with atomic(self.context) as session:
            statement = (
                sa.update(self.entity)
                .where(clause.bind(self.entity))
                .values(**msgspec.to_builtins(schema))
            )
            result = await session.execute(statement)
            if result.rowcount == 0:
                raise does_not_exist(
                    self.entity.__name__.removesuffix("Entity")
                )
            if result.rowcount > 1:
                raise validation_error(
                    "Multiple entities updated, expected only one."
                )
        return schema

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
