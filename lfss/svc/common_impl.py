import json
from fastapi import Request, Response, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from typing import Optional, Literal
from ..eng.connection_pool import unique_cursor
from ..eng.datatype import UserRecord, FileRecord, PathContents, AccessLevel, FileReadPermission
from ..eng.database import FileConn, UserConn, delayed_log_access, check_file_read_permission, check_path_permission
from ..eng.thumb import get_thumb
from ..eng.utils import format_last_modified, ensure_uri_compnents
from ..eng.config import CHUNK_SIZE

from .app_base import skip_request_log, db, logger

@skip_request_log
async def emit_thumbnail(
    path: str, download: bool,
    create_time: Optional[str] = None, 
    is_head = False
    ):
    if path.endswith("/"):
        fname = path.split("/")[-2]
    else:
        fname = path.split("/")[-1]
    if (thumb_res := await get_thumb(path)) is None:
        return Response(status_code=415, content="Thumbnail not supported")
    thumb_blob, mime_type = thumb_res
    disp = "inline" if not download else "attachment"
    headers = {
        "Content-Disposition": f"{disp}; filename={fname}.thumb.jpg",
        "Content-Length": str(len(thumb_blob)),
    }
    if create_time is not None:
        headers["Last-Modified"] = format_last_modified(create_time)
    if is_head: return Response(status_code=200, headers=headers)
    return Response(
        content=thumb_blob, media_type=mime_type, headers=headers
    )
async def emit_file(
    file_record: FileRecord, 
    media_type: Optional[str] = None, 
    disposition = "attachment", 
    is_head = False, 
    range_start = -1,
    range_end = -1
    ):
    if range_start < 0: assert range_start == -1
    if range_end < 0: assert range_end == -1

    if media_type is None:
        media_type = file_record.mime_type
    path = file_record.url
    fname = path.split("/")[-1]

    if range_start == -1:
        arng_s = 0          # actual range start
    else:
        arng_s = range_start
    if range_end == -1:
        arng_e = file_record.file_size - 1
    else:
        arng_e = range_end
    
    if arng_s >= file_record.file_size or arng_e >= file_record.file_size:
        raise HTTPException(status_code=416, detail="Range not satisfiable")
    if arng_s > arng_e:
        raise HTTPException(status_code=416, detail="Invalid range")

    headers = {
        "Content-Disposition": f"{disposition}; filename={fname}", 
        "Content-Length": str(arng_e - arng_s + 1),
        "Content-Range": f"bytes {arng_s}-{arng_e}/{file_record.file_size}",
        "Last-Modified": format_last_modified(file_record.create_time), 
        "Accept-Ranges": "bytes", 
    }

    if is_head: return Response(status_code=200 if (range_start == -1 and range_end == -1) else 206, headers=headers)

    await delayed_log_access(path)
    return StreamingResponse(
        await db.read_file(
            path, 
            start_byte=arng_s if range_start != -1 else -1,
            end_byte=arng_e + 1 if range_end != -1 else -1
        ),
        media_type=media_type, 
        headers=headers, 
        status_code=206 if range_start != -1 or range_end != -1 else 200
    )

async def get_file_impl(
    request: Request,
    user: UserRecord, 
    path: str, 
    download: bool = False, 
    thumb: bool = False,
    is_head = False,
    ):
    path = ensure_uri_compnents(path)

    # handle directory query
    if path == "": path = "/"
    if path.endswith("/"):
        # return file under the path as json
        async with unique_cursor() as cur:
            fconn = FileConn(cur)
            if user.id == 0:
                raise HTTPException(status_code=401, detail="Permission denied, credential required")
            if thumb:
                return await emit_thumbnail(path, download, create_time=None)
            
            if path == "/":
                peer_users = await UserConn(cur).list_peer_users(user.id, AccessLevel.READ)
                return PathContents(
                    dirs = await fconn.list_root_dirs(user.username, *[x.username for x in peer_users], skim=True) \
                        if not user.is_admin else await fconn.list_root_dirs(skim=True),
                    files = []
                )

            if not await check_path_permission(path, user, cursor=cur) >= AccessLevel.READ:
                raise HTTPException(status_code=403, detail="Permission denied")

            return await fconn.list_path(path)
    
    # handle file query
    async with unique_cursor() as cur:
        fconn = FileConn(cur)
        file_record = await fconn.get_file_record(path, throw=True)
        uconn = UserConn(cur)
        owner = await uconn.get_user_by_id(file_record.owner_id, throw=True)

        if not await check_path_permission(path, user, cursor=cur) >= AccessLevel.READ:
            allow_access, reason = check_file_read_permission(user, owner, file_record)
            if not allow_access:
                raise HTTPException(status_code=403 if user.id != 0 else 401, detail=reason)
    
    req_range = request.headers.get("Range", None)
    if not req_range is None:
        # handle range request
        if not req_range.startswith("bytes="):
            raise HTTPException(status_code=400, detail="Invalid range request")
        range_str = req_range[6:].strip()
        if "," in range_str:
            raise HTTPException(status_code=400, detail="Multiple ranges not supported")
        if "-" not in range_str:
            raise HTTPException(status_code=400, detail="Invalid range request")
        range_start, range_end = map(lambda x: int(x) if x != "" else -1 , range_str.split("-"))
    else:
        range_start, range_end = -1, -1
    
    if thumb:
        if (range_start != -1 or range_end != -1): logger.warning("Range request for thumbnail")
        return await emit_thumbnail(path, download, create_time=file_record.create_time, is_head=is_head)
    else:
        if download:
            return await emit_file(file_record, 'application/octet-stream', "attachment", is_head = is_head, range_start=range_start, range_end=range_end)
        else:
            return await emit_file(file_record, None, "inline", is_head = is_head, range_start=range_start, range_end=range_end)

