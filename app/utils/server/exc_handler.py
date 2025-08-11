from http import HTTPStatus

import msgspec
from blacksheep import Application, Content, Request, Response
from loguru import logger

from app.utils.server.operation import operation_from_request

from .exceptions import APIError


async def api_error_handler(
    self: Application, request: Request, exc: APIError
) -> Response:
    operation_id = (
        await operation_from_request(request, self.services)
    ).request_id
    log_dispatcher = logger.info if exc.status_code < 500 else logger.error
    log_dispatcher(
        f"Received failing request: {request.method} - {request.path} - {exc.status_code} - {request.original_client_ip}",
        operation_id=operation_id,
    )
    log_dispatcher(
        f"Error details: {exc.message} - {exc.detail}",
        operation_id=operation_id,
    )
    return Response(
        status=exc.status_code,
        headers=[(b"X-Error", exc.message.encode("utf-8"))],
        content=Content(
            b"application/json", msgspec.json.encode(exc.to_dict())
        ),
    )


async def msgspec_error_handler(
    self: Application, request: Request, exc: msgspec.MsgspecError
) -> Response:
    error = APIError(
        message=str(exc),
        detail="Invalid JSON payload",
        status_code=HTTPStatus.UNPROCESSABLE_CONTENT,
    )
    operation_id = (
        await operation_from_request(request, self.services)
    ).request_id
    logger.info(
        f"Received failing request: {request.method} - {request.path} - {error.status_code} - {request.original_client_ip}",
        operation_id=operation_id,
    )
    logger.info(
        f"Error details: {error.message} - {error.detail}",
        operation_id=operation_id,
    )
    return Response(
        status=HTTPStatus.UNPROCESSABLE_CONTENT,
        headers=[(b"X-Error", b"Invalid JSON payload")],
        content=Content(
            b"application/json",
            msgspec.json.encode(error.to_dict()),
        ),
    )
