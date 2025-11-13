"""
High level user-management API.
"""

import secrets
from typing import Optional
from .utils import parse_storage_size, parse_sec_time, fmt_sec_time
from .datatype import UserRecord, FileReadPermission, AccessLevel
from .connection_pool import transaction, unique_cursor
from .database_conn import UserConn
from .database import Database
from .log import get_logger
from .error import *

async def _get_user__check(u: str | int, check_expire = False) -> UserRecord:
    async with unique_cursor() as conn:
        uconn = UserConn(conn)

        if isinstance(u, str): user = await uconn.get_user(u)
        else: user = await uconn.get_user_by_id(u)

        if user is None:
            raise UserNotFoundError(f"User {u} not found")
        if check_expire:
            expire_seconds = await uconn.query_user_expire(user.id)
            if expire_seconds is not None and expire_seconds <= 0:
                raise UserNotFoundError(f"User {u} has expired in: {-expire_seconds} seconds")
    return user

def parse_access_level(s: str) -> AccessLevel:
    for p in AccessLevel:
        if p.name.lower() == s.lower():
            return p
    raise ValueError(f"Invalid access level {s}")

def parse_permission(s: str) -> FileReadPermission:
    for p in FileReadPermission:
        if p.name.lower() == s.lower():
            return p
    raise ValueError(f"Invalid file read permission {s}")

def parse_peer_list(s: str) -> dict[AccessLevel, list[str]]:
    """
    Parse peer string in the format of:
    "READ:user1,user2;WRITE:user3"
    """
    peers: dict[AccessLevel, list[str]] = {}
    if not s:
        return peers
    for part in s.split(';'):
        if ':' not in part:
            raise ValueError(f"Invalid peer format: {part}")
        level_str, users_str = part.split(':', 1)
        level = parse_access_level(level_str)
        users = [u.strip() for u in users_str.split(',') if u.strip()]
        if not users:
            raise ValueError(f"No users specified for access level {level.name}")
        peers[level] = users
    return peers

