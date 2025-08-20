import argon2
from escudeiro.context import atomic
from escudeiro.data import data

from app.users import schemas
from app.users.repository import UserRepository
from app.utils.database import (
    BindClause,
    SessionContext,
    Where,
    comparison,
    and_,
)
from app.utils.server import (
    FieldError,
    Page,
    PagedResponse,
    already_exists,
    validation_error,
)

DEFAULT_SU_STATUS = False
hasher = argon2.PasswordHasher()


def create_password(password: str) -> str:
    """Create a hashed password using Argon2."""
    return hasher.hash(password)


def validate_password(password: str, hashed: str) -> bool:
    """Validate a password against a hashed password."""
    try:
        return hasher.verify(hashed, password)
    except (
        argon2.exceptions.VerifyMismatchError,
        argon2.exceptions.VerificationError,
        argon2.exceptions.InvalidHashError,
    ):
        return False


@data
class CreateUserUseCase:
    context: SessionContext
    payload: schemas.CreateUserSchema

    async def execute(self) -> schemas.UserSchema:
        context = atomic(self.context)
        repository = UserRepository(context)
        async with context:
            await self._check_email_exists(repository)
            return await repository.create(self._make_user())

    async def _check_email_exists(self, repository: UserRepository):
        if await repository.exists(Where("email", self.payload.email)):
            raise already_exists(
                "User",
                [
                    FieldError(
                        "email",
                        f"Email {self.payload.email} already exists",
                    )
                ],
            )

    def _make_user(self) -> schemas.UserSchema:
        return schemas.UserSchema(
            email=self.payload.email,
            password=create_password(self.payload.password),
            full_name=self.payload.full_name,
            is_superuser=DEFAULT_SU_STATUS,
            birth_date=self.payload.birth_date,
            **schemas.UserSchema.make_create_content(),
        )


@data
class GetUserUseCase:
    context: SessionContext
    clause: BindClause

    async def execute(self) -> schemas.UserSchema:
        return await UserRepository(self.context).get(
            and_(
                self.clause,
                Where(
                    "deleted_at",
                    True,
                    comparison.isnull,
                ),
            )
        )


@data
class FetchUsersUseCase:
    context: SessionContext
    clause: BindClause
    page: Page

    async def execute(self) -> PagedResponse[schemas.UserSchema]:
        users = await UserRepository(self.context).fetch(
            UserRepository.make_paged_query(self.page), self.clause
        )
        count = await UserRepository(self.context).count(self.clause)
        return PagedResponse.from_data(
            data=users,
            page=self.page,
            total=count,
        )


@data
class UpdateUserUseCase:
    context: SessionContext
    clause: BindClause
    payload: schemas.UpdateUserSchema

    async def execute(self) -> schemas.UserSchema:
        context = atomic(self.context)
        repository = UserRepository(context)
        async with context:
            user = await repository.get(self.clause)
            updated = self._update_user(user)
            return await repository.update(self.clause, updated)

    def _update_user(self, user: schemas.UserSchema) -> schemas.UserSchema:
        user.email = self.payload.email or user.email
        user.full_name = self.payload.full_name or user.full_name
        user.birth_date = self.payload.birth_date or user.birth_date
        if self.payload.password:
            if validate_password(self.payload.password, user.password):
                raise validation_error(
                    "New password cannot be the same as the old one",
                    [
                        FieldError(
                            "password",
                            "New password cannot be the same as the old one",
                        )
                    ],
                )
            user.password = create_password(self.payload.password)
        return user


@data
class DeleteUserUseCase:
    context: SessionContext
    clause: BindClause

    async def execute(self) -> None:
        context = atomic(self.context)
        repository = UserRepository(context)
        async with context:
            await self._check_user_exists(repository)
            return await repository.delete(self.clause)

    async def _check_user_exists(self, repository: UserRepository):
        if not await repository.exists(self.clause):
            raise validation_error(
                "User does not exist",
                [
                    FieldError(
                        "id_",
                        "User with the given ID does not exist",
                    )
                ],
            )
