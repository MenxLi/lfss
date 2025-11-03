import aiosqlite
from typing import Optional
from contextlib import asynccontextmanager
from .datatype import UserRecord, FileRecord, FileReadPermission, AccessLevel
from .database_conn import UserConn, FileConn
from .connection_pool import unique_cursor
from .dir_config import load_dir_config
from .utils import decode_uri_components
from .config import DIR_CONFIG_FNAME
from .error import *

def is_dir_config_file(path: str | FileRecord) -> bool:
    if isinstance(path, FileRecord):
        return path.name() == DIR_CONFIG_FNAME
    elif isinstance(path, str):
        return decode_uri_components(path).endswith('/' + DIR_CONFIG_FNAME)
    else:
        return False

async def _get_path_owner(cur: aiosqlite.Cursor, path: str) -> UserRecord:
    path_username = path.split('/')[0]
    uconn = UserConn(cur)
    path_user = await uconn.get_user(path_username)
    if path_user is None:
        raise PathNotFoundError(f"Path not found: {path_username} is not a valid username")
    return path_user

async def check_file_read_permission(user: UserRecord, file: FileRecord, cursor: Optional[aiosqlite.Cursor] = None) -> tuple[bool, str]:
    """
    This does not consider alias level permission,
    use check_path_permission for alias level permission check first:
    ```
    if await check_path_permission(file.url, user) < AccessLevel.READ:
        read_allowed, reason = check_file_read_permission(user, file)
    ```
    The implementation assumes the user is not admin and is not the owner/peer of the file/path
    """
    @asynccontextmanager
    async def this_cur():
        if cursor is None:
            async with unique_cursor() as _cur:
                yield _cur
        else:
            yield cursor
    
    if is_dir_config_file(file):
        return False, "Permission denied, directory config file can only be accessed by the owner/admin"
    
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
    
    # if the path is a file
    if not path.endswith('/'):
        async with this_cur() as cur:
            fconn = FileConn(cur)
            file = await fconn.get_file_record(path)
        
        # file owner has all access
        if file and file.owner_id == user.id:
            return AccessLevel.ALL

        # directory config file can only be accessed by owner/path owner/admin
        if is_dir_config_file(path):
            return AccessLevel.NONE
    
    # check directory config access control
    async with this_cur() as cur:
        dir_cfg = await load_dir_config(path, cur)
    if user.username in dir_cfg.access_control:
        return dir_cfg.access_control[user.username]
    
    # check alias level
    async with this_cur() as cur:
        uconn = UserConn(cur)
        return await uconn.query_peer_level(user.id, path_owner.id)