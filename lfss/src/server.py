from typing import Optional, Literal
from functools import wraps

from fastapi import FastAPI, APIRouter, Depends, Request, Response
from fastapi.responses import StreamingResponse
from fastapi.exceptions import HTTPException 
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
import mimesniff

import asyncio, json, time
import mimetypes
from contextlib import asynccontextmanager

from .error import *
from .log import get_logger
from .stat import RequestDB
from .config import MAX_BUNDLE_BYTES, MAX_FILE_BYTES, LARGE_BLOB_DIR, LARGE_FILE_BYTES
from .utils import ensure_uri_compnents, format_last_modified, now_stamp
from .database import Database, UserRecord, DECOY_USER, FileRecord, check_user_permission, FileReadPermission

logger = get_logger("server", term_level="DEBUG")
logger_failed_request = get_logger("failed_requests", term_level="INFO")
conn = Database()
req_conn = RequestDB()

@asynccontextmanager
async def lifespan(app: FastAPI):
    global conn
    await asyncio.gather(conn.init(), req_conn.init())
    yield
    await asyncio.gather(conn.commit(), req_conn.commit())
    await asyncio.gather(conn.close(), req_conn.close())

def handle_exception(fn):
    @wraps(fn)
    async def wrapper(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except Exception as e:
            if isinstance(e, HTTPException): raise e
            if isinstance(e, StorageExceededError): raise HTTPException(status_code=413, detail=str(e))
            if isinstance(e, PermissionError): raise HTTPException(status_code=403, detail=str(e))
            if isinstance(e, InvalidPathError): raise HTTPException(status_code=400, detail=str(e))
            if isinstance(e, FileNotFoundError): raise HTTPException(status_code=404, detail=str(e))
            if isinstance(e, FileExistsError): raise HTTPException(status_code=409, detail=str(e))
            logger.error(f"Uncaptured error in {fn.__name__}: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    return wrapper

async def get_credential_from_params(request: Request):
    return request.query_params.get("token")
async def get_current_user(
    token: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False)), 
    q_token: Optional[str] = Depends(get_credential_from_params)
    ):
    """
    First try to get the user from the bearer token, 
    if not found, try to get the user from the query parameter
    """
    if token:
        user = await conn.user.get_user_by_credential(token.credentials)
    else:
        if not q_token:
            return DECOY_USER
        else:
            user = await conn.user.get_user_by_credential(q_token)

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

@app.middleware("http")
async def log_requests(request: Request, call_next):

    request_time_stamp = now_stamp()
    start_time = time.perf_counter()
    response: Response = await call_next(request)
    end_time = time.perf_counter()
    response_time = end_time - start_time
    response.headers["X-Response-Time"] = str(response_time)

    if response.status_code >= 400:
        logger_failed_request.error(f"{request.method} {request.url.path} {response.status_code}")
        
    await req_conn.log_request(
        request_time_stamp, 
        request.method, request.url.path, response.status_code, response_time,
        headers = dict(request.headers), 
        query = dict(request.query_params), 
        client = request.client, 
        request_size = int(request.headers.get("Content-Length", 0)),
        response_size = int(response.headers.get("Content-Length", 0))
    )
    await req_conn.ensure_commit_once()

    return response

router_fs = APIRouter(prefix="")

@router_fs.get("/{path:path}")
@handle_exception
async def get_file(path: str, download = False, user: UserRecord = Depends(get_current_user)):
    path = ensure_uri_compnents(path)

    # handle directory query
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

        return await conn.file.list_path(path, flat = False)
    
    file_record = await conn.file.get_file_record(path)
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")

    owner = await conn.user.get_user_by_id(file_record.owner_id)
    assert owner is not None, "Owner not found"
    allow_access, reason = check_user_permission(user, owner, file_record)
    if not allow_access:
        raise HTTPException(status_code=403, detail=reason)
    
    fname = path.split("/")[-1]
    async def send(media_type: Optional[str] = None, disposition = "attachment"):
        if not file_record.external:
            fblob = await conn.read_file(path)
            if media_type is None:
                media_type, _ = mimetypes.guess_type(fname)
            if media_type is None:
                media_type = mimesniff.what(fblob)
            return Response(
                content=fblob, media_type=media_type, headers={
                    "Content-Disposition": f"{disposition}; filename={fname}", 
                    "Content-Length": str(len(fblob)), 
                    "Last-Modified": format_last_modified(file_record.create_time)
                }
            )
        
        else:
            if media_type is None:
                media_type, _ = mimetypes.guess_type(fname)
            if media_type is None:
                media_type = mimesniff.what(str((LARGE_BLOB_DIR / file_record.file_id).absolute()))
            return StreamingResponse(
                await conn.read_file_stream(path), media_type=media_type, headers={
                    "Content-Disposition": f"{disposition}; filename={fname}", 
                    "Content-Length": str(file_record.file_size),
                    "Last-Modified": format_last_modified(file_record.create_time)
                }
            )
    
    if download:
        return await send('application/octet-stream', "attachment")
    else:
        return await send(None, "inline")

