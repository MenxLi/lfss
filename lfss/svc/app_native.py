from typing import Optional, Literal, Annotated
from collections import OrderedDict

from fastapi import Depends, Request, Response, UploadFile, Query
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.exceptions import HTTPException 

from ..eng.utils import ensure_uri_compnents
from ..eng.config import MAX_MEM_FILE_BYTES
from ..eng.connection_pool import unique_cursor
from ..eng.database import check_file_read_permission, check_path_permission, FileConn, delayed_log_access
from ..eng.datatype import (
    FileReadPermission, UserRecord, AccessLevel, 
    FileSortKey, DirSortKey
)
from ..eng.error import InvalidPathError

from .app_base import *
from .common_impl import get_impl, put_file_impl, post_file_impl, delete_impl, copy_impl

@router_fs.get("/{path:path}")
@handle_exception
async def get_file(
    request: Request,
    path: str, 
    download: bool = False, thumb: bool = False,
    user: UserRecord = Depends(get_current_user)
    ):
    return await get_impl(
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
    return await get_impl(
        request = request,
        user = user, path = path, download = download, thumb = thumb, is_head = True
        )

@router_fs.put("/{path:path}")
@handle_exception
async def put_file(
    request: Request, 
    path: str, 
    conflict: Literal["overwrite", "skip", "abort"] = "overwrite",
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
    conflict: Literal["overwrite", "skip", "abort"] = "overwrite",
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
    if not path.endswith("/"):
        raise HTTPException(status_code=400, detail="Path must end with /")
    if path[0] == "/":      # adapt to both /path and path
        path = path[1:]
    if path == "":
        raise HTTPException(status_code=400, detail="Cannot bundle root")
    
    async with unique_cursor() as cur:
        dir_record = await FileConn(cur).get_dir_record(path)

    pathname = f"{path.split('/')[-2]}"

    if dir_record.size < MAX_MEM_FILE_BYTES:
        logger.debug(f"Bundle {path} in memory")
        dir_bytes = (await db.zip_dir(path, op_user=user)).getvalue()
        return Response(
            content = dir_bytes,
            media_type = "application/zip",
            headers = {
                f"Content-Disposition": f"attachment; filename=bundle-{pathname}.zip",
                "Content-Length": str(len(dir_bytes)),
                "X-Content-Bytes": str(dir_record.size),
            }
        )
    else:
        logger.debug(f"Bundle {path} in stream")
        return StreamingResponse(
            content = await db.zip_dir_stream(path, op_user=user),
            media_type = "application/zip",
            headers = {
                f"Content-Disposition": f"attachment; filename=bundle-{pathname}.zip",
                "X-Content-Bytes": str(dir_record.size),
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
                is_allowed, reason = await check_file_read_permission(user, record, cursor=cur)
                if not is_allowed:
                    raise HTTPException(status_code=403, detail=reason)
        else:
            if await check_path_permission(path, user, cursor=cur) < AccessLevel.READ:
                raise HTTPException(status_code=403, detail="Permission denied")
            record = await fconn.get_dir_record(path)
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
            # will raise duplicate path error if same name path exists in the new path
            await db.move_dir(path, new_path, user)

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
@handle_exception
async def count_files(path: str, flat: bool = False, user: UserRecord = Depends(registered_user)):
    await validate_path_read_permission(path, user)
    path = ensure_uri_compnents(path)
    async with unique_cursor() as conn:
        fconn = FileConn(conn)
        return { "count": await fconn.count_dir_files(url = path, flat = flat) }
@router_api.get("/list-files")
@handle_exception
async def list_files(
    path: str, offset: int = 0, limit: int = 1000,
    order_by: FileSortKey = "", order_desc: bool = False,
    flat: bool = False, user: UserRecord = Depends(registered_user)
    ):
    await validate_path_read_permission(path, user)
    path = ensure_uri_compnents(path)
    async with unique_cursor() as conn:
        fconn = FileConn(conn)
        return await fconn.list_dir_files(
            url = path, offset = offset, limit = limit,
            order_by=order_by, order_desc=order_desc, 
            flat=flat
        )

@router_api.get("/count-dirs")
@handle_exception
async def count_dirs(path: str, user: UserRecord = Depends(registered_user)):
    await validate_path_read_permission(path, user)
    path = ensure_uri_compnents(path)
    async with unique_cursor() as conn:
        fconn = FileConn(conn)
        return { "count": await fconn.count_path_dirs(url = path) }
@router_api.get("/list-dirs")
@handle_exception
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

# https://fastapi.tiangolo.com/tutorial/query-params-str-validations/#query-parameter-list-multiple-values
@router_api.get("/get-multiple")
@handle_exception
async def get_multiple_files(
    path: Annotated[list[str], Query()], 
    skip_content: bool = False,
    user: UserRecord = Depends(registered_user)
    ):
    """
    Get multiple files by path. 
    Please note that the content is supposed to be text and are small enough to fit in memory.

    Not existing files will have content null, and the response will be 206 Partial Content if not all files are found.
    if skip_content is True, the content of the files will always be ''
    """
    for p in path:
        if p.endswith("/"):
            raise InvalidPathError(f"Path '{p}' must not end with /")

    # here we unify the path, so need to keep a record of the inputs
    # make output keys consistent with inputs
    upath2path = OrderedDict[str, str]()
    for p in path:
        p_ = p if not p.startswith("/") else p[1:]
        upath2path[ensure_uri_compnents(p_)] = p
    upaths = list(upath2path.keys())

    # get files
    raw_res = await db.read_files_bulk(upaths, skip_content=skip_content, op_user=user)
    for k in raw_res.keys():
        await delayed_log_access(k)
    partial_content = len(raw_res) != len(upaths)

    return JSONResponse(
        content = {
            upath2path[k]: v.decode('utf-8') if v is not None else None for k, v in raw_res.items()
        },
        status_code = 206 if partial_content else 200
    )
    
    
@router_api.get("/whoami")
@handle_exception
async def whoami(user: UserRecord = Depends(registered_user)):
    user.credential = "__HIDDEN__"
    return user

__all__ = [
    "app", "router_api", "router_fs"
]