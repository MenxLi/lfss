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
from .config import MAX_BUNDLE_BYTES, MAX_FILE_BYTES, LARGE_FILE_BYTES, CHUNK_SIZE
from .utils import ensure_uri_compnents, format_last_modified, now_stamp, wait_for_debounce_tasks
from .connection_pool import global_connection_init, global_connection_close, unique_cursor
from .database import Database, DECOY_USER, check_user_permission, UserConn, FileConn, delayed_log_activity
from .datatype import (
    FileReadPermission, FileRecord, UserRecord, PathContents, 
    FileSortKey, DirSortKey
)
from .thumb import get_thumb

logger = get_logger("server", term_level="DEBUG")
logger_failed_request = get_logger("failed_requests", term_level="INFO")
db = Database()
req_conn = RequestDB()

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db
    try:
        await global_connection_init(n_read = 2)
        await asyncio.gather(db.init(), req_conn.init())
        yield
        await req_conn.commit()
    finally:
        await wait_for_debounce_tasks()
        await asyncio.gather(req_conn.close(), global_connection_close())

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
            if isinstance(e, TooManyItemsError): raise HTTPException(status_code=400, detail=str(e))
            logger.error(f"Uncaptured error in {fn.__name__}: {e}")
            raise 
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
    async with unique_cursor() as conn:
        uconn = UserConn(conn)
        if token:
            user = await uconn.get_user_by_credential(token.credentials)
        else:
            if not q_token:
                return DECOY_USER
            else:
                user = await uconn.get_user_by_credential(q_token)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user

async def registered_user(user: UserRecord = Depends(get_current_user)):
    if user.id == 0:
        raise HTTPException(status_code=401, detail="Permission denied")
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

    if response.headers.get("X-Skip-Log", None) is not None:
        return response

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

def skip_request_log(fn):
    @wraps(fn)
    async def wrapper(*args, **kwargs):
        response = await fn(*args, **kwargs)
        assert isinstance(response, Response), "Response expected"
        response.headers["X-Skip-Log"] = "1"
        return response
    return wrapper

router_fs = APIRouter(prefix="")

@skip_request_log
async def emit_thumbnail(
    path: str, download: bool,
    create_time: Optional[str] = None
    ):
    if path.endswith("/"):
        fname = path.split("/")[-2]
    else:
        fname = path.split("/")[-1]
    if (thumb_res := await get_thumb(path)) is None:
        return Response(status_code=415, content="Thumbnail not supported")
    thumb_blob, mime_type = thumb_res
    disp = "inline" if not download else "attachment"
    headers = {
        "Content-Disposition": f"{disp}; filename={fname}.thumb.jpg",
        "Content-Length": str(len(thumb_blob)),
    }
    if create_time is not None:
        headers["Last-Modified"] = format_last_modified(create_time)
    return Response(
        content=thumb_blob, media_type=mime_type, headers=headers
    )
async def emit_file(
    file_record: FileRecord, 
    media_type: Optional[str] = None, 
    disposition = "attachment"
    ):
    if media_type is None:
        media_type = file_record.mime_type
    path = file_record.url
    fname = path.split("/")[-1]
    if not file_record.external:
        fblob = await db.read_file(path)
        return Response(
            content=fblob, media_type=media_type, headers={
                "Content-Disposition": f"{disposition}; filename={fname}", 
                "Content-Length": str(len(fblob)), 
                "Last-Modified": format_last_modified(file_record.create_time)
            }
        )
    else:
        return StreamingResponse(
            await db.read_file_stream(path), media_type=media_type, headers={
                "Content-Disposition": f"{disposition}; filename={fname}", 
                "Content-Length": str(file_record.file_size),
                "Last-Modified": format_last_modified(file_record.create_time)
            }
        )

@router_fs.get("/{path:path}")
@handle_exception
async def get_file(
    path: str, 
    download: bool = False, thumb: bool = False,
    user: UserRecord = Depends(get_current_user)
    ):
    path = ensure_uri_compnents(path)

    # handle directory query
    if path == "": path = "/"
    if path.endswith("/"):
        # return file under the path as json
        async with unique_cursor() as conn:
            fconn = FileConn(conn)
            if user.id == 0:
                raise HTTPException(status_code=401, detail="Permission denied, credential required")
            if thumb:
                return await emit_thumbnail(path, download, create_time=None)
            
            if path == "/":
                return PathContents(
                    dirs = await fconn.list_root_dirs(user.username, skim=True) \
                        if not user.is_admin else await fconn.list_root_dirs(skim=True),
                    files = []
                )

            if not path.startswith(f"{user.username}/") and not user.is_admin:
                raise HTTPException(status_code=403, detail="Permission denied, path must start with username")

            return await fconn.list_path(path)
    
    # handle file query
    async with unique_cursor() as conn:
        fconn = FileConn(conn)
        file_record = await fconn.get_file_record(path)
        if not file_record:
            raise HTTPException(status_code=404, detail="File not found")

        uconn = UserConn(conn)
        owner = await uconn.get_user_by_id(file_record.owner_id)

    assert owner is not None, "Owner not found"
    allow_access, reason = check_user_permission(user, owner, file_record)
    if not allow_access:
        raise HTTPException(status_code=403, detail=reason)
    
    if thumb:
        return await emit_thumbnail(path, download, create_time=file_record.create_time)
    else:
        if download:
            return await emit_file(file_record, 'application/octet-stream', "attachment")
        else:
            return await emit_file(file_record, None, "inline")

