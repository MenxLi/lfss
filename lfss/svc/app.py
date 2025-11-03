from .app_base import ENABLE_WEBDAV
from .app_native import *
from .app_native_user import *

# order matters
app.include_router(router_user, prefix="/_api/user")
app.include_router(router_user, prefix="/.api/user")
app.include_router(router_api, prefix="/_api")
app.include_router(router_api, prefix="/.api")
if ENABLE_WEBDAV:
    from .app_dav import *
    app.include_router(router_dav, prefix="")
app.include_router(router_fs, prefix="")
