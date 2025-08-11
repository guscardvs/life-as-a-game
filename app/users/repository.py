from app.users import schemas
from app.users.entities import UserEntity
from app.utils.database import Repository, SessionContext


class UserRepository(Repository[UserEntity, schemas.UserSchema]):
    """
    Repository for UserEntity.
    """

    def __init__(self, context: SessionContext):
        super().__init__(
            context=context,
            entity=UserEntity,
            to_schema=schemas.UserSchema.to_schema,
            to_entity=self._to_entity,
        )

    def _to_entity(self, schema: schemas.UserSchema) -> UserEntity:
        return UserEntity(
            id_=schema.id_,
            created_at=schema.created_at,
            updated_at=schema.updated_at,
            deleted_at=schema.deleted_at,
            email=schema.email,
            full_name=schema.full_name,
            is_superuser=schema.is_superuser,
            birth_date=schema.birth_date,
            last_login=schema.last_login,
            password=schema.password,
        )
