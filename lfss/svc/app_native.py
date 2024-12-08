from typing import Optional, Literal

from fastapi import Depends, Request, Response, UploadFile
from fastapi.exceptions import HTTPException 

from ..eng.config import MAX_BUNDLE_BYTES
from ..eng.utils import ensure_uri_compnents
from ..eng.connection_pool import unique_cursor
from ..eng.database import check_file_read_permission, check_path_permission, UserConn, FileConn
from ..eng.datatype import (
    FileReadPermission, FileRecord, UserRecord, AccessLevel, 
    FileSortKey, DirSortKey
)

from .app_base import *
from .common_impl import get_file_impl, put_file_impl, post_file_impl, delete_impl, copy_impl

@router_fs.get("/{path:path}")
@handle_exception
async def get_file(
    request: Request,
    path: str, 
    download: bool = False, thumb: bool = False,
    user: UserRecord = Depends(get_current_user)
    ):
    return await get_file_impl(
        request = request,
        user = user, path = path, download = download, thumb = thumb
        )

@router_fs.head("/{path:path}")
@handle_exception
async def head_file(
    request: Request,
    path: str, 
    download: bool = False, thumb: bool = False,
    user: UserRecord = Depends(get_current_user)
    ):
    if path.startswith("_api/"):
        raise HTTPException(status_code=405, detail="HEAD not supported for API")
    if path.endswith("/"):
        raise HTTPException(status_code=405, detail="HEAD not supported for directory")
    return await get_file_impl(
        request = request,
        user = user, path = path, download = download, thumb = thumb, is_head = True
        )

@router_fs.put("/{path:path}")
@handle_exception
async def put_file(
    request: Request, 
    path: str, 
    conflict: Literal["overwrite", "skip", "abort"] = "abort",
    permission: int = 0,
    user: UserRecord = Depends(registered_user)
    ):
    return await put_file_impl(
        request = request, user = user, path = path, conflict = conflict, permission = permission
    )

# using form-data instead of raw body
@router_fs.post("/{path:path}")
@handle_exception
async def post_file(
    path: str, 
    file: UploadFile,
    conflict: Literal["overwrite", "skip", "abort"] = "abort",
    permission: int = 0,
    user: UserRecord = Depends(registered_user)
    ):
    return await post_file_impl(
        file = file, user = user, path = path, conflict = conflict, permission = permission
    )

@router_fs.delete("/{path:path}")
@handle_exception
async def delete_file(path: str, user: UserRecord = Depends(registered_user)):
    return await delete_impl(path, user)


@router_api.get("/bundle")
@handle_exception
async def bundle_files(path: str, user: UserRecord = Depends(registered_user)):
    logger.info(f"GET bundle({path}), user: {user.username}")
    path = ensure_uri_compnents(path)
    assert path.endswith("/") or path == ""

    if not path == "" and path[0] == "/":   # adapt to both /path and path
        path = path[1:]
    
    # TODO: may check peer users here
    owner_records_cache: dict[int, UserRecord] = {}     # cache owner records, ID -> UserRecord
    async def is_access_granted(file_record: FileRecord):
        owner_id = file_record.owner_id
        owner = owner_records_cache.get(owner_id, None)
        if owner is None:
            async with unique_cursor() as conn:
                uconn = UserConn(conn)
                owner = await uconn.get_user_by_id(owner_id, throw=True)
            owner_records_cache[owner_id] = owner
            
        allow_access, _ = check_file_read_permission(user, owner, file_record)
        return allow_access
    
    async with unique_cursor() as conn:
        fconn = FileConn(conn)
        files = await fconn.list_path_files(
            url = path, flat = True, 
            limit=(await fconn.count_path_files(url = path, flat = True))
            )
    files = [f for f in files if await is_access_granted(f)]
    if len(files) == 0:
        raise HTTPException(status_code=404, detail="No files found")

    # return bundle of files
    total_size = sum([f.file_size for f in files])
    if total_size > MAX_BUNDLE_BYTES:
        raise HTTPException(status_code=400, detail="Too large to zip")

    file_paths = [f.url for f in files]
    zip_buffer = await db.zip_path(path, file_paths)
    return Response(
        content=zip_buffer.getvalue(), media_type="application/zip", headers={
            "Content-Disposition": f"attachment; filename=bundle.zip", 
            "Content-Length": str(zip_buffer.getbuffer().nbytes)
        }
    )

