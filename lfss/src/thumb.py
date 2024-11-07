from lfss.src.config import DATA_HOME
from lfss.src.database import FileConn
from lfss.src.connection_pool import unique_cursor
from typing import Optional
from PIL import Image
from io import BytesIO
import aiosqlite

def prepare_svg(svg_str: str):
    """
    Injects grey color to the svg string, and encodes it to bytes
    """
    color = "#666"
    x = svg_str.replace('<path', '<path fill="{}"'.format(color))
    x = x.replace('<svg', '<svg fill="{}"'.format(color))
    return x.encode()

# from: https://pictogrammers.com/library/mdi/
ICON_FOLER = prepare_svg('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><title>folder-outline</title><path d="M20,18H4V8H20M20,6H12L10,4H4C2.89,4 2,4.89 2,6V18A2,2 0 0,0 4,20H20A2,2 0 0,0 22,18V8C22,6.89 21.1,6 20,6Z" /></svg>')
ICON_FILE = prepare_svg('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><title>file-document-outline</title><path d="M6,2A2,2 0 0,0 4,4V20A2,2 0 0,0 6,22H18A2,2 0 0,0 20,20V8L14,2H6M6,4H13V9H18V20H6V4M8,12V14H16V12H8M8,16V18H13V16H8Z" /></svg>')
ICON_PDF = prepare_svg('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><title>file-pdf-box</title><path d="M19 3H5C3.9 3 3 3.9 3 5V19C3 20.1 3.9 21 5 21H19C20.1 21 21 20.1 21 19V5C21 3.9 20.1 3 19 3M9.5 11.5C9.5 12.3 8.8 13 8 13H7V15H5.5V9H8C8.8 9 9.5 9.7 9.5 10.5V11.5M14.5 13.5C14.5 14.3 13.8 15 13 15H10.5V9H13C13.8 9 14.5 9.7 14.5 10.5V13.5M18.5 10.5H17V11.5H18.5V13H17V15H15.5V9H18.5V10.5M12 10.5H13V13.5H12V10.5M7 10.5H8V11.5H7V10.5Z" /></svg>')
ICON_EXE = prepare_svg('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><title>application-brackets-outline</title><path d="M9.5,8.5L11,10L8,13L11,16L9.5,17.5L5,13L9.5,8.5M14.5,17.5L13,16L16,13L13,10L14.5,8.5L19,13L14.5,17.5M21,2H3A2,2 0 0,0 1,4V20A2,2 0 0,0 3,22H21A2,2 0 0,0 23,20V4A2,2 0 0,0 21,2M21,20H3V6H21V20Z" /></svg>')
ICON_ZIP = prepare_svg('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><title>zip-box-outline</title><path d="M12 17V15H14V17H12M14 13V11H12V13H14M14 9V7H12V9H14M10 11H12V9H10V11M10 15H12V13H10V15M21 5V19C21 20.1 20.1 21 19 21H5C3.9 21 3 20.1 3 19V5C3 3.9 3.9 3 5 3H19C20.1 3 21 3.9 21 5M19 5H12V7H10V5H5V19H19V5Z" /></svg>')
ICON_CODE = prepare_svg('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><title>file-code-outline</title><path d="M14 2H6C4.89 2 4 2.9 4 4V20C4 21.11 4.89 22 6 22H18C19.11 22 20 21.11 20 20V8L14 2M18 20H6V4H13V9H18V20M9.54 15.65L11.63 17.74L10.35 19L7 15.65L10.35 12.3L11.63 13.56L9.54 15.65M17 15.65L13.65 19L12.38 17.74L14.47 15.65L12.38 13.56L13.65 12.3L17 15.65Z" /></svg>')

THUMB_DB = DATA_HOME / 'thumbs.db'
THUMB_SIZE = (48, 48)

async def _maybe_init_thumb(c: aiosqlite.Cursor):
    await c.execute('''
        CREATE TABLE IF NOT EXISTS thumbs (
            path TEXT PRIMARY KEY,
            ctime TEXT,
            thumb BLOB
        )
    ''')

