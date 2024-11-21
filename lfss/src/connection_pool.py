import os
from pathlib import Path
import aiosqlite, aiofiles
from contextlib import asynccontextmanager
from dataclasses import dataclass
from asyncio import Semaphore, Lock
from functools import wraps
from typing import Callable, Awaitable

from .log import get_logger
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
        timeout = 60, uri = True
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
    _w_sem: Lock | Semaphore
    def __init__(self):
        self._readers: list[SqlConnection] = []
        self._writer: None | SqlConnection = None
        self._lock = Lock()
    
    async def init(self, n_read: int):
        await self.close()
        self._readers = []

        self._writer = SqlConnection(await get_connection(read_only=False))
        self._w_sem = Lock()
        # self._w_sem = Semaphore(1)

        for _ in range(n_read):
            conn = await get_connection(read_only=True)
            self._readers.append(SqlConnection(conn))
        self._r_sem = Semaphore(n_read)
    
    @property
    def n_read(self):
        return len(self._readers)
    @property
    def r_sem(self):
        return self._r_sem
    @property
    def w_sem(self):
        return self._w_sem
    
    async def get(self, w: bool = False) -> SqlConnection:
        if len(self._readers) == 0:
            raise Exception("No available connections, please init the pool first")
        
        async with self._lock:
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
    
    async def release(self, conn: SqlConnection):
        async with self._lock:
            if conn == self._writer:
                conn.is_available = True
                return

            if not conn in self._readers:
                raise Exception("Connection not in pool")
            conn.is_available = True
    
    async def close(self):
        for c in self._readers:
            await c.conn.close()
        if self._writer:
            await self._writer.conn.close()

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

@asynccontextmanager
async def unique_cursor(is_write: bool = False):
    if not is_write:
        async with g_pool.r_sem:
            connection_obj = await g_pool.get()
            try:
                yield await connection_obj.conn.cursor()
            finally:
                await g_pool.release(connection_obj)
    else:
        async with g_pool.w_sem:
            connection_obj = await g_pool.get(w=True)
            try:
                yield await connection_obj.conn.cursor()
            finally:
                await g_pool.release(connection_obj)

# todo: add exclusive transaction option
@asynccontextmanager
async def transaction():
    async with unique_cursor(is_write=True) as cur:
        try:
            await cur.execute('BEGIN')
            yield cur
            await cur.execute('COMMIT')
        except Exception as e:
            get_logger('database', global_instance=True).error(f"Error in transaction: {e}, rollback.")
            await cur.execute('ROLLBACK')
            raise e
