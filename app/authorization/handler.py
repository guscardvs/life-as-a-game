from collections.abc import Callable, Coroutine
from functools import wraps
from typing import Any, Concatenate, cast, override

from blacksheep import Request
from escudeiro.lazyfields import lazyfield
from guardpost import (
    AuthorizationContext,
    Identity,
    Requirement,
)

from app.authentication.handler import AuthHandler
from app.authentication.typedef import AuthenticatedRequest, Authentication
from app.authorization.repository import GroupRepository
from app.authorization.typedef import ADMIN_ROLE_NAME
from app.utils.database import Where, and_, comparison
from app.utils.database.query.order_by import OrderBy
from app.utils.server import unauthorized_error


def authorize(*roles: str):
    """Decorator to authorize access based on user roles."""

    if not roles:
        raise ValueError("At least one role must be specified")

    def decorator[**P, T](
        func: Callable[
            Concatenate[AuthenticatedRequest, P], Coroutine[Any, Any, T]
        ],
    ) -> Callable[
        Concatenate[AuthenticatedRequest, P], Coroutine[Any, Any, T]
    ]:
        # Using setattr to avoid linting issues
        print(func.__annotations__)

        @wraps(func)
        async def _wrapper(
            request: AuthenticatedRequest,
            *args: P.args,
            **kwargs: P.kwargs,
        ) -> T:
            # Check if the user is authorized
            if not request.identity or not request.identity.roles_intersect(
                roles
            ):
                raise unauthorized_error()

            return await func(request, *args, **kwargs)

        return _wrapper

    return decorator


class AuthorizationHandler(AuthHandler):
    @lazyfield
    def group_repository(self) -> GroupRepository:
        return GroupRepository(self.context)

    @override
    async def authenticate(self, context: Request) -> Identity | None:
        result = await super().authenticate(context)
        if result is None:
            return

        result = cast(Authentication, result)
        groups = await self.group_repository.fetch(
            OrderBy.none(),
            and_(
                Where("deleted_at", True, comparison.isnull),
                Where("users.id", result.user.id_),
            ),
        )
        roles = [role.codename for group in groups for role in group.roles]
        result.roles = roles
        result.groups = [group.name for group in groups]
        return result


class SuperuserRequirements(Requirement):
    @override
    async def handle(self, context: AuthorizationContext):
        identity = context.identity
        if not identity:
            return
        identity = cast(Authentication, identity)
        if identity.is_authenticated() and identity.user.is_superuser:
            context.succeed(self)


class AdminRequirement(Requirement):
    @override
    async def handle(self, context: AuthorizationContext):
        identity = context.identity
        if not identity:
            return
        identity = cast(Authentication, identity)
        if identity.is_authenticated() and (
            identity.roles_intersect((ADMIN_ROLE_NAME,))
            or identity.user.is_superuser
        ):
            context.succeed(self)
