from guardpost import Policy
import msgspec
from blacksheep import Application
from blacksheep.settings.json import json_settings
from escudeiro.misc import Caster, jsonx

from app.authentication.handler import (
    SECURITY_SCHEME_NAME,
    authentication_scheme,
    make_auth_handler,
)
from app.authorization.handler import (
    AdminRequirement,
    AuthorizationHandler,
    SuperuserRequirements,
)
from app.authorization.typedef import Admin, Superuser
from app.settings import CACHE_CONFIG, DATABASE_CONFIG, DEBUG, ROOT
from app.utils.cache import make_cache_setup
from app.utils.database.adapter import make_database_setup, teardown_database
from app.utils.oas import docs
from app.utils.server import (
    APIError,
    api_error_handler,
    find,
    make_log_middleware,
    msgspec_error_handler,
    setup_operation,
)


def get_application() -> Application:
    """
    Returns the main application instance.
    """
    find(ROOT)
    json_settings.use(
        loads=jsonx.loads,
        dumps=Caster(msgspec.json.encode).join(bytes.decode),
    )
    app = Application()
    make_log_middleware(app)
    docs.security_schemes[SECURITY_SCHEME_NAME] = authentication_scheme
    docs.bind_app(app)

    app.exceptions_handlers[APIError] = api_error_handler
    app.exceptions_handlers[msgspec.MsgspecError] = msgspec_error_handler

    app.on_start += make_database_setup(DATABASE_CONFIG, DEBUG)
    app.on_start += make_cache_setup(CACHE_CONFIG)
    app.on_stop += teardown_database
    setup_operation(app)
    _ = make_auth_handler(
        app,
        AuthorizationHandler,
        Policy(Superuser, SuperuserRequirements()),
        Policy(Admin, AdminRequirement()),
    )

    return app


app = get_application()
