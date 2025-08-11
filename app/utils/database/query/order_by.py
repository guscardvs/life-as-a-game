from typing import Any

from escudeiro.data import data
from escudeiro.misc import ValueEnum
from sqlalchemy.sql import ColumnElement, Select


class OrderDirection(ValueEnum):
    ASC = "asc"
    DESC = "desc"


@data
class OrderBy:
    field: str | None
    direction: OrderDirection

    @property
    def _should_apply(self):
        return self.field is not None

    @classmethod
    def none(cls):
        return cls(field=None, direction=OrderDirection.ASC)

    @classmethod
    def asc(cls, field: str):
        return cls(field, OrderDirection.ASC)

    @classmethod
    def desc(cls, field: str):
        return cls(field, OrderDirection.DESC)

    def apply[S: Select[Any]](self, query: S) -> S:
        return (
            query.order_by(self._apply_order(self._find_column(query)))
            if self._should_apply
            else query
        )

    def _find_column(self, query: Select[Any]) -> ColumnElement[Any]:
        try:
            return next(
                col for col in query.selected_columns if col.key == self.field
            )
        except StopIteration:
            raise ValueError(
                f"Field {self.field} does not exist in query"
            ) from None

    def _apply_order(self, col: ColumnElement[Any]) -> ColumnElement[Any]:
        return col.asc() if self.direction is OrderDirection.ASC else col.desc()
