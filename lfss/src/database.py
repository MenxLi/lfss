
from typing import Optional, overload, Literal, AsyncIterable
from abc import ABC

import urllib.parse
import uuid
import zipfile, io, asyncio

import aiosqlite, aiofiles
import aiofiles.os

from .connection_pool import execute_sql, unique_cursor, transaction
from .datatype import UserRecord, FileReadPermission, FileRecord, DirectoryRecord, PathContents
from .config import LARGE_BLOB_DIR, hash_credential
from .log import get_logger
from .utils import decode_uri_compnents
from .error import *

class DBObjectBase(ABC):
    logger = get_logger('database', global_instance=True)
    _cur: aiosqlite.Cursor

    def set_cursor(self, cur: aiosqlite.Cursor):
        self._cur = cur

    @property
    def cur(self)->aiosqlite.Cursor:
        if not hasattr(self, '_cur'):
            raise ValueError("Connection not set")
        return self._cur

    # async def commit(self):
    #     await self.conn.commit()

DECOY_USER = UserRecord(0, 'decoy', 'decoy', False, '2021-01-01 00:00:00', '2021-01-01 00:00:00', 0, FileReadPermission.PRIVATE)
class UserConn(DBObjectBase):

    def __init__(self, cur: aiosqlite.Cursor) -> None:
        super().__init__()
        self.set_cursor(cur)

    @staticmethod
    def parse_record(record) -> UserRecord:
        return UserRecord(*record)

    async def init(self, cur: aiosqlite.Cursor):
        self.set_cursor(cur)
        return self
    
    async def get_user(self, username: str) -> Optional[UserRecord]:
        await self.cur.execute("SELECT * FROM user WHERE username = ?", (username, ))
        res = await self.cur.fetchone()
        
        if res is None: return None
        return self.parse_record(res)
    
    async def get_user_by_id(self, user_id: int) -> Optional[UserRecord]:
        await self.cur.execute("SELECT * FROM user WHERE id = ?", (user_id, ))
        res = await self.cur.fetchone()
        
        if res is None: return None
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
        assert not username.startswith('_'), "Error: reserved username"
        assert not ('/' in username or len(username) > 255), "Invalid username"
        assert urllib.parse.quote(username) == username, "Invalid username, must be URL safe"
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
        await self.cur.execute("DELETE FROM user WHERE username = ?", (username, ))
        self.logger.info(f"Delete user {username}")

