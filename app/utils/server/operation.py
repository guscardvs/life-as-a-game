from datetime import datetime
from typing import Any, cast
from uuid import UUID

from blacksheep import Application, Request
from blacksheep.server.bindings import ServiceBinder
from escudeiro.data import call_init, data
from escudeiro.misc import timezone
from loguru import logger
from rodi import Container, ContainerProtocol
from uuid_extensions import uuid7


@data
class OperationContext:
    request_id: UUID
    request_start: datetime
    context: dict[str, Any]

    def __init__(self):
        call_init(self, uuid7(), timezone.now(), {})


def setup_operation(app: Application) -> None:
    with logger.contextualize(operation_id="setup_operation"):
        logger.info("Setting up operation context...")
        services = cast(Container, app.services)
        _ = services.add_scoped(OperationContext)
        logger.info("Operation context setup complete.")


async def operation_from_request(
    request: Request, services: ContainerProtocol
) -> OperationContext:
    binder = ServiceBinder(
        OperationContext, type(OperationContext).__name__, True, services
    )
    return await binder.get_value(request)
