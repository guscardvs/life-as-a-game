from escudeiro.data import data


@data
class ServerSettings:
    host: str
    port: int
    workers: int = 1
    access_log: str = "-"
    worker_connections: int = 15