class FileConn(DBObjectBase):

    def __init__(self, cur: aiosqlite.Cursor) -> None:
        super().__init__()
        self.set_cursor(cur)

    @staticmethod
    def parse_record(record) -> FileRecord:
        return FileRecord(*record)
    
    def init(self, cur: aiosqlite.Cursor):
        self.set_cursor(cur)
        return self
    
    async def get_file_record(self, url: str) -> Optional[FileRecord]:
        cursor = await self.cur.execute("SELECT * FROM fmeta WHERE url = ?", (url, ))
        res = await cursor.fetchone()
        if res is None:
            return None
        return self.parse_record(res)
    
    async def get_file_records(self, urls: list[str]) -> list[FileRecord]:
        await self.cur.execute("SELECT * FROM fmeta WHERE url IN ({})".format(','.join(['?'] * len(urls))), urls)
        res = await self.cur.fetchall()
        if res is None:
            return []
        return [self.parse_record(r) for r in res]
    
    async def list_root(self, *usernames: str) -> list[DirectoryRecord]:
        """
        Efficiently list users' directories, if usernames is empty, list all users' directories.
        """
        if not usernames:
            # list all users
            await self.cur.execute("SELECT username FROM user")
            res = await self.cur.fetchall()
            dirnames = [u[0] + '/' for u in res]
            dirs = [DirectoryRecord(u, await self.path_size(u, include_subpath=True)) for u in dirnames]
            return dirs
        else:
            # list specific users
            dirnames = [uname + '/' for uname in usernames]
            dirs = [DirectoryRecord(u, await self.path_size(u, include_subpath=True)) for u in dirnames]
            return dirs
    
    @overload
    async def list_path(self, url: str, flat: Literal[True]) -> list[FileRecord]:...
    @overload
    async def list_path(self, url: str, flat: Literal[False]) -> PathContents:...
    
    async def list_path(self, url: str, flat: bool = False) -> list[FileRecord] | PathContents:
        """
        List all files and directories under the given path, 
        if flat is True, return a list of FileDBRecord, recursively including all subdirectories. 
        Otherwise, return a tuple of (dirs, files), where dirs is a list of DirectoryRecord,
        """
        if not url.endswith('/'):
            url += '/'
        if url == '/':
            # users cannot be queried using '/', because we store them without '/' prefix, 
            # so we need to handle this case separately, 
            if flat:
                cursor = await self.cur.execute("SELECT * FROM fmeta")
                res = await cursor.fetchall()
                return [self.parse_record(r) for r in res]

            else:
                return PathContents(await self.list_root(), [])
        
        if flat:
            cursor = await self.cur.execute("SELECT * FROM fmeta WHERE url LIKE ?", (url + '%', ))
            res = await cursor.fetchall()
            return [self.parse_record(r) for r in res]

        cursor = await self.cur.execute("SELECT * FROM fmeta WHERE url LIKE ? AND url NOT LIKE ?", (url + '%', url + '%/%'))
        res = await cursor.fetchall()
        files = [self.parse_record(r) for r in res]

        # substr indexing starts from 1
        cursor = await self.cur.execute(
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
            )
        res = await cursor.fetchall()
        dirs_str = [r[0] + '/' for r in res if r[0] != '/']
        async def get_dir(dir_url):
            return DirectoryRecord(dir_url, -1)
        dirs = await asyncio.gather(*[get_dir(url + d) for d in dirs_str])
        return PathContents(dirs, files)
    
    async def get_path_record(self, url: str) -> DirectoryRecord:
        assert url.endswith('/'), "Path must end with /"
        cursor = await self.cur.execute("""
            SELECT MIN(create_time) as create_time, 
                MAX(create_time) as update_time, 
                MAX(access_time) as access_time 
            FROM fmeta 
            WHERE url LIKE ?
        """, (url + '%', ))
        result = await cursor.fetchone()
        if result is None or any(val is None for val in result):
            raise PathNotFoundError(f"Path {url} not found")
        create_time, update_time, access_time = result
        p_size = await self.path_size(url, include_subpath=True)
        return DirectoryRecord(url, p_size, create_time=create_time, update_time=update_time, access_time=access_time)
    
    async def user_size(self, user_id: int) -> int:
        cursor = await self.cur.execute("SELECT size FROM usize WHERE user_id = ?", (user_id, ))
        res = await cursor.fetchone()
        if res is None:
            return -1
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
            cursor = await self.cur.execute("SELECT SUM(file_size) FROM fmeta WHERE url LIKE ? AND url NOT LIKE ?", (url + '%', url + '%/%'))
            res = await cursor.fetchone()
        else:
            cursor = await self.cur.execute("SELECT SUM(file_size) FROM fmeta WHERE url LIKE ?", (url + '%', ))
            res = await cursor.fetchone()
        assert res is not None
        return res[0] or 0
    
    async def update_file_record(
        self, url, owner_id: Optional[int] = None, permission: Optional[FileReadPermission] = None
        ):
        old = await self.get_file_record(url)
        assert old is not None, f"File {url} not found"
        if owner_id is None:
            owner_id = old.owner_id
        if permission is None:
            permission = old.permission
        await self.cur.execute(
            "UPDATE fmeta SET owner_id = ?, permission = ? WHERE url = ?", 
            (owner_id, int(permission), url)
            )
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
    
    async def move_file(self, old_url: str, new_url: str):
        old = await self.get_file_record(old_url)
        if old is None:
            raise FileNotFoundError(f"File {old_url} not found")
        new_exists = await self.get_file_record(new_url)
        if new_exists is not None:
            raise FileExistsError(f"File {new_url} already exists")
        await self.cur.execute("UPDATE fmeta SET url = ?, create_time = CURRENT_TIMESTAMP WHERE url = ?", (new_url, old_url))
        self.logger.info(f"Moved file {old_url} to {new_url}")
    
    async def move_path(self, old_url: str, new_url: str, conflict_handler: Literal['skip', 'overwrite'] = 'overwrite', user_id: Optional[int] = None):
        assert old_url.endswith('/'), "Old path must end with /"
        assert new_url.endswith('/'), "New path must end with /"
        if user_id is None:
            cursor = await self.cur.execute("SELECT * FROM fmeta WHERE url LIKE ?", (old_url + '%', ))
            res = await cursor.fetchall()
        else:
            cursor = await self.cur.execute("SELECT * FROM fmeta WHERE url LIKE ? AND owner_id = ?", (old_url + '%', user_id))
            res = await cursor.fetchall()
        for r in res:
            new_r = new_url + r[0][len(old_url):]
            if conflict_handler == 'overwrite':
                await self.cur.execute("DELETE FROM fmeta WHERE url = ?", (new_r, ))
            elif conflict_handler == 'skip':
                if (await self.cur.execute("SELECT url FROM fmeta WHERE url = ?", (new_r, ))) is not None:
                    continue
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
        cursor = await self.cur.execute("SELECT * FROM fmeta WHERE owner_id = ?", (owner_id, ))
        res = await cursor.fetchall()
        await self.cur.execute("DELETE FROM usize WHERE user_id = ?", (owner_id, ))
        res = await self.cur.execute("DELETE FROM fmeta WHERE owner_id = ? RETURNING *", (owner_id, ))
        ret = [self.parse_record(r) for r in await res.fetchall()]
        self.logger.info(f"Deleted {len(ret)} file(s) for user {owner_id}") # type: ignore
        return ret
    
    async def delete_path_records(self, path: str, under_user_id: Optional[int] = None) -> list[FileRecord]:
        """Delete all records with url starting with path"""
        # update user size
        cursor = await self.cur.execute("SELECT DISTINCT owner_id FROM fmeta WHERE url LIKE ?", (path + '%', ))
        res = await cursor.fetchall()
        for r in res:
            cursor = await self.cur.execute("SELECT SUM(file_size) FROM fmeta WHERE owner_id = ? AND url LIKE ?", (r[0], path + '%'))
            size = await cursor.fetchone()
            if size is not None:
                await self._user_size_dec(r[0], size[0])
        
        # if any new records are created here, the size update may be inconsistent
        # but it's not a big deal...
        
        if under_user_id is None:
            res = await self.cur.execute("DELETE FROM fmeta WHERE url LIKE ? RETURNING *", (path + '%', ))
        else:
            res = await self.cur.execute("DELETE FROM fmeta WHERE url LIKE ? AND owner_id = ? RETURNING *", (path + '%', under_user_id))
        all_f_rec = await res.fetchall()
        self.logger.info(f"Deleted {len(all_f_rec)} file(s) for path {path}") # type: ignore
        return [self.parse_record(r) for r in all_f_rec]
    
    async def set_file_blob(self, file_id: str, blob: bytes):
        await self.cur.execute("INSERT OR REPLACE INTO blobs.fdata (file_id, data) VALUES (?, ?)", (file_id, blob))
    
    async def set_file_blob_external(self, file_id: str, stream: AsyncIterable[bytes])->int:
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
    
    async def get_file_blob(self, file_id: str) -> Optional[bytes]:
        cursor = await self.cur.execute("SELECT data FROM blobs.fdata WHERE file_id = ?", (file_id, ))
        res = await cursor.fetchone()
        if res is None:
            return None
        return res[0]
    
    async def get_file_blob_external(self, file_id: str) -> AsyncIterable[bytes]:
        assert (LARGE_BLOB_DIR / file_id).exists(), f"File {file_id} not found"
        async with aiofiles.open(LARGE_BLOB_DIR / file_id, 'rb') as f:
            async for chunk in f:
                yield chunk
    
    async def delete_file_blob_external(self, file_id: str):
        if (LARGE_BLOB_DIR / file_id).exists():
            await aiofiles.os.remove(LARGE_BLOB_DIR / file_id)
    
    async def delete_file_blob(self, file_id: str):
        await self.cur.execute("DELETE FROM blobs.fdata WHERE file_id = ?", (file_id, ))
    
    async def delete_file_blobs(self, file_ids: list[str]):
        await self.cur.execute("DELETE FROM blobs.fdata WHERE file_id IN ({})".format(','.join(['?'] * len(file_ids))), file_ids)

