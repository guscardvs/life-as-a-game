from sqlalchemy.orm import Mapped, mapped_column

from app.utils.database import DefaultEntity, LongStr, Text


class RoleEntity(DefaultEntity):
    codename: Mapped[LongStr] = mapped_column(unique=True)
    description: Mapped[Text] = mapped_column()
