
from .bundle import *
from .connector import Client
from ..eng.datatype import (
    UserRecord, DirectoryRecord, FileRecord, 
    DirConfig, AccessLevel, 
    parse_access_level, parse_read_permission
)

# Backward compatibility
class Connector(Client): ...

__all__ = [
    "upload_file", "upload_directory",
    "download_file", "download_directory", 
    "Client", "Connector",

    "UserRecord", "DirectoryRecord", "FileRecord",
    "DirConfig", "AccessLevel",
    "parse_access_level", "parse_read_permission",
]