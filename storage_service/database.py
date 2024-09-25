
from typing import Optional
from abc import ABC, abstractmethod

import dataclasses, hashlib
from enum import IntEnum

import asyncio
import aiosqlite
import aiofiles
import aiofiles.os
import aiofiles.ospath

from .config import DATA_HOME, FILE_ROOT
from .log import get_logger

_g_conn: Optional[aiosqlite.Connection] = None

def hash_credential(username, password):
    return hashlib.sha256((username + password).encode()).hexdigest()

class DBConnBase(ABC):
    logger = get_logger('database', global_instance=True)

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

@dataclasses.dataclass
class DBUserRecord:
    id: int
    username: str
    credential: str
    is_admin: bool
    create_time: str
    last_active: str

    def __str__(self):
        return f"User {self.username} (id={self.id}, admin={self.is_admin}, created at {self.create_time}, last active at {self.last_active})"

DECOY_USER = DBUserRecord(0, 'decoy', 'decoy', False, '2021-01-01 00:00:00', '2021-01-01 00:00:00')
class UserConn(DBConnBase):

    @staticmethod
    def parse_record(record) -> DBUserRecord:
        return DBUserRecord(*record)

    async def init(self):
        await super().init()
        await self.conn.execute('''
        CREATE TABLE IF NOT EXISTS user (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username VARCHAR(255) UNIQUE NOT NULL,
            credential VARCHAR(255) NOT NULL,
            is_admin BOOLEAN DEFAULT FALSE,
            create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        return self
    
    async def get_user(self, username: str) -> Optional[DBUserRecord]:
        async with self.conn.execute("SELECT * FROM user WHERE username = ?", (username, )) as cursor:
            res = await cursor.fetchone()
        
        if res is None: return None
        return self.parse_record(res)
    
    async def get_user_by_id(self, user_id: int) -> Optional[DBUserRecord]:
        async with self.conn.execute("SELECT * FROM user WHERE id = ?", (user_id, )) as cursor:
            res = await cursor.fetchone()
        
        if res is None: return None
        return self.parse_record(res)
    
    async def get_user_by_credential(self, credential: str) -> Optional[DBUserRecord]:
        async with self.conn.execute("SELECT * FROM user WHERE credential = ?", (credential, )) as cursor:
            res = await cursor.fetchone()
        
        if res is None: return None
        return self.parse_record(res)
    
    async def create_user(self, username: str, password: str, is_admin: bool = False) -> int:
        assert not username.startswith('_'), "Error: reserved username"
        self.logger.debug(f"Creating user {username}")
        credential = hash_credential(username, password)
        assert await self.get_user(username) is None
        async with self.conn.execute("INSERT INTO user (username, credential, is_admin) VALUES (?, ?, ?)", (username, credential, is_admin)) as cursor:
            self.logger.info(f"User {username} created")
            assert cursor.lastrowid is not None
            return cursor.lastrowid
    
    async def set_user(self, username: str, password: Optional[str] = None, is_admin: Optional[bool] = None):
        assert not username.startswith('_'), "Error: reserved username"
        if password is not None:
            credential = hash_credential(username, password)
        else:
            async with self.conn.execute("SELECT credential FROM user WHERE username = ?", (username, )) as cursor:
                res = await cursor.fetchone()
                assert res is not None, f"User {username} not found"
                credential = res[0]
        
        if is_admin is None:
            async with self.conn.execute("SELECT is_admin FROM user WHERE username = ?", (username, )) as cursor:
                res = await cursor.fetchone()
                assert res is not None, f"User {username} not found"
                is_admin = res[0]

        await self.conn.execute("UPDATE user SET credential = ?, is_admin = ? WHERE username = ?", (credential, is_admin, username))
        self.logger.info(f"User {username} updated")
    
    async def all(self):
        async with self.conn.execute("SELECT * FROM user") as cursor:
            async for record in cursor:
                yield self.parse_record(record)
    
    async def set_active(self, username: str):
        await self.conn.execute("UPDATE user SET last_active = CURRENT_TIMESTAMP WHERE username = ?", (username, ))
    
    async def delete_user(self, username: str):
        await self.conn.execute("DELETE FROM user WHERE username = ?", (username, ))
        self.logger.info(f"Delete user {username}")

class FileReadPermission(IntEnum):
    PUBLIC = 0          # accessible by anyone
    PROTECTED = 1       # accessible by any user
    PRIVATE = 2         # accessible by owner only (including admin)

@dataclasses.dataclass
class FileDBRecord:
    url: str
    user_id: int
    file_path: str      # relative to FILE_ROOT
    file_size: int
    create_time: str
    permission: FileReadPermission

    def __str__(self):
        return f"File {self.url} (user={self.user_id}, created at {self.create_time}, path={self.file_path}, permission={self.permission}, size={self.file_size})"

@dataclasses.dataclass
class DirectoryRecord:
    url: str
    size: int

    def __str__(self):
        return f"Directory {self.url} (size={self.size})"
    
class FileConn(DBConnBase):

    @staticmethod
    def parse_record(record) -> FileDBRecord:
        return FileDBRecord(*record)
    
    async def init(self):
        await super().init()
        await self.conn.execute('''
        CREATE TABLE IF NOT EXISTS file (
            url VARCHAR(255) PRIMARY KEY,
            user_id INTEGER NOT NULL,
            file_path VARCHAR(255) NOT NULL,
            file_size INTEGER,
            create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
            permission INTEGER DEFAULT 0
        )
        ''')
        return self
    
    async def get_file_record(self, url: str) -> Optional[FileDBRecord]:
        async with self.conn.execute("SELECT * FROM file WHERE url = ?", (url, )) as cursor:
            res = await cursor.fetchone()
        if res is None:
            return None
        return self.parse_record(res)
    
    async def get_user_file_records(self, user_id: int) -> list[FileDBRecord]:
        async with self.conn.execute("SELECT * FROM file WHERE user_id = ?", (user_id, )) as cursor:
            res = await cursor.fetchall()
        return [self.parse_record(r) for r in res]
    
    async def get_path_records(self, url: str) -> list[FileDBRecord]:
        async with self.conn.execute("SELECT * FROM file WHERE url LIKE ?", (url + '%', )) as cursor:
            res = await cursor.fetchall()
        return [self.parse_record(r) for r in res]
    
    async def list_path(self, url: str) -> tuple[list[DirectoryRecord], list[FileDBRecord]]:
        if not url.endswith('/'):
            url += '/'
        async with self.conn.execute("SELECT * FROM file WHERE url LIKE ? AND url NOT LIKE ?", (url + '%', url + '%/%')) as cursor:
            res = await cursor.fetchall()
        files = [self.parse_record(r) for r in res]

        # substr indexing starts from 1
        async with self.conn.execute(
            """
            SELECT DISTINCT 
                SUBSTR(
                    url, 
                    1 + LENGTH(?),
                    INSTR(SUBSTR(url, 1 + LENGTH(?)), '/') - 1
                ) AS subdir 
                FROM file WHERE url LIKE ?
            """, 
            (url, url, url + '%')
            ) as cursor:
            res = await cursor.fetchall()
        dirs_str = [r[0] for r in res if r[0] != '/']
        dirs = [DirectoryRecord(url + d, await self.path_size(url + d, include_subpath=True)) for d in dirs_str]
            
        return (dirs, files)
    
    async def path_size(self, url: str, include_subpath = False) -> int:
        if not url.endswith('/'):
            url += '/'
        if not include_subpath:
            async with self.conn.execute("SELECT SUM(file_size) FROM file WHERE url LIKE ? AND url NOT LIKE ?", (url + '%', url + '%/%')) as cursor:
                res = await cursor.fetchone()
        else:
            async with self.conn.execute("SELECT SUM(file_size) FROM file WHERE url LIKE ?", (url + '%', )) as cursor:
                res = await cursor.fetchone()
        assert res is not None
        return res[0] or 0
    
    async def set_file_record(self, url: str, user_id: int, file_path: str, permission: Optional[ FileReadPermission ] = None):
        """file_path is relative to FILE_ROOT"""
        self.logger.debug(f"Updating file {url}: user_id={user_id}, file_path={file_path}")

        abs_file_path = FILE_ROOT / file_path
        assert await aiofiles.ospath.exists(abs_file_path), f"File {abs_file_path} not found"
        file_size = (await aiofiles.os.stat(abs_file_path)).st_size
        
        old = await self.get_file_record(url)
        if old is not None:
            assert old.user_id == user_id, f"User mismatch: {old.user_id} != {user_id}"
            if permission is None:
                permission = old.permission
            await self.conn.execute("UPDATE file SET file_path = ?, file_size = ?, permission = ? WHERE url = ?", (file_path, file_size, permission, url))
            self.logger.info(f"File {url} updated")
        else:
            if permission is None:
                permission = FileReadPermission.PUBLIC
            await self.conn.execute("INSERT INTO file (url, user_id, file_path, file_size, permission) VALUES (?, ?, ?, ?, ?)", (url, user_id, file_path, file_size, permission))
            self.logger.info(f"File {url} created")
    
    async def delete_file_record(self, url: str):
        file_record = await self.get_file_record(url)
        if file_record is None: return
        await self.conn.execute("DELETE FROM file WHERE url = ?", (url, ))
        self.logger.info(f"Deleted file {url}")
    
    async def delete_user_file_records(self, user_id: int):
        async with self.conn.execute("SELECT * FROM file WHERE user_id = ?", (user_id, )) as cursor:
            res = await cursor.fetchall()
        await self.conn.execute("DELETE FROM file WHERE user_id = ?", (user_id, ))
        self.logger.info(f"Deleted {len(res)} files for user {user_id}") # type: ignore
    
    async def delete_path_records(self, path: str):
        async with self.conn.execute("SELECT * FROM file WHERE file_path LIKE ?", (path + '%', )) as cursor:
            res = await cursor.fetchall()
        await self.conn.execute("DELETE FROM file WHERE file_path LIKE ?", (path + '%', ))
        self.logger.info(f"Deleted {len(res)} files for path {path}") # type: ignore

async def _remove_files_if_exist(files: list):
    async def remove_file(file_path):
        if await aiofiles.ospath.exists(file_path):
            await aiofiles.os.remove(file_path)
    await asyncio.gather(*[remove_file(f) for f in files])

def _validate_url(url: str, is_file = True) -> bool:
    ret = not url.startswith('/') and not ('..' in url) and ('/' in url) and not ('//' in url)
    if is_file:
        ret = ret and not url.endswith('/')
    return ret

async def get_user(db: "Database", user: int | str) -> Optional[DBUserRecord]:
    if isinstance(user, str):
        return await db.user.get_user(user)
    elif isinstance(user, int):
        return await db.user.get_user_by_id(user)
    else:
        return None

@dataclasses.dataclass(frozen=True)
class Database:
    user: UserConn = UserConn()
    file: FileConn = FileConn()

    async def init(self):
        await self.user.init()
        await self.file.init()
        return self
    
    async def commit(self):
        global _g_conn
        if _g_conn is not None:
            await _g_conn.commit()
    
    async def close(self):
        global _g_conn
        if _g_conn is not None:
            await _g_conn.close()

    async def save_file(self, u: int | str, url: str, blob: bytes):
        if not _validate_url(url):
            raise ValueError(f"Invalid URL: {url}")
        assert isinstance(blob, bytes), "blob must be bytes"

        user = await get_user(self, u)
        if user is None:
            return

        username = user.username
        assert url.startswith(f"{username}/"), f"URL must start with {username}/, get: {url}"

        file_path = FILE_ROOT / url
        await aiofiles.os.makedirs(file_path.parent, exist_ok=True)

        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(blob)

        rel_path = str(file_path.relative_to(FILE_ROOT))
        assert _validate_url(rel_path)

        await self.file.set_file_record(url, user.id, str(rel_path))
        await self.user.set_active(username)
        await self.commit()

        return rel_path

    async def read_file(self, url: str) -> bytes:
        if not _validate_url(url): raise ValueError(f"Invalid URL: {url}")

        r = await self.file.get_file_record(url)
        if r is None:
            raise FileNotFoundError(f"File {url} not found")
        async with aiofiles.open(FILE_ROOT / r.file_path, 'rb') as f:
            return await f.read()
    
    async def read_file_stream(self, url: str):
        if not _validate_url(url): raise ValueError(f"Invalid URL: {url}")

        r = await self.file.get_file_record(url)
        if r is None:
            raise FileNotFoundError(f"File {url} not found")
        fpath = FILE_ROOT / r.file_path
        fsize = (await aiofiles.os.stat(fpath)).st_size
        return (fsize, await aiofiles.open(fpath, 'rb'))

    async def delete_file(self, url: str) -> Optional[FileDBRecord]:
        if not _validate_url(url): raise ValueError(f"Invalid URL: {url}")

        r = await self.file.get_file_record(url)
        if r is None:
            return None
        if await aiofiles.ospath.exists(FILE_ROOT / r.file_path):
            await aiofiles.os.remove(FILE_ROOT / r.file_path)
        await self.file.delete_file_record(url)
        await self.commit()
        return r

    async def delete_files(self, url: str):
        if not _validate_url(url): raise ValueError(f"Invalid URL: {url}")

        records = await self.file.get_path_records(url)
        await _remove_files_if_exist([FILE_ROOT / r.file_path for r in records])
        await self.file.delete_path_records(url)
        await self.commit()
        return

    async def delete_user(self, u: str | int):
        user = await get_user(self, u)
        if user is None:
            return
        
        # delete user's files
        records = await self.file.get_user_file_records(user.id)
        await _remove_files_if_exist([FILE_ROOT / r.file_path for r in records])
        await self.file.delete_user_file_records(user.id)
        await self.user.delete_user(user.username)
        await self.commit()

        user_root = FILE_ROOT / user.username
        if await aiofiles.ospath.exists(user_root):
            await aiofiles.os.rmdir(user_root)

        return