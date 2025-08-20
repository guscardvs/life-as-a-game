import sqlalchemy as sa
from uuid_extensions import uuid7

from .entity import AbstractEntity


def create_relation_table(table_name: str, *entities: str):
    return sa.Table(
        table_name,
        AbstractEntity.metadata,
        sa.Column("id", sa.Uuid(), primary_key=True, default=uuid7),
        *[
            sa.Column(
                get_entity_column_name(entity),
                sa.Uuid(),
                sa.ForeignKey(f"{entity}.id"),
            )
            for entity in entities
        ],
    )


def get_entity_column_name(entity: str) -> str:
    return f"{entity}_id"
