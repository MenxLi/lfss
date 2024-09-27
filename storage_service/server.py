from typing import Optional

from fastapi import FastAPI, APIRouter, Depends, Request, Response
from fastapi.exceptions import HTTPException 
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
import mimesniff

from contextlib import asynccontextmanager
import mimetypes

import json
from .log import get_logger
from .config import MAX_BUNDLE_BYTES
from .utils import ensure_uri_compnents
from .database import Database, DBUserRecord, DECOY_USER, FileReadPermission

logger = get_logger("server")
conn = Database()

@asynccontextmanager
async def lifespan(app: FastAPI):
    global conn
    await conn.init()
    yield
    await conn.close()

async def get_current_user(token: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False))):
    if not token:
        return DECOY_USER
    user = await conn.user.get_user_by_credential(token.credentials)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user

app = FastAPI(docs_url=None, redoc_url=None, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

router_fs = APIRouter(prefix="")

@router_fs.get("/{path:path}")
async def get_file(path: str, asfile = False, user: DBUserRecord = Depends(get_current_user)):
    path = ensure_uri_compnents(path)
    if path == "": path = "/"
    if path.endswith("/"):
        # return file under the path as json
        if user.id == 0:
            raise HTTPException(status_code=403, detail="Permission denied, credential required")
        if path == "/":
            return {
                "dirs": await conn.file.list_root(user.username) \
                    if not user.is_admin else await conn.file.list_root(),
                "files": []
            }

        if not path.startswith(f"{user.username}/") and not user.is_admin:
            raise HTTPException(status_code=403, detail="Permission denied, path must start with username")

        dirs, files = await conn.file.list_path(path, flat = False)
        return {
            "dirs": dirs,
            "files": files
        }

    file_record = await conn.file.get_file_record(path)
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")
    
    # permission check
    perm = file_record.permission
    if perm == FileReadPermission.PRIVATE:
        if not user.is_admin and user.id != file_record.owner_id:
            raise HTTPException(status_code=403, detail="Permission denied")
        else:
            assert path.startswith(f"{user.username}/")
    elif perm == FileReadPermission.PROTECTED:
        if user.id == 0:
            raise HTTPException(status_code=403, detail="Permission denied")
    else:
        assert perm == FileReadPermission.PUBLIC
    
    fname = path.split("/")[-1]
    async def send(media_type: Optional[str] = None, disposition = "attachment"):
        fblob = await conn.read_file(path)
        if media_type is None:
            media_type, _ = mimetypes.guess_type(fname)
        if media_type is None:
            media_type = mimesniff.what(fblob)

        return Response(
            content=fblob, media_type=media_type, headers={
                "Content-Disposition": f"{disposition}; filename={fname}", 
                "Content-Length": str(len(fblob))
            }
        )
    
    if asfile:
        return await send('application/octet-stream', "attachment")
    else:
        return await send(None, "inline")

@router_fs.put("/{path:path}")
async def put_file(request: Request, path: str, user: DBUserRecord = Depends(get_current_user)):
    path = ensure_uri_compnents(path)
    if user.id == 0:
        logger.debug("Reject put request from DECOY_USER")
        raise HTTPException(status_code=403, detail="Permission denied")
    if not path.startswith(f"{user.username}/") and not user.is_admin:
        logger.debug(f"Reject put request from {user.username} to {path}")
        raise HTTPException(status_code=403, detail="Permission denied")
    
    logger.info(f"PUT {path}, user: {user.username}")
    exists_flag = False
    file_record = await conn.file.get_file_record(path)
    if file_record:
        exists_flag = True
        # remove the old file
        await conn.delete_file(path)
    
    # check content-type
    content_type = request.headers.get("Content-Type")
    logger.debug(f"Content-Type: {content_type}")
    if content_type == "application/json":
        body = await request.json()
        await conn.save_file(user.id, path, json.dumps(body).encode('utf-8'))
    elif content_type == "application/x-www-form-urlencoded":
        # may not work...
        body = await request.form()
        file = body.get("file")
        if isinstance(file, str) or file is None:
            raise HTTPException(status_code=400, detail="Invalid form data, file required")
        await conn.save_file(user.id, path, await file.read())
    elif content_type == "application/octet-stream":
        body = await request.body()
        await conn.save_file(user.id, path, body)
    else:
        body = await request.body()
        await conn.save_file(user.id, path, body)

    # https://developer.mozilla.org/zh-CN/docs/Web/HTTP/Methods/PUT
    if exists_flag:
        return Response(status_code=201, headers={
            "Content-Type": "application/json",
        }, content=json.dumps({"url": path}))
    else:
        return Response(status_code=200, headers={
            "Content-Type": "application/json",
        }, content=json.dumps({"url": path}))

@router_fs.delete("/{path:path}")
async def delete_file(path: str, user: DBUserRecord = Depends(get_current_user)):
    path = ensure_uri_compnents(path)
    if user.id == 0:
        raise HTTPException(status_code=403, detail="Permission denied")
    if not path.startswith(f"{user.username}/") and not user.is_admin:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    logger.info(f"DELETE {path}, user: {user.username}")

    if path.endswith("/"):
        res = await conn.delete_path(path)
    else:
        res = await conn.delete_file(path)

    if res:
        return Response(status_code=200, content="Deleted")
    else:
        return Response(status_code=404, content="Not found")

router_api = APIRouter(prefix="/_api")

@router_api.get("/bundle")
async def bundle_files(path: str, user: DBUserRecord = Depends(get_current_user)):
    logger.info(f"GET bundle({path}), user: {user.username}")
    path = ensure_uri_compnents(path)
    assert path.endswith("/") or path == ""

    if not path == "" and path[0] == "/":   # adapt to both /path and path
        path = path[1:]
    
    # TODO: maybe check permission here...

    # return bundle of files
    files = await conn.file.list_path(path, flat = True)
    if len(files) == 0:
        raise HTTPException(status_code=404, detail="No files found")
    total_size = sum([f.file_size for f in files])
    if total_size > MAX_BUNDLE_BYTES:
        raise HTTPException(status_code=400, detail="Too large to zip")

    file_paths = [f.url for f in files]
    zip_buffer = await conn.zip_path(path, file_paths)
    return Response(
        content=zip_buffer.getvalue(), media_type="application/zip", headers={
            "Content-Disposition": f"attachment; filename=bundle.zip", 
            "Content-Length": str(zip_buffer.getbuffer().nbytes)
        }
    )

@router_api.get("/fmeta")
async def get_file_meta(path: str, user: DBUserRecord = Depends(get_current_user)):
    logger.info(f"GET meta({path}), user: {user.username}")
    if path.endswith("/"):
        raise HTTPException(status_code=400, detail="Invalid path")
    path = ensure_uri_compnents(path)
    file_record = await conn.file.get_file_record(path)
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")
    return file_record

# order matters
app.include_router(router_api)
app.include_router(router_fs)