""" WebDAV service """

from fastapi import Request, Response, Depends, HTTPException
import time, uuid, os
import aiosqlite
from typing import Literal, Optional
import xml.etree.ElementTree as ET
from ..eng.connection_pool import unique_cursor
from ..eng.error import *
from ..eng.config import DATA_HOME
from ..eng.datatype import UserRecord, FileRecord, DirectoryRecord
from ..eng.database import FileConn
from ..eng.utils import ensure_uri_compnents, decode_uri_compnents, format_last_modified
from .app_base import *
from .common_impl import get_file_impl, put_file_impl, delete_file_impl

LOCK_DB_PATH = DATA_HOME / "lock.db"
MKDIR_PLACEHOLDER = ".lfss_keep"
DAV_NS = "DAV:"

# at the beginning of the service, remove the lock database
try: os.remove(LOCK_DB_PATH)
except Exception: ...

ET.register_namespace("d", DAV_NS)  # Register the default namespace
ptype = Literal["file", "dir", None]
async def eval_path(path: str) -> tuple[ptype, str, Optional[FileRecord | DirectoryRecord]]:
    """
    Evaluate the type of the path, 
    the return value is a uri-safe string,
    return (ptype, lfss_path, record)

    lfss_path is the path recorded in the database, 
        it should not start with /, 
        and should end with / if it is a directory, otherwise it is a file
    record is the FileRecord or DirectoryRecord object, it is None if the path does not exist
    """
    path = decode_uri_compnents(path)
    if "://" in path:
        if not path.startswith("http://") and not path.startswith("https://"):
            raise HTTPException(status_code=400, detail="Bad Request, unsupported protocol")
        # pop the protocol part, host part, and port part
        path = path.split("/", 3)[-1]
        route_prefix = router_dav.prefix
        if route_prefix.startswith("/"): route_prefix = route_prefix[1:]
        assert path.startswith(route_prefix), "Path should start with the route prefix, got: " + path
        path = path[len(route_prefix):]

    path = ensure_uri_compnents(path)
    if path.startswith("/"): path = path[1:]

    # path now is url-safe and without leading slash
    if path.endswith("/"):
        lfss_path = path
        async with unique_cursor() as c:
            fconn = FileConn(c)
            if await fconn.count_path_files(path, flat=True) == 0:
                return None, lfss_path, None
            return "dir", lfss_path, await fconn.get_path_record(path)

    # not end with /, check if it is a file
    async with unique_cursor() as c:
        res = await FileConn(c).get_file_record(path)
        if res:
            lfss_path = path
            return "file", lfss_path, res
    
    if path == "": return "dir", "", DirectoryRecord("")
    async with unique_cursor() as c:
        fconn = FileConn(c)
        if await fconn.count_path_files(path + "/") > 0:
            lfss_path = path + "/"
            return "dir", lfss_path, await fconn.get_path_record(lfss_path)
    
    return None, path, None

lock_table_create_sql = """
CREATE TABLE IF NOT EXISTS locks (
    path TEXT PRIMARY KEY,
    user TEXT,
    token TEXT,
    timeout float,
    lock_time float
);
"""
async def lock_path(user: UserRecord, p: str, token: str, timeout: int = 600):
    async with aiosqlite.connect(LOCK_DB_PATH) as conn:
        await conn.execute(lock_table_create_sql)
        async with conn.execute("SELECT user, timeout, lock_time FROM locks WHERE path=?", (p,)) as cur:
            row = await cur.fetchone()
            if row:
                user_, timeout_, lock_time_ = row
                curr_time = time.time()
                if timeout > 0 and curr_time - lock_time_ < timeout_:
                    raise FileLockedError(f"File is locked (by {user_}) [{p}]")
            await cur.execute("INSERT OR REPLACE INTO locks VALUES (?, ?, ?, ?, ?)", (p, user.username, token, timeout, time.time()))
            await conn.commit()
async def unlock_path(user: UserRecord, p: str, token: str):
    async with aiosqlite.connect(LOCK_DB_PATH) as conn:
        await conn.execute(lock_table_create_sql)
        async with conn.execute("SELECT user, token FROM locks WHERE path=?", (p,)) as cur:
            row = await cur.fetchone()
            if not row: return
            user_, token_ = row
            if user_ != user.username or token_ != token:
                raise FileLockedError(f"Failed to unlock file [{p}] with token {token}")
            await cur.execute("DELETE FROM locks WHERE path=?", (p,))
            await conn.commit()
