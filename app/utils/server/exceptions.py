from collections.abc import Collection
from http import HTTPStatus
from typing import final

from escudeiro.data import data
from escudeiro.data.converters import asdict
from escudeiro.misc import exclude_none


@data
class FieldError:
    name: str
    detail: str


@final
class APIError(Exception):
    def __init__(
        self,
        message: str,
        detail: str | None = None,
        status_code: int = HTTPStatus.BAD_REQUEST,
        fields: list[FieldError] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.detail = detail
        self.status_code = status_code
        self.fields = fields or []

    def to_dict(self):
        return exclude_none(
            {
                "message": self.message,
                "detail": self.detail,
                "fields": list(map(asdict, self.fields)),
                "status_code": self.status_code,
            }
        )


def environment_not_set(key: str) -> APIError:
    return APIError(
        message="Environment variable not set",
        detail=f"The env key {key} is unset",
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
    )


def does_not_exist(obj: str = "Object") -> APIError:
    return APIError(
        message=f"{obj} not found",
        status_code=HTTPStatus.NOT_FOUND,
    )


def already_exists(
    obj: str = "Object", fields: Collection[FieldError] = ()
) -> APIError:
    return APIError(
        message=f"{obj} already exists",
        status_code=HTTPStatus.CONFLICT,
        fields=list(fields),
    )


def unexpected_error(detail: str | None = None) -> APIError:
    return APIError(
        message="An unexpected error occurred, talk to the tech team",
        detail=detail,
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
    )


def unauthenticated() -> APIError:
    return APIError(
        message="You are not authenticated",
        status_code=HTTPStatus.UNAUTHORIZED,
    )


def unauthorized_error() -> APIError:
    return APIError(
        message="You do not have permission to use this route",
        status_code=HTTPStatus.FORBIDDEN,
    )


def invalid_or_expired_token() -> APIError:
    return APIError(
        message="Token is invalid or expired",
        status_code=HTTPStatus.UNAUTHORIZED,
    )


def validation_error(
    message: str = "Validation error",
    fields: list[FieldError] | None = None,
    detail: str | None = None,
) -> APIError:
    return APIError(
        message=message,
        detail=detail,
        status_code=HTTPStatus.UNPROCESSABLE_CONTENT,
        fields=fields,
    )
