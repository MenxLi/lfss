import os
from pathlib import Path
import asyncio, threading
import aiosqlite, aiofiles
from contextlib import asynccontextmanager
from dataclasses import dataclass
from asyncio import Semaphore, Lock
from functools import wraps
from typing import Callable, Awaitable, Optional, overload, TypeVar, Type
from abc import ABC, abstractmethod

from .log import get_logger
from .error import DatabaseLockedError, DatabaseTransactionError
from .config import DATA_HOME

async def execute_sql(conn: aiosqlite.Connection | aiosqlite.Cursor, name: str):
    this_dir = Path(__file__).parent
    sql_dir = this_dir.parent / 'sql'
    async with aiofiles.open(sql_dir / name, 'r') as f:
        sql = await f.read()
    sql = sql.split(';')
    for s in sql:
        await conn.execute(s)

async def get_connection(read_only: bool = False) -> aiosqlite.Connection:
    if not os.environ.get('SQLITE_TEMPDIR'):
        os.environ['SQLITE_TEMPDIR'] = str(DATA_HOME)

    def get_db_uri(path: Path, read_only: bool = False):
        return f"file:{path}?mode={ 'ro' if read_only else 'rwc' }"

    conn = await aiosqlite.connect(
        get_db_uri(DATA_HOME / 'index.db', read_only=read_only), 
        timeout = 10, uri = True
        )
    async with conn.cursor() as c:
        await c.execute(
            f"ATTACH DATABASE ? AS blobs", 
            (get_db_uri(DATA_HOME/'blobs.db', read_only=read_only), )
            )
    await execute_sql(conn, 'pragma.sql')
    return conn


@dataclass
class SqlConnection:
    conn: aiosqlite.Connection
    is_available: bool = True

class SqlConnectionPool:
    _r_sem: Semaphore
    _w_sem: Lock
    def __init__(self):
        self._readers: list[SqlConnection] = []
        self._writer: None | SqlConnection = None
        self.t_lock = threading.Lock()
    
    async def init(self, n_read: int):
        self._writer = SqlConnection(await get_connection(read_only=False))
        self._readers = [
            SqlConnection(await get_connection(read_only=True)) 
            for _ in range(n_read)
        ]

        self._w_sem = Lock()
        self._r_sem = Semaphore(n_read)
    
    def status(self):   # debug
        assert self._writer
        assert len(self._readers) == self.n_read
        n_free_readers = sum([1 for c in self._readers if c.is_available])
        n_free_writers = 1 if self._writer.is_available else 0
        n_free_r_sem = self._r_sem._value
        n_free_w_sem = 1 - self._w_sem.locked()
        assert n_free_readers == n_free_r_sem, f"{n_free_readers} != {n_free_r_sem}"
        assert n_free_writers == n_free_w_sem, f"{n_free_writers} != {n_free_w_sem}"
        return f"Readers: {n_free_readers}/{self.n_read}, Writers: {n_free_writers}/{1}"
    
    @property
    def n_read(self):
        return len(self._readers)
    @property
    def r_sem(self):
        return self._r_sem
    @property
    def w_sem(self):
        return self._w_sem
    
    def get(self, w: bool = False) -> SqlConnection:
        with self.t_lock:
            if w:
                assert self._writer
                if self._writer.is_available:
                    self._writer.is_available = False
                    return self._writer
                raise Exception("Write connection is not available")

            else:
                for c in self._readers:
                    if c.is_available:
                        c.is_available = False
                        return c
                raise Exception("No available connections, impossible?")
    
    def release(self, conn: SqlConnection):
        assert conn == self._writer or conn in self._readers
        with self.t_lock:
            conn.is_available = True
    
    async def close(self):
        asyncio.gather(*(
            [c.conn.close() for c in self._readers] 
            + ([self._writer.conn.close()] if self._writer else [])
        ))

# these two functions shold be called before and after the event loop
g_pool = SqlConnectionPool()
async def global_connection_init(n_read: int = 1):
    await g_pool.init(n_read)

async def global_connection_close():
    await g_pool.close()

@asynccontextmanager
async def global_connection(n_read: int = 1):
    await global_connection_init(n_read)
    try:
        yield g_pool
    finally:
        await global_connection_close()

def global_entrance(n_read: int = 1):
    def decorator(func: Callable[..., Awaitable]):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            async with global_connection(n_read):
                return await func(*args, **kwargs)
        return wrapper
    return decorator

def handle_sqlite_error(e: Exception):
    if 'database is locked' in str(e):
        raise DatabaseLockedError from e
    if 'cannot start a transaction within a transaction' in str(e):
        get_logger('database', global_instance=True).error(f"Unexpected error: {e}")
        raise DatabaseTransactionError from e
    raise e

@asynccontextmanager
async def unique_cursor(is_write: bool = False):
    if not is_write:
        async with g_pool.r_sem:
            connection_obj = g_pool.get()
            try:
                yield await connection_obj.conn.cursor()
            except Exception as e:
                handle_sqlite_error(e)
            finally:
                g_pool.release(connection_obj)
    else:
        async with g_pool.w_sem:
            connection_obj = g_pool.get(w=True)
            try:
                yield await connection_obj.conn.cursor()
            except Exception as e:
                handle_sqlite_error(e)
            finally:
                g_pool.release(connection_obj)

from contextlib import AbstractAsyncContextManager
class TransactionContextManager(ABC):
    @abstractmethod
    async def on_commit(self): ...
    @abstractmethod
    async def on_rollback(self): ...
TCM_T = TypeVar('TCM_T', bound=TransactionContextManager)
@overload
def transaction(tcm_cls: None = None, args: tuple = ..., kwargs: dict = ...) \
    -> AbstractAsyncContextManager[aiosqlite.Cursor]: ...
@overload
def transaction(tcm_cls: Type[TCM_T] | TCM_T, args: tuple = ..., kwargs: dict = ...) \
    -> AbstractAsyncContextManager[tuple[aiosqlite.Cursor, TCM_T]]: ...
@asynccontextmanager
async def transaction(tcm_cls: Optional[Type[TCM_T] | TCM_T] = None, args: Optional[tuple] = None, kwargs: Optional[dict] = None):
    args = args or ()
    kwargs = kwargs or {}
    tcm = tcm_cls if isinstance(tcm_cls, TransactionContextManager) \
        else (tcm_cls(*args, **kwargs) if tcm_cls else None)
    async with unique_cursor(is_write=True) as cur:
        try:
            await cur.execute('BEGIN')
            if tcm is None:
                yield cur
            else:
                yield cur, tcm
            await cur.execute('COMMIT')
            if tcm is not None:
                await tcm.on_commit()
        except Exception as e:
            get_logger('database', global_instance=True).error(f"Error in transaction: {e}, rollback.")
            await cur.execute('ROLLBACK')
            if tcm is not None:
                try: await tcm.on_rollback()
                except Exception as e2: 
                    get_logger('database', global_instance=True).error(f"Error in on_rollback: {e2}")
            raise
