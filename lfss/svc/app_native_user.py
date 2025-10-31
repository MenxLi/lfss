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
async def list_peers(
    user: UserRecord = Depends(registered_user), 
    level: AccessLevel = AccessLevel.READ, 
    incoming: bool = False, 
    admin: bool = True
    ):
    async with unique_cursor() as conn:
        uconn = UserConn(conn)
        peer_users = set(await uconn.list_peer_users(user.id, level, incoming=incoming))
    
        if admin and incoming:
            admin_users = set(await uconn.list_admin_users())
            peer_users.update(admin_users)
        
        if admin and not incoming and user.is_admin:
            all_users = set(await uconn.list_all_users())
            peer_users.update(all_users)

    return [u.desensitize() for u in peer_users if u.id != user.id]     # exclude self
