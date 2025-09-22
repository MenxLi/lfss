
from ..api.connector import Connector
from ..eng.datatype import DirectoryRecord, FileRecord

def mimetype_unicode(r: DirectoryRecord | FileRecord):
    if isinstance(r, DirectoryRecord):
        return "📁"
    if r.mime_type in ["application/pdf", "application/x-pdf"]:
        return "📕"
    elif r.mime_type.startswith("image/"):
        return "🖼️"
    elif r.mime_type.startswith("video/"):
        return "🎞️"
    elif r.mime_type.startswith("audio/"):
        return "🎵"
    elif r.mime_type in ["application/zip", "application/x-tar", "application/gzip", "application/x-7z-compressed"]:
        return "📦"
    elif r.mime_type in ["application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]:
        return "📊"
    elif r.mime_type in ["application/x-msdownload", "application/x-executable", "application/x-mach-binary", "application/x-elf"]:
        return "💻"
    elif r.mime_type in ["application/vnd.ms-powerpoint", "application/vnd.openxmlformats-officedocument.presentationml.presentation"]:
        return "📈"
    elif r.mime_type in set([
        "text/html", "application/xhtml+xml", "application/xml", "text/css", "text/x-scss", "application/javascript", "text/javascript",
        "application/json", "text/x-yaml", "text/x-markdown", "application/wasm", 
        "text/x-ruby", "application/x-ruby", "text/x-perl", "application/x-lisp", 
        "text/x-haskell", "text/x-lua", "application/x-tcl", 
        "text/x-python", "text/x-java-source", "text/x-go", "application/x-rust", "text/x-asm", 
        "application/sql", "text/x-c", "text/x-c++", "text/x-csharp", 
        "application/x-httpd-php", "application/x-sh", "application/x-shellscript", 
        "application/x-latex", "application/x-tex", 
    ]):
        return "👨‍💻"
    elif r.mime_type.startswith("text/"):
        return "📃"
    return "📄"

def stream_text(
    conn: Connector, 
    path: str,
    encoding="utf-8",
    chunk_size=1024 * 8,
    ):
    """
    Stream text content of a file from the server.
    Raise FileNotFoundError if the file does not exist.
    Raise ValueError if the file size exceeds MAX_TEXT_SIZE.
    
    Yields str chunks.
    """
    MAX_TEXT_SIZE = 100 * 1024 * 1024  # 100 MB
    r = conn.get_fmeta(path)
    if r is None:
        raise FileNotFoundError(f"File not found: {path}")
    if r.file_size > MAX_TEXT_SIZE:
        raise ValueError(f"File size {r.file_size} exceeds maximum text size {MAX_TEXT_SIZE}")
    ss = conn.get_stream(r.url, chunk_size=chunk_size)
    total_read = 0
    for chunk in ss:
        total_read += len(chunk)
        if total_read > MAX_TEXT_SIZE:
            raise ValueError(f"File size exceeds maximum text size {MAX_TEXT_SIZE}")
        yield chunk.decode(encoding, errors='replace')  # decode bytes to str, replace errors
