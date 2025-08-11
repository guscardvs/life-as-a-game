from escudeiro.data import data, field
from escudeiro.misc import lazymethod
from escudeiro.url import URL, Netloc

HOUR = 3600


@data
class PoolConfig:
    size: int = 3
    recycle: int = HOUR
    max_overflow: int = 2


@data
class DatabaseConfig:
    host: str
    port: int
    user: str
    password: str
    name: str
    pool: PoolConfig = field(default_factory=PoolConfig)

    @lazymethod
    def make_uri(self, is_asyncio: bool) -> URL:
        scheme = "postgresql+asyncpg" if is_asyncio else "postgresql+psycopg"
        return URL.from_args(
            netloc_obj=Netloc.from_args(
                host=self.host,
                port=self.port,
                username=self.user,
                password=self.password,
            ),
            scheme=scheme,
            path=self.name,
        )