async def query_lock_el(p: str, top_el_name: str = f"{{{DAV_NS}}}lockinfo") -> Optional[ET.Element]:
    async with aiosqlite.connect(LOCK_DB_PATH) as conn:
        await conn.execute(lock_table_create_sql)
        async with conn.execute("SELECT user, token, timeout, lock_time FROM locks WHERE path=?", (p,)) as cur:
            row = await cur.fetchone()
            if not row: return None
            curr_time = time.time()
            user_, token, timeout, lock_time = row
            if timeout > 0 and curr_time - lock_time > timeout:
                await cur.execute("DELETE FROM locks WHERE path=?", (p,))
                await conn.commit()
                return None
            lock_info = ET.Element(top_el_name)
            locktype = ET.SubElement(lock_info, f"{{{DAV_NS}}}locktype")
            ET.SubElement(locktype, f"{{{DAV_NS}}}write")
            lockscope = ET.SubElement(lock_info, f"{{{DAV_NS}}}lockscope")
            ET.SubElement(lockscope, f"{{{DAV_NS}}}exclusive")
            owner = ET.SubElement(lock_info, f"{{{DAV_NS}}}owner")
            owner.text = user_
            timeout = ET.SubElement(lock_info, f"{{{DAV_NS}}}timeout")
            timeout.text = f"Second-{timeout}"
            locktoken = ET.SubElement(lock_info, f"{{{DAV_NS}}}locktoken")
            href = ET.SubElement(locktoken, f"{{{DAV_NS}}}href")
            href.text = f"{token}"
            return lock_info

async def create_file_xml_element(frecord: FileRecord) -> ET.Element:
    file_el = ET.Element(f"{{{DAV_NS}}}response")
    href = ET.SubElement(file_el, f"{{{DAV_NS}}}href")
    href.text = f"/{frecord.url}"
    propstat = ET.SubElement(file_el, f"{{{DAV_NS}}}propstat")
    prop = ET.SubElement(propstat, f"{{{DAV_NS}}}prop")
    ET.SubElement(prop, f"{{{DAV_NS}}}displayname").text = frecord.url.split("/")[-1]
    ET.SubElement(prop, f"{{{DAV_NS}}}resourcetype")
    ET.SubElement(prop, f"{{{DAV_NS}}}getcontentlength").text = str(frecord.file_size)
    ET.SubElement(prop, f"{{{DAV_NS}}}getlastmodified").text = format_last_modified(frecord.create_time)
    ET.SubElement(prop, f"{{{DAV_NS}}}getcontenttype").text = frecord.mime_type
    lock_discovery = ET.SubElement(prop, f"{{{DAV_NS}}}lockdiscovery")
    lock_el = await query_lock_el(frecord.url, top_el_name=f"{{{DAV_NS}}}activelock")
    if lock_el is not None:
        lock_discovery.append(lock_el)
    return file_el

async def create_dir_xml_element(drecord: DirectoryRecord) -> ET.Element:
    dir_el = ET.Element(f"{{{DAV_NS}}}response")
    href = ET.SubElement(dir_el, f"{{{DAV_NS}}}href")
    href.text = f"/{drecord.url}"
    propstat = ET.SubElement(dir_el, f"{{{DAV_NS}}}propstat")
    prop = ET.SubElement(propstat, f"{{{DAV_NS}}}prop")
    ET.SubElement(prop, f"{{{DAV_NS}}}displayname").text = drecord.url.split("/")[-2]
    ET.SubElement(prop, f"{{{DAV_NS}}}resourcetype").append(ET.Element(f"{{{DAV_NS}}}collection"))
    if drecord.size >= 0:
        ET.SubElement(prop, f"{{{DAV_NS}}}getlastmodified").text = format_last_modified(drecord.create_time)
        ET.SubElement(prop, f"{{{DAV_NS}}}getcontentlength").text = str(drecord.size)
    lock_discovery = ET.SubElement(prop, f"{{{DAV_NS}}}lockdiscovery")
    lock_el = await query_lock_el(drecord.url, top_el_name=f"{{{DAV_NS}}}activelock")
    if lock_el is not None:
        lock_discovery.append(lock_el)
    return dir_el

async def xml_request_body(request: Request) -> Optional[ET.Element]:
    try:
        assert request.headers.get("Content-Type") == "application/xml"
        body = await request.body()
        return ET.fromstring(body)
    except Exception as e:
        return None

@router_dav.options("/{path:path}")
async def dav_options(request: Request, path: str):
    return Response(headers={
        "DAV": "1,2",
        "MS-Author-Via": "DAV",
        "Allow": "OPTIONS, GET, HEAD, POST, DELETE, TRACE, PROPFIND, PROPPATCH, COPY, MOVE, LOCK, UNLOCK",
        "Content-Length": "0"
    })

