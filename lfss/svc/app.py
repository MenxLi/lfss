from pathlib import Path
from fastapi.staticfiles import StaticFiles
from .app_base import ENABLE_WEBDAV
from .app_native import *
from .app_native_user import *

__src_root = Path(__file__).parent.parent
__doc_path = __src_root.parent / "docs" / ".vitepress" / "dist"
assert __doc_path.parent.exists()
if not __doc_path.exists():
    __doc_path.mkdir()
    with open(__doc_path / "index.html", "w") as f:
        f.write("<h1>Documentation not built yet.</h1><p>Please build the documentation first.</p>")

# order matters
app.mount("/.docs", StaticFiles(directory=__doc_path), name="docs")
app.include_router(router_user, prefix="/_api/user")
app.include_router(router_user, prefix="/.api/user")
app.include_router(router_api, prefix="/_api")
app.include_router(router_api, prefix="/.api")
if ENABLE_WEBDAV:
    from .app_dav import *
    app.include_router(router_dav, prefix="")
app.include_router(router_fs, prefix="")
