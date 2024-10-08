import os
from pathlib import Path
import aiosqlite, aiofiles
from contextlib import asynccontextmanager
from dataclasses import dataclass
from asyncio import Semaphore, Lock
from functools import wraps

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

async def get_connection() -> aiosqlite.Connection:
    if not os.environ.get('SQLITE_TEMPDIR'):
        os.environ['SQLITE_TEMPDIR'] = str(DATA_HOME)
    # large blobs are stored in a separate database, should be more efficient
    conn = await aiosqlite.connect(DATA_HOME / 'index.db', timeout = 60)
    async with conn.cursor() as c:
        await c.execute(f"ATTACH DATABASE ? AS blobs", (str(DATA_HOME/'blobs.db'), ))
    await execute_sql(conn, 'pragma.sql')
    return conn


@dataclass
class SqlConnection:
    conn: aiosqlite.Connection
    is_available: bool = True

class SqlConnectionPool:
    _sem: Semaphore
    _w_sem: Semaphore
    def __init__(self):
        self._connections: list[SqlConnection] = []
        self._w_connection: None | SqlConnection = None
        self._lock = Lock()
    
    async def init(self, n_read: int):
        await self.close()
        self._connections = []
        for _ in range(n_read):
            conn = await get_connection()
            self._connections.append(SqlConnection(conn))
        self._w_connection = SqlConnection(await get_connection())
        self._sem = Semaphore(n_read)
        self._w_sem = Semaphore(1)
    
    @property
    def n_read(self):
        return len(self._connections)
    @property
    def sem(self):
        return self._sem
    @property
    def w_sem(self):
        return self._w_sem
    
    async def get(self, w: bool = False) -> SqlConnection:
        if len(self._connections) == 0:
            raise Exception("No available connections, please init the pool first")
        
        if w:
            assert self._w_connection
            if self._w_connection.is_available:
                self._w_connection.is_available = False
                return self._w_connection
            raise Exception("Write connection is not available")

        async with self._lock:
            i = 0
            for c in self._connections:
                i += 1
                if c.is_available:
                    print(f"Got connection {i}/{len(self._connections)}, sem: {self._sem._value}")
                    c.is_available = False
                    return c
        raise Exception("No available connections, impossible?")
    
    async def release(self, conn: SqlConnection):
        if conn == self._w_connection:
            conn.is_available = True
            return

        async with self._lock:
            if not conn in self._connections:
                raise Exception("Connection not in pool")
            conn.is_available = True
    
    async def close(self):
        for c in self._connections:
            await c.conn.close()
        if self._w_connection:
            await self._w_connection.conn.close()

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
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            async with global_connection(n_read):
                return await func(*args, **kwargs)
        return wrapper
    return decorator

@asynccontextmanager
async def unique_cursor(is_write: bool = False):
    if not is_write:
        async with g_pool.sem:
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
