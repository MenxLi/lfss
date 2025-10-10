from fastapi import Depends

from .app_base import *
from ..eng.datatype import UserRecord, AccessLevel
from ..eng.database import unique_cursor, UserConn, FileConn

@router_user.get("/whoami")
@handle_exception
async def whoami(user: UserRecord = Depends(registered_user)):
    return user.desensitize()

@router_user.get("/storage")
@handle_exception
async def user_storage(user: UserRecord = Depends(registered_user)):
    async with unique_cursor() as conn:
        fconn = FileConn(conn)
        return {
            "quota": user.max_storage,
            "used": await fconn.user_size(user.id)
        }

@router_user.get("/list-peers")
@handle_exception
async def list_peers(user: UserRecord = Depends(registered_user), level: AccessLevel = AccessLevel.READ, incoming: bool = False):
    async with unique_cursor() as conn:
        uconn = UserConn(conn)
        peer_users = await uconn.list_peer_users(user.id, level, incoming=incoming)
    return [u.desensitize() for u in peer_users]
