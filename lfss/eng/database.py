
from typing import Optional, Literal, overload
from collections.abc import AsyncIterable
from contextlib import asynccontextmanager
from abc import ABC
import re

import uuid, datetime
import urllib.parse
import zipfile, io, asyncio

import aiosqlite, aiofiles
import aiofiles.os
import mimetypes, mimesniff

from .connection_pool import execute_sql, unique_cursor, transaction
from .datatype import (
    UserRecord, AccessLevel, 
    FileReadPermission, FileRecord, DirectoryRecord, PathContents, 
    FileSortKey, DirSortKey, isValidFileSortKey, isValidDirSortKey
    )
from .config import LARGE_BLOB_DIR, CHUNK_SIZE, LARGE_FILE_BYTES, MAX_MEM_FILE_BYTES
from .log import get_logger
from .utils import decode_uri_compnents, hash_credential, concurrent_wrap, debounce_async, static_vars
from .error import *

class DBObjectBase(ABC):
    """
    NOTE: 
    The object of this class should hold a cursor to the database. 
    The methods calling the cursor should not be called concurrently. 
    """

    logger = get_logger('database', global_instance=True)
    _cur: aiosqlite.Cursor

    def set_cursor(self, cur: aiosqlite.Cursor):
        self._cur = cur

    @property
    def cur(self)->aiosqlite.Cursor:
        if not hasattr(self, '_cur'):
            raise ValueError("Connection not set")
        return self._cur

DECOY_USER = UserRecord(0, 'decoy', 'decoy', False, '2021-01-01 00:00:00', '2021-01-01 00:00:00', 0, FileReadPermission.PRIVATE)
class UserConn(DBObjectBase):

    def __init__(self, cur: aiosqlite.Cursor) -> None:
        super().__init__()
        self.set_cursor(cur)

    @staticmethod
    def parse_record(record) -> UserRecord:
        return UserRecord(*record)

    async def get_user(self, username: str) -> Optional[UserRecord]:
        await self.cur.execute("SELECT * FROM user WHERE username = ?", (username, ))
        res = await self.cur.fetchone()
        
        if res is None: return None
        return self.parse_record(res)
    
    @overload
    async def get_user_by_id(self, user_id: int, throw: Literal[True]) -> UserRecord: ...
    @overload
    async def get_user_by_id(self, user_id: int, throw: Literal[False] = False) -> Optional[UserRecord]: ...
    async def get_user_by_id(self, user_id: int, throw = False) -> Optional[UserRecord]:
        await self.cur.execute("SELECT * FROM user WHERE id = ?", (user_id, ))
        res = await self.cur.fetchone()
        if res is None:
            if throw: raise ValueError(f"User {user_id} not found")
            return None
        return self.parse_record(res)
    
    async def get_user_by_credential(self, credential: str) -> Optional[UserRecord]:
        await self.cur.execute("SELECT * FROM user WHERE credential = ?", (credential, ))
        res = await self.cur.fetchone()
        
        if res is None: return None
        return self.parse_record(res)
    
    async def create_user(
        self, username: str, password: str, is_admin: bool = False, 
        max_storage: int = 1073741824, permission: FileReadPermission = FileReadPermission.UNSET
        ) -> int:
        def validate_username(username: str):
            assert not set(username) & {'/', ':'}, "Invalid username"
            assert not username.startswith('_'), "Error: reserved username"
            assert not (len(username) > 255), "Username too long"
            assert urllib.parse.quote(username) == username, "Invalid username, must be URL safe"
        validate_username(username)
        self.logger.debug(f"Creating user {username}")
        credential = hash_credential(username, password)
        assert await self.get_user(username) is None, "Duplicate username"
        await self.cur.execute("INSERT INTO user (username, credential, is_admin, max_storage, permission) VALUES (?, ?, ?, ?, ?)", (username, credential, is_admin, max_storage, permission))
        self.logger.info(f"User {username} created")
        assert self.cur.lastrowid is not None
        return self.cur.lastrowid
    
    async def update_user(
        self, username: str, password: Optional[str] = None, is_admin: Optional[bool] = None, 
        max_storage: Optional[int] = None, permission: Optional[FileReadPermission] = None
        ):
        assert not username.startswith('_'), "Error: reserved username"
        assert not ('/' in username or len(username) > 255), "Invalid username"
        assert urllib.parse.quote(username) == username, "Invalid username, must be URL safe"

        current_record = await self.get_user(username)
        if current_record is None:
            raise ValueError(f"User {username} not found")

        if password is not None:
            credential = hash_credential(username, password)
        else:
            credential = current_record.credential
        
        if is_admin is None: is_admin = current_record.is_admin
        if max_storage is None: max_storage = current_record.max_storage
        if permission is None: permission = current_record.permission
        
        await self.cur.execute(
            "UPDATE user SET credential = ?, is_admin = ?, max_storage = ?, permission = ? WHERE username = ?", 
            (credential, is_admin, max_storage, int(permission), username)
            )
        self.logger.info(f"User {username} updated")
    
    async def all(self):
        await self.cur.execute("SELECT * FROM user")
        for record in await self.cur.fetchall():
            yield self.parse_record(record)
    
    async def set_active(self, username: str):
        await self.cur.execute("UPDATE user SET last_active = CURRENT_TIMESTAMP WHERE username = ?", (username, ))
    
    async def delete_user(self, username: str):
        await self.cur.execute("DELETE FROM upeer WHERE src_user_id = (SELECT id FROM user WHERE username = ?) OR dst_user_id = (SELECT id FROM user WHERE username = ?)", (username, username))
        await self.cur.execute("DELETE FROM user WHERE username = ?", (username, ))
        self.logger.info(f"Delete user {username}")
    
    async def set_peer_level(self, src_user: int | str, dst_user: int | str, level: AccessLevel):
        """ src_user can do [AccessLevel] to dst_user """
        assert int(level) >= AccessLevel.NONE, f"Cannot set alias level to {level}"
        match (src_user, dst_user):
            case (int(), int()):
                await self.cur.execute("INSERT OR REPLACE INTO upeer (src_user_id, dst_user_id, access_level) VALUES (?, ?, ?)", (src_user, dst_user, int(level)))
            case (str(), str()):
                await self.cur.execute("INSERT OR REPLACE INTO upeer (src_user_id, dst_user_id, access_level) VALUES ((SELECT id FROM user WHERE username = ?), (SELECT id FROM user WHERE username = ?), ?)", (src_user, dst_user, int(level)))
            case (str(), int()):
                await self.cur.execute("INSERT OR REPLACE INTO upeer (src_user_id, dst_user_id, access_level) VALUES ((SELECT id FROM user WHERE username = ?), ?, ?)", (src_user, dst_user, int(level)))
            case (int(), str()):
                await self.cur.execute("INSERT OR REPLACE INTO upeer (src_user_id, dst_user_id, access_level) VALUES (?, (SELECT id FROM user WHERE username = ?), ?)", (src_user, dst_user, int(level)))
            case (_, _):
                raise ValueError("Invalid arguments")
    
    async def query_peer_level(self, src_user_id: int, dst_user_id: int) -> AccessLevel:
        """ src_user can do [AliasLevel] to dst_user """
        if src_user_id == dst_user_id:
            return AccessLevel.ALL
        await self.cur.execute("SELECT access_level FROM upeer WHERE src_user_id = ? AND dst_user_id = ?", (src_user_id, dst_user_id))
        res = await self.cur.fetchone()
        if res is None:
            return AccessLevel.NONE
        return AccessLevel(res[0])
    
    async def list_peer_users(self, src_user: int | str, level: AccessLevel) -> list[UserRecord]:
        """
        List all users that src_user can do [AliasLevel] to, with level >= level, 
        Note: the returned list does not include src_user and is not apporiate for admin (who has all permissions for all users)
        """
        assert int(level) > AccessLevel.NONE, f"Invalid level, {level}"
        match src_user:
            case int():
                await self.cur.execute("""
                    SELECT * FROM user WHERE id IN (
                        SELECT dst_user_id FROM upeer WHERE src_user_id = ? AND access_level >= ?
                    )
                """, (src_user, int(level)))
            case str():
                await self.cur.execute("""
                    SELECT * FROM user WHERE id IN (
                        SELECT dst_user_id FROM upeer WHERE src_user_id = (SELECT id FROM user WHERE username = ?) AND access_level >= ?
                    )
                """, (src_user, int(level)))
            case _:
                raise ValueError("Invalid arguments")
        res = await self.cur.fetchall()
        return [self.parse_record(r) for r in res]

