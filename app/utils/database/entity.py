from datetime import datetime
from typing import Any, ClassVar, NewType
from uuid import UUID

import sqlalchemy as sa
from escudeiro.misc import timezone, to_snake
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    declared_attr,
    mapped_column,
)
from uuid_extensions import uuid7

Text = NewType("Text", str)
LongStr = NewType("LongStr", str)


class AbstractEntity(DeclarativeBase):
    type_annotation_map: ClassVar[dict[Any, Any]] = {
        datetime: sa.TIMESTAMP(timezone=True),
        Text: sa.Text(),
        LongStr: sa.String(255),
        str: sa.String(50),
    }


class CommonMixin:
    id_: Mapped[UUID] = mapped_column("id", primary_key=True, default=uuid7)

    @declared_attr.directive
    @classmethod
    def __tablename__(cls) -> str:
        return cls.make_tablename(cls.__module__, cls.__name__)

    @staticmethod
    def make_tablename(module: str, pascalname: str) -> str:
        _, modname, *_ = module.split(".")
        classname = to_snake(pascalname.removesuffix("Entity"))
        classname = classname.removesuffix("s") + "s"  # Ensure pluralization
        return f"{modname}__{classname}"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        "created_at", nullable=False, default=timezone.now
    )
    updated_at: Mapped[datetime] = mapped_column(
        "updated_at",
        nullable=False,
        default=timezone.now,
        onupdate=timezone.now,
    )


class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(
        "deleted_at", nullable=True, default=None
    )

    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def mark_as_deleted(self) -> None:
        self.deleted_at = timezone.now()


class DefaultEntity(
    AbstractEntity,
    CommonMixin,
    TimestampMixin,
    SoftDeleteMixin,
):
    __abstract__ = True
