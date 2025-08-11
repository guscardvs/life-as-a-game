import hashlib
import hmac
import math
from datetime import datetime, timedelta
from typing import Any, cast
from uuid import UUID

import jwt
from escudeiro.data import data
from escudeiro.misc import timezone

from app.authentication.schemas import CreateSessionResponse
from app.authentication.typedef import TokenClaims
from app.settings import PRIMARY_SECRET
from app.users.domain import GetUserUseCase
from app.users.schemas import UserSchema
from app.utils.cache import CacheContext, asserts_async
from app.utils.database import SessionContext, Where
from app.utils.server import invalid_or_expired_token
from app.utils.server.exceptions import APIError, unexpected_error

ALGORITHM = "HS256"
JWT_TOKEN_EXPIRES = timedelta(minutes=5)
REFRESH_TOKEN_EXPIRES = timedelta(days=7)


@data
class AuthenticationService:
    context: SessionContext
    cache: CacheContext

    def encode_claims(self, payload: TokenClaims) -> str:
        return jwt.encode(
            cast(dict[str, Any], payload),
            PRIMARY_SECRET,
            ALGORITHM,
        )

    def decode_claims(
        self, token: str, verify_exp: bool = True
    ) -> TokenClaims:
        try:
            return cast(
                TokenClaims,
                jwt.decode(
                    token,
                    PRIMARY_SECRET,
                    algorithms=[ALGORITHM],
                    options={"verify_exp": verify_exp},
                ),
            )
        except jwt.PyJWTError as exc:
            raise invalid_or_expired_token() from exc

    async def create_session(self, user: UserSchema) -> CreateSessionResponse:
        """
        Creates a session for the user and returns the session response.
        """
        issued_at = timezone.now().replace(microsecond=0)
        user_id = user.id_.hex
        jti = self._generate_signature(user_id, issued_at)

        access_claims: TokenClaims = {
            "sub": user_id,
            "exp": self.as_timestamp(issued_at + JWT_TOKEN_EXPIRES),
            "iat": self.as_timestamp(issued_at),
            "jti": jti,
            "token_type": "access",
        }
        refresh_claims: TokenClaims = {
            "sub": user_id,
            "exp": self.as_timestamp(issued_at + REFRESH_TOKEN_EXPIRES),
            "iat": self.as_timestamp(issued_at),
            "jti": jti,
            "token_type": "refresh",
        }
        access_token = self.encode_claims(access_claims)
        refresh_token = self.encode_claims(refresh_claims)
        async with self.cache as cache:
            rowcount = await asserts_async(cache.hset)(
                user_id,
                jti,
                user_id,
            )
        if rowcount == 0:
            raise unexpected_error("Could not create session.")
        return CreateSessionResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=math.floor(JWT_TOKEN_EXPIRES.total_seconds()),
            jti=jti,
        )

    def _generate_signature(self, user_id: str, issued_at: datetime) -> str:
        """
        Generates a unique signature for the session.
        """
        return hmac.new(
            key=PRIMARY_SECRET.encode(),
            msg=f"{user_id}-{issued_at.isoformat()}".encode(),
            digestmod=hashlib.sha256,
        ).hexdigest()

    def _validate_signature(
        self, user_id: str, issued_at: datetime, signature: str
    ) -> bool:
        """
        Validates the session signature.
        """
        expected_signature = self._generate_signature(user_id, issued_at)
        return hmac.compare_digest(expected_signature, signature)

    async def validate_token(self, token: str) -> UserSchema:
        """
        Validates the token and returns the user schema.
        """
        claims = self.decode_claims(token)
        if claims["token_type"] != "access":
            raise invalid_or_expired_token()
        jti = claims["jti"]
        user_id = claims["sub"]
        issued_at = datetime.fromtimestamp(
            claims["iat"],
            tz=timezone._DEFAULT_TZ,  # pyright: ignore[reportPrivateUsage]
        )
        if not self._validate_signature(user_id, issued_at, jti):
            raise invalid_or_expired_token()

        async with self.cache as redis:
            cached_id = await asserts_async(redis.hget)(user_id, jti)
            if cached_id is None:
                raise invalid_or_expired_token()
        try:
            return await GetUserUseCase(
                self.context, Where("id", UUID(user_id))
            ).execute()
        except APIError:
            raise unexpected_error("Invalid sesssion received") from None

    async def refresh_session(self, token: str) -> CreateSessionResponse:
        """
        Refreshes the session and returns a new session response.
        """
        claims = self.decode_claims(token)
        if claims["token_type"] != "refresh":
            raise invalid_or_expired_token()
        jti = claims["jti"]
        user_id = claims["sub"]
        issued_at = datetime.fromtimestamp(
            claims["iat"],
            tz=timezone._DEFAULT_TZ,  # pyright: ignore[reportPrivateUsage]
        )
        if not self._validate_signature(user_id, issued_at, jti):
            raise invalid_or_expired_token()

        async with self.cache as redis:
            cached_id = await asserts_async(redis.hget)(user_id, jti)
            if cached_id is None:
                raise invalid_or_expired_token()
            _ = await asserts_async(redis.hdel)(user_id, jti)

        user = await GetUserUseCase(
            self.context, Where("id_", user_id)
        ).execute()
        return await self.create_session(user)

    async def revoke_session(self, token: str) -> None:
        """
        Revokes the session associated with the token.
        """
        claims = self.decode_claims(token, verify_exp=False)
        jti = claims["jti"]
        user_id = claims["sub"]

        async with self.cache as cache:
            _ = await asserts_async(cache.hdel)(user_id, jti)

    async def clear_all_sessions(self, user_id: UUID) -> None:
        """
        Clears all sessions for the user.
        """
        id_ = user_id.hex
        async with self.cache as cache:
            keys = await asserts_async(cache.hkeys)(id_)
            if not keys:
                return

            _ = await asserts_async(cache.hdel)(id_, *keys)

    @staticmethod
    def as_timestamp(dt: datetime) -> int:
        return math.floor(dt.timestamp())
