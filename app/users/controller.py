from http import HTTPStatus

import msgspec
from blacksheep import get, json, post
from blacksheep.server.openapi.common import ContentInfo, ResponseInfo

from app.authentication.handler import protected
from app.authentication.typedef import AuthenticatedRequest
from app.users import schemas
from app.users.domain import CreateUserUseCase
from app.users.schemas import UserSchema
from app.utils.database import SessionContext
from app.utils.msgspec import FromMsgSpec, enforce_out
from app.utils.oas import docs
from app.utils.server import DefaultController


class UsersController(DefaultController):
    @post("/")
    @docs(
        responses={
            HTTPStatus.CREATED: ResponseInfo(
                content=[ContentInfo(schemas.UserOutSchema)],
                description="User created successfully",
            ),
        }
    )
    async def create_user(
        self,
        payload: FromMsgSpec[schemas.CreateUserSchema],
        context: SessionContext,
    ):
        """
        Create a new user.
        """
        use_case = CreateUserUseCase(context=context, payload=payload.value)
        result = await use_case.execute()
        return json(
            msgspec.convert(
                result, type=schemas.UserOutSchema, from_attributes=True
            ),
            status=HTTPStatus.CREATED,
        )

    @get("/me")
    @protected
    @enforce_out(schemas.UserOutSchema)
    async def get_me(self, request: AuthenticatedRequest) -> UserSchema:
        """
        Get the current user.
        """
        return request.identity.user