async def _get_cache_thumb(c: aiosqlite.Cursor, path: str, ctime: str) -> Optional[bytes]:
    res = await c.execute('''
        SELECT ctime, thumb FROM thumbs WHERE path = ? 
    ''', (path, ))
    row = await res.fetchone()
    if row is None:
        return None
    # check if ctime matches, if not delete and return None
    if row[0] != ctime:
        await _delete_cache_thumb(c, path)
        return None
    blob: bytes = row[1]
    return blob
    
async def _save_cache_thumb(c: aiosqlite.Cursor, path: str, ctime: str, raw_bytes: bytes) -> bytes:
    raw_img = Image.open(BytesIO(raw_bytes))
    raw_img.thumbnail(THUMB_SIZE)
    img = raw_img.convert('RGB')
    bio = BytesIO()
    img.save(bio, 'JPEG')
    blob = bio.getvalue()
    await c.execute('''
        INSERT OR REPLACE INTO thumbs (path, ctime, thumb) VALUES (?, ?, ?)
    ''', (path, ctime, blob))
    await c.execute('COMMIT')  # commit immediately
    return blob

async def _delete_cache_thumb(c: aiosqlite.Cursor, path: str):
    await c.execute('''
        DELETE FROM thumbs WHERE path = ?
    ''', (path, ))
    await c.execute('COMMIT')

async def get_thumb(path: str) -> tuple[bytes, str]:
    """
    returns [image bytes of thumbnail, mime type] if supported, 
    or None if not supported. 
    Raises FileNotFoundError if file does not exist
    """
    if path.endswith('/'):
        return ICON_FOLER, 'image/svg+xml'

    async with aiosqlite.connect(THUMB_DB) as conn:
        cur = await conn.cursor()
        await _maybe_init_thumb(cur)

        async with unique_cursor() as main_c:
            fconn = FileConn(main_c)
            r = await fconn.get_file_record(path)
            if r is None:
                await _delete_cache_thumb(cur, path)
                raise FileNotFoundError(f'File not found: {path}')
        
            if not r.mime_type.startswith('image/'):
                match r.mime_type:
                    case 'application/pdf' | 'application/x-pdf':
                        return ICON_PDF, 'image/svg+xml'
                    case 'application/x-msdownload' | 'application/x-msdos-program' | 'application/x-msi' | 'application/octet-stream':
                        return ICON_EXE, 'image/svg+xml'
                    case 'application/zip' | 'application/x-zip-compressed' | 'application/x-zip' | 'application/x-compressed' | 'application/x-compress':
                        return ICON_ZIP, 'image/svg+xml'
                    case 'text/plain' | 'text/x-python' | 'text/x-c' | 'text/x-c++' | 'text/x-java' | 'text/x-php' | 'text/x-shellscript' | 'text/x-perl' | 'text/x-ruby' | 'text/x-go' | 'text/x-rust' | 'text/x-haskell' | 'text/x-lisp' | 'text/x-lua' | 'text/x-tcl' | 'text/x-sql' | 'text/x-yaml' | 'text/x-xml' | 'text/x-markdown' | 'text/x-tex' | 'text/x-asm' | 'text/x-fortran' | 'text/x-pascal' | 'text/x-erlang' | 'text/x-ocaml' | 'text/x-matlab' | 'text/x-csharp' | 'text/x-swift' | 'text/x-kotlin' | 'text/x-dart' | 'text/x-julia' | 'text/x-scala' | 'text/x-clojure' | 'text/x-elm' | 'text/x-crystal' | 'text/x-nim' | 'text/x-zig':
                        return ICON_CODE, 'image/svg+xml'
                    case _:
                        return ICON_FILE, 'image/svg+xml'

        c_time = r.create_time
        thumb_blob = await _get_cache_thumb(cur, path, c_time)
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
        
        thumb_blob = await _save_cache_thumb(cur, path, c_time, data)
        return thumb_blob, "image/jpeg"
