"""
High level user-management API.
"""

from typing import Optional
from .utils import parse_storage_size
from .datatype import UserRecord, FileReadPermission, AccessLevel
from .database import Database, UserConn, transaction, unique_cursor
from .error import *

async def _ensure_user_exists(u: str | int) -> UserRecord:
    async with unique_cursor() as conn:
        uconn = UserConn(conn)
        if isinstance(u, str):
            user = await uconn.get_user(u)
        else:
            user = await uconn.get_user_by_id(u)
        if user is None:
            raise UserNotFoundError(f"User {u} not found")
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

class UserCtl:

    @staticmethod
    async def get_user(u: str | int) -> UserRecord:
        return await _ensure_user_exists(u)

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
            import secrets
            password = secrets.token_urlsafe(16)
        if isinstance(max_storage, str):
            max_storage = parse_storage_size(max_storage)
        if isinstance(permission, str):
            permission = parse_permission(permission)
        async with transaction() as conn:
            uconn = UserConn(conn)
            user_id = await uconn.create_user(username, password, admin, max_storage=max_storage, permission=permission)
            user = await uconn.get_user_by_id(user_id)
            assert user is not None
            return user
    
    @staticmethod
    async def delete(username: str) -> UserRecord:
        """ Delete a user from the system"""
        await _ensure_user_exists(username)
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
        await _ensure_user_exists(username)
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
        src_user = await _ensure_user_exists(src_username)
        dst_user = await _ensure_user_exists(dst_username)
        if isinstance(level, str):
            level = parse_access_level(level)
        assert_or(level != AccessLevel.GUEST, lambda: InvalidInputError("Cannot set peer access level to GUEST"))
        assert_or(level != AccessLevel.ALL, lambda: InvalidInputError("Cannot set peer access level to ALL"))
        async with transaction() as conn:
            uconn = UserConn(conn)
            await uconn.set_peer_level(src_user.id, dst_user.id, level)