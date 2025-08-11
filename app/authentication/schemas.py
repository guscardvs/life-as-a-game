from blacksheep import FromQuery
from escudeiro.contrib.msgspec import CamelStruct, SquireStruct

from app.utils.msgspec import NotEmptyString


class SessionResponse(SquireStruct, kw_only=True):
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "Bearer"


class CreateSessionResponse(SessionResponse):
    jti: str


class AuthSchema(CamelStruct):
    username: NotEmptyString
    password: NotEmptyString


class RefreshTokenSchema(CamelStruct):
    token: NotEmptyString


class FullLogoutQuery(FromQuery[bool]):
    name = "full_logout"
