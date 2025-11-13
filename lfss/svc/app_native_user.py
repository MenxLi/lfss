from fastapi import Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from .app_base import *
from ..eng.datatype import UserRecord, AccessLevel, FileReadPermission
from ..eng.database import unique_cursor, UserConn, FileConn
from ..eng.userman import UserCtl

@router_user.get("/whoami")
@handle_exception
async def whoami(user: UserRecord = Depends(registered_user)):
    return user.desensitize()

@router_user.get("/storage")
@handle_exception
async def user_storage(
    user: UserRecord = Depends(registered_user), 
    as_user: Optional[str] = None
    ):
    if as_user is not None:
        if not user.is_admin:
            raise HTTPException(status_code=403, detail="Admin permission required to query other user's storage")
        aim_user = await UserCtl.get_user(as_user)
        user = aim_user     # switch to the specified user

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
    admin: bool = True, 
    as_user: Optional[str] = None
    ):
    if as_user is not None:
        if not user.is_admin:
            raise HTTPException(status_code=403, detail="Admin permission required to list peers as another user")
        aim_user = await UserCtl.get_user(as_user)
        user = aim_user     # switch to the specified user
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


# ========================== Admin APIs ==========================
@router_user.get("/query")
@handle_exception
async def query_user(
    username: Optional[str] = None,
    userid: Optional[int] = None,
    op_user: UserRecord = Depends(registered_user), 
    ):
    if username is None and userid is None:
        raise HTTPException(status_code=400, detail="username or userid required")
    user = await UserCtl.get_user(username or userid)   # type: ignore
    if op_user.is_admin: return user                    # not desensitized
    else: return user.desensitize()

@router_user.post("/add")
@handle_exception
async def add_user(
    username: str, 
    password: Optional[str] = None, 
    admin: bool = False, 
    max_storage: str = '100G', 
    permission: str = 'UNSET', 
    _: UserRecord = Depends(admin_user), 
    ):
    # not desensitized
    return await UserCtl.add(
        username=username, 
        password=password, 
        admin=admin, 
        max_storage=max_storage, 
        permission=permission
        )

@router_user.post("/add-virtual")
@handle_exception
async def add_virtual_user(
    tag: str = "",
    peers: str = "",
    max_storage: str = '1G',
    expire: Optional[int | str] = None,
    _: UserRecord = Depends(admin_user), 
    ):
    # not desensitized
    return await UserCtl.add_virtual(
        tag=tag,
        peers=peers,
        max_storage=max_storage, 
        expire=expire
        )

@router_user.post("/update")
@handle_exception
async def update_user(
    username: str, 
    password: Optional[str] = None, 
    admin: Optional[bool] = None, 
    max_storage: Optional[str] = None, 
    permission: Optional[str] = None, 
    _: UserRecord = Depends(admin_user), 
    ):
    # not desensitized
    return await UserCtl.update(
        username=username,
        password=password,
        admin=admin,
        max_storage=max_storage,
        permission=permission
        )

@router_user.post("/delete")
@handle_exception
async def delete_user(
    username: str, 
    _: UserRecord = Depends(admin_user), 
    ):
    return (await UserCtl.delete(username)).desensitize()

@router_user.post("/set-peer")
@handle_exception
async def set_peer(
    src_username: str, 
    dst_username: str, 
    level: str, 
    _: UserRecord = Depends(admin_user), 
    ):
    await UserCtl.set_peer(src_username, dst_username, level)
    return {"detail": "Success, now '{}' has '{}' access to '{}'".format(
        src_username, level, dst_username
    )}