@router_dav.get("/{path:path}")
@handle_exception
async def dav_get(request: Request, path: str, user: UserRecord = Depends(registered_user)):
    ptype, path, _ = await eval_path(path)
    if ptype is None: raise PathNotFoundError(path)
    elif ptype == "dir": raise InvalidOptionsError("Directory should not be fetched")
    else: return await get_file_impl(request, user=user, path=path)

@router_dav.head("/{path:path}")
@handle_exception
async def dav_head(request: Request, path: str, user: UserRecord = Depends(registered_user)):
    ptype, path, _ = await eval_path(path)
    # some clients may send HEAD request to check if the file exists
    if ptype is None: raise PathNotFoundError(path)
    elif ptype == "dir": return Response(status_code=200)
    else: return await get_file_impl(request, user=user, path=path, is_head=True)

@router_dav.put("/{path:path}")
@handle_exception
async def dav_put(request: Request, path: str, user: UserRecord = Depends(registered_user)):
    _, path, _ = await eval_path(path)
    return await put_file_impl(request, user=user, path=path, conflict='overwrite')

@router_dav.delete("/{path:path}")
@handle_exception
async def dav_delete(path: str, user: UserRecord = Depends(registered_user)):
    _, path, _ = await eval_path(path)
    return await delete_file_impl(user=user, path=path)

@router_dav.api_route("/{path:path}", methods=["PROPFIND"])
@handle_exception
async def dav_propfind(request: Request, path: str, user: UserRecord = Depends(registered_user)):
    if path.startswith("/"): path = path[1:]
    path = ensure_uri_compnents(path)

    depth = request.headers.get("Depth", "1")
    # Generate XML response
    multistatus = ET.Element(f"{{{DAV_NS}}}multistatus")
    path_type, lfss_path, record = await eval_path(path)
    logger.info(f"PROPFIND {lfss_path} (depth: {depth})")
    return_status = 200
    if path_type == "dir" and depth == "0":
        # query the directory itself
        return_status = 200
        assert isinstance(record, DirectoryRecord)
        dir_el = await create_dir_xml_element(record)
        multistatus.append(dir_el)

    elif path_type == "dir":
        return_status = 207
        async with unique_cursor() as c:
            flist = await FileConn(c).list_path_files(lfss_path, flat = True if depth == "infinity" else False)
        for frecord in flist:
            if frecord.url.split("/")[-1] == MKDIR_PLACEHOLDER: continue
            file_el = await create_file_xml_element(frecord)
            multistatus.append(file_el)

        async with unique_cursor() as c:
            drecords = await FileConn(c).list_path_dirs(lfss_path)
        for drecord in drecords:
            dir_el = await create_dir_xml_element(drecord)
            multistatus.append(dir_el)

    elif path_type == "file": 
        assert isinstance(record, FileRecord)
        file_el = await create_file_xml_element(record)
        multistatus.append(file_el)
    
    else:
        raise PathNotFoundError(path)

    xml_response = ET.tostring(multistatus, encoding="utf-8", method="xml")
    return Response(content=xml_response, media_type="application/xml", status_code=return_status)

@router_dav.api_route("/{path:path}", methods=["MKCOL"])
@handle_exception
async def dav_mkcol(path: str, user: UserRecord = Depends(registered_user)):
    # TODO: implement MKCOL more elegantly
    if path.endswith("/"): path = path[:-1]     # make sure returned path is a file
    ptype, lfss_path, _ = await eval_path(path)
    if not ptype is None:
        raise HTTPException(status_code=409, detail="Conflict")
    logger.info(f"MKCOL {path}")
    fpath = lfss_path + "/" + MKDIR_PLACEHOLDER
    async def _ustream():
        yield b""
    await db.save_file(user.username, fpath, _ustream())
    return Response(status_code=201)

