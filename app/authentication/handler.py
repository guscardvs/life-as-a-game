from collections.abc import Callable, Mapping
from typing import Any, cast, overload, override

from blacksheep import Application, Request, auth
from blacksheep.server.authorization import Policy
from blacksheep.server.openapi.common import (
    ParameterInfo,
    RequestBodyInfo,
    ResponseInfo,
    ResponseStatusType,
    SecurityInfo,
)
from guardpost import AuthenticationHandler, AuthorizationStrategy, Identity
from guardpost.common import AuthenticatedRequirement
from openapidocs.v3 import OAuth2Security, OAuthFlow, OAuthFlows
from rodi import Container

from app.authentication.service import AuthenticationService
from app.authentication.typedef import Authenticated, Authentication
from app.utils.cache import CacheContext
from app.utils.database import SessionContext
from app.utils.oas import docs
from app.utils.server import OperationContext


class AuthHandler(AuthenticationHandler):
    def __init__(
        self,
        cache: CacheContext,
        context: SessionContext,
        operation: OperationContext,
    ) -> None:
        self.cache = cache
        self.context = context
        self.operation = operation
        self.service = AuthenticationService(self.context, self.cache)

    @override
    async def authenticate(self, context: Request) -> Identity | None:
        if context.identity is not None:
            return context.identity

        authorization = context.get_first_header(b"Authorization")
        if not authorization:
            return None

        scheme, _, param = authorization.partition(b" ")
        if scheme.lower() != b"bearer" or not param:
            return None

        token = param.decode()
        user = await self.service.validate_token(token)
        identity_user = Authentication(
            {Authentication.user_key: user}, Authenticated
        )
        identity_user.access_token = token
        context.identity = identity_user
        return identity_user


def make_auth_handler(
    app: Application,
    handler: type[AuthHandler] = AuthHandler,
    *extra_policies: Policy,
) -> AuthorizationStrategy:
    auth = app.use_authentication()
    _ = auth.add(handler)
    services = cast(Container, app.services)
    _ = services.register(handler)

    result = app.use_authorization().add(
        Policy(Authenticated, AuthenticatedRequirement())
    )
    for policy in extra_policies:
        result = result.add(policy)
    return result


TOKEN_URL = "/token"
REFRESH_URL = "/refresh"

SECURITY_SCHEME_NAME = "OAuth2"

authentication_scheme = OAuth2Security(
    OAuthFlows(
        password=OAuthFlow(
            {},
            token_url=f"/auth{TOKEN_URL}",
            refresh_url=f"/auth{REFRESH_URL}",
        )
    ),
)


@overload
def protected[**P, T](
    func: Callable[P, T],
    /,
    *,
    summary: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
    parameters: Mapping[str, ParameterInfo] | None = None,
    request_body: RequestBodyInfo | None = None,
    responses: dict[ResponseStatusType, str | ResponseInfo] | None = None,
    ignored: bool | None = None,
    deprecated: bool | None = None,
    on_created: Callable[[Any, Any], None] | None = None,
    security: list[SecurityInfo] | None = None,
    policy: str = Authenticated,
) -> Callable[P, T]: ...


@overload
def protected[**P, T](
    func: None = None,
    /,
    *,
    summary: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
    parameters: Mapping[str, ParameterInfo] | None = None,
    request_body: RequestBodyInfo | None = None,
    responses: dict[ResponseStatusType, str | ResponseInfo] | None = None,
    ignored: bool | None = None,
    deprecated: bool | None = None,
    on_created: Callable[[Any, Any], None] | None = None,
    security: list[SecurityInfo] | None = None,
    policy: str = Authenticated,
) -> Callable[[Callable[P, T]], Callable[P, T]]: ...


def protected[**P, T](
    func: Callable[P, T] | None = None,
    /,
    *,
    summary: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
    parameters: Mapping[str, ParameterInfo] | None = None,
    request_body: RequestBodyInfo | None = None,
    responses: dict[ResponseStatusType, str | ResponseInfo] | None = None,
    ignored: bool | None = None,
    deprecated: bool | None = None,
    on_created: Callable[[Any, Any], None] | None = None,
    security: list[SecurityInfo] | None = None,
    policy: str = Authenticated,
) -> Callable[P, T] | Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Decorator to protect a route with authentication.
    """
    security = security or []
    security.append(SecurityInfo(SECURITY_SCHEME_NAME, []))
    docs_decorator = docs(
        summary=summary,
        description=description,
        tags=tags,
        parameters=parameters,
        request_body=request_body,
        responses=responses,
        ignored=ignored,
        deprecated=deprecated,
        on_created=on_created,
        security=security,
    )
    auth_decorator = auth(policy)

    def wrapper(func: Callable[P, T]) -> Callable[P, T]:
        return auth_decorator(docs_decorator(func))

    if func is not None:
        return wrapper(func)
    return wrapper
