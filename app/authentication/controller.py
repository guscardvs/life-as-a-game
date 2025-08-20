from http import HTTPStatus

from blacksheep import Response, delete, post

from app.authentication.domain import (
    AuthenticateUseCase,
    LogoutUseCase,
    RefreshSessionUseCase,
)
from app.authentication.handler import REFRESH_URL, TOKEN_URL, protected
from app.authentication.schemas import (
    AuthSchema,
    CreateSessionResponse,
    FullLogoutQuery,
    RefreshTokenSchema,
    SessionResponse,
)
from app.authentication.typedef import AuthenticatedRequest
from app.utils.cache import CacheContext
from app.utils.database import SessionContext
from app.utils.msgspec import FromMsgSpec, FromMsgSpecForm, enforce_out
from app.utils.server import DefaultController


class AuthController(DefaultController):
    @post(TOKEN_URL)
    @enforce_out(SessionResponse)
    async def authenticate(
        self,
        payload: FromMsgSpecForm[AuthSchema],
        context: SessionContext,
        cache: CacheContext,
    ) -> CreateSessionResponse:
        """
        Authenticate a user and create a session.
        """
        domain = AuthenticateUseCase(
            payload.value,
            context,
            cache,
        )
        return await domain.execute()

    @post(REFRESH_URL)
    @enforce_out(SessionResponse)
    async def refresh(
        self,
        payload: FromMsgSpec[RefreshTokenSchema],
        context: SessionContext,
        cache: CacheContext,
    ) -> CreateSessionResponse:
        """
        Refresh the access token using a valid refresh token.
        """
        domain = RefreshSessionUseCase(
            payload.value.token,
            context,
            cache,
        )
        return await domain.execute()

    @delete("/logout")
    @protected(
        responses={
            HTTPStatus.NO_CONTENT: "Logout successful",
            HTTPStatus.UNAUTHORIZED: "Improper authentication",
        }
    )
    async def logout(
        self,
        request: AuthenticatedRequest,
        context: SessionContext,
        cache: CacheContext,
        full_logout: FullLogoutQuery = FullLogoutQuery(False),
    ) -> Response:
        """
        Logout the user, optionally invalidating all sessions.

        If `full_logout` is true, all sessions for the user will be invalidated.
        Otherwise, only the current session will be invalidated.
        """
        domain = LogoutUseCase(
            request.identity.user,
            request.identity.token,
            full_logout.value,
            context,
            cache,
        )
        await domain.execute()

        return Response(HTTPStatus.NO_CONTENT)