async def put_file_impl(
    request: Request, 
    user: UserRecord, 
    path: str, 
    conflict: Literal["overwrite", "skip", "abort"] = "abort",
    permission: int = 0,
    ):
    path = ensure_uri_compnents(path)
    assert not path.endswith("/"), "Path must not end with /"

    access_level = await check_path_permission(path, user)
    if access_level < AccessLevel.WRITE:
        logger.debug(f"Reject put request from {user.username} to {path}")
        raise HTTPException(status_code=403, detail="Permission denied")
    
    logger.info(f"PUT {path}, user: {user.username}")
    exists_flag = False
    async with unique_cursor() as conn:
        fconn = FileConn(conn)
        file_record = await fconn.get_file_record(path)

    if file_record:
        if conflict == "abort":
            raise HTTPException(status_code=409, detail="File exists")
        if conflict == "skip":
            return Response(status_code=200, headers={
                "Content-Type": "application/json",
            }, content=json.dumps({"url": path}))
        exists_flag = True
        if await check_path_permission(path, user) < AccessLevel.WRITE:
            raise HTTPException(status_code=403, detail="Permission denied, cannot overwrite other's file")
        await db.delete_file(path)
    
    # check content-type
    content_type = request.headers.get("Content-Type", "application/octet-stream")
    logger.debug(f"Content-Type: {content_type}")
    if not (content_type == "application/octet-stream" or content_type == "application/json"):
        # raise HTTPException(status_code=415, detail="Unsupported content type, put request must be application/json or application/octet-stream, got " + content_type)
        logger.warning(f"Unsupported content type, put request must be application/json or application/octet-stream, got {content_type}")
    
    async def blob_reader():
        nonlocal request
        async for chunk in request.stream():
            yield chunk

    await db.save_file(user.id, path, blob_reader(), permission = FileReadPermission(permission))

    # https://developer.mozilla.org/zh-CN/docs/Web/HTTP/Methods/PUT
    return Response(status_code=200 if exists_flag else 201, headers={
        "Content-Type": "application/json",
    }, content=json.dumps({"url": path}))


async def post_file_impl(
    path: str, 
    user: UserRecord, 
    file: UploadFile,
    conflict: Literal["overwrite", "skip", "abort"] = "abort",
    permission: int = 0,
):
    path = ensure_uri_compnents(path)
    assert not path.endswith("/"), "Path must not end with /"

    access_level = await check_path_permission(path, user)
    if access_level < AccessLevel.WRITE:
        logger.debug(f"Reject post request from {user.username} to {path}")
        raise HTTPException(status_code=403, detail="Permission denied")

    logger.info(f"POST {path}, user: {user.username}")
    exists_flag = False
    async with unique_cursor() as conn:
        fconn = FileConn(conn)
        file_record = await fconn.get_file_record(path)

    if file_record:
        if conflict == "abort":
            raise HTTPException(status_code=409, detail="File exists")
        if conflict == "skip":
            return Response(status_code=200, headers={
                "Content-Type": "application/json",
            }, content=json.dumps({"url": path}))
        exists_flag = True
        if await check_path_permission(path, user) < AccessLevel.WRITE: 
            raise HTTPException(status_code=403, detail="Permission denied, cannot overwrite other's file")
        await db.delete_file(path)
    
    async def blob_reader():
        nonlocal file
        while (chunk := await file.read(CHUNK_SIZE)):
            yield chunk

    await db.save_file(user.id, path, blob_reader(), permission = FileReadPermission(permission))
    return Response(status_code=200 if exists_flag else 201, headers={
        "Content-Type": "application/json",
    }, content=json.dumps({"url": path}))

async def delete_impl(path: str, user: UserRecord):
    path = ensure_uri_compnents(path)
    if await check_path_permission(path, user) < AccessLevel.WRITE:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    logger.info(f"DELETE {path}, user: {user.username}")

    if path.endswith("/"):
        res = await db.delete_path(path, user)
    else:
        res = await db.delete_file(path, user)

    if res:
        return Response(status_code=200, content="Deleted")
    else:
        return Response(status_code=404, content="Not found")

async def copy_impl(
    op_user: UserRecord, src_path: str, dst_path: str,
):
    src_path = ensure_uri_compnents(src_path)
    dst_path = ensure_uri_compnents(dst_path)
    copy_type = "file" if not src_path[-1] == "/" else "directory"
    if not src_path[-1] == dst_path[-1]:
        raise HTTPException(status_code=400, detail="Source and destination must be same type")

    if src_path == dst_path:
        raise HTTPException(status_code=400, detail="Source and destination are the same")
    
    logger.info(f"Copy {src_path} to {dst_path}, user: {op_user.username}")
    if copy_type == "file":
        async with unique_cursor() as cur:
            fconn = FileConn(cur)
            dst_record = fconn.get_file_record(dst_path)
        if dst_record:
            raise HTTPException(status_code=409, detail="Destination exists")
        await db.copy_file(src_path, dst_path, op_user)
    else:
        async with unique_cursor() as cur:
            fconn = FileConn(cur)
            dst_fcount = await fconn.count_path_files(dst_path, flat=True)
        if dst_fcount > 0:
            raise HTTPException(status_code=409, detail="Destination exists")
        await db.copy_path(src_path, dst_path, op_user)
    return Response(status_code=201, content="OK")