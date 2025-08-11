from escudeiro.data import data
from escudeiro.misc import lazymethod
from escudeiro.url import URL, Netloc


@data
class CacheConfig:
    host: str
    port: int
    user: str = ""
    password: str = ""
    db: str = ""

    @lazymethod
    def make_uri(self) -> URL:
        return URL.from_args(
            netloc_obj=Netloc.from_args(
                host=self.host,
                port=self.port,
                username=self.user or None,
                password=self.password or None,
            ),
            path=self.db or None,
            scheme="redis",
        )
