import json
from dataclasses import dataclass
from typing import Optional
from contextlib import asynccontextmanager
import aiosqlite

from .log import get_logger
from .datatype import DirConfig
from .connection_pool import unique_cursor
from .database_conn import FileConn
from .utils import ensure_uri_components
from .config import DIR_CONFIG_FNAME

async def load_dir_config(path: str, cur: Optional[aiosqlite.Cursor] = None) -> DirConfig:
    @asynccontextmanager
    async def this_cur():
        if cur is None:
            async with unique_cursor() as _cur:
                yield _cur
        else:
            yield cur

    async def load_config(pth: str, cur: aiosqlite.Cursor):
        assert pth.endswith('/'), "Path must be a directory"
        cfg_file = ensure_uri_components(pth + DIR_CONFIG_FNAME)

        config = DirConfig()
        fconn = FileConn(cur)
        dir_config_file = await fconn.get_file_record(cfg_file, throw=False)
        if dir_config_file is None:
            return config
        
        # load json
        if dir_config_file.external:
            blob_iter = fconn.get_file_blob_external(dir_config_file.file_id)
            blob = b''.join([chunk async for chunk in blob_iter])
        else:
            blob = await fconn.get_file_blob(dir_config_file.file_id)
        config = DirConfig.from_json(json.loads(blob.decode('utf-8')))
        return config

    # main logic
    try:
        if path.endswith('/'):
            async with this_cur() as cur:
                return await load_config(path, cur)
        else:
            parent_path = path.rsplit('/', 1)[0] + '/'
            async with this_cur() as cur:
                return await load_config(parent_path, cur)

    except Exception as e:
        get_logger('database', global_instance=True).warning(f"Failed to load directory config for {path}: {e}")
    return DirConfig()
