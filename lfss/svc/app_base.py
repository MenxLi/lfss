import asyncio, time, os
from contextlib import asynccontextmanager
from typing import Optional
from functools import wraps

from fastapi import FastAPI, HTTPException, Request, Response, APIRouter, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, HTTPBasic, HTTPBasicCredentials

from ..eng.log import get_logger
from ..eng.datatype import UserRecord
from ..eng.connection_pool import unique_cursor
from ..eng.database import Database, UserConn, delayed_log_activity, DECOY_USER
from ..eng.connection_pool import global_connection_init, global_connection_close
from ..eng.utils import wait_for_debounce_tasks, now_stamp, hash_credential
from ..eng.error import *
from ..eng.config import DEBUG_MODE
from .request_log import RequestDB

ENABLE_WEBDAV = os.environ.get("LFSS_WEBDAV", "0") == "1"
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
            if isinstance(e, HTTPException): 
                print(f"HTTPException: {e}, detail: {e.detail}")
            if isinstance(e, HTTPException): raise e
            if isinstance(e, StorageExceededError): raise HTTPException(status_code=413, detail=str(e))
            if isinstance(e, PermissionError): raise HTTPException(status_code=403, detail=str(e))
            if isinstance(e, InvalidPathError): raise HTTPException(status_code=400, detail=str(e))
            if isinstance(e, InvalidOptionsError): raise HTTPException(status_code=400, detail=str(e))
            if isinstance(e, InvalidDataError): raise HTTPException(status_code=400, detail=str(e))
            if isinstance(e, FileNotFoundError): raise HTTPException(status_code=404, detail=str(e))
            if isinstance(e, FileDuplicateError): raise HTTPException(status_code=409, detail=str(e))
            if isinstance(e, FileExistsError): raise HTTPException(status_code=409, detail=str(e))
            if isinstance(e, TooManyItemsError): raise HTTPException(status_code=400, detail=str(e))
            if isinstance(e, DatabaseLockedError): raise HTTPException(status_code=503, detail=str(e))
            if isinstance(e, FileLockedError): raise HTTPException(status_code=423, detail=str(e))
            logger.error(f"Uncaptured error in {fn.__name__}: {e}")
            raise 
    return wrapper

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
        logger_failed_request.error(f"{request.method} {request.url.path} \033[91m{response.status_code}\033[0m")
    if DEBUG_MODE:
        print(f"{request.method} {request.url.path} {response.status_code} {response_time:.3f}s")
        print(f"Request headers: {dict(request.headers)}")
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

async def get_credential_from_params(request: Request):
    return request.query_params.get("token")
async def get_current_user(
    h_token: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)), 
    b_token: Optional[HTTPBasicCredentials] = Depends(HTTPBasic(auto_error=False)),
    q_token: Optional[str] = Depends(get_credential_from_params)
    ):
    """
    First try to get the user from the bearer token, 
    if not found, try to get the user from the query parameter
    """
    async with unique_cursor() as conn:
        uconn = UserConn(conn)
        if h_token:
            user = await uconn.get_user_by_credential(h_token.credentials)
            if not user: raise HTTPException(status_code=401, detail="Invalid token", headers={"WWW-Authenticate": "Basic" if ENABLE_WEBDAV else "Bearer"})
        elif ENABLE_WEBDAV and b_token:
            user = await uconn.get_user_by_credential(hash_credential(b_token.username, b_token.password))
            if not user: raise HTTPException(status_code=401, detail="Invalid token", headers={"WWW-Authenticate": "Basic" if ENABLE_WEBDAV else "Bearer"})
        elif q_token:
            user = await uconn.get_user_by_credential(q_token)
            if not user: raise HTTPException(status_code=401, detail="Invalid token", headers={"WWW-Authenticate": "Basic" if ENABLE_WEBDAV else "Bearer"})
        else:
            return DECOY_USER

    if not user.id == 0:
        await delayed_log_activity(user.username)

    return user

async def registered_user(user: UserRecord = Depends(get_current_user)):
    if user.id == 0:
        raise HTTPException(status_code=401, detail="Permission denied", headers={"WWW-Authenticate": "Basic" if ENABLE_WEBDAV else "Bearer"})
    return user

router_api = APIRouter(prefix="/_api")
router_dav = APIRouter(prefix="")
router_fs = APIRouter(prefix="")

__all__ = [
    "app", "db", "logger", 
    "handle_exception", "skip_request_log", 
    "router_api", "router_fs", "router_dav", 
    "get_current_user", "registered_user"
    ]