from app.roles import schemas
from app.roles.entities import RoleEntity
from app.utils.database import Repository, SessionContext


class RoleRepository(Repository[RoleEntity, schemas.RoleSchema]):
    """
    Repository for RoleEntity.
    """

    def __init__(self, context: SessionContext):
        super().__init__(
            context=context,
            entity=RoleEntity,
            to_schema=schemas.RoleSchema.to_schema,
            to_entity=self._to_entity,
        )

    def _to_entity(self, schema: schemas.RoleSchema) -> RoleEntity:
        return RoleEntity(
            id_=schema.id_,
            created_at=schema.created_at,
            updated_at=schema.updated_at,
            deleted_at=schema.deleted_at,
            codename=schema.codename,
            description=schema.description,
        )
