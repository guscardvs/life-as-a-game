from escudeiro.data import data
from escudeiro.misc import timezone

from app.authentication.schemas import (
    AuthSchema,
    CreateSessionResponse,
)
from app.authentication.service import AuthenticationService
from app.users.domain import (
    GetUserUseCase,
    UpdateUserUseCase,
    validate_password,
)
from app.users.repository import UserRepository
from app.users.schemas import UserSchema
from app.utils.cache import CacheContext
from app.utils.database import SessionContext, Where, and_, comparison
from app.utils.server import APIError, unauthenticated


@data
class AuthenticateUseCase:
    payload: AuthSchema
    context: SessionContext
    cache: CacheContext

    async def execute(
        self,
    ) -> CreateSessionResponse:
        service = AuthenticationService(self.context, self.cache)
        user = await self._validate_credentials()
        session = await service.create_session(user)
        user.last_login = timezone.now()
        _ = await UserRepository(self.context).update(
            Where("id", user.id_), user
        )

        return session

    async def _validate_credentials(self) -> UserSchema:
        get_user = GetUserUseCase(
            self.context,
            and_(
                Where("email", self.payload.username),
                Where("deleted_at", True, comparison.isnull),
            ),
        )
        try:
            user = await get_user.execute()
        except APIError as exc:
            raise unauthenticated() from exc
        else:
            if not validate_password(self.payload.password, user.password):
                raise unauthenticated()
            return user


@data
class RefreshSessionUseCase:
    token: str
    context: SessionContext
    cache: CacheContext

    async def execute(self) -> CreateSessionResponse:
        service = AuthenticationService(self.context, self.cache)
        return await service.refresh_session(self.token)


@data
class LogoutUseCase:
    user: UserSchema
    token: str
    full_logout: bool
    context: SessionContext
    cache: CacheContext

    async def execute(self) -> None:
        service = AuthenticationService(self.context, self.cache)
        if not self.full_logout:
            await service.revoke_session(self.token)
        else:
            await service.clear_all_sessions(self.user.id_)
