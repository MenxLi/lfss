from enum import IntEnum
import dataclasses, typing
import urllib.parse
from typing import Optional
import json
from .utils import fmt_storage_size

class FileReadPermission(IntEnum):
    UNSET = 0           # not set
    PUBLIC = 1          # accessible by anyone
    PROTECTED = 2       # accessible by any user
    PRIVATE = 3         # accessible by owner only (including admin)

class AccessLevel(IntEnum):
    GUEST = -1          # guest, no permission
    NONE  = 0           # no permission
    READ  = 1           # read permission
    WRITE = 2           # write/delete permission
    ALL   = 10          # all permission, currently same as WRITE

@dataclasses.dataclass
class UserRecord:
    id: int
    username: str
    credential: str
    is_admin: bool
    create_time: str
    last_active: str
    max_storage: int
    permission: 'FileReadPermission'

    def __post_init__(self):
        self.permission = FileReadPermission(self.permission)

    def __str__(self):
        return  f"User {self.username} (id={self.id}, admin={self.is_admin}, created at {self.create_time}, last active at {self.last_active}, " + \
                f"storage={fmt_storage_size(self.max_storage)}, permission={self.permission.name})"
    
    def __hash__(self):
        return hash(self.id)
    
    def desensitize(self):
        self.credential = "__HIDDEN__"
        return self

@dataclasses.dataclass
class FileRecord:
    url: str
    owner_id: int
    file_id: str      # defines mapping from fmata to blobs.fdata
    file_size: int
    create_time: str
    access_time: str
    permission: FileReadPermission
    external: bool
    mime_type: str

    def name(self, raw: bool = False):
        name = self.url.rsplit('/', 1)[-1]
        return name if raw else urllib.parse.unquote(name)
    
    def parent(self):
        if '/' not in self.url:
            return DirectoryRecord(url='/')
        parent_url = self.url.rsplit('/', 1)[0]
        if not parent_url.endswith('/'):
            parent_url += '/'
        return DirectoryRecord(url=parent_url)

    def __post_init__(self):
        assert not self.url.endswith('/'), "File URL should not end with '/'"
        self.permission = FileReadPermission(self.permission)

    def __str__(self):
        return  f"File {self.url} [{self.mime_type}] (owner={self.owner_id}, created at {self.create_time}, accessed at {self.access_time}, " + \
                f"file_id={self.file_id}, permission={self.permission.name}, size={fmt_storage_size(self.file_size)}, external={self.external})"

@dataclasses.dataclass
class DirectoryRecord:
    url: str
    size: int = -1
    create_time: str = ""
    update_time: str = ""
    access_time: str = ""
    n_files: int = -1

    def name(self, raw: bool = False):
        if self.url == "/" or self.url == "": 
            return ""
        name = self.url.rstrip('/').rsplit('/', 1)[-1]
        return name if raw else urllib.parse.unquote(name)
    
    def parent(self):
        if self.url in ('/', ''):
            raise RuntimeError("Root directory has no parent")
        if '/' not in (rsp:=self.url.rstrip('/')):
            return DirectoryRecord(url='/')
        parent_url = rsp.rsplit('/', 1)[0]
        if not parent_url.endswith('/'):
            parent_url += '/'
        return DirectoryRecord(url=parent_url)

    def __post_init__(self):
        assert self.url.endswith('/'), "Directory URL should end with '/'"

    def __str__(self):
        return f"Directory {self.url} (size={fmt_storage_size(self.size)}, created at {self.create_time}, updated at {self.update_time}, accessed at {self.access_time}, n_files={self.n_files})"

@dataclasses.dataclass
class PathContents:
    dirs: list[DirectoryRecord] = dataclasses.field(default_factory=list)
    files: list[FileRecord] = dataclasses.field(default_factory=list)

@dataclasses.dataclass
class DirConfig:
    index: Optional[str] = None
    access_control: dict[str, AccessLevel] = dataclasses.field(default_factory=dict)

    def set_index(self, index_fname: str):
        self.index = index_fname
        return self

    def set_access(self, username: str, level: AccessLevel):
        if self.access_control is None:
            self.access_control = {}
        self.access_control[username] = level
        return self

    def remove_access(self, username: str):
        if self.access_control and username in self.access_control:
            del self.access_control[username]
        return self
    
    def to_json_str(self) -> str:
        return json.dumps(self.to_json(), indent=4)
    
    def to_json(self) -> dict:
        obj = {}
        obj['index'] = self.index
        obj['access-control'] = {k: v.name for k, v in self.access_control.items()}
        return obj

    @staticmethod
    def from_json(config_json: dict) -> 'DirConfig':
        config = DirConfig()
        if 'index' in config_json:
            config.index = config_json['index']
        if 'access-control' in config_json:
            config.access_control = {}
            for k, v in config_json['access-control'].items():
                config.access_control[k] = parse_access_level(v)
        return config


def parse_read_permission(s: str | int) -> FileReadPermission:
    if isinstance(s, int):
        return FileReadPermission(s)
    for p in FileReadPermission:
        if p.name.lower() == s.lower():
            return p
    raise ValueError(f"Invalid file read permission {s}")

def parse_access_level(s: str | int) -> AccessLevel:
    if isinstance(s, int):
        return AccessLevel(s)

    for p in AccessLevel:
        if p.name.lower() == s.lower():
            return p
    raise ValueError(f"Invalid access level {s}")
    
DECOY_USER = UserRecord(0, 'decoy', 'decoy', False, '2021-01-01 00:00:00', '2021-01-01 00:00:00', 0, FileReadPermission.PRIVATE)
FileSortKey = typing.Literal['', 'url', 'file_size', 'create_time', 'access_time', 'mime_type']
isValidFileSortKey = lambda x: x in typing.get_args(FileSortKey)
DirSortKey = typing.Literal['', 'dirname']
isValidDirSortKey = lambda x: x in typing.get_args(DirSortKey)