from blacksheep.testing import TestClient
from escudeiro.config import get_env


class TestHealthCheck:
    async def test_healthcheck(self, test_client: TestClient):
        response = await test_client.get("/healthcheck")
        assert response.status == 200
        assert await response.json() == {
            "status": "ok",
            "environment": get_env().val,
        }
