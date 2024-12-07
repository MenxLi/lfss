from .app_native import *
import os

# order matters
app.include_router(router_api)
if os.environ.get("LFSS_WEBDAV", "0") == "1":
    from .app_dav import *
    app.include_router(router_dav)
app.include_router(router_fs)