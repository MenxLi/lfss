from .app_native import *
from .app_dav import *
import os

# order matters
if os.environ.get("LFSS_DAV", "0") == "1":
    app.include_router(router_dav)
else:
    app.include_router(router_api)
    app.include_router(router_fs)