class FileConn(DBObjectBase):

    def __init__(self, cur: aiosqlite.Cursor) -> None:
        super().__init__()
        self.set_cursor(cur)

    @staticmethod
    def parse_record(record) -> FileRecord:
        return FileRecord(*record)
    
    @staticmethod
    def escape_sqlike(url: str) -> str:
        """ Escape a url for use in SQL LIKE clause (The % and _ characters) """
        return url.replace('%', r'\%').replace('_', r'\_')
    
    @overload
    async def get_file_record(self, url: str, throw: Literal[True]) -> FileRecord: ...
    @overload
    async def get_file_record(self, url: str, throw: Literal[False] = False) -> Optional[FileRecord]: ...
    async def get_file_record(self, url: str, throw = False):
        cursor = await self.cur.execute("SELECT * FROM fmeta WHERE url = ?", (url, ))
        res = await cursor.fetchone()
        if res is None:
            if throw: raise FileNotFoundError(f"File {url} not found")
            return None
        return self.parse_record(res)
    
    async def get_file_records(self, urls: list[str]) -> list[FileRecord]:
        """
        Get all file records with the given urls, only urls in the database will be returned. 
        If the urls are not in the database, they will be ignored.
        """
        await self.cur.execute("SELECT * FROM fmeta WHERE url IN ({})".format(','.join(['?'] * len(urls))), urls)
        res = await self.cur.fetchall()
        if res is None:
            return []
        return [self.parse_record(r) for r in res]
    
    async def list_root_dirs(self, *usernames: str, skim = False) -> list[DirectoryRecord]:
        """
        Efficiently list users' directories, if usernames is empty, list all users' directories.
        """
        if not usernames:
            # list all users
            await self.cur.execute("SELECT username FROM user")
            res = await self.cur.fetchall()
            dirnames = [u[0] + '/' for u in res]
            dirs = [await self.get_dir_record(u) for u in dirnames] if not skim else [DirectoryRecord(u) for u in dirnames]
            return dirs
        else:
            # list specific users
            dirnames = [uname + '/' for uname in usernames]
            dirs = [await self.get_dir_record(u) for u in dirnames] if not skim else [DirectoryRecord(u) for u in dirnames]
            return dirs
    
    async def count_path_dirs(self, url: str):
        if not url.endswith('/'): url += '/'
        if url == '/': url = ''
        cursor = await self.cur.execute("""
        SELECT COUNT(*) FROM (
            SELECT DISTINCT SUBSTR( 
                url, LENGTH(?) + 1, 
                INSTR(SUBSTR(url, LENGTH(?) + 1), '/')
                ) AS dirname
            FROM fmeta WHERE url LIKE ? ESCAPE '\\' AND dirname != ''
        )
        """, (url, url, self.escape_sqlike(url) + '%'))
        res = await cursor.fetchone()
        assert res is not None, "Error: count_path_dirs"
        return res[0]

    async def list_path_dirs(
        self, url: str, 
        offset: int = 0, limit: int = 10_000, 
        order_by: DirSortKey = '', order_desc: bool = False,
        skim: bool = True
        ) -> list[DirectoryRecord]:
        if not isValidDirSortKey(order_by):
            raise ValueError(f"Invalid order_by ({order_by})")

        if not url.endswith('/'): url += '/'
        if url == '/': url = ''

        sql_qury = """
            SELECT DISTINCT SUBSTR(
                url, 
                1 + LENGTH(?),
                INSTR(SUBSTR(url, 1 + LENGTH(?)), '/')
            ) AS dirname 
            FROM fmeta WHERE url LIKE ? ESCAPE '\\' AND dirname != ''
        """ \
        + (f"ORDER BY {order_by} {'DESC' if order_desc else 'ASC'}" if order_by else '') \
        + " LIMIT ? OFFSET ?"
        cursor = await self.cur.execute(sql_qury, (url, url, self.escape_sqlike(url) + '%', limit, offset))
        res = await cursor.fetchall()
        dirs_str = [r[0] for r in res]
        async def get_dir(dir_url):
            if skim:
                return DirectoryRecord(dir_url)
            else:
                return await self.get_dir_record(dir_url)
        dirs = [await get_dir(url + d) for d in dirs_str]
        return dirs
    
    async def count_dir_files(self, url: str, flat: bool = False):
        if not url.endswith('/'): url += '/'
        if url == '/': url = ''
        if flat:
            cursor = await self.cur.execute(
                "SELECT COUNT(*) FROM fmeta WHERE url LIKE ? ESCAPE '\\'", 
                (self.escape_sqlike(url) + '%', )
                )
        else:
            cursor = await self.cur.execute(
                "SELECT COUNT(*) FROM fmeta WHERE url LIKE ? ESCAPE '\\' AND url NOT LIKE ? ESCAPE '\\'", 
                (self.escape_sqlike(url) + '%', self.escape_sqlike(url) + '%/%')
                )
        res = await cursor.fetchone()
        assert res is not None, "Error: count_path_files"
        return res[0]

    async def list_dir_files(
        self, url: str, 
        offset: int = 0, limit: int = 10_000, 
        order_by: FileSortKey = '', order_desc: bool = False,
        flat: bool = False, 
        ) -> list[FileRecord]:
        if not isValidFileSortKey(order_by):
            raise ValueError(f"Invalid order_by {order_by}")

        if not url.endswith('/'): url += '/'
        if url == '/': url = ''

        sql_query = "SELECT * FROM fmeta WHERE url LIKE ? ESCAPE '\\'"
        if not flat: sql_query += " AND url NOT LIKE ? ESCAPE '\\'"
        if order_by: sql_query += f" ORDER BY {order_by} {'DESC' if order_desc else 'ASC'}"
        sql_query += " LIMIT ? OFFSET ?"
        if flat:
            cursor = await self.cur.execute(sql_query, (self.escape_sqlike(url) + '%', limit, offset))
        else:
            cursor = await self.cur.execute(sql_query, (self.escape_sqlike(url) + '%', self.escape_sqlike(url) + '%/%', limit, offset))
        res = await cursor.fetchall()
        files = [self.parse_record(r) for r in res]
        return files
    
    async def list_path(self, url: str) -> PathContents:
        """
        List all files and directories under the given path.  
        This method is a handy way file browsing, but has limitaions:
        - It does not support pagination
        - It does not support sorting
        - It cannot flatten directories
        - It cannot list directories with details
        """
        MAX_ITEMS = 10_000
        dir_count = await self.count_path_dirs(url)
        file_count = await self.count_dir_files(url, flat=False)
        if dir_count + file_count > MAX_ITEMS:
            raise TooManyItemsError("Too many items, please paginate")
        return PathContents(
            dirs = await self.list_path_dirs(url, skim=True, limit=MAX_ITEMS),
            files = await self.list_dir_files(url, flat=False, limit=MAX_ITEMS)
            )
    
    async def get_dir_record(self, url: str) -> DirectoryRecord:
        """
        Get the full record of a directory, including size, create_time, update_time, access_time etc.
        """
        assert url.endswith('/'), "Path must end with /"
        cursor = await self.cur.execute("""
            SELECT MIN(create_time) as create_time, 
                MAX(create_time) as update_time, 
                MAX(access_time) as access_time, 
                COUNT(*) as n_files
            FROM fmeta 
            WHERE url LIKE ? ESCAPE '\\'
        """, (self.escape_sqlike(url) + '%', ))
        result = await cursor.fetchone()
        if result is None or any(val is None for val in result):
            raise PathNotFoundError(f"Path {url} not found")
        create_time, update_time, access_time, n_files = result
        p_size = await self.path_size(url, include_subpath=True)
        return DirectoryRecord(url, p_size, create_time=create_time, update_time=update_time, access_time=access_time, n_files=n_files)
    
    async def user_size(self, user_id: int) -> int:
        cursor = await self.cur.execute("SELECT size FROM usize WHERE user_id = ?", (user_id, ))
        res = await cursor.fetchone()
        if res is None: return 0
        return res[0]
    async def _user_size_inc(self, user_id: int, inc: int):
        self.logger.debug(f"Increasing user {user_id} size by {inc}")
        await self.cur.execute("INSERT OR REPLACE INTO usize (user_id, size) VALUES (?, COALESCE((SELECT size FROM usize WHERE user_id = ?), 0) + ?)", (user_id, user_id, inc))
    async def _user_size_dec(self, user_id: int, dec: int):
        self.logger.debug(f"Decreasing user {user_id} size by {dec}")
        await self.cur.execute("INSERT OR REPLACE INTO usize (user_id, size) VALUES (?, COALESCE((SELECT size FROM usize WHERE user_id = ?), 0) - ?)", (user_id, user_id, dec))
    
    async def path_size(self, url: str, include_subpath = False) -> int:
        if not url.endswith('/'):
            url += '/'
        if not include_subpath:
            cursor = await self.cur.execute(
                "SELECT SUM(file_size) FROM fmeta WHERE url LIKE ? ESCAPE '\\' AND url NOT LIKE ? ESCAPE '\\'",
                (self.escape_sqlike(url) + '%', self.escape_sqlike(url) + '%/%')
                )
            res = await cursor.fetchone()
        else:
            cursor = await self.cur.execute(
                "SELECT SUM(file_size) FROM fmeta WHERE url LIKE ? ESCAPE '\\'",
                (self.escape_sqlike(url) + '%', )
                )
            res = await cursor.fetchone()
        assert res is not None
        return res[0] or 0
    
    async def update_file_record(
        self, url, 
        permission: Optional[FileReadPermission] = None, 
        mime_type: Optional[str] = None
        ):
        if permission is not None:
            await self.cur.execute("UPDATE fmeta SET permission = ? WHERE url = ?", (int(permission), url))
        if mime_type is not None:
            await self.cur.execute("UPDATE fmeta SET mime_type = ? WHERE url = ?", (mime_type, url))
        self.logger.info(f"Updated file {url}")
    
    async def set_file_record(
        self, url: str, 
        owner_id: int, 
        file_id:str, 
        file_size: int, 
        permission: FileReadPermission, 
        external: bool, 
        mime_type: str
        ):
        self.logger.debug(f"Creating fmeta {url}: permission={permission}, owner_id={owner_id}, file_id={file_id}, file_size={file_size}, external={external}, mime_type={mime_type}")
        if permission is None:
            permission = FileReadPermission.UNSET
        assert owner_id is not None and file_id is not None and file_size is not None and external is not None
        await self.cur.execute(
            "INSERT INTO fmeta (url, owner_id, file_id, file_size, permission, external, mime_type) VALUES (?, ?, ?, ?, ?, ?, ?)", 
            (url, owner_id, file_id, file_size, int(permission), external, mime_type)
            )
        await self._user_size_inc(owner_id, file_size)
        self.logger.info(f"File {url} created")

    async def copy_file(self, old_url: str, new_url: str, user_id: Optional[int] = None):
        """
        Copy file from old_url to new_url, 
        if user_id is None, will not change the owner_id of the file. Otherwise, will change the owner_id to user_id.
        """
        old = await self.get_file_record(old_url)
        if old is None:
            raise FileNotFoundError(f"File {old_url} not found")
        new_exists = await self.get_file_record(new_url)
        if new_exists is not None:
            raise FileExistsError(f"File {new_url} already exists")
        user_id = old.owner_id if user_id is None else user_id
        await self.cur.execute(
            "INSERT INTO fmeta (url, owner_id, file_id, file_size, permission, external, mime_type) VALUES (?, ?, ?, ?, ?, ?, ?)", 
            (new_url, user_id, old.file_id, old.file_size, old.permission, old.external, old.mime_type)
            )
        await self.cur.execute("INSERT OR REPLACE INTO dupcount (file_id, count) VALUES (?, COALESCE((SELECT count FROM dupcount WHERE file_id = ?), 0) + 1)", (old.file_id, old.file_id))
        await self._user_size_inc(user_id, old.file_size)
        self.logger.info(f"Copied file {old_url} to {new_url}")
    
    async def copy_dir(self, old_url: str, new_url: str, user_id: Optional[int] = None):
        """
        Copy all files under old_url to new_url, 
        if user_id is None, will not change the owner_id of the files. Otherwise, will change the owner_id to user_id.
        """
        assert old_url.endswith('/'), "Old path must end with /"
        assert new_url.endswith('/'), "New path must end with /"
        cursor = await self.cur.execute(
            "SELECT * FROM fmeta WHERE url LIKE ? ESCAPE '\\'",
            (self.escape_sqlike(old_url) + '%', )
            )
        res = await cursor.fetchall()
        for r in res:
            old_record = FileRecord(*r)
            new_r = new_url + old_record.url[len(old_url):]
            if await (await self.cur.execute("SELECT url FROM fmeta WHERE url = ?", (new_r, ))).fetchone() is not None:
                raise FileExistsError(f"File {new_r} already exists")
            user_id = old_record.owner_id if user_id is None else user_id
            await self.cur.execute(
                "INSERT INTO fmeta (url, owner_id, file_id, file_size, permission, external, mime_type) VALUES (?, ?, ?, ?, ?, ?, ?)", 
                (new_r, user_id, old_record.file_id, old_record.file_size, old_record.permission, old_record.external, old_record.mime_type)
                )
            await self.cur.execute("INSERT OR REPLACE INTO dupcount (file_id, count) VALUES (?, COALESCE((SELECT count FROM dupcount WHERE file_id = ?), 0) + 1)", (old_record.file_id, old_record.file_id))
            await self._user_size_inc(user_id, old_record.file_size)
        self.logger.info(f"Copied path {old_url} to {new_url}")
    
    async def move_file(self, old_url: str, new_url: str):
        old = await self.get_file_record(old_url)
        if old is None:
            raise FileNotFoundError(f"File {old_url} not found")
        new_exists = await self.get_file_record(new_url)
        if new_exists is not None:
            raise FileExistsError(f"File {new_url} already exists")
        await self.cur.execute("UPDATE fmeta SET url = ?, create_time = CURRENT_TIMESTAMP WHERE url = ?", (new_url, old_url))
        self.logger.info(f"Moved file {old_url} to {new_url}")
    
    async def move_dir(self, old_url: str, new_url: str, user_id: Optional[int] = None):
        assert old_url.endswith('/'), "Old path must end with /"
        assert new_url.endswith('/'), "New path must end with /"
        if user_id is None:
            cursor = await self.cur.execute(
                "SELECT * FROM fmeta WHERE url LIKE ? ESCAPE '\\'",
                (self.escape_sqlike(old_url) + '%', )
                )
            res = await cursor.fetchall()
        else:
            cursor = await self.cur.execute(
                "SELECT * FROM fmeta WHERE url LIKE ? ESCAPE '\\' AND owner_id = ?", 
                (self.escape_sqlike(old_url) + '%', user_id)
                )
            res = await cursor.fetchall()
        for r in res:
            new_r = new_url + r[0][len(old_url):]
            if await (await self.cur.execute("SELECT url FROM fmeta WHERE url = ?", (new_r, ))).fetchone():
                self.logger.error(f"File {new_r} already exists on move path: {old_url} -> {new_url}")
                raise FileDuplicateError(f"File {new_r} already exists")
            await self.cur.execute("UPDATE fmeta SET url = ?, create_time = CURRENT_TIMESTAMP WHERE url = ?", (new_r, r[0]))
    
    async def log_access(self, url: str):
        await self.cur.execute("UPDATE fmeta SET access_time = CURRENT_TIMESTAMP WHERE url = ?", (url, ))
    
    async def delete_file_record(self, url: str) -> Optional[FileRecord]:
        res = await self.cur.execute("DELETE FROM fmeta WHERE url = ? RETURNING *", (url, ))
        row = await res.fetchone()
        if row is None:
            raise FileNotFoundError(f"File {url} not found")
        file_record = FileRecord(*row)
        await self._user_size_dec(file_record.owner_id, file_record.file_size)
        self.logger.info(f"Deleted fmeta {url}")
        return file_record
    
    async def delete_user_file_records(self, owner_id: int) -> list[FileRecord]:
        """ Delete all records with owner_id """
        cursor = await self.cur.execute("SELECT * FROM fmeta WHERE owner_id = ?", (owner_id, ))
        res = await cursor.fetchall()
        await self.cur.execute("DELETE FROM usize WHERE user_id = ?", (owner_id, ))
        res = await self.cur.execute("DELETE FROM fmeta WHERE owner_id = ? RETURNING *", (owner_id, ))
        ret = [self.parse_record(r) for r in await res.fetchall()]
        self.logger.info(f"Deleted {len(ret)} file records for user {owner_id}") # type: ignore
        return ret
    
    async def delete_records_by_prefix(self, path: str, under_owner_id: Optional[int] = None) -> list[FileRecord]:
        """Delete all records with url starting with path"""
        # update user size
        cursor = await self.cur.execute(
            "SELECT DISTINCT owner_id FROM fmeta WHERE url LIKE ? ESCAPE '\\'",
            (self.escape_sqlike(path) + '%', )
            )
        res = await cursor.fetchall()
        for r in res:
            cursor = await self.cur.execute(
                "SELECT SUM(file_size) FROM fmeta WHERE owner_id = ? AND url LIKE ? ESCAPE '\\'", 
                (r[0], self.escape_sqlike(path) + '%')
                )
            size = await cursor.fetchone()
            if size is not None:
                await self._user_size_dec(r[0], size[0])
        
        # if any new records are created here, the size update may be inconsistent
        # but it's not a big deal... we should have only one writer
        
        if under_owner_id is None:
            res = await self.cur.execute("DELETE FROM fmeta WHERE url LIKE ? ESCAPE '\\' RETURNING *", (self.escape_sqlike(path) + '%', ))
        else:
            res = await self.cur.execute("DELETE FROM fmeta WHERE url LIKE ? ESCAPE '\\' AND owner_id = ? RETURNING *", (self.escape_sqlike(path) + '%', under_owner_id))
        all_f_rec = await res.fetchall()
        self.logger.info(f"Deleted {len(all_f_rec)} file(s) for path {path}") # type: ignore
        return [self.parse_record(r) for r in all_f_rec]
    
    async def set_file_blob(self, file_id: str, blob: bytes):
        await self.cur.execute("INSERT INTO blobs.fdata (file_id, data) VALUES (?, ?)", (file_id, blob))
    
    @staticmethod
    async def set_file_blob_external(file_id: str, stream: AsyncIterable[bytes])->int:
        size_sum = 0
        try:
            async with aiofiles.open(LARGE_BLOB_DIR / file_id, 'wb') as f:
                async for chunk in stream:
                    size_sum += len(chunk)
                    await f.write(chunk)
        except Exception as e:
            if (LARGE_BLOB_DIR / file_id).exists():
                await aiofiles.os.remove(LARGE_BLOB_DIR / file_id)
            raise
        return size_sum
    
    async def get_file_blob(self, file_id: str, start_byte = -1, end_byte = -1) -> bytes:
        cursor = await self.cur.execute("SELECT data FROM blobs.fdata WHERE file_id = ?", (file_id, ))
        res = await cursor.fetchone()
        if res is None:
            raise FileNotFoundError(f"File {file_id} not found")
        blob = res[0]
        match (start_byte, end_byte):
            case (-1, -1):
                return blob
            case (s, -1):
                return blob[s:]
            case (-1, e):
                return blob[:e]
            case (s, e):
                return blob[s:e]
    
    @staticmethod
    async def get_file_blob_external(file_id: str, start_byte = -1, end_byte = -1) -> AsyncIterable[bytes]:
        assert (LARGE_BLOB_DIR / file_id).exists(), f"File {file_id} not found"
        async with aiofiles.open(LARGE_BLOB_DIR / file_id, 'rb') as f:
            if start_byte >= 0:
                await f.seek(start_byte)
            if end_byte >= 0:
                while True:
                    head_ptr = await f.tell()
                    if head_ptr >= end_byte:
                        break
                    chunk = await f.read(min(CHUNK_SIZE, end_byte - head_ptr))
                    if not chunk: break
                    yield chunk
            else:
                while True:
                    chunk = await f.read(CHUNK_SIZE)
                    if not chunk: break
                    yield chunk
    
    async def unlink_file_blob_external(self, file_id: str):
        # first check if the file has duplication
        cursor = await self.cur.execute("SELECT count FROM dupcount WHERE file_id = ?", (file_id, ))
        res = await cursor.fetchone()
        if res is not None and res[0] > 0:
            await self.cur.execute("UPDATE dupcount SET count = count - 1 WHERE file_id = ?", (file_id, ))
            return

        # finally delete the file and the duplication count
        if (LARGE_BLOB_DIR / file_id).exists():
            await aiofiles.os.remove(LARGE_BLOB_DIR / file_id)
        await self.cur.execute("DELETE FROM dupcount WHERE file_id = ?", (file_id, ))
    
    async def unlink_file_blob(self, file_id: str):
        # first check if the file has duplication
        cursor = await self.cur.execute("SELECT count FROM dupcount WHERE file_id = ?", (file_id, ))
        res = await cursor.fetchone()
        if res is not None and res[0] > 0:
            await self.cur.execute("UPDATE dupcount SET count = count - 1 WHERE file_id = ?", (file_id, ))
            return

        # finally delete the file and the duplication count
        await self.cur.execute("DELETE FROM blobs.fdata WHERE file_id = ?", (file_id, ))
        await self.cur.execute("DELETE FROM dupcount WHERE file_id = ?", (file_id, ))
    
    async def _group_del(self, file_ids_all: list[str]):
        """
        The file_ids_all may contain duplication, 
        yield tuples of unique (to_del_ids, to_dec_ids) for each iteration, 
        every iteration should unlink one copy of the files, repeat until all re-occurrence in the input list are removed.
        """
        async def check_dup(file_ids: set[str]):
            cursor = await self.cur.execute("SELECT file_id FROM dupcount WHERE file_id IN ({}) AND count > 0".format(','.join(['?'] * len(file_ids))), tuple(file_ids))
            res = await cursor.fetchall()
            to_dec_ids = [r[0] for r in res]
            to_del_ids = list(file_ids - set(to_dec_ids))
            return to_del_ids, to_dec_ids
        # gather duplication from all file_ids
        fid_occurrence = {}
        for file_id in file_ids_all:
            fid_occurrence[file_id] = fid_occurrence.get(file_id, 0) + 1
        while fid_occurrence:
            to_del_ids, to_dec_ids = await check_dup(set(fid_occurrence.keys()))
            for file_id in to_del_ids:
                del fid_occurrence[file_id]
            for file_id in to_dec_ids:
                fid_occurrence[file_id] -= 1
                if fid_occurrence[file_id] == 0:
                    del fid_occurrence[file_id]
            yield (to_del_ids, to_dec_ids)
    
    async def unlink_file_blobs(self, file_ids: list[str]):
        async for (to_del_ids, to_dec_ids) in self._group_del(file_ids):
            # delete the only copy
            await self.cur.execute("DELETE FROM blobs.fdata WHERE file_id IN ({})".format(','.join(['?'] * len(to_del_ids))), to_del_ids)
            await self.cur.execute("DELETE FROM dupcount WHERE file_id IN ({})".format(','.join(['?'] * len(to_del_ids))), to_del_ids)
            # decrease duplication count
            await self.cur.execute("UPDATE dupcount SET count = count - 1 WHERE file_id IN ({})".format(','.join(['?'] * len(to_dec_ids))), to_dec_ids)
    
    async def unlink_file_blobs_external(self, file_ids: list[str]):
        async def del_file(file_id: str):
            if (LARGE_BLOB_DIR / file_id).exists():
                await aiofiles.os.remove(LARGE_BLOB_DIR / file_id)
        async for (to_del_ids, to_dec_ids) in self._group_del(file_ids):
            # delete the only copy
            await asyncio.gather(*(
                [del_file(file_id) for file_id in to_del_ids] + 
                [self.cur.execute("DELETE FROM dupcount WHERE file_id = ?", (file_id, )) for file_id in to_del_ids]
                ))
            # decrease duplication count
            await self.cur.execute("UPDATE dupcount SET count = count - 1 WHERE file_id IN ({})".format(','.join(['?'] * len(to_dec_ids))), to_dec_ids)
        