@router_api.get("/meta")
@handle_exception
async def get_file_meta(path: str, user: UserRecord = Depends(registered_user)):
    logger.info(f"GET meta({path}), user: {user.username}")
    path = ensure_uri_compnents(path)
    is_file = not path.endswith("/")
    async with unique_cursor() as cur:
        fconn = FileConn(cur)
        if is_file:
            record = await fconn.get_file_record(path, throw=True)
            if await check_path_permission(path, user, cursor=cur) < AccessLevel.READ:
                uconn = UserConn(cur)
                owner = await uconn.get_user_by_id(record.owner_id, throw=True)
                is_allowed, reason = check_file_read_permission(user, owner, record)
                if not is_allowed:
                    raise HTTPException(status_code=403, detail=reason)
        else:
            if await check_path_permission(path, user, cursor=cur) < AccessLevel.READ:
                raise HTTPException(status_code=403, detail="Permission denied")
            record = await fconn.get_path_record(path)
    return record

@router_api.post("/meta")
@handle_exception
async def update_file_meta(
    path: str, 
    perm: Optional[int] = None, 
    new_path: Optional[str] = None,
    user: UserRecord = Depends(registered_user)
    ):
    path = ensure_uri_compnents(path)
    if path.startswith("/"):
        path = path[1:]

    # file
    if not path.endswith("/"):
        if perm is not None:
            logger.info(f"Update permission of {path} to {perm}")
            await db.update_file_record(
                url = path, 
                permission = FileReadPermission(perm), 
                op_user = user,
            )
    
        if new_path is not None:
            new_path = ensure_uri_compnents(new_path)
            logger.info(f"Update path of {path} to {new_path}")
            await db.move_file(path, new_path, user)
    
    # directory
    else:
        assert perm is None, "Permission is not supported for directory"
        if new_path is not None:
            new_path = ensure_uri_compnents(new_path)
            logger.info(f"Update path of {path} to {new_path}")
            # currently only move own file, with overwrite
            await db.move_path(path, new_path, user)

    return Response(status_code=200, content="OK")

@router_api.post("/copy")
@handle_exception
async def copy_file(
    src: str, dst: str, 
    user: UserRecord = Depends(registered_user)
    ):
    return await copy_impl(src_path = src, dst_path = dst, op_user = user)

async def validate_path_read_permission(path: str, user: UserRecord):
    if not path.endswith("/"):
        raise HTTPException(status_code=400, detail="Path must end with /")
    if not await check_path_permission(path, user) >= AccessLevel.READ:
        raise HTTPException(status_code=403, detail="Permission denied")
@router_api.get("/count-files")
async def count_files(path: str, flat: bool = False, user: UserRecord = Depends(registered_user)):
    await validate_path_read_permission(path, user)
    path = ensure_uri_compnents(path)
    async with unique_cursor() as conn:
        fconn = FileConn(conn)
        return { "count": await fconn.count_path_files(url = path, flat = flat) }
@router_api.get("/list-files")
async def list_files(
    path: str, offset: int = 0, limit: int = 1000,
    order_by: FileSortKey = "", order_desc: bool = False,
    flat: bool = False, user: UserRecord = Depends(registered_user)
    ):
    await validate_path_read_permission(path, user)
    path = ensure_uri_compnents(path)
    async with unique_cursor() as conn:
        fconn = FileConn(conn)
        return await fconn.list_path_files(
            url = path, offset = offset, limit = limit,
            order_by=order_by, order_desc=order_desc, 
            flat=flat
        )

@router_api.get("/count-dirs")
async def count_dirs(path: str, user: UserRecord = Depends(registered_user)):
    await validate_path_read_permission(path, user)
    path = ensure_uri_compnents(path)
    async with unique_cursor() as conn:
        fconn = FileConn(conn)
        return { "count": await fconn.count_path_dirs(url = path) }
@router_api.get("/list-dirs")
async def list_dirs(
    path: str, offset: int = 0, limit: int = 1000,
    order_by: DirSortKey = "", order_desc: bool = False,
    skim: bool = True, user: UserRecord = Depends(registered_user)
    ):
    await validate_path_read_permission(path, user)
    path = ensure_uri_compnents(path)
    async with unique_cursor() as conn:
        fconn = FileConn(conn)
        return await fconn.list_path_dirs(
            url = path, offset = offset, limit = limit,
            order_by=order_by, order_desc=order_desc, skim=skim
        )
    
@router_api.get("/whoami")
@handle_exception
async def whoami(user: UserRecord = Depends(registered_user)):
    user.credential = "__HIDDEN__"
    return user

__all__ = [
    "app", "router_api", "router_fs"
]