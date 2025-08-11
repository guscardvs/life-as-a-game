from blacksheep import get
from escudeiro.config import get_env

from app.utils.server import DefaultController


class HealthCheckController(DefaultController):
    @get()
    async def healthcheck(self):
        return {"status": "ok", "environment": get_env().val}