_log_active_queue = []
_log_active_lock = asyncio.Lock()
@debounce_async()
async def _set_all_active():
    async with transaction() as conn:
        uconn = UserConn(conn)
        async with _log_active_lock:
            for u in _log_active_queue:
                await uconn.set_active(u)
            _log_active_queue.clear()
async def delayed_log_activity(username: str):
    async with _log_active_lock:
        _log_active_queue.append(username)
    await _set_all_active()

_log_access_queue = []
_log_access_lock = asyncio.Lock()
@debounce_async()
async def _log_all_access():
    async with transaction() as conn:
        fconn = FileConn(conn)
        async with _log_access_lock:
            for r in _log_access_queue:
                await fconn.log_access(r)
            _log_access_queue.clear()
async def delayed_log_access(url: str):
    async with _log_access_lock:
        _log_access_queue.append(url)
    await _log_all_access()

@static_vars(
    prohibited_regex = re.compile(
            r"^[/_.]",              # start with / or _ or .
        ),
    prohibited_part_regex = re.compile(
        "|".join([
            r"^\s*\.+\s*$",       # dot path
            "[{}]".format("".join(re.escape(c) for c in ('/', "\\", "'", '"', "*"))), # prohibited characters
        ])
    ),
)
def validate_url(url: str, utype: Literal['file', 'dir'] = 'file'):
    """ Check if a path is valid. The input path is considered url safe """
    if len(url) > 1024: 
        raise InvalidPathError(f"URL too long: {url}")

    is_valid = validate_url.prohibited_regex.search(url) is None
    if not is_valid:    # early return, no need to check further
        raise InvalidPathError(f"Invalid URL: {url}")

    for part in url.split('/'):
        if validate_url.prohibited_part_regex.search(urllib.parse.unquote(part)):
            is_valid = False
            break

    if utype == 'file': is_valid = is_valid and not url.endswith('/')
    else: is_valid = is_valid and url.endswith('/')

    if not is_valid: 
        raise InvalidPathError(f"Invalid URL: {url}")

