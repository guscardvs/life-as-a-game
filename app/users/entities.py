from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.utils.database import DefaultEntity, LongStr, Text


def _users_groups():
    from app.authorization.entities import UsersGroups

    return UsersGroups


class UserEntity(DefaultEntity):
    email: Mapped[LongStr] = mapped_column(unique=True)
    password: Mapped[Text]
    full_name: Mapped[str]
    is_superuser: Mapped[bool] = mapped_column(default=False)
    birth_date: Mapped[date]
    last_login: Mapped[datetime | None] = mapped_column(default=None)
    groups = relationship("GroupEntity", _users_groups, back_populates="users")

    if TYPE_CHECKING:
        from app.authorization.entities import GroupEntity

        groups: Mapped[list[GroupEntity]]
