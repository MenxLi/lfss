
from typing import Optional
from abc import ABC, abstractmethod

import urllib.parse
import dataclasses, hashlib, uuid
from contextlib import asynccontextmanager
from threading import Lock
from enum import IntEnum

import aiosqlite

from .config import DATA_HOME
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
            _g_conn = await aiosqlite.connect(DATA_HOME / 'fss.db')

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
        assert not ('/' in username or len(username) > 255), "Invalid username"
        assert urllib.parse.quote(username) == username, "Invalid username, must be URL safe"
        self.logger.debug(f"Creating user {username}")
        credential = hash_credential(username, password)
        assert await self.get_user(username) is None, "Duplicate username"
        async with self.conn.execute("INSERT INTO user (username, credential, is_admin) VALUES (?, ?, ?)", (username, credential, is_admin)) as cursor:
            self.logger.info(f"User {username} created")
            assert cursor.lastrowid is not None
            return cursor.lastrowid
    
    async def set_user(self, username: str, password: Optional[str] = None, is_admin: Optional[bool] = None):
        assert not username.startswith('_'), "Error: reserved username"
        assert not ('/' in username or len(username) > 255), "Invalid username"
        assert urllib.parse.quote(username) == username, "Invalid username, must be URL safe"
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
    owner_id: int
    file_path: str      # a virtual path, defines mapping from fmata to fdata
    file_size: int
    create_time: str
    permission: FileReadPermission

    def __str__(self):
        return f"File {self.url} (owner={self.owner_id}, created at {self.create_time}, path={self.file_path}, permission={self.permission}, size={self.file_size})"

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
        CREATE TABLE IF NOT EXISTS fmeta (
            url VARCHAR(512) PRIMARY KEY,
            owner_id INTEGER NOT NULL,
            file_path VARCHAR(256) NOT NULL,
            file_size INTEGER,
            create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
            permission INTEGER DEFAULT 0
        )
        ''')
        await self.conn.execute('''
        CREATE INDEX IF NOT EXISTS idx_fmeta_owner_id ON fmeta(owner_id)
        ''')

        await self.conn.execute('''
        CREATE TABLE IF NOT EXISTS fdata (
            file_path VARCHAR(256) PRIMARY KEY,
            data BLOB
        )
        ''')

        return self
    
    async def get_file_record(self, url: str) -> Optional[FileDBRecord]:
        async with self.conn.execute("SELECT * FROM fmeta WHERE url = ?", (url, )) as cursor:
            res = await cursor.fetchone()
        if res is None:
            return None
        return self.parse_record(res)
    
    async def get_user_file_records(self, owner_id: int) -> list[FileDBRecord]:
        async with self.conn.execute("SELECT * FROM fmeta WHERE owner_id = ?", (owner_id, )) as cursor:
            res = await cursor.fetchall()
        return [self.parse_record(r) for r in res]
    
    async def get_path_records(self, url: str) -> list[FileDBRecord]:
        async with self.conn.execute("SELECT * FROM fmeta WHERE url LIKE ?", (url + '%', )) as cursor:
            res = await cursor.fetchall()
        return [self.parse_record(r) for r in res]
    
    async def list_path(self, url: str) -> tuple[list[DirectoryRecord], list[FileDBRecord]]:
        if not url.endswith('/'):
            url += '/'
        if url == '/':
            # users cannot be queried using '/', because we store them without '/' prefix, 
            # so we need to handle this case separately, 
            # directly query all usernames is more efficient.
            async with self.conn.execute("SELECT username FROM user") as cursor:
                res = await cursor.fetchall()
            dirs = [DirectoryRecord(u[0], await self.path_size(u[0], include_subpath=True)) for u in res]
            return (dirs, [])

        async with self.conn.execute("SELECT * FROM fmeta WHERE url LIKE ? AND url NOT LIKE ?", (url + '%', url + '%/%')) as cursor:
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
                FROM fmeta WHERE url LIKE ?
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
            async with self.conn.execute("SELECT SUM(file_size) FROM fmeta WHERE url LIKE ? AND url NOT LIKE ?", (url + '%', url + '%/%')) as cursor:
                res = await cursor.fetchone()
        else:
            async with self.conn.execute("SELECT SUM(file_size) FROM fmeta WHERE url LIKE ?", (url + '%', )) as cursor:
                res = await cursor.fetchone()
        assert res is not None
        return res[0] or 0
    
    async def set_file_record(self, url: str, owner_id: int, file_path: str, file_size: int, permission: Optional[ FileReadPermission ] = None):
        """file_path is relative to FILE_ROOT"""
        self.logger.debug(f"Updating fmeta {url}: user_id={owner_id}, file_path={file_path}")

        old = await self.get_file_record(url)
        if old is not None:
            assert old.owner_id == owner_id, f"User mismatch: {old.owner_id} != {owner_id}"
            if permission is None:
                permission = old.permission
            await self.conn.execute("UPDATE fmeta SET file_path = ?, file_size = ?, permission = ? WHERE url = ?", (file_path, file_size, permission, url))
            self.logger.info(f"File {url} updated")
        else:
            if permission is None:
                permission = FileReadPermission.PUBLIC
            await self.conn.execute("INSERT INTO fmeta (url, owner_id, file_path, file_size, permission) VALUES (?, ?, ?, ?, ?)", (url, owner_id, file_path, file_size, permission))
            self.logger.info(f"File {url} created")
    
    async def delete_file_record(self, url: str):
        file_record = await self.get_file_record(url)
        if file_record is None: return
        await self.conn.execute("DELETE FROM fmeta WHERE url = ?", (url, ))
        self.logger.info(f"Deleted fmeta {url}")
    
    async def delete_user_file_records(self, owner_id: int):
        async with self.conn.execute("SELECT * FROM fmeta WHERE owner_id = ?", (owner_id, )) as cursor:
            res = await cursor.fetchall()
        await self.conn.execute("DELETE FROM fmeta WHERE owner_id = ?", (owner_id, ))
        self.logger.info(f"Deleted {len(res)} files for user {owner_id}") # type: ignore
    
    async def delete_path_records(self, path: str):
        """Delete all records with url starting with path"""
        async with self.conn.execute("SELECT * FROM fmeta WHERE file_path LIKE ?", (path + '%', )) as cursor:
            res = await cursor.fetchall()
        await self.conn.execute("DELETE FROM fmeta WHERE file_path LIKE ?", (path + '%', ))
        self.logger.info(f"Deleted {len(res)} files for path {path}") # type: ignore
    
    async def set_file_blob(self, file_path: str, blob: bytes) -> int:
        await self.conn.execute("INSERT OR REPLACE INTO fdata (file_path, data) VALUES (?, ?)", (file_path, blob))
        return len(blob)
    
    async def get_file_blob(self, file_path: str) -> Optional[bytes]:
        async with self.conn.execute("SELECT data FROM fdata WHERE file_path = ?", (file_path, )) as cursor:
            res = await cursor.fetchone()
        if res is None:
            return None
        return res[0]
    
    async def delete_file_blob(self, file_path: str):
        await self.conn.execute("DELETE FROM fdata WHERE file_path = ?", (file_path, ))
    
    async def delete_file_blobs(self, file_paths: list[str]):
        await self.conn.execute("DELETE FROM fdata WHERE file_path IN (?)", (file_paths, ))

def _validate_url(url: str, is_file = True) -> bool:
    ret = not url.startswith('/') and not ('..' in url) and ('/' in url) and not ('//' in url) \
        and not ' ' in url and not url.startswith('\\') and not url.startswith('_') and not url.startswith('.')

    if not ret:
        return False
    
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

_transaction_lock = Lock()
@asynccontextmanager
async def transaction(db: "Database"):
    try:
        _transaction_lock.acquire()
        yield
        await db.commit()
    except Exception as e:
        db.logger.error(f"Error in transaction: {e}")
        await db.rollback()
    finally:
        _transaction_lock.release()

@dataclasses.dataclass(frozen=True)
class Database:
    user: UserConn = UserConn()
    file: FileConn = FileConn()
    logger = get_logger('database', global_instance=True)

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
    
    async def rollback(self):
        global _g_conn
        if _g_conn is not None:
            await _g_conn.rollback()

    async def save_file(self, u: int | str, url: str, blob: bytes):
        if not _validate_url(url):
            raise ValueError(f"Invalid URL: {url}")
        assert isinstance(blob, bytes), "blob must be bytes"

        user = await get_user(self, u)
        if user is None:
            return

        username = user.username
        assert url.startswith(f"{username}/"), f"URL must start with {username}/, get: {url}"

        f_id = uuid.uuid4().hex

        async with transaction(self):
            file_size = await self.file.set_file_blob(f_id, blob)
            await self.file.set_file_record(url, owner_id=user.id, file_path=f_id, file_size=file_size)
            await self.user.set_active(username)

    # async def read_file_stream(self, url: str): ...
    async def read_file(self, url: str) -> bytes:
        if not _validate_url(url): raise ValueError(f"Invalid URL: {url}")

        r = await self.file.get_file_record(url)
        if r is None:
            raise FileNotFoundError(f"File {url} not found")

        f_id = r.file_path
        blob = await self.file.get_file_blob(f_id)
        if blob is None:
            raise FileNotFoundError(f"File {url} data not found")
        return blob

    async def delete_file(self, url: str) -> Optional[FileDBRecord]:
        if not _validate_url(url): raise ValueError(f"Invalid URL: {url}")

        async with transaction(self):
            r = await self.file.get_file_record(url)
            if r is None:
                return None
            f_id = r.file_path
            await self.file.delete_file_blob(f_id)
            await self.file.delete_file_record(url)
            return r

    async def delete_files(self, url: str):
        if not _validate_url(url): raise ValueError(f"Invalid URL: {url}")

        async with transaction(self):
            records = await self.file.get_path_records(url)
            await self.file.delete_file_blobs([r.file_path for r in records])
            await self.file.delete_path_records(url)

    async def delete_user(self, u: str | int):
        user = await get_user(self, u)
        if user is None:
            return
        
        async with transaction(self):
            records = await self.file.get_user_file_records(user.id)
            await self.file.delete_file_blobs([r.file_path for r in records])
            await self.file.delete_user_file_records(user.id)
            await self.user.delete_user(user.username)