async def get_user(cur: aiosqlite.Cursor, user: int | str) -> Optional[UserRecord]:
    uconn = UserConn(cur)
    if isinstance(user, str):
        return await uconn.get_user(user)
    elif isinstance(user, int):
        return await uconn.get_user_by_id(user)
    else:
        return None

# higher level database operations, mostly transactional
class Database:
    logger = get_logger('database', global_instance=True)

    async def init(self):
        async with transaction() as conn:
            await execute_sql(conn, 'init.sql')
        return self
    
    async def update_file_record(self, url: str, permission: FileReadPermission, op_user: Optional[UserRecord] = None):
        validate_url(url)
        async with transaction() as conn:
            fconn = FileConn(conn)
            r = await fconn.get_file_record(url)
            if r is None:
                raise PathNotFoundError(f"File {url} not found")
            if op_user is not None:
                if await check_path_permission(url, op_user) < AccessLevel.WRITE:
                    raise PermissionDeniedError(f"Permission denied: {op_user.username} cannot update file {url}")
            await fconn.update_file_record(url, permission=permission)
    
    async def save_file(
        self, u: int | str, url: str, 
        blob_stream: AsyncIterable[bytes], 
        permission: FileReadPermission = FileReadPermission.UNSET, 
        mime_type: Optional[str] = None
        ) -> int:
        """
        Save a file to the database. 
        Will check file size and user storage limit, 
        should check permission before calling this method. 
        """
        validate_url(url)
        async with unique_cursor() as cur:
            user = await get_user(cur, u)
            assert user is not None, f"User {u} not found"

            if await check_path_permission(url, user, cursor=cur) < AccessLevel.WRITE:
                raise PermissionDeniedError(f"Permission denied: {user.username} cannot write to {url}")
            
            fconn_r = FileConn(cur)
            user_size_used = await fconn_r.user_size(user.id)

            f_id = uuid.uuid4().hex

        async with aiofiles.tempfile.SpooledTemporaryFile(max_size=MAX_MEM_FILE_BYTES) as f:
            async for chunk in blob_stream:
                await f.write(chunk)
            file_size = await f.tell()
            if user_size_used + file_size > user.max_storage:
                raise StorageExceededError(f"Unable to save file, user {user.username} has storage limit of {user.max_storage}, used {user_size_used}, requested {file_size}")
            
            # check mime type
            if mime_type is None:
                mime_type, _ = mimetypes.guess_type(url)
            if mime_type is None:
                await f.seek(0)
                mime_type = mimesniff.what(await f.read(1024))
            if mime_type is None:
                mime_type = 'application/octet-stream'
            await f.seek(0)
            
            if file_size < LARGE_FILE_BYTES:
                blob = await f.read()
                async with transaction() as w_cur:
                    fconn_w = FileConn(w_cur)
                    await fconn_w.set_file_blob(f_id, blob)
                    await fconn_w.set_file_record(
                        url, owner_id=user.id, file_id=f_id, file_size=file_size, 
                        permission=permission, external=False, mime_type=mime_type)
            
            else:
                async def blob_stream_tempfile():
                    nonlocal f
                    while True:
                        chunk = await f.read(CHUNK_SIZE)
                        if not chunk: break
                        yield chunk
                await FileConn.set_file_blob_external(f_id, blob_stream_tempfile())
                async with transaction() as w_cur:
                    await FileConn(w_cur).set_file_record(
                        url, owner_id=user.id, file_id=f_id, file_size=file_size, 
                        permission=permission, external=True, mime_type=mime_type)
        return file_size

    async def read_file(self, url: str, start_byte = -1, end_byte = -1) -> AsyncIterable[bytes]:
        """
        Read a file from the database.
        end byte is exclusive: [start_byte, end_byte)
        """
        # The implementation is tricky, should not keep the cursor open for too long
        validate_url(url)
        async with unique_cursor() as cur:
            fconn = FileConn(cur)
            r = await fconn.get_file_record(url)
            if r is None:
                raise FileNotFoundError(f"File {url} not found")

            if r.external:
                _blob_stream = fconn.get_file_blob_external(r.file_id, start_byte=start_byte, end_byte=end_byte)
                async def blob_stream():
                    async for chunk in _blob_stream:
                        yield chunk
            else:
                blob = await fconn.get_file_blob(r.file_id, start_byte=start_byte, end_byte=end_byte)
                async def blob_stream():
                    yield blob
        ret = blob_stream()
        return ret
    
    async def read_files_bulk(
        self, urls: list[str], 
        skip_content = False, 
        op_user: Optional[UserRecord] = None, 
        ) -> dict[str, Optional[bytes]]:
        """
        A frequent use case is to read multiple files at once, 
        this method will read all files in the list and return a dict of url -> blob.
        if the file is not found, the value will be None.
        - skip_content: if True, will not read the content of the file, resulting in a dict of url -> b''

        may raise StorageExceededError if the total size of the files exceeds MAX_MEM_FILE_BYTES
        """
        for url in urls:
            validate_url(url)
        
        async with unique_cursor() as cur:
            fconn = FileConn(cur)
            file_records = await fconn.get_file_records(urls)

            if op_user is not None:
                for r in file_records:
                    if await check_path_permission(r.url, op_user, cursor=cur) >= AccessLevel.READ:
                        continue
                    is_allowed, reason = await check_file_read_permission(op_user, r, cursor=cur)
                    if not is_allowed:
                        raise PermissionDeniedError(f"Permission denied: {op_user.username} cannot read file {r.url}: {reason}")

        # first check if the files are too big
        sum_size = sum([r.file_size for r in file_records])
        if not skip_content and sum_size > MAX_MEM_FILE_BYTES:
            raise StorageExceededError(f"Unable to read files at once, total size {sum_size} exceeds {MAX_MEM_FILE_BYTES}")
        
        self.logger.debug(f"Reading {len(file_records)} files{' (skip content)' if skip_content else ''}, getting {sum_size} bytes, from {urls}")
        # read the file content
        async with unique_cursor() as cur:
            fconn = FileConn(cur)
            blobs: dict[str, bytes] = {}
            for r in file_records:
                if skip_content:
                    blobs[r.url] = b''
                    continue

                if r.external:
                    blob_iter = fconn.get_file_blob_external(r.file_id)
                    blob = b''.join([chunk async for chunk in blob_iter])
                else:
                    blob = await fconn.get_file_blob(r.file_id)
                blobs[r.url] = blob
            
            return {url: blobs.get(url, None) for url in urls}

    async def delete_file(self, url: str, op_user: Optional[UserRecord] = None) -> Optional[FileRecord]:
        validate_url(url)

        async with transaction() as cur:
            fconn = FileConn(cur)
            r = await fconn.delete_file_record(url)
            if r is None:
                return None
            if op_user is not None:
                if  r.owner_id != op_user.id and \
                    await check_path_permission(r.url, op_user, cursor=cur) < AccessLevel.WRITE:
                    # will rollback
                    raise PermissionDeniedError(f"Permission denied: {op_user.username} cannot delete file {url}")
            f_id = r.file_id
            if r.external:
                await fconn.unlink_file_blob_external(f_id)
            else:
                await fconn.unlink_file_blob(f_id)
            return r
    
    async def move_file(self, old_url: str, new_url: str, op_user: Optional[UserRecord] = None):
        validate_url(old_url)
        validate_url(new_url)

        async with transaction() as cur:
            fconn = FileConn(cur)
            r = await fconn.get_file_record(old_url)
            if r is None:
                raise FileNotFoundError(f"File {old_url} not found")
            if op_user is not None:
                if await check_path_permission(old_url, op_user, cursor=cur) < AccessLevel.WRITE:
                    raise PermissionDeniedError(f"Permission denied: {op_user.username} cannot move file {old_url}")
                if await check_path_permission(new_url, op_user, cursor=cur) < AccessLevel.WRITE:
                    raise PermissionDeniedError(f"Permission denied: {op_user.username} cannot move file to {new_url}")
            await fconn.move_file(old_url, new_url)

            new_mime, _ = mimetypes.guess_type(new_url)
            if not new_mime is None:
                await fconn.update_file_record(new_url, mime_type=new_mime)
    
    # not tested
    async def copy_file(self, old_url: str, new_url: str, op_user: Optional[UserRecord] = None):
        validate_url(old_url)
        validate_url(new_url)

        async with transaction() as cur:
            fconn = FileConn(cur)
            r = await fconn.get_file_record(old_url)
            if r is None:
                raise FileNotFoundError(f"File {old_url} not found")
            if op_user is not None:
                if await check_path_permission(old_url, op_user, cursor=cur) < AccessLevel.READ:
                    raise PermissionDeniedError(f"Permission denied: {op_user.username} cannot copy file {old_url}")
                if await check_path_permission(new_url, op_user, cursor=cur) < AccessLevel.WRITE:
                    raise PermissionDeniedError(f"Permission denied: {op_user.username} cannot copy file to {new_url}")
            await fconn.copy_file(old_url, new_url, user_id=op_user.id if op_user is not None else None)
    
    async def move_dir(self, old_url: str, new_url: str, op_user: UserRecord):
        validate_url(old_url, 'dir')
        validate_url(new_url, 'dir')

        if new_url.startswith('/'):
            new_url = new_url[1:]
        if old_url.startswith('/'):
            old_url = old_url[1:]
        assert old_url != new_url, "Old and new path must be different"
        assert old_url.endswith('/'), "Old path must end with /"
        assert new_url.endswith('/'), "New path must end with /"

        async with unique_cursor() as cur:
            if not (
                await check_path_permission(old_url, op_user, cursor=cur) >= AccessLevel.WRITE and
                await check_path_permission(new_url, op_user, cursor=cur) >= AccessLevel.WRITE
                ):
                raise PermissionDeniedError(f"Permission denied: {op_user.username} cannot move path {old_url} to {new_url}")

        async with transaction() as cur:
            fconn = FileConn(cur)
            await fconn.move_dir(old_url, new_url, op_user.id)
    
    async def copy_dir(self, old_url: str, new_url: str, op_user: UserRecord):
        validate_url(old_url, 'dir')
        validate_url(new_url, 'dir')
        
        if new_url.startswith('/'):
            new_url = new_url[1:]
        if old_url.startswith('/'):
            old_url = old_url[1:]
        assert old_url != new_url, "Old and new path must be different"
        assert old_url.endswith('/'), "Old path must end with /"
        assert new_url.endswith('/'), "New path must end with /"

        async with unique_cursor() as cur:
            if not (
                await check_path_permission(old_url, op_user, cursor=cur) >= AccessLevel.READ and
                await check_path_permission(new_url, op_user, cursor=cur) >= AccessLevel.WRITE
                ):
                raise PermissionDeniedError(f"Permission denied: {op_user.username} cannot copy path {old_url} to {new_url}")
        
        async with transaction() as cur:
            fconn = FileConn(cur)
            await fconn.copy_dir(old_url, new_url, op_user.id)

    async def __batch_delete_file_blobs(self, fconn: FileConn, file_records: list[FileRecord], batch_size: int = 512):
        # https://github.com/langchain-ai/langchain/issues/10321
        internal_ids = []
        external_ids = []
        for r in file_records:
            if r.external:
                external_ids.append(r.file_id)
            else:
                internal_ids.append(r.file_id)
        
        async def del_internal():
            for i in range(0, len(internal_ids), batch_size):
                await fconn.unlink_file_blobs([r for r in internal_ids[i:i+batch_size]])
        async def del_external():
            for i in range(0, len(external_ids), batch_size):
                await fconn.unlink_file_blobs_external([r for r in external_ids[i:i+batch_size]])
        await del_internal()
        await del_external()

    async def delete_dir(self, url: str, op_user: Optional[UserRecord] = None) -> Optional[list[FileRecord]]:
        validate_url(url, 'dir')
        from_owner_id = op_user.id if op_user is not None and not (op_user.is_admin or await check_path_permission(url, op_user) >= AccessLevel.WRITE) else None

        async with transaction() as cur:
            fconn = FileConn(cur)
            records = await fconn.delete_records_by_prefix(url, from_owner_id)
            if not records:
                return None
            await self.__batch_delete_file_blobs(fconn, records)
            return records
    
    async def delete_user(self, u: str | int):
        async with transaction() as cur:
            user = await get_user(cur, u)
            if user is None:
                return

            # no new files can be added since profile deletion
            uconn = UserConn(cur)
            await uconn.delete_user(user.username)

            fconn = FileConn(cur)
            records = await fconn.delete_user_file_records(user.id)
            self.logger.debug("Deleting files...")
            await self.__batch_delete_file_blobs(fconn, records)
            self.logger.info(f"Deleted {len(records)} file(s) for user {user.username}")

            # make sure the user's directory is deleted, 
            # may contain admin's files, but delete them all
            await fconn.delete_records_by_prefix(user.username + '/')
    
    async def iter_dir(self, top_url: str, urls: Optional[list[str]]) -> AsyncIterable[tuple[FileRecord, bytes | AsyncIterable[bytes]]]:
        validate_url(top_url, 'dir')
        async with unique_cursor() as cur:
            fconn = FileConn(cur)
            if urls is None:
                fcount = await fconn.count_dir_files(top_url, flat=True)
                urls = [r.url for r in (await fconn.list_dir_files(top_url, flat=True, limit=fcount))]

            for url in urls:
                if not url.startswith(top_url):
                    continue
                r = await fconn.get_file_record(url)
                if r is None:
                    continue
                f_id = r.file_id
                if r.external:
                    blob = fconn.get_file_blob_external(f_id)
                else:
                    blob = await fconn.get_file_blob(f_id)
                yield r, blob
    
    async def zip_dir_stream(self, top_url: str, op_user: Optional[UserRecord] = None) -> AsyncIterable[bytes]:
        from stat import S_IFREG
        from stream_zip import async_stream_zip, ZIP_64
        if top_url.startswith('/'):
            top_url = top_url[1:]
        
        if op_user:
            if await check_path_permission(top_url, op_user) < AccessLevel.READ:
                raise PermissionDeniedError(f"Permission denied: {op_user.username} cannot zip path {top_url}")
        
        # https://stream-zip.docs.trade.gov.uk/async-interface/
        async def data_iter():
            async for (r, blob) in self.iter_dir(top_url, None):
                rel_path = r.url[len(top_url):]
                rel_path = decode_uri_compnents(rel_path)
                b_iter: AsyncIterable[bytes]
                if isinstance(blob, bytes):
                    async def blob_iter(): yield blob
                    b_iter = blob_iter()    # type: ignore
                else:
                    assert isinstance(blob, AsyncIterable)
                    b_iter = blob
                yield (
                    rel_path, 
                    datetime.datetime.now(), 
                    S_IFREG | 0o600,
                    ZIP_64, 
                    b_iter
                )
        return async_stream_zip(data_iter())

    @concurrent_wrap()
    async def zip_dir(self, top_url: str, op_user: Optional[UserRecord]) -> io.BytesIO:
        if top_url.startswith('/'):
            top_url = top_url[1:]
        
        if op_user:
            if await check_path_permission(top_url, op_user) < AccessLevel.READ:
                raise PermissionDeniedError(f"Permission denied: {op_user.username} cannot zip path {top_url}")
        
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as zf:
            async for (r, blob) in self.iter_dir(top_url, None):
                rel_path = r.url[len(top_url):]
                rel_path = decode_uri_compnents(rel_path)
                if r.external:
                    assert isinstance(blob, AsyncIterable)
                    zf.writestr(rel_path, b''.join([chunk async for chunk in blob]))
                else:
                    assert isinstance(blob, bytes)
                    zf.writestr(rel_path, blob)
        buffer.seek(0)
        return buffer

