from pathlib import Path
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.staticfiles import StaticFiles
from .app_base import ENABLE_WEBDAV
from .app_native import *
from .app_native_user import *


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404:
                return await super().get_response("index.html", scope)
            raise
        if response.status_code == 404:
            return await super().get_response("index.html", scope)
        return response

__this_dir = Path(__file__).parent
__doc_path = __this_dir / "static" / "docs"
__panel_path = __this_dir / "static" / "panel"
if __doc_path.exists():
    app.mount("/.docs", StaticFiles(directory=__doc_path, html=True), name="docs")
if __panel_path.exists():
    app.mount("/.panel", SPAStaticFiles(directory=__panel_path, html=True), name="panel")

# order matters
app.include_router(router_user, prefix="/_api/user")
app.include_router(router_user, prefix="/.api/user")
app.include_router(router_api, prefix="/_api")
app.include_router(router_api, prefix="/.api")
if ENABLE_WEBDAV:
    from .app_dav import *
    app.include_router(router_dav, prefix="")
app.include_router(router_fs, prefix="")