@router_dav.api_route("/{path:path}", methods=["MOVE"])
@handle_exception
async def dav_move(request: Request, path: str, user: UserRecord = Depends(registered_user)):
    destination = request.headers.get("Destination")
    if not destination:
        raise HTTPException(status_code=400, detail="Destination header is required")

    ptype, lfss_path, _ = await eval_path(path)
    if ptype is None:
        raise PathNotFoundError(path)
    dptype, dlfss_path, ddav_path = await eval_path(destination)
    if dptype is not None:
        raise HTTPException(status_code=409, detail="Conflict")

    logger.info(f"MOVE {path} -> {destination}")
    if ptype == "file":
        assert not lfss_path.endswith("/"), "File path should not end with /"
        assert not dlfss_path.endswith("/"), "File path should not end with /"
        await db.move_file(lfss_path, dlfss_path, user)
    else:
        assert ptype == "dir", "Directory path should end with /"
        assert lfss_path.endswith("/"), "Directory path should end with /"
        if not dlfss_path.endswith("/"): dlfss_path += "/"  # the header destination may not end with /
        await db.move_path(lfss_path, dlfss_path, user)
    return Response(status_code=201)

@router_dav.api_route("/{path:path}", methods=["COPY"])
@handle_exception
async def dav_copy(request: Request, path: str, user: UserRecord = Depends(registered_user)):
    destination = request.headers.get("Destination")
    if not destination:
        raise HTTPException(status_code=400, detail="Destination header is required")

    ptype, lfss_path, _ = await eval_path(path)
    if ptype is None:
        raise PathNotFoundError(path)
    dptype, dlfss_path, ddav_path = await eval_path(destination)
    if dptype is not None:
        raise HTTPException(status_code=409, detail="Conflict")
    
    logger.info(f"COPY {path} -> {destination}")
    if ptype == "file":
        assert not lfss_path.endswith("/"), "File path should not end with /"
        assert not dlfss_path.endswith("/"), "File path should not end with /"
        await db.copy_file(lfss_path, dlfss_path, user)
    else:
        assert ptype == "dir", "Directory path should end with /"
        assert lfss_path.endswith("/"), "Directory path should end with /"
        assert dlfss_path.endswith("/"), "Directory path should end with /"
        await db.copy_path(lfss_path, dlfss_path, user)
    return Response(status_code=201)

@router_dav.api_route("/{path:path}", methods=["LOCK"])
@handle_exception
async def dav_lock(request: Request, path: str, user: UserRecord = Depends(registered_user)):
    raw_timeout = request.headers.get("Timeout", "Second-3600")
    if raw_timeout == "Infinite": timeout = -1
    else:
        if not raw_timeout.startswith("Second-"): 
            raise HTTPException(status_code=400, detail="Bad Request, invalid timeout: " + raw_timeout + ", expected Second-<seconds> or Infinite")
        _, timeout_str = raw_timeout.split("-")
        timeout = int(timeout_str)

    _, path, _ = await eval_path(path)
    # lock_token = f"opaquelocktoken:{uuid.uuid4().hex}"
    lock_token = f"urn:uuid:{uuid.uuid4()}"
    logger.info(f"LOCK {path} (timeout: {timeout}), token: {lock_token}")
    await lock_path(user, path, lock_token, timeout=timeout)
    response_elem = ET.Element(f"{{{DAV_NS}}}prop")
    lockdiscovery = ET.SubElement(response_elem, f"{{{DAV_NS}}}lockdiscovery")
    activelock = await query_lock_el(path, top_el_name=f"{{{DAV_NS}}}activelock")
    assert activelock is not None, "Lock info should not be None"
    lockdiscovery.append(activelock)
    lock_response = ET.tostring(response_elem, encoding="utf-8", method="xml")
    return Response(content=lock_response, media_type="application/xml", status_code=201, headers={
        "Lock-Token": f"<{lock_token}>"
    })

@router_dav.api_route("/{path:path}", methods=["UNLOCK"])
@handle_exception
async def dav_unlock(request: Request, path: str, user: UserRecord = Depends(registered_user)):
    lock_token = request.headers.get("Lock-Token")
    if not lock_token:
        raise HTTPException(status_code=400, detail="Lock-Token header is required")
    if lock_token.startswith("<") and lock_token.endswith(">"):
        lock_token = lock_token[1:-1]
    logger.info(f"UNLOCK {path}, token: {lock_token}")
    _, path, _ = await eval_path(path)
    await unlock_path(user, path, lock_token)
    return Response(status_code=204)

@router_dav.api_route("/{path:path}", methods=["PROPPATCH"])
@handle_exception
async def dav_proppatch(request: Request, path: str, user: UserRecord = Depends(registered_user), body: ET.Element = Depends(xml_request_body)):
    # TODO: implement PROPPATCH
    print("PROPPATCH", path, body)
    multistatus = ET.Element(f"{{{DAV_NS}}}multistatus")
    return Response(content=ET.tostring(multistatus, encoding="utf-8", method="xml"), media_type="application/xml", status_code=207)

__all__ = ["router_dav"]