async def _get_path_owner(cur: aiosqlite.Cursor, path: str) -> UserRecord:
    path_username = path.split('/')[0]
    uconn = UserConn(cur)
    path_user = await uconn.get_user(path_username)
    if path_user is None:
        raise InvalidPathError(f"Invalid path: {path_username} is not a valid username")
    return path_user

async def check_file_read_permission(user: UserRecord, file: FileRecord, cursor: Optional[aiosqlite.Cursor] = None) -> tuple[bool, str]:
    """
    This does not consider alias level permission,
    use check_path_permission for alias level permission check first:
    ```
    if await check_path_permission(file.url, user) < AccessLevel.READ:
        read_allowed, reason = check_file_read_permission(user, file)
    ```
    The implementation assumes the user is not admin and is not the owner of the file/path
    """
    @asynccontextmanager
    async def this_cur():
        if cursor is None:
            async with unique_cursor() as _cur:
                yield _cur
        else:
            yield cursor
    
    f_perm = file.permission

    # if file permission unset, use path owner's permission as fallback
    if f_perm == FileReadPermission.UNSET:
        async with this_cur() as cur:
            path_owner = await _get_path_owner(cur, file.url)
        f_perm = path_owner.permission
    
    # check permission of the file
    if f_perm == FileReadPermission.PRIVATE:
        return False, "Permission denied, private file"
    elif f_perm == FileReadPermission.PROTECTED:
        if user.id == 0:
            return False, "Permission denied, protected file"
    elif f_perm == FileReadPermission.PUBLIC:
        return True, ""
    else:
        assert f_perm == FileReadPermission.UNSET

    return True, ""

