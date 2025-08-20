from typing import cast

from blacksheep.testing import TestClient
from blacksheep.testing.simulator import TestSimulator
from rodi import Container


def get_services(test_client: TestClient) -> Container:
    app = cast(TestSimulator, test_client._test_simulator).app  # pyright: ignore[reportPrivateUsage]
    return cast(Container, app.services)


def resolve[T](test_client: TestClient, service_type: type[T]) -> T:
    """
    Resolves a service from the test client.
    """
    return get_services(test_client).resolve(service_type)
