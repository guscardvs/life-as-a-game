# pyright: reportImportCycles=false
from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.users.entities import (
    UserEntity,
)
from app.utils.database import (
    DefaultEntity,
    LongStr,
    Text,
    create_relation_table,
)

roles_groups_name = DefaultEntity.make_tablename(__name__, "RolesGroups")
users_groups_name = DefaultEntity.make_tablename(__name__, "UsersGroups")


class RoleEntity(DefaultEntity):
    codename: Mapped[LongStr] = mapped_column(unique=True)
    description: Mapped[Text] = mapped_column()
    groups = relationship(
        "GroupEntity",
        roles_groups_name,
        back_populates="roles",
    )

    if TYPE_CHECKING:
        groups: Mapped[list["GroupEntity"]]


class GroupEntity(DefaultEntity):
    name: Mapped[LongStr] = mapped_column(unique=True)
    description: Mapped[Text] = mapped_column()

    roles: Mapped[list[RoleEntity]] = relationship(
        "RoleEntity",
        roles_groups_name,
        back_populates="groups",
        lazy="selectin",
    )
    users: Mapped[list[UserEntity]] = relationship(
        "UserEntity",
        users_groups_name,
        back_populates="groups",
    )


RolesGroups = create_relation_table(
    roles_groups_name,
    RoleEntity.__tablename__,
    GroupEntity.__tablename__,
)

UsersGroups = create_relation_table(
    users_groups_name,
    UserEntity.__tablename__,
    GroupEntity.__tablename__,
)