@router_fs.put("/{path:path}")
@handle_exception
async def put_file(
    request: Request, 
    path: str, 
    conflict: Literal["overwrite", "skip", "abort"] = "abort",
    permission: int = 0,
    user: UserRecord = Depends(registered_user)):
    path = ensure_uri_compnents(path)
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
    async with unique_cursor() as conn:
        fconn = FileConn(conn)
        file_record = await fconn.get_file_record(path)

    if file_record:
        if conflict == "abort":
            raise HTTPException(status_code=409, detail="File exists")
        if conflict == "skip":
            return Response(status_code=200, headers={
                "Content-Type": "application/json",
            }, content=json.dumps({"url": path}))
        exists_flag = True
        if not user.is_admin and not file_record.owner_id == user.id:
            raise HTTPException(status_code=403, detail="Permission denied, cannot overwrite other's file")
        await db.delete_file(path)
    
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
    
    # check file type
    assert not path.endswith("/"), "Path must be a file"
    fname = path.split("/")[-1]
    mime_t, _ = mimetypes.guess_type(fname)
    if mime_t is None:
        mime_t = mimesniff.what(blobs)
    if mime_t is None:
        mime_t = "application/octet-stream"

    if len(blobs) > LARGE_FILE_BYTES:
        async def blob_reader():
            for b in range(0, len(blobs), CHUNK_SIZE):
                yield blobs[b:b+CHUNK_SIZE]
        await db.save_file(user.id, path, blob_reader(), permission = FileReadPermission(permission), mime_type = mime_t)
    else:
        await db.save_file(user.id, path, blobs, permission = FileReadPermission(permission), mime_type=mime_t)

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
async def delete_file(path: str, user: UserRecord = Depends(registered_user)):
    path = ensure_uri_compnents(path)
    if not path.startswith(f"{user.username}/") and not user.is_admin:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    logger.info(f"DELETE {path}, user: {user.username}")

    if path.endswith("/"):
        res = await db.delete_path(path, user if not user.is_admin else None)
    else:
        res = await db.delete_file(path, user if not user.is_admin else None)

    await delayed_log_activity(user.username)
    if res:
        return Response(status_code=200, content="Deleted")
    else:
        return Response(status_code=404, content="Not found")

router_api = APIRouter(prefix="/_api")

@router_api.get("/bundle")
@handle_exception
async def bundle_files(path: str, user: UserRecord = Depends(registered_user)):
    logger.info(f"GET bundle({path}), user: {user.username}")
    path = ensure_uri_compnents(path)
    assert path.endswith("/") or path == ""

    if not path == "" and path[0] == "/":   # adapt to both /path and path
        path = path[1:]
    
    owner_records_cache: dict[int, UserRecord] = {}     # cache owner records, ID -> UserRecord
    async def is_access_granted(file_record: FileRecord):
        owner_id = file_record.owner_id
        owner = owner_records_cache.get(owner_id, None)
        if owner is None:
            async with unique_cursor() as conn:
                uconn = UserConn(conn)
                owner = await uconn.get_user_by_id(owner_id)
                assert owner is not None, "Owner not found"
            owner_records_cache[owner_id] = owner
            
        allow_access, _ = check_user_permission(user, owner, file_record)
        return allow_access
    
    async with unique_cursor() as conn:
        fconn = FileConn(conn)
        files = await fconn.list_path_files(
            url = path, flat = True, 
            limit=(await fconn.count_path_files(url = path, flat = True))
            )
    files = [f for f in files if await is_access_granted(f)]
    if len(files) == 0:
        raise HTTPException(status_code=404, detail="No files found")

    # return bundle of files
    total_size = sum([f.file_size for f in files])
    if total_size > MAX_BUNDLE_BYTES:
        raise HTTPException(status_code=400, detail="Too large to zip")

    file_paths = [f.url for f in files]
    zip_buffer = await db.zip_path(path, file_paths)
    return Response(
        content=zip_buffer.getvalue(), media_type="application/zip", headers={
            "Content-Disposition": f"attachment; filename=bundle.zip", 
            "Content-Length": str(zip_buffer.getbuffer().nbytes)
        }
    )

