from pathlib import Path, PurePosixPath
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.staticfiles import StaticFiles
from .app_base import ENABLE_WEBDAV
from .app_native import *
from .app_native_user import *
from .app_native_metric import *


class SPAStaticFiles(StaticFiles):
    @staticmethod
    def _is_route_navigation(path: str, scope) -> bool:
        method = scope.get("method", "GET").upper()
        if method not in {"GET", "HEAD"}:
            return False

        if PurePosixPath(path).suffix:
            return False

        accept_headers = [
            value.decode("latin-1").lower()
            for key, value in scope.get("headers", [])
            if key.lower() == b"accept"
        ]
        if not accept_headers:
            return True

        accept = ",".join(accept_headers)
        return "text/html" in accept or "application/xhtml+xml" in accept

    async def get_response(self, path: str, scope):
        try:
            res = await super().get_response(path, scope)
            if res.status_code == 404 and self._is_route_navigation(path, scope):
                return await super().get_response("index.html", scope)
            else:
                return res
        except (HTTPException, StarletteHTTPException) as ex:
            if ex.status_code == 404 and self._is_route_navigation(path, scope):
                return await super().get_response("index.html", scope)
            else:
                raise ex

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
app.include_router(router_metric, prefix="/_api/metric")
app.include_router(router_metric, prefix="/.api/metric")
app.include_router(router_api, prefix="/_api")
app.include_router(router_api, prefix="/.api")
if ENABLE_WEBDAV:
    from .app_dav import *
    app.include_router(router_dav, prefix="")
app.include_router(router_fs, prefix="")
