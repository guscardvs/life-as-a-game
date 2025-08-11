from collections.abc import Callable, Coroutine
from datetime import datetime
from functools import wraps
from typing import Annotated, Any, Self, TypedDict, cast, override
from uuid import UUID

import msgspec
from blacksheep import Request
from blacksheep.server.bindings import (
    BodyBinder,
    BoundValue,
    FormBinder,
    MissingBodyError,
    SyncBinder,
)
from blacksheep.server.openapi.v3 import (
    FieldInfo,
    ObjectTypeHandler,
    OpenAPIHandler,
)
from escudeiro.contrib.msgspec import CamelStruct, MsgspecTransformRegistry
from escudeiro.misc import (
    filter_issubclass,
    is_instanceexact,
    next_or,
    timezone,
)
from msgspec.structs import fields
from uuid_extensions import uuid7

registry = MsgspecTransformRegistry()


class FromMsgSpec[T](BoundValue[T]): ...


class FromMsgSpecForm[T](BoundValue[T]): ...


class FromMsgSpecQuery[T](BoundValue[T]): ...


class MsgspecBinder(BodyBinder):
    handle = FromMsgSpec

    @override
    async def get_value(self, request: Request) -> Any:
        content = await request.read()
        if content is None or not content.strip():
            raise MissingBodyError()
        return registry.require_decoder(self.expected_type)(content)

    @property
    @override
    def content_type(self) -> str:
        return "application/json"

    @override
    def matches_content_type(self, request: Request) -> bool:
        return request.declares_json()


class MsgspecFormBinder(FormBinder):
    handle = FromMsgSpecForm

    @override
    async def get_value(self, request: Request) -> Any:
        content = await request.form()
        if not content:
            raise MissingBodyError()
        return msgspec.convert(content, self.expected_type)

    @property
    @override
    def content_type(self) -> str:
        return "multipart/form-data;application/x-www-form-urlencoded"

    @override
    def matches_content_type(self, request: Request) -> bool:
        return request.declares_content_type(
            b"application/x-www-form-urlencoded"
        ) or request.declares_content_type(b"multipart/form-data")


class MsgspecQueryBinder(SyncBinder):
    handle = FromMsgSpecQuery

    def __init__(
        self,
        expected_type: type[msgspec.Struct] = msgspec.Struct,
        name: str = "",
        implicit: bool = False,
        required: bool = False,
    ):
        super().__init__(
            expected_type, name, implicit, required, self._msgspec_converter
        )
        self.fields = fields(expected_type)
        self.possible_names = {
            field.encode_name
            for field in self.fields
            if field.encode_name != field.name
        }.union([field.name for field in self.fields])

    @property
    @override
    def source_name(self) -> str:
        return "query"

    def _msgspec_converter(self, value: dict[str, str | None]) -> Any:
        return msgspec.convert(value, self.expected_type, strict=False)

    @override
    def get_raw_value(self, request: Request) -> dict[str, str | None]:  # pyright: ignore[reportIncompatibleMethodOverride]
        values = {
            key: next_or(request.query.get(key, []))
            for key in self.possible_names
        }
        for field in self.fields:
            if (
                field.name != field.encode_name
                and field.encode_name not in values
                and field.name in values
            ):
                values[field.encode_name] = values.pop(field.name)
        return values


class MsgspecTypeHandler(ObjectTypeHandler):
    """
    A type handler for Msgspec objects.
    """

    @override
    def handles_type(self, object_type: Any) -> bool:
        return any(filter_issubclass(msgspec.Struct, (object_type,)))

    @override
    def set_type_schema(
        self, object_type: Any, context: OpenAPIHandler
    ) -> None:
        _, schema = msgspec.json.schema_components((object_type,))
        object_schema = next_or(schema.values())
        context.set_type_schema(object_type, object_schema)

    @override
    def get_type_fields(
        self, object_type: Any, register_type: Any
    ) -> list[FieldInfo]:
        _ = (object_type, register_type)
        return []


NotEmptyString = Annotated[
    str,
    msgspec.Meta(
        min_length=1, pattern=r"^(?!\s*$).+", examples=["stringstr", "a", "1"]
    ),
]


class CreateContent(TypedDict):
    id_: UUID
    created_at: datetime
    updated_at: datetime | None
    deleted_at: datetime | None


class DefaultSchema(CamelStruct):
    id_: UUID
    created_at: datetime
    updated_at: datetime | None
    deleted_at: datetime | None

    @classmethod
    def to_schema(cls, anyobject: Any) -> Self:
        return msgspec.convert(anyobject, cls, from_attributes=True)

    @classmethod
    def make_create_content(cls) -> CreateContent:
        """
        Generates a dictionary with default values for the fields
        required when creating a new instance of the schema.
        """
        return {
            "id_": cast(UUID, uuid7()),
            "created_at": timezone.now(),
            "updated_at": timezone.now(),
            "deleted_at": None,
        }


def enforce_out[**P, T](
    expected_type: type[T],
) -> Callable[
    [Callable[P, Coroutine[Any, Any, Any]]],
    Callable[P, Coroutine[Any, Any, T]],
]:
    """
    Decorator to enforce the output type of a function.
    """

    def decorator(
        func: Callable[P, Coroutine[Any, Any, Any]],
    ) -> Callable[P, Coroutine[Any, Any, T]]:
        func.__annotations__["return"] = expected_type

        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            result = await func(*args, **kwargs)
            if is_instanceexact(result, expected_type):
                return result
            return msgspec.convert(
                result, type=expected_type, from_attributes=True
            )

        return wrapper

    return decorator