@router_api.get("/meta")
@handle_exception
async def get_file_meta(path: str, user: UserRecord = Depends(registered_user)):
    logger.info(f"GET meta({path}), user: {user.username}")
    path = ensure_uri_compnents(path)
    is_file = not path.endswith("/")
    async with unique_cursor() as conn:
        fconn = FileConn(conn)
        if is_file:
            record = await fconn.get_file_record(path)
            if not record:
                raise HTTPException(status_code=404, detail="File not found")
            if not path.startswith(f"{user.username}/") and not user.is_admin:
                uconn = UserConn(conn)
                owner = await uconn.get_user_by_id(record.owner_id)
                assert owner is not None, "Owner not found"
                is_allowed, reason = check_user_permission(user, owner, record)
                if not is_allowed:
                    raise HTTPException(status_code=403, detail=reason)
        else:
            record = await fconn.get_path_record(path)
            if not path.startswith(f"{user.username}/") and not user.is_admin:
                raise HTTPException(status_code=403, detail="Permission denied")
    return record

@router_api.post("/meta")
@handle_exception
async def update_file_meta(
    path: str, 
    perm: Optional[int] = None, 
    new_path: Optional[str] = None,
    user: UserRecord = Depends(registered_user)
    ):
    path = ensure_uri_compnents(path)
    if path.startswith("/"):
        path = path[1:]
    await delayed_log_activity(user.username)

    # file
    if not path.endswith("/"):
        if perm is not None:
            logger.info(f"Update permission of {path} to {perm}")
            await db.update_file_record(
                user = user,
                url = path, 
                permission = FileReadPermission(perm)
            )
    
        if new_path is not None:
            new_path = ensure_uri_compnents(new_path)
            logger.info(f"Update path of {path} to {new_path}")
            await db.move_file(path, new_path, user)
    
    # directory
    else:
        assert perm is None, "Permission is not supported for directory"
        if new_path is not None:
            new_path = ensure_uri_compnents(new_path)
            logger.info(f"Update path of {path} to {new_path}")
            # currently only move own file, with overwrite
            await db.move_path(user, path, new_path)

    return Response(status_code=200, content="OK")

async def validate_path_permission(path: str, user: UserRecord):
    if not path.endswith("/"):
        raise HTTPException(status_code=400, detail="Path must end with /")
    if not path.startswith(f"{user.username}/") and not user.is_admin:
        raise HTTPException(status_code=403, detail="Permission denied")

@router_api.get("/count-files")
async def count_files(path: str, flat: bool = False, user: UserRecord = Depends(registered_user)):
    await validate_path_permission(path, user)
    path = ensure_uri_compnents(path)
    async with unique_cursor() as conn:
        fconn = FileConn(conn)
        return { "count": await fconn.count_path_files(url = path, flat = flat) }
@router_api.get("/list-files")
async def list_files(
    path: str, offset: int = 0, limit: int = 1000,
    order_by: FileSortKey = "", order_desc: bool = False,
    flat: bool = False, user: UserRecord = Depends(registered_user)
    ):
    await validate_path_permission(path, user)
    path = ensure_uri_compnents(path)
    async with unique_cursor() as conn:
        fconn = FileConn(conn)
        return await fconn.list_path_files(
            url = path, offset = offset, limit = limit,
            order_by=order_by, order_desc=order_desc, 
            flat=flat
        )

@router_api.get("/count-dirs")
async def count_dirs(path: str, user: UserRecord = Depends(registered_user)):
    await validate_path_permission(path, user)
    path = ensure_uri_compnents(path)
    async with unique_cursor() as conn:
        fconn = FileConn(conn)
        return { "count": await fconn.count_path_dirs(url = path) }
@router_api.get("/list-dirs")
async def list_dirs(
    path: str, offset: int = 0, limit: int = 1000,
    order_by: DirSortKey = "", order_desc: bool = False,
    skim: bool = True, user: UserRecord = Depends(registered_user)
    ):
    await validate_path_permission(path, user)
    path = ensure_uri_compnents(path)
    async with unique_cursor() as conn:
        fconn = FileConn(conn)
        return await fconn.list_path_dirs(
            url = path, offset = offset, limit = limit,
            order_by=order_by, order_desc=order_desc, skim=skim
        )
    
@router_api.get("/whoami")
@handle_exception
async def whoami(user: UserRecord = Depends(registered_user)):
    user.credential = "__HIDDEN__"
    return user

# order matters
app.include_router(router_api)
app.include_router(router_fs)