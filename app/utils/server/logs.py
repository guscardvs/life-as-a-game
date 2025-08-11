import sys
from collections.abc import Callable, Coroutine
from logging import INFO
from typing import TYPE_CHECKING, Any, cast

from blacksheep import Application, Request, Response
from loguru import logger
from loguru._defaults import LOGURU_FORMAT
from rodi import Container

from app.utils.server.operation import operation_from_request

if TYPE_CHECKING:
    from loguru import Record


def _format_log_message(record: "Record") -> str:
    extra = record["extra"]
    extra.setdefault("operation_id", "no-operation-id")
    return f"{LOGURU_FORMAT} - {{operation_id}}\n".format_map(
        {**record, **extra}
    )


def make_log_middleware(app: Application):
    services = cast(Container, app.services)
    logger.remove()
    _ = logger.add(sys.stderr, level=INFO, format=_format_log_message)

    @app.middlewares.append
    async def log_request_response(
        request: Request,
        handler: Callable[[Request], Coroutine[Any, Any, Response]],
    ) -> Response:
        """
        Logs the request and response details.

        Args:
            request (Request): The incoming request object.
            handler (Callable): The handler function to process the request.

        Returns:
            Response: The response object returned by the handler.
        """
        operation = await operation_from_request(request, services)
        with logger.contextualize(operation_id=operation.request_id):
            logger.info(
                f"Received request: {request.method} - {request.url} - {request.original_client_ip}"
            )

            response = await handler(request)
            content_type = response.content_type()
            if content_type:
                content_type = content_type.decode()
            else:
                content_type = "no response"
            logger.info(
                f"Response status: {response.status}, Content-Type: {content_type}"
            )

            return response

    _ = log_request_response
