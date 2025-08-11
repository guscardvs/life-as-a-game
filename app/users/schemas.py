import re
from datetime import date, datetime

from escudeiro.contrib.msgspec import CamelStruct

from app.utils.msgspec import DefaultSchema, NotEmptyString
from app.utils.server import FieldError, validation_error

special_chars = re.compile(r"[@_!#$%^&*()<>?/\|}{~:]")


class CreateUserSchema(CamelStruct):
    email: NotEmptyString
    password: NotEmptyString
    full_name: NotEmptyString
    birth_date: date

    def __post_init__(self):
        self.validate_password()

    def validate_password(self):
        errors = []
        if len(self.password) < 8:
            errors.append("Password must be at least 8 characters long.")
        if not any(char.isdigit() for char in self.password):
            errors.append("Password must contain at least one digit.")
        if not any(char.isupper() for char in self.password):
            errors.append(
                "Password must contain at least one uppercase letter."
            )
        if not any(char.islower() for char in self.password):
            errors.append(
                "Password must contain at least one lowercase letter."
            )
        if not special_chars.search(self.password):
            errors.append(
                "Password must contain at least one special character."
            )

        if errors:
            raise validation_error(
                "Invalid password",
                [
                    FieldError(name="password", detail=error)
                    for error in errors
                ],
            )


class UpdateUserSchema(CamelStruct):
    email: NotEmptyString | None = None
    password: NotEmptyString | None = None
    full_name: NotEmptyString | None = None
    birth_date: date | None = None


class UserOutSchema(DefaultSchema):
    email: NotEmptyString
    full_name: NotEmptyString
    is_superuser: bool
    birth_date: date
    last_login: datetime | None = None


class UserSchema(UserOutSchema, kw_only=True):
    password: NotEmptyString