class UserCtl:
    virtual_prefix = ".v-"
    logger = get_logger('userman', global_instance=True)

    @staticmethod
    async def get_user(u: str | int, check_expire = True) -> UserRecord:
        return await _get_user__check(u, check_expire=check_expire)

    @staticmethod
    async def get_user_by_credential(u: str, check_expire = True) -> Optional[UserRecord]:
        async with unique_cursor() as conn:
            uconn = UserConn(conn)
            user = await uconn.get_user_by_credential(u)
            if user is None:
                return None
            if check_expire:
                expire_seconds = await uconn.query_user_expire(user.id)
                if expire_seconds is not None and expire_seconds <= 0:
                    UserCtl.logger.debug(f"Try to get expired user by credential: {u} | expired {-expire_seconds} seconds ago")
                    return None
            return user

    @staticmethod
    async def add(
        username: str, 
        password: Optional[str] = None, 
        admin: bool = False, 
        max_storage: int | str = '100G', 
        permission: FileReadPermission | str = 'unset'
        ) -> UserRecord:
        """
        Add a new user to the system.
        if password is None, a random password will be generated.
        Returns the created UserRecord.
        """
        if password is None:
            password = secrets.token_urlsafe(16)
        if isinstance(max_storage, str):
            max_storage = parse_storage_size(max_storage)
        if isinstance(permission, str):
            permission = parse_permission(permission)
        
        UserCtl.logger.info(f"Creating user: {username}, admin: {admin}, max_storage: {max_storage}, permission: {permission.name}")
        async with transaction() as conn:
            uconn = UserConn(conn)
            user_id = await uconn.create_user(username, password, admin, max_storage=max_storage, permission=permission)
            user = await uconn.get_user_by_id(user_id)
            assert user is not None
            return user

    @staticmethod
    async def add_virtual(
        tag: str = "", 
        peers: dict[AccessLevel, list[str]] | str = {},
        max_storage: int | str = '100G', 
        expire_seconds: Optional[int] = None, 
        ) -> UserRecord:
        """
        Add a new virtual (hidden) user to the system.
        The username will be prefixed with UserCtl.virtual_prefix.
        if tag is provided, the username will be "{virtual_prefix}{tag}-{random}".
        if peers is a string, it will be parsed by parse_peer_list.
        Returns the created UserRecord.
        """
        if tag:
            assert tag.isalnum(), "Tag must be alphanumeric"
            username = f"{UserCtl.virtual_prefix}{tag}-{secrets.token_urlsafe(8)}"
        else:
            username = f"{UserCtl.virtual_prefix}{secrets.token_urlsafe(12)}"
        
        if isinstance(peers, str):
            peers = parse_peer_list(peers)
        
        UserCtl.logger.info(f"Creating virtual user: {username}, expire in {expire_seconds} seconds, peers: {peers}")
        async with transaction() as conn:
            uconn = UserConn(conn)
            if isinstance(max_storage, str):
                max_storage = parse_storage_size(max_storage)
            user_id = await uconn.create_user(
                username=username, 
                password=secrets.token_urlsafe(16), 
                is_admin=False, 
                max_storage=max_storage, 
                permission=FileReadPermission.UNSET,
                _validate = False
            )
            if expire_seconds is not None:
                await uconn.set_user_expire(user_id, expire_seconds)
            for level, user_list in peers.items():
                if isinstance(level, str):
                    level = parse_access_level(level)
                for peer_username in user_list:
                    peer_user = await _get_user__check(peer_username)
                    await uconn.set_peer_level(user_id, peer_user.id, level)
            user = await uconn.get_user_by_id(user_id)
            assert user is not None
            return user
    
    @staticmethod
    async def set_expire(username: str, expire_seconds: Optional[int | str]):
        """
        Set user expire time in seconds, or a string in the format of '1d2h3m4s'.
        if expire_seconds is None, set the user to never expire.
        """
        if isinstance(expire_seconds, str):
            expire_seconds = parse_sec_time(expire_seconds)
        user = await _get_user__check(username)
        UserCtl.logger.info(
            f"Setting user expire: {username} to "
            f"{fmt_sec_time(expire_seconds) if expire_seconds is not None else 'never'}"
            )
        async with transaction() as conn:
            uconn = UserConn(conn)
            if expire_seconds is None:
                await uconn.clear_user_expire(user.id)
            else: 
                await uconn.set_user_expire(user.id, expire_seconds)
    
    @staticmethod
    async def delete(username: str) -> UserRecord:
        """ Delete a user from the system"""
        await _get_user__check(username)

        UserCtl.logger.info(f"Deleting user: {username}")
        return await Database().delete_user(username)
    
    @staticmethod
    async def update(
        username: str, 
        password: Optional[str] = None, 
        admin: Optional[bool] = None, 
        max_storage: Optional[int | str] = None, 
        permission: Optional[FileReadPermission | str] = None
        ) -> UserRecord:
        """
        Update user information.
        Returns the updated UserRecord.
        """
        await _get_user__check(username)
        if isinstance(max_storage, str):
            max_storage = parse_storage_size(max_storage)
        if isinstance(permission, str):
            permission = parse_permission(permission)
        async with transaction() as conn:
            uconn = UserConn(conn)
            await uconn.update_user(
                username=username, 
                password=password, 
                is_admin=admin, 
                max_storage=max_storage, 
                permission=permission
            )
            user = await uconn.get_user(username)
            assert user is not None
            return user
    
    @staticmethod
    async def set_peer(src_username: str, dst_username: str, level: AccessLevel | str):
        """
        Set peer access level from src_username to dst_username.
        So that [src_username] can do [level] to [dst_username].
        """
        src_user = await _get_user__check(src_username)
        dst_user = await _get_user__check(dst_username)
        if isinstance(level, str):
            level = parse_access_level(level)
        assert_or(level != AccessLevel.GUEST, lambda: InvalidInputError("Cannot set peer access level to GUEST"))
        assert_or(level != AccessLevel.ALL, lambda: InvalidInputError("Cannot set peer access level to ALL"))
        async with transaction() as conn:
            uconn = UserConn(conn)
            await uconn.set_peer_level(src_user.id, dst_user.id, level)