async def check_path_permission(path: str, user: UserRecord, cursor: Optional[aiosqlite.Cursor] = None) -> AccessLevel:
    """
    Check if the user has access to the path. 
    If the user is admin, the user will have all access.
    If the path is a file, the user will have all access if the user is the owner.
    Otherwise, the user will have alias level access w.r.t. the path user.
    """
    @asynccontextmanager
    async def this_cur():
        if cursor is None:
            async with unique_cursor() as _cur:
                yield _cur
        else:
            yield cursor

    # check if path user exists, may raise exception
    async with this_cur() as cur:
        path_owner = await _get_path_owner(cur, path)

    if user.id == 0:
        return AccessLevel.GUEST
    
    if user.is_admin:
        return AccessLevel.ALL
    
    # check if user is admin or the owner of the path
    if user.id == path_owner.id:
        return AccessLevel.ALL
    
    # if the path is a file, check if the user is the owner
    if not path.endswith('/'):
        async with this_cur() as cur:
            fconn = FileConn(cur)
            file = await fconn.get_file_record(path)
        if file and file.owner_id == user.id:
            return AccessLevel.ALL
    
    # check alias level
    async with this_cur() as cur:
        uconn = UserConn(cur)
        return await uconn.query_peer_level(user.id, path_owner.id)