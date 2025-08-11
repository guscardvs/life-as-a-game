from typing import Any, override

from blacksheep.server.openapi.common import ParameterSource
import msgspec
from blacksheep.server.bindings import Binder, empty
from blacksheep.server.openapi.v3 import OpenAPIHandler
from escudeiro.misc import assert_notnone, next_or
from openapidocs.v3 import (
    Info,
    Parameter,
    ParameterLocation,
    Reference,
    Schema,
)

from app.utils.msgspec import MsgspecQueryBinder, MsgspecTypeHandler


class OASMsgspecHandler(OpenAPIHandler):
    @override
    def get_parameter_location_for_binder(
        self, binder: Binder
    ) -> ParameterLocation | None:
        if isinstance(binder, MsgspecQueryBinder):
            return ParameterLocation.QUERY
        return super().get_parameter_location_for_binder(binder)

    @override
    def get_parameters(
        self, handler: Any
    ) -> list[Parameter | Reference] | None:
        if not hasattr(handler, "binders"):
            return None
        binders: list[Binder] = handler.binders
        parameters: dict[str, Parameter | Reference] = {}

        docs = self.get_handler_docs(handler)
        parameters_info = (docs.parameters if docs else None) or dict()

        for binder in binders:
            if binder.__class__ in self._binder_docs:
                self._handle_binder_docs(binder, parameters)
                continue

            location = self.get_parameter_location_for_binder(binder)

            if not location:
                # the binder is used for something that is not a parameter
                # expressed in OpenAPI Docs (e.g. a DI service)
                continue

            if location == ParameterLocation.PATH:
                required = True
            else:
                required = binder.required and binder.default is empty

            # did the user specified information about the parameter?
            param_info = parameters_info.get(binder.parameter_name)
            if isinstance(binder, MsgspecQueryBinder):
                schema = self._make_query_schema(binder.expected_type)
                for param_name, info in schema.items():
                    parameters[param_name] = Parameter(
                        name=param_name,
                        in_=location,
                        required=required or None,
                        schema=Schema(
                            type=info.get("type", "string"),
                            default=info.get("default"),
                        ),
                        description=info.get("description", ""),
                        example=info.get("example"),
                    )
            else:
                parameters[binder.parameter_name] = Parameter(
                    name=binder.parameter_name,
                    in_=location,
                    required=required or None,
                    schema=self.get_schema_by_type(binder.expected_type),
                    description=param_info.description if param_info else "",
                    example=param_info.example if param_info else None,
                )

        for key, param_info in parameters_info.items():
            if key not in parameters:
                parameters[key] = Parameter(
                    name=key,
                    in_=self._parameter_source_to_openapi_obj(
                        param_info.source or ParameterSource.QUERY
                    ),
                    required=param_info.required,
                    schema=(
                        self.get_schema_by_type(param_info.value_type)
                        if param_info.value_type
                        else None
                    ),
                    description=param_info.description,
                    example=param_info.example,
                )

        return list(parameters.values())

    def _make_query_schema(self, expected_type: Any) -> Any:
        """
        Create a schema for query parameters based on the expected type.
        This method can be overridden to customize the schema generation.
        """
        _, schema = msgspec.json.schema_components([expected_type])
        object_schema = assert_notnone(next_or(schema.values()))
        return assert_notnone(object_schema.get("properties"))


docs = OASMsgspecHandler(
    info=Info(
        title="Life as a Game API",
        version="0.1.0",
        description="API for the Life as a Game project",
    ),
)
docs.object_types_handlers.append(MsgspecTypeHandler())
