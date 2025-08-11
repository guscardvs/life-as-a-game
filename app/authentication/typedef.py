from typing import TYPE_CHECKING, ClassVar, Literal, TypedDict, cast

from blacksheep import Request
from guardpost import Identity

from app.users.schemas import UserSchema


class TokenClaims(TypedDict):
    sub: str  # Subject (user ID)
    exp: int  # Expiration time (timestamp)
    iat: int  # Issued at time (timestamp)
    jti: str  # JWT ID (unique identifier for the token)
    token_type: Literal[
        "access", "refresh"
    ]  # Type of token (access or refresh)


class Authentication(Identity):
    user_key: ClassVar[str] = "user"

    @property
    def user(self) -> UserSchema:
        return self[self.user_key]

    @user.setter
    def user(self, value: UserSchema) -> None:
        self.claims[self.user_key] = value

    @property
    def token(self) -> str:
        return cast(str, self.access_token)


Authenticated = "authenticated"

AuthenticatedRequest = Request  # pyright: ignore[reportAssignmentType]

if TYPE_CHECKING:

    class AuthenticatedRequest(Request):
        identity: Authentication  # pyright: ignore[reportIncompatibleVariableOverride]
