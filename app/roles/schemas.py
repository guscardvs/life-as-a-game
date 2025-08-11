from escudeiro.contrib.msgspec import CamelStruct

from app.utils.msgspec import DefaultSchema


class CreateRoleSchema(CamelStruct):
    codename: str
    description: str


class UpdateRoleSchema(CamelStruct):
    codename: str | None = None
    description: str | None = None


class RoleSchema(DefaultSchema):
    codename: str
    description: str
