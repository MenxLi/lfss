
from typing import Optional
from abc import ABC, abstractmethod

import asyncio
import aiosqlite
import aiofiles
import aiofiles.os
import aiofiles.ospath

import dataclasses
from .config import DATA_HOME

_g_conn: Optional[aiosqlite.Connection] = None

class DBConnBase(ABC):

    @property
    def conn(self)->aiosqlite.Connection:
        global _g_conn
        if _g_conn is None:
            raise ValueError('Connection not initialized, did you forget to call super().init()?')
        return _g_conn

    @abstractmethod
    async def init(self):
        """Should return self"""
        global _g_conn
        if _g_conn is None:
            _g_conn = await aiosqlite.connect(DATA_HOME / 'index.db')

    async def commit(self):
        await self.conn.commit()

async def commit_all():
    global _g_conn
    if _g_conn is not None:
        await _g_conn.commit()

async def close_all():
    global _g_conn
    if _g_conn is not None:
        await _g_conn.close()

@dataclasses.dataclass
class DBUserRecord:
    id: int
    username: str
    password: str
    is_admin: bool
    create_time: str
    last_active: str

    def __str__(self):
        return f"User {self.username} (id={self.id}, admin={self.is_admin}, created at {self.create_time}, last active at {self.last_active})"

DECOY_USER = DBUserRecord(0, 'decoy', 'decoy', False, '2021-01-01 00:00:00', '2021-01-01 00:00:00')
class UserConn(DBConnBase):

    @staticmethod
    def parse_record(record: list) -> DBUserRecord:
        return DBUserRecord(*record)

    async def init(self):
        await super().init()
        await self.conn.execute('''
        CREATE TABLE IF NOT EXISTS user (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username VARCHAR(255) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            is_admin BOOLEAN DEFAULT FALSE,
            create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        return self
    
    async def get_user(self, username: str) -> Optional[DBUserRecord]:
        async with self.conn.execute("SELECT * FROM user WHERE username = ?", (username, )) as cursor:
            res = await cursor.fetchone()
        
        if res is None:
            return None
        return self.parse_record(res)
    
    async def create_user(self, username: str, password: str, is_admin: bool = False) -> int:
        assert await self.get_user(username) is None
        async with self.conn.execute("INSERT INTO user (username, password, is_admin) VALUES (?, ?, ?)", (username, password, is_admin)) as cursor:
            return cursor.lastrowid
    
    async def set_user(self, username: str, password: str, is_admin: bool = False):
        await self.conn.execute("UPDATE user SET password = ?, is_admin = ? WHERE username = ?", (password, is_admin, username))
    
    async def all(self):
        async with self.conn.execute("SELECT * FROM user") as cursor:
            async for record in cursor:
                yield self.parse_record(record)
    
    async def set_active(self, username: str):
        await self.conn.execute("UPDATE user SET last_active = CURRENT_TIMESTAMP WHERE username = ?", (username, ))
    
    async def delete_user(self, username: str):
        await self.conn.execute("DELETE FROM user WHERE username = ?", (username, ))


@dataclasses.dataclass
class FileDBRecord:
    url: str
    user_id: int
    file_path: str
    create_time: str

    def __str__(self):
        return f"File {self.url} (user={self.user_id}, created at {self.create_time}, path={self.file_path})"
    
async def _remove_files_if_exist(files: list):
    async def remove_file(file_path):
        if await aiofiles.ospath.exists(file_path):
            await aiofiles.os.remove(file_path)
    await asyncio.gather(*[remove_file(f) for f in files])

class FileConn(DBConnBase):

    @staticmethod
    def parse_record(record: list) -> FileDBRecord:
        return FileDBRecord(*record)
    
    async def init(self):
        await super().init()
        await self.conn.execute('''
        CREATE TABLE IF NOT EXISTS file (
            url VARCHAR(255) PRIMARY KEY,
            user_id INTEGER NOT NULL,
            file_path VARCHAR(255) NOT NULL,
            create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        return self
    
    async def get_file_record(self, url: str) -> Optional[FileDBRecord]:
        async with self.conn.execute("SELECT * FROM file WHERE url = ?", (url, )) as cursor:
            res = await cursor.fetchone()
        if res is None:
            return None
        return self.parse_record(res)
    
    async def create_file_record(self, url: str, user_id: int, file_path: str):
        assert await self.get_file_record(url) is None
        await self.conn.execute("INSERT INTO file (url, user_id, file_path) VALUES (?, ?, ?)", (url, user_id, file_path))
    
    async def delete_file(self, url: str, remove_file: bool = True):
        file_record = await self.get_file_record(url)
        if file_record is None: return
        if remove_file:
            await _remove_files_if_exist([file_record.file_path])
        self.conn.execute("DELETE FROM file WHERE url = ?", (url, ))
    
    async def delete_user_files(self, user_id: int, remove_files: bool = True):
        async with self.conn.execute("SELECT * FROM file WHERE user_id = ?", (user_id, )) as cursor:
            res = await cursor.fetchall()
        if remove_files:
            await _remove_files_if_exist([self.parse_record(r).file_path for r in res])
        await self.conn.execute("DELETE FROM file WHERE user_id = ?", (user_id, ))
    
    async def delete_path_files(self, path: str, remove_files: bool = True):
        async with self.conn.execute("SELECT * FROM file WHERE file_path LIKE ?", (path + '%', )) as cursor:
            res = await cursor.fetchall()
        if remove_files:
            await _remove_files_if_exist([self.parse_record(r).file_path for r in res])
        await self.conn.execute("DELETE FROM file WHERE file_path LIKE ?", (path + '%', ))
