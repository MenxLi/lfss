from typing import Optional, Any
import aiosqlite
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
                time TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
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

    async def close(self):
        await self.conn.close()
    
    async def commit(self):
        await self.conn.commit()
    
    @debounce_async(0.1)
    async def ensure_commit_once(self):
        await self.commit()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc, tb):
        await self.commit()
    
    async def log_request(
        self, method: str, path: str, 
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
                method, path, headers, query, client, duration, request_size, response_size, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (method, path, headers, query, client, duration, request_size, response_size, status)) as cursor:
            assert cursor.lastrowid is not None
            return cursor.lastrowid
        