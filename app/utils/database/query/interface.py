from datetime import date, time
from typing import Any, Protocol

import sqlalchemy as sa
from sqlalchemy.sql import Delete, Select, Update
from sqlalchemy.sql.elements import ColumnElement

type ExecutableType = Select[Any] | Update | Delete
type Sortable = int | float | date | time | str
type Comparison = ColumnElement[bool]
type FieldType = ColumnElement[Any] | sa.Column[Any]
type Mapper = sa.Table | type


class Comparator[T](Protocol):
    def __call__(self, field: FieldType, target: T) -> Comparison: ...


class BindClause(Protocol):
    def bind(self, mapper: Mapper) -> Comparison: ...


class ApplyClause[T: ExecutableType](Protocol):
    def apply(self, query: T) -> T: ...
