from re import T
from fastapi import FastAPI, APIRouter, Depends, Request, Response
from fastapi.exceptions import HTTPException 
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse, JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

import json
from .log import get_logger
from .database import Database, DBUserRecord, DECOY_USER, FileReadPermission, DBConnBase

logger = get_logger("server")
conn = Database()

@asynccontextmanager
async def lifespan(app: FastAPI):
    global conn
    await conn.init()
    yield
    await conn.close()

    logger.finalize()
    DBConnBase.logger.finalize()

async def get_current_user(token: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False))):
    if not token:
        return DECOY_USER
    user = await conn.user.get_user_by_credential(token.credentials)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user

app = FastAPI(docs_url="/", redoc_url=None, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

router_fs = APIRouter(prefix="")

@router_fs.get("/{path:path}")
async def get_file(path: str, asfile = False, user: DBUserRecord = Depends(get_current_user)):
    if path.endswith("/"):
        # return file under the path as json
        if user.id == 0:
            raise HTTPException(status_code=403, detail="Permission denied, credential required")
        if not path.startswith(f"{user.username}/") and not user.is_admin:
            raise HTTPException(status_code=403, detail="Permission denied, path must start with username")
        dirs, files = await conn.file.list_path(path)
        return {
            "dirs": dirs,
            "files": files
        }

    file_record = await conn.file.get_file_record(path)
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")
    
    # permission check
    perm = file_record.permission
    if perm == FileReadPermission.PRIVATE:
        if not user.is_admin and user.id != file_record.owner_id:
            raise HTTPException(status_code=403, detail="Permission denied")
        else:
            assert path.startswith(f"{user.username}/")
    elif perm == FileReadPermission.PROTECTED:
        if user.id == 0:
            raise HTTPException(status_code=403, detail="Permission denied")
    else:
        assert perm == FileReadPermission.PUBLIC
    
    fname = path.split("/")[-1]
    async def send_as(media_type: str = "application/octet-stream", ftype = "attachment"):
        fblob = await conn.read_file(path)
        return Response(
            content=fblob, media_type=media_type, headers={
                "Content-Disposition": f"{ftype}; filename={fname}", 
                "Content-Length": str(len(fblob))
            }
        )
    
    if asfile:
        return await send_as('application/octet-stream')
    
    if not '.' in fname:
        return await send_as('application/octet-stream')
    
    # infer content-type
    blob = await conn.read_file(path)
    suffix = fname.split(".")[-1].lower()
    match suffix:
        case "json":
            try:
                return JSONResponse(content=json.loads(blob))
            except json.JSONDecodeError:
                await send_as('application/octet-stream')
        case "txt" | "log" | "md" | "html" | "htm" | "xml" | "csv" | "tsv" | "yaml" | "yml":
            return await send_as('text/plain', 'inline')
        case "jpg" | "jpeg":
            return await send_as('image/jpeg', 'inline')
        case "png":
            return await send_as('image/png', 'inline')
        case "pdf":
            return await send_as('application/pdf', 'inline')
        case _:
            return await send_as('application/octet-stream')
        

@router_fs.put("/{path:path}")
async def put_file(request: Request, path: str, user: DBUserRecord = Depends(get_current_user)):
    if user.id == 0:
        logger.debug("Reject put request from DECOY_USER")
        raise HTTPException(status_code=403, detail="Permission denied")
    if not path.startswith(f"{user.username}/"):
        logger.debug(f"Reject put request from {user.username} to {path}")
        raise HTTPException(status_code=403, detail="Permission denied")
    
    logger.info(f"PUT {path}, user: {user.username}")
    exists_flag = False
    file_record = await conn.file.get_file_record(path)
    if file_record:
        exists_flag = True
        # remove the old file
        await conn.delete_file(path)
    
    # check content-type
    content_type = request.headers.get("Content-Type")
    logger.debug(f"Content-Type: {content_type}")
    if content_type == "application/json":
        body = await request.json()
        await conn.save_file(user.id, path, json.dumps(body).encode('utf-8'))
    elif content_type == "application/x-www-form-urlencoded":
        # may not work...
        body = await request.form()
        file = body.get("file")
        if isinstance(file, str) or file is None:
            raise HTTPException(status_code=400, detail="Invalid form data, file required")
        await conn.save_file(user.id, path, await file.read())
    elif content_type == "application/octet-stream":
        body = await request.body()
        await conn.save_file(user.id, path, body)
    else:
        body = await request.body()
        await conn.save_file(user.id, path, body)

    # https://developer.mozilla.org/zh-CN/docs/Web/HTTP/Methods/PUT
    if exists_flag:
        return Response(status_code=201)
    else:
        return Response(status_code=200)

@router_fs.delete("/{path:path}")
async def delete_file(path: str, user: DBUserRecord = Depends(get_current_user)):
    if user.id == 0:
        raise HTTPException(status_code=403, detail="Permission denied")
    if not path.startswith(f"{user.username}/"):
        raise HTTPException(status_code=403, detail="Permission denied")
    
    logger.info(f"DELETE {path}, user: {user.username}")
    res = await conn.delete_file(path)
    if res:
        return Response(status_code=200, content="Deleted")
    else:
        return Response(status_code=404, content="Not found")

app.include_router(router_fs)