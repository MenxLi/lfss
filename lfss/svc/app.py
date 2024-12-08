from .app_base import ENABLE_WEBDAV
from .app_native import *

# order matters
app.include_router(router_api)
if ENABLE_WEBDAV:
    from .app_dav import *
    app.include_router(router_dav)
app.include_router(router_fs)