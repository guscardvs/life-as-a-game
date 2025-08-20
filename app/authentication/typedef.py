from collections.abc import Sequence
from typing import TYPE_CHECKING, ClassVar, Literal, TypedDict, cast

from blacksheep import Request
from guardpost import Identity

from app.users.schemas import UserSchema


class TokenClaims(TypedDict):
    sub: str  # Subject (user ID)
    exp: int  # Expiration time (timestamp)
    iat: int  # Issued at time (timestamp)
    jti: str  # JWT ID (unique identifier for the token)
    tid: str  # Token ID (unique identifier for the session)
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

    @property
    def roles(self) -> Sequence[str]:
        return cast(Sequence[str], self.claims.get("roles", []))

    @roles.setter
    def roles(self, value: Sequence[str]) -> None:
        self.claims["roles"] = value

    @property
    def groups(self) -> Sequence[str]:
        return cast(Sequence[str], self.claims.get("groups", []))

    @groups.setter
    def groups(self, value: Sequence[str]) -> None:
        self.claims["groups"] = value

    def roles_intersect(self, roles: Sequence[str]) -> bool:
        return bool(set(self.roles) & set(roles))


Authenticated = "authenticated"

AuthenticatedRequest = Request  # pyright: ignore[reportAssignmentType]

if TYPE_CHECKING:

    class AuthenticatedRequest(Request):
        identity: Authentication  # pyright: ignore[reportIncompatibleVariableOverride]
