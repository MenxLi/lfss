from typing import Optional, Any
import aiosqlite
from contextlib import asynccontextmanager
from .config import DATA_HOME
from .utils import debounce_async

class RequestDB:
    conn: aiosqlite.Connection
    def __init__(self):
        self.db = DATA_HOME / 'requests.db'

    async def init(self):
        self.conn = await aiosqlite.connect(self.db)
        await self.conn.execute('''
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                time FLOAT DEFAULT (strftime('%s', 'now')),
                method TEXT,
                path TEXT,
                headers TEXT,
                query TEXT,
                client TEXT,
                duration REAL, 
                request_size INTEGER, 
                response_size INTEGER, 
                status INTEGER
            )
        ''')
        return self
    
    def connect(self):
        @asynccontextmanager
        async def _mgr():
            await self.init()
            yield self
            await self.close()
        return _mgr()

    async def close(self):
        await self.conn.close()
    
    async def commit(self):
        await self.conn.commit()
    
    @debounce_async()
    async def ensure_commit_once(self):
        await self.commit()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc, tb):
        await self.commit()
    
    async def log_request(
        self, time: float, 
        method: str, path: str, 
        status: int, duration: float,
        headers: Optional[Any] = None, 
        query: Optional[Any] = None, 
        client: Optional[Any] = None,
        request_size: int = 0,
        response_size: int = 0
        ) -> int:
        method = str(method).upper()
        headers = str(headers)
        query = str(query)
        client = str(client)
        async with self.conn.execute('''
            INSERT INTO requests (
                time, method, path, headers, query, client, duration, request_size, response_size, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (time, method, path, headers, query, client, duration, request_size, response_size, status)) as cursor:
            assert cursor.lastrowid is not None
            return cursor.lastrowid
    
    async def shrink(self, max_rows: int = 1_000_000, time_before: float = 0):
        async with aiosqlite.connect(self.db) as conn:

            # remove all but the last max_rows
            res = await (await conn.execute('SELECT COUNT(*) FROM requests')).fetchone()
            assert res is not None
            row_len = res[0]
            if row_len > max_rows:
                await conn.execute('''
                    DELETE FROM requests WHERE id NOT IN (
                        SELECT id FROM requests ORDER BY time DESC LIMIT ?
                    )
                ''', (max_rows,))

            # remove old requests that is older than time_before
            if time_before > 0:
                await conn.execute('''
                    DELETE FROM requests WHERE time < ?
                ''', (time_before,))

            await conn.commit()
        