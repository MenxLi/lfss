
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