@router_fs.put("/{path:path}")
@handle_exception
async def put_file(
    request: Request, 
    path: str, 
    conflict: Literal["overwrite", "skip", "abort"] = "abort",
    permission: int = 0,
    user: UserRecord = Depends(get_current_user)):
    path = ensure_uri_compnents(path)
    if user.id == 0:
        logger.debug("Reject put request from DECOY_USER")
        raise HTTPException(status_code=401, detail="Permission denied")
    if not path.startswith(f"{user.username}/") and not user.is_admin:
        logger.debug(f"Reject put request from {user.username} to {path}")
        raise HTTPException(status_code=403, detail="Permission denied")
    
    content_length = request.headers.get("Content-Length")
    if content_length is not None:
        content_length = int(content_length)
        if content_length > MAX_FILE_BYTES:
            logger.debug(f"Reject put request from {user.username} to {path}, file too large")
            raise HTTPException(status_code=413, detail="File too large")
    
    logger.info(f"PUT {path}, user: {user.username}")
    exists_flag = False
    file_record = await conn.file.get_file_record(path)
    if file_record:
        if conflict == "abort":
            raise HTTPException(status_code=409, detail="File exists")
        if conflict == "skip":
            return Response(status_code=200, headers={
                "Content-Type": "application/json",
            }, content=json.dumps({"url": path}))
        # remove the old file
        exists_flag = True
        await conn.delete_file(path)
    
    # check content-type
    content_type = request.headers.get("Content-Type")
    logger.debug(f"Content-Type: {content_type}")
    if content_type == "application/json":
        body = await request.json()
        blobs = json.dumps(body).encode('utf-8')
    elif content_type == "application/x-www-form-urlencoded":
        # may not work...
        body = await request.form()
        file = body.get("file")
        if isinstance(file, str) or file is None:
            raise HTTPException(status_code=400, detail="Invalid form data, file required")
        blobs = await file.read()
    elif content_type == "application/octet-stream":
        blobs = await request.body()
    else:
        blobs = await request.body()
    if len(blobs) > LARGE_FILE_BYTES:
        async def blob_reader():
            chunk_size = 16 * 1024 * 1024    # 16MB
            for b in range(0, len(blobs), chunk_size):
                yield blobs[b:b+chunk_size]
        await conn.save_file(user.id, path, blob_reader(), permission = FileReadPermission(permission))
    else:
        await conn.save_file(user.id, path, blobs, permission = FileReadPermission(permission))

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
@handle_exception
async def delete_file(path: str, user: UserRecord = Depends(get_current_user)):
    path = ensure_uri_compnents(path)
    if user.id == 0:
        raise HTTPException(status_code=401, detail="Permission denied")
    if not path.startswith(f"{user.username}/") and not user.is_admin:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    logger.info(f"DELETE {path}, user: {user.username}")

    if path.endswith("/"):
        res = await conn.delete_path(path)
    else:
        res = await conn.delete_file(path)

    await conn.user.set_active(user.username)
    if res:
        return Response(status_code=200, content="Deleted")
    else:
        return Response(status_code=404, content="Not found")

router_api = APIRouter(prefix="/_api")

