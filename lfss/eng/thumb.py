from lfss.eng.config import THUMB_DB, THUMB_SIZE
from lfss.eng.database import FileConn
from lfss.eng.error import *
from lfss.eng.connection_pool import unique_cursor
from typing import Optional
from PIL import Image
from io import BytesIO
import aiosqlite
from contextlib import asynccontextmanager

async def _maybe_init_thumb(c: aiosqlite.Cursor):
    await c.execute('''
        CREATE TABLE IF NOT EXISTS thumbs (
            file_id CHAR(32) PRIMARY KEY,
            thumb BLOB
        )
    ''')
    await c.execute('CREATE INDEX IF NOT EXISTS thumbs_path_idx ON thumbs (file_id)')

async def _get_cache_thumb(c: aiosqlite.Cursor, file_id: str) -> Optional[bytes]:
    res = await c.execute('''
        SELECT thumb FROM thumbs WHERE file_id = ? 
    ''', (file_id, ))
    row = await res.fetchone()
    if row is None:
        return None
    blob: bytes = row[0]
    return blob
    
async def _save_cache_thumb(c: aiosqlite.Cursor, file_id: str, raw_bytes: bytes) -> bytes:
    try:
        raw_img = Image.open(BytesIO(raw_bytes))
    except Exception:
        raise InvalidDataError('Invalid image data for thumbnail: ' + file_id)
    raw_img.thumbnail(THUMB_SIZE)
    img = raw_img.convert('RGB')
    bio = BytesIO()
    img.save(bio, 'JPEG')
    blob = bio.getvalue()
    await c.execute('''
        INSERT OR REPLACE INTO thumbs (file_id, thumb) VALUES (?, ?)
    ''', (file_id, blob))
    await c.execute('COMMIT')  # commit immediately
    return blob

async def _delete_cache_thumb(c: aiosqlite.Cursor, file_id: str):
    await c.execute('''
        DELETE FROM thumbs WHERE file_id = ?
    ''', (file_id, ))
    await c.execute('COMMIT')

@asynccontextmanager
async def cache_cursor():
    async with aiosqlite.connect(THUMB_DB) as conn:
        cur = await conn.cursor()
        await _maybe_init_thumb(cur)
        yield cur

async def get_thumb(path: str) -> Optional[tuple[bytes, str]]:
    """
    returns [image bytes of thumbnail, mime type] if supported, 
    or None if not supported. 
    Raises FileNotFoundError if file does not exist
    """
    if path.endswith('/'):
        return None

    async with unique_cursor() as main_c:
        fconn = FileConn(main_c)
        r = await fconn.get_file_record(path)

    if r is None:
        raise FileNotFoundError(f'File not found: {path}')
    if not r.mime_type.startswith('image/'):
        return None

    file_id = r.file_id
    async with cache_cursor() as cur:
        thumb_blob = await _get_cache_thumb(cur, file_id)
        if thumb_blob is not None:
            return thumb_blob, "image/jpeg"
        
        # generate thumb
        async with unique_cursor() as main_c:
            fconn = FileConn(main_c)
            if r.external:
                data = b""
                async for chunk in fconn.get_file_blob_external(r.file_id):
                    data += chunk
            else:
                data = await fconn.get_file_blob(r.file_id)
            assert data is not None
        
        thumb_blob = await _save_cache_thumb(cur, file_id, data)
        return thumb_blob, "image/jpeg"