def validate_url(url: str, is_file = True):
    prohibited_chars = ['..', ';', "'", '"', '\\', '\0', '\n', '\r', '\t', '\x0b', '\x0c']
    ret = not url.startswith('/') and not url.startswith('_') and not url.startswith('.')
    ret = ret and not any([c in url for c in prohibited_chars])

    if not ret:
        raise InvalidPathError(f"Invalid URL: {url}")
    
    if is_file:
        ret = ret and not url.endswith('/')
    else:
        ret = ret and url.endswith('/')

    if not ret:
        raise InvalidPathError(f"Invalid URL: {url}")

async def get_user(cur: aiosqlite.Cursor, user: int | str) -> Optional[UserRecord]:
    uconn = UserConn(cur)
    if isinstance(user, str):
        return await uconn.get_user(user)
    elif isinstance(user, int):
        return await uconn.get_user_by_id(user)
    else:
        return None

# mostly transactional operations
class Database:
    logger = get_logger('database', global_instance=True)

    async def init(self):
        async with transaction() as conn:
            await execute_sql(conn, 'init.sql')
        return self
    
    async def record_user_activity(self, u: str):
        async with transaction() as conn:
            uconn = UserConn(conn)
            await uconn.set_active(u)
    
    async def update_file_record(self, user: UserRecord, url: str, permission: FileReadPermission):
        validate_url(url)
        async with transaction() as conn:
            fconn = FileConn(conn)
            r = await fconn.get_file_record(url)
            if r is None:
                raise PathNotFoundError(f"File {url} not found")
            if r.owner_id != user.id and not user.is_admin:
                raise PermissionDeniedError(f"Permission denied: {user.username} cannot update file {url}")
            await fconn.update_file_record(url, permission=permission)
    
    async def save_file(
        self, u: int | str, url: str, 
        blob: bytes | AsyncIterable[bytes], 
        permission: FileReadPermission = FileReadPermission.UNSET, 
        mime_type: str = 'application/octet-stream'
        ):
        """
        if file_size is not provided, the blob must be bytes
        """
        validate_url(url)
        async with transaction() as cur:
            uconn = UserConn(cur)
            fconn = FileConn(cur)
            user = await get_user(cur, u)
            if user is None:
                return
            
            # check if the user is the owner of the path, or is admin
            if url.startswith('/'):
                url = url[1:]
            first_component = url.split('/')[0]
            if first_component != user.username:
                if not user.is_admin:
                    raise PermissionDeniedError(f"Permission denied: {user.username} cannot write to {url}")
                else:
                    if await get_user(cur, first_component) is None:
                        raise PermissionDeniedError(f"Invalid path: {first_component} is not a valid username")
            
            user_size_used = await fconn.user_size(user.id)
            if isinstance(blob, bytes):
                file_size = len(blob)
                if user_size_used + file_size > user.max_storage:
                    raise StorageExceededError(f"Unable to save file, user {user.username} has storage limit of {user.max_storage}, used {user_size_used}, requested {file_size}")
                f_id = uuid.uuid4().hex
                await fconn.set_file_blob(f_id, blob)
                await fconn.set_file_record(
                    url, owner_id=user.id, file_id=f_id, file_size=file_size, 
                    permission=permission, external=False, mime_type=mime_type)
            else:
                assert isinstance(blob, AsyncIterable)
                f_id = uuid.uuid4().hex
                file_size = await fconn.set_file_blob_external(f_id, blob)
                if user_size_used + file_size > user.max_storage:
                    await fconn.delete_file_blob_external(f_id)
                    raise StorageExceededError(f"Unable to save file, user {user.username} has storage limit of {user.max_storage}, used {user_size_used}, requested {file_size}")
                await fconn.set_file_record(
                    url, owner_id=user.id, file_id=f_id, file_size=file_size, 
                    permission=permission, external=True, mime_type=mime_type)
            await uconn.set_active(user.username)

    async def read_file_stream(self, url: str) -> AsyncIterable[bytes]:
        validate_url(url)
        async with unique_cursor() as cur:
            fconn = FileConn(cur)
            r = await fconn.get_file_record(url)
            if r is None:
                raise FileNotFoundError(f"File {url} not found")
            if not r.external:
                raise ValueError(f"File {url} is not stored externally, should use read_file instead")
            ret = fconn.get_file_blob_external(r.file_id)

        async with transaction() as w_cur:
            await FileConn(w_cur).log_access(url)
        
        return ret


    async def read_file(self, url: str) -> bytes:
        validate_url(url)

        async with transaction() as cur:
            fconn = FileConn(cur)
            r = await fconn.get_file_record(url)
            if r is None:
                raise FileNotFoundError(f"File {url} not found")
            if r.external:
                raise ValueError(f"File {url} is stored externally, should use read_file_stream instead")

            f_id = r.file_id
            blob = await fconn.get_file_blob(f_id)
            if blob is None:
                raise FileNotFoundError(f"File {url} data not found")
            await fconn.log_access(url)

        return blob

    async def delete_file(self, url: str, assure_user: Optional[UserRecord] = None) -> Optional[FileRecord]:
        validate_url(url)

        async with transaction() as cur:
            fconn = FileConn(cur)
            r = await fconn.delete_file_record(url)
            if r is None:
                return None
            if assure_user is not None:
                if r.owner_id != assure_user.id:
                    # will rollback
                    raise PermissionDeniedError(f"Permission denied: {assure_user.username} cannot delete file {url}")
            f_id = r.file_id
            if r.external:
                await fconn.delete_file_blob_external(f_id)
            else:
                await fconn.delete_file_blob(f_id)
            return r
    
    async def move_file(self, old_url: str, new_url: str, ensure_user: Optional[UserRecord] = None):
        validate_url(old_url)
        validate_url(new_url)

        async with transaction() as cur:
            fconn = FileConn(cur)
            r = await fconn.get_file_record(old_url)
            if r is None:
                raise FileNotFoundError(f"File {old_url} not found")
            if ensure_user is not None:
                if r.owner_id != ensure_user.id:
                    raise PermissionDeniedError(f"Permission denied: {ensure_user.username} cannot move file {old_url}")
            await fconn.move_file(old_url, new_url)
    
    async def move_path(self, user: UserRecord, old_url: str, new_url: str):
        validate_url(old_url, is_file=False)
        validate_url(new_url, is_file=False)

        if new_url.startswith('/'):
            new_url = new_url[1:]
        if old_url.startswith('/'):
            old_url = old_url[1:]
        assert old_url != new_url, "Old and new path must be different"
        assert old_url.endswith('/'), "Old path must end with /"
        assert new_url.endswith('/'), "New path must end with /"

        async with transaction() as cur:
            first_component = new_url.split('/')[0]
            if not (first_component == user.username or user.is_admin):
                raise PermissionDeniedError(f"Permission denied: path must start with {user.username}")
            elif user.is_admin:
                uconn = UserConn(cur)
                _is_user = await uconn.get_user(first_component)
                if not _is_user:
                    raise PermissionDeniedError(f"Invalid path: {first_component} is not a valid username")
            
            # check if old path is under user's directory (non-admin)
            if not old_url.startswith(user.username + '/') and not user.is_admin:
                raise PermissionDeniedError(f"Permission denied: {user.username} cannot move path {old_url}")

            fconn = FileConn(cur)
            await fconn.move_path(old_url, new_url, 'overwrite', user.id)

    async def __batch_delete_file_blobs(self, fconn: FileConn, file_records: list[FileRecord], batch_size: int = 512):
        # https://github.com/langchain-ai/langchain/issues/10321
        internal_ids = []
        external_ids = []
        for r in file_records:
            if r.external:
                external_ids.append(r.file_id)
            else:
                internal_ids.append(r.file_id)
        
        for i in range(0, len(internal_ids), batch_size):
            await fconn.delete_file_blobs([r for r in internal_ids[i:i+batch_size]])
        for i in range(0, len(external_ids)):
            await fconn.delete_file_blob_external(external_ids[i])
            

    async def delete_path(self, url: str, under_user: Optional[UserRecord] = None) -> Optional[list[FileRecord]]:
        validate_url(url, is_file=False)
        user_id = under_user.id if under_user is not None else None

        async with transaction() as cur:
            fconn = FileConn(cur)
            records = await fconn.delete_path_records(url, user_id)
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
            await self.__batch_delete_file_blobs(fconn, records)

            # make sure the user's directory is deleted, 
            # may contain admin's files, but delete them all
            await fconn.delete_path_records(user.username + '/')
    
    async def iter_path(self, top_url: str, urls: Optional[list[str]]) -> AsyncIterable[tuple[FileRecord, bytes | AsyncIterable[bytes]]]:
        async with unique_cursor() as cur:
            fconn = FileConn(cur)
            if urls is None:
                urls = [r.url for r in await fconn.list_path(top_url, flat=True)]

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
                    if blob is None:
                        self.logger.warning(f"Blob not found for {url}")
                        continue
                yield r, blob

    async def zip_path(self, top_url: str, urls: Optional[list[str]]) -> io.BytesIO:
        if top_url.startswith('/'):
            top_url = top_url[1:]
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as zf:
            async for (r, blob) in self.iter_path(top_url, urls):
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

def check_user_permission(user: UserRecord, owner: UserRecord, file: FileRecord) -> tuple[bool, str]:
    if user.is_admin:
        return True, ""
    
    # check permission of the file
    if file.permission == FileReadPermission.PRIVATE:
        if user.id != owner.id:
            return False, "Permission denied, private file"
    elif file.permission == FileReadPermission.PROTECTED:
        if user.id == 0:
            return False, "Permission denied, protected file"
    elif file.permission == FileReadPermission.PUBLIC:
        return True, ""
    else:
        assert file.permission == FileReadPermission.UNSET

    # use owner's permission as fallback
    if owner.permission == FileReadPermission.PRIVATE:
        if user.id != owner.id:
            return False, "Permission denied, private user file"
    elif owner.permission == FileReadPermission.PROTECTED:
        if user.id == 0:
            return False, "Permission denied, protected user file"
    else:
        assert owner.permission == FileReadPermission.PUBLIC or owner.permission == FileReadPermission.UNSET

    return True, ""