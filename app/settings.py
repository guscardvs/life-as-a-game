from pathlib import Path

from escudeiro.config import (
    AdapterConfigFactory,
    DotFile,
    Env,
    EnvConfig,
    set_config,
)
from escudeiro.config.core.utils import boolean_cast

from app.utils.cache import CacheConfig
from app.utils.database import DatabaseConfig
from app.utils.server import ServerSettings

ROOT = Path(__file__).parent
BASE_DIR = ROOT.parent
ENV_DIR = BASE_DIR / "envs"

config = EnvConfig(
    DotFile(ENV_DIR / "local.env", Env.LOCAL),
    DotFile(ENV_DIR / "test.env", Env.TEST),
    DotFile(ENV_DIR / "prod.env", Env.PRD),
)
set_config(config)

factory = AdapterConfigFactory(config)

DATABASE_CONFIG = factory.load(DatabaseConfig, __prefix__="db")
SERVER_SETTINGS = factory.load(ServerSettings, __prefix__="server")
CACHE_CONFIG = factory.load(CacheConfig, __prefix__="redis")
DEBUG = config(
    "DEBUG",
    default=config.env is Env.LOCAL,
    cast=boolean_cast.strict,
)

# Multi-secret configuration
PRIMARY_SECRET = config("PRIMARY_SECRET", str)
SECONDARY_SECRET = config("SECONDARY_SECRET", str)
