from abc import ABC, abstractmethod
from typing import Any, override

from escudeiro.data import data
from sqlalchemy.sql import Select

from app.utils.database.query import comparison

from .interface import ApplyClause, Comparator, Sortable
from .where import Where


@data
class Paginate(ApplyClause[Any], ABC):
    limit: int
    offset: int

    @abstractmethod
    @override
    def apply[S: Select[Any]](self, query: S) -> S:
        raise NotImplementedError

    @staticmethod
    def none():
        return _NullPaginate(limit=0, offset=0)

    def __bool__(self):
        return isinstance(self, _NullPaginate)


class LimitOffsetPaginate(Paginate):
    @override
    def apply[S: Select[Any]](self, query: S) -> S:
        return query.limit(self.limit).offset(self.offset)


@data
class FieldPaginate(Paginate):
    offset: Any
    field: str = "id"
    jump_comparison: Comparator[Sortable] = comparison.greater

    @override
    def apply[S: Select[Any]](self, query: S) -> S:
        return query.where(
            Where(self.field, self.offset, self.jump_comparison).bind(
                query.selected_columns  # pyright: ignore[reportArgumentType]
            )
        ).limit(self.limit)


class _NullPaginate(Paginate):
    @override
    def apply[S: Select[Any]](self, query: S) -> S:
        return query
