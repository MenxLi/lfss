import asyncio, time
from contextlib import asynccontextmanager
from functools import wraps

from fastapi import FastAPI, HTTPException, Request, Response, APIRouter
from fastapi.middleware.cors import CORSMiddleware

from ..eng.log import get_logger
from ..eng.database import Database
from ..eng.connection_pool import global_connection_init, global_connection_close
from ..eng.utils import wait_for_debounce_tasks, now_stamp
from ..eng.error import StorageExceededError, InvalidPathError, TooManyItemsError, DatabaseLockedError
from .request_log import RequestDB

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
            if isinstance(e, FileNotFoundError): raise HTTPException(status_code=404, detail=str(e))
            if isinstance(e, FileExistsError): raise HTTPException(status_code=409, detail=str(e))
            if isinstance(e, TooManyItemsError): raise HTTPException(status_code=400, detail=str(e))
            if isinstance(e, DatabaseLockedError): raise HTTPException(status_code=503, detail=str(e))
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
        logger_failed_request.error(f"{request.method} {request.url.path} {response.status_code}")
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

router_api = APIRouter(prefix="/_api")
router_dav = APIRouter(prefix="")
router_fs = APIRouter(prefix="")

__all__ = [
    "app", "db", "logger", 
    "handle_exception", "skip_request_log", 
    "router_api", "router_fs", "router_dav"
    ]