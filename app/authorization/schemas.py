from uuid import UUID

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


class CreateGroupSchema(CamelStruct):
    name: str
    description: str


class UpdateGroupSchema(CamelStruct):
    name: str | None = None
    description: str | None = None


class GroupSchema(DefaultSchema):
    name: str
    description: str


class ExtendedGroupSchema(GroupSchema):
    roles: list[RoleSchema]


class GroupRoleBindingSchema(CamelStruct):
    role_ids: list[UUID]

class GroupUserBindingSchema(CamelStruct):
    user_ids: list[UUID]
