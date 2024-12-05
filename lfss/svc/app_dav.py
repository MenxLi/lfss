""" WebDAV service """

from fastapi import Request, Response, Depends, HTTPException
from typing import Literal
import xml.etree.ElementTree as ET
from ..eng.connection_pool import unique_cursor
from ..eng.error import *
from ..eng.datatype import UserRecord
from ..eng.database import UserConn, FileConn
from ..eng.utils import ensure_uri_compnents, decode_uri_compnents
from .app_base import *
from .common_impl import get_file_impl, put_file_impl, delete_file_impl


MKDIR_PLACEHOLDER = ".lfss_keep"
ptype = Literal["file", "dir", None]
async def eval_path(path: str) -> tuple[ptype, str, str]:
    """
    Evaluate the type of the path, 
    the return value is a uri-safe string,
    return (ptype, lfss_path, dav_path)

    lfss_path is the path recorded in the database, 
        it should not start with /, 
        and should end with / if it is a directory, otherwise it is a file
    dav_path 
        starts with /, 
        and end with / if it is a directory, otherwise it is a file
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
        dav_path = "/" + path
        async with unique_cursor() as c:
            if await FileConn(c).count_path_files(path, flat=True) == 0:
                return None, lfss_path, dav_path
        return "dir", lfss_path, dav_path

    # not end with /, check if it is a file
    async with unique_cursor() as c:
        res = await FileConn(c).get_file_record(path)
    if res:
        lfss_path = path
        dav_path = "/" + path
        return "file", lfss_path, dav_path
    
    if path == "": return "dir", "", "/"
    async with unique_cursor() as c:
        if await FileConn(c).count_path_files(path + "/") > 0:
            lfss_path = path + "/"
            dav_path = "/" + path + "/"
            return "dir", lfss_path, dav_path
    
    return None, path, "/" + path

async def user_auth(request: Request):
    async with unique_cursor() as c:
        # temporary...
        return await UserConn(c).get_user("limengxun")

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
async def dav_get(request: Request, path: str, user: UserRecord = Depends(user_auth)):
    return await get_file_impl(request, user=user, path=path)

@router_dav.head("/{path:path}")
@handle_exception
async def dav_head(request: Request, path: str, user: UserRecord = Depends(user_auth)):
    return await get_file_impl(request, user=user, path=path, is_head=True)

@router_dav.put("/{path:path}")
@handle_exception
async def dav_put(request: Request, path: str, user: UserRecord = Depends(user_auth)):
    return await put_file_impl(request, user=user, path=path, conflict='overwrite')

@router_dav.delete("/{path:path}")
@handle_exception
async def dav_delete(path: str, user: UserRecord = Depends(user_auth)):
    return await delete_file_impl(user=user, path=path)

@router_dav.api_route("/{path:path}", methods=["PROPFIND"])
@handle_exception
async def dav_propfind(request: Request, path: str, user: UserRecord = Depends(user_auth)):
    if path.startswith("/"): path = path[1:]
    path = ensure_uri_compnents(path)

    depth = request.headers.get("Depth", "infinity")
    # Generate XML response
    multistatus = ET.Element("multistatus", xmlns="DAV:")
    path_type, lfss_path, dav_path = await eval_path(path)
    print(f"PROPFIND {path} (depth: {depth}), type: {path_type}, lfss_path: {lfss_path}, dav_path: {dav_path}")
    if path_type == "dir":
        async with unique_cursor() as c:
            flist = await FileConn(c).list_path_files(lfss_path, flat = True if depth == "infinity" else False)
            furls = [f.url for f in flist]
        for item in furls:
            assert not item.endswith("/")
            item_name = item.split("/")[-1]
            if item_name == MKDIR_PLACEHOLDER: continue
            response = ET.SubElement(multistatus, "response")
            href = ET.SubElement(response, "href")
            href.text = f"/{item}"
            propstat = ET.SubElement(response, "propstat")
            prop = ET.SubElement(propstat, "prop")
            ET.SubElement(prop, "displayname").text = item_name
            ET.SubElement(propstat, "status").text = "HTTP/1.1 200 OK"
            ET.SubElement(prop, "resourcetype")

        async with unique_cursor() as c:
            dlist = await FileConn(c).list_path_dirs(lfss_path)
            durls = [d.url for d in dlist]
        for item in durls:
            assert item.endswith("/")
            response = ET.SubElement(multistatus, "response")
            href = ET.SubElement(response, "href")
            href.text = f"/{item}"
            propstat = ET.SubElement(response, "propstat")
            prop = ET.SubElement(propstat, "prop")
            ET.SubElement(prop, "displayname").text = item[:-1].split("/")[-1]
            ET.SubElement(propstat, "status").text = "HTTP/1.1 200 OK"
            ET.SubElement(prop, "resourcetype").append(ET.Element("collection"))

    elif path_type == "file": 
        print("File found: ", path)
        response = ET.SubElement(multistatus, "response")
        href = ET.SubElement(response, "href")
        href.text = f"{dav_path[:-1]}"
        propstat = ET.SubElement(response, "propstat")
        prop = ET.SubElement(propstat, "prop")
        ET.SubElement(prop, "displayname").text = dav_path.split("/")[-1]
        ET.SubElement(propstat, "status").text = "HTTP/1.1 200 OK"
    
    else:
        raise PathNotFoundError(path)

    xml_response = ET.tostring(multistatus, encoding="utf-8", method="xml")
    print(xml_response.decode())
    return Response(content=xml_response, media_type="application/xml")

@router_dav.api_route("/{path:path}", methods=["MKCOL"])
@handle_exception
async def dav_mkcol(path: str, user: UserRecord = Depends(user_auth)):
    # TODO: implement MKCOL more elegantly
    if path.endswith("/"): path = path[:-1]     # make sure returned path is a file
    ptype, lfss_path, _ = await eval_path(path)
    if not ptype is None:
        raise HTTPException(status_code=409, detail="Conflict")
    fpath = lfss_path + "/" + MKDIR_PLACEHOLDER
    async def _ustream():
        yield b""
    await db.save_file(user.username, fpath, _ustream())
    return Response(status_code=201, media_type="application/xml")

@router_dav.api_route("/{path:path}", methods=["MOVE"])
@handle_exception
async def dav_move(request: Request, path: str, user: UserRecord = Depends(user_auth)):
    destination = request.headers.get("Destination")
    if not destination:
        raise HTTPException(status_code=400, detail="Destination header is required")

    print(f"MOVE {path} -> {destination}")
    ptype, lfss_path, dav_path = await eval_path(path)
    if ptype is None:
        raise PathNotFoundError(path)
    if ptype == "dir" and not dav_path.endswith("/"):
        raise HTTPException(status_code=400, detail="Bad Request")
    dptype, dlfss_path, ddav_path = await eval_path(destination)
    if dptype is not None:
        raise HTTPException(status_code=409, detail="Conflict")

    if ptype == "file":
        assert not lfss_path.endswith("/"), "File path should not end with /"
        assert not dlfss_path.endswith("/"), "File path should not end with /"
        await db.move_file(lfss_path, dlfss_path, user)
    else:
        assert ptype == "dir", "Directory path should end with /"
        assert lfss_path.endswith("/"), "Directory path should end with /"
        assert dlfss_path.endswith("/"), "Directory path should end with /"
        await db.move_path(lfss_path, dlfss_path, user)
    return Response(status_code=201)

@router_dav.api_route("/{path:path}", methods=["COPY"])
@handle_exception
async def dav_copy(request: Request, path: str, user: UserRecord = Depends(user_auth)):
    destination = request.headers.get("Destination")
    if not destination:
        raise HTTPException(status_code=400, detail="Destination header is required")
    # TODO: implement COPY
    print(f"COPY {path} -> {destination}")
    return Response(status_code=501)

@router_dav.api_route("/{path:path}", methods=["LOCK"])
@handle_exception
async def dav_lock(request: Request, path: str, user: UserRecord = Depends(user_auth)):
    print(f"LOCK {path}")
    return Response(status_code=501)

@router_dav.api_route("/{path:path}", methods=["UNLOCK"])
@handle_exception
async def dav_unlock(request: Request, path: str, user: UserRecord = Depends(user_auth)):
    print(f"UNLOCK {path}")
    return Response(status_code=501)
    

__all__ = ["router_dav"]