@router_api.get("/bundle")
@handle_exception
async def bundle_files(path: str, user: UserRecord = Depends(get_current_user)):
    logger.info(f"GET bundle({path}), user: {user.username}")
    if user.id == 0:
        raise HTTPException(status_code=401, detail="Permission denied")
    path = ensure_uri_compnents(path)
    assert path.endswith("/") or path == ""

    if not path == "" and path[0] == "/":   # adapt to both /path and path
        path = path[1:]
    
    owner_records_cache = {}     # cache owner records, ID -> UserRecord
    async def is_access_granted(file_record: FileRecord):
        owner_id = file_record.owner_id
        owner = owner_records_cache.get(owner_id, None)
        if owner is None:
            owner = await conn.user.get_user_by_id(owner_id)
            assert owner is not None, f"File owner not found: id={owner_id}"
            owner_records_cache[owner_id] = owner
            
        allow_access, _ = check_user_permission(user, owner, file_record)
        return allow_access
    
    files = await conn.file.list_path(path, flat = True)
    files = [f for f in files if await is_access_granted(f)]
    if len(files) == 0:
        raise HTTPException(status_code=404, detail="No files found")

    # return bundle of files
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

@router_api.get("/meta")
@handle_exception
async def get_file_meta(path: str, user: UserRecord = Depends(get_current_user)):
    logger.info(f"GET meta({path}), user: {user.username}")
    path = ensure_uri_compnents(path)
    get_fn = conn.file.get_file_record if not path.endswith("/") else conn.file.get_path_record
    record = await get_fn(path)
    if not record:
        raise HTTPException(status_code=404, detail="Path not found")
    return record

@router_api.post("/meta")
@handle_exception
async def update_file_meta(
    path: str, 
    perm: Optional[int] = None, 
    new_path: Optional[str] = None,
    user: UserRecord = Depends(get_current_user)
    ):
    if user.id == 0:
        raise HTTPException(status_code=401, detail="Permission denied")
    path = ensure_uri_compnents(path)
    if path.startswith("/"):
        path = path[1:]
    await conn.user.set_active(user.username)

    # file
    if not path.endswith("/"):
        file_record = await conn.file.get_file_record(path)
        if not file_record:
            logger.debug(f"Reject update meta request from {user.username} to {path}")
            raise HTTPException(status_code=404, detail="File not found")
        
        if not (user.is_admin or user.id == file_record.owner_id):
            logger.debug(f"Reject update meta request from {user.username} to {path}")
            raise HTTPException(status_code=403, detail="Permission denied")
        
        if perm is not None:
            logger.info(f"Update permission of {path} to {perm}")
            await conn.file.set_file_record(
                url = file_record.url, 
                permission = FileReadPermission(perm)
            )
    
        if new_path is not None:
            new_path = ensure_uri_compnents(new_path)
            logger.info(f"Update path of {path} to {new_path}")
            await conn.move_file(path, new_path)
    
    # directory
    else:
        assert perm is None, "Permission is not supported for directory"
        if new_path is not None:
            new_path = ensure_uri_compnents(new_path)
            logger.info(f"Update path of {path} to {new_path}")
            assert new_path.endswith("/"), "New path must end with /"
            if new_path.startswith("/"):
                new_path = new_path[1:]

            # check if new path is under the user's directory
            first_component = new_path.split("/")[0]
            if not (first_component == user.username or user.is_admin):
                raise HTTPException(status_code=403, detail="Permission denied, path must start with username")
            elif user.is_admin:
                _is_user = await conn.user.get_user(first_component)
                if not _is_user:
                    raise HTTPException(status_code=404, detail="User not found, path must start with username")

            # check if old path is under the user's directory (non-admin)
            if not path.startswith(f"{user.username}/") and not user.is_admin:
                raise HTTPException(status_code=403, detail="Permission denied, path must start with username")
            # currently only move own file, with overwrite
            await conn.move_path(path, new_path, user_id = user.id)

    return Response(status_code=200, content="OK")
    
@router_api.get("/whoami")
@handle_exception
async def whoami(user: UserRecord = Depends(get_current_user)):
    if user.id == 0:
        raise HTTPException(status_code=401, detail="Login required")
    user.credential = "__HIDDEN__"
    return user

# order matters
app.include_router(router_api)
app.include_router(router_fs)