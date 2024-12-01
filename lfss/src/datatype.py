from enum import IntEnum
import dataclasses, typing
from .utils import fmt_storage_size

class FileReadPermission(IntEnum):
    UNSET = 0           # not set
    PUBLIC = 1          # accessible by anyone
    PROTECTED = 2       # accessible by any user
    PRIVATE = 3         # accessible by owner only (including admin)

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

    def __post_init__(self):
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

    def __str__(self):
        return f"Directory {self.url} (size={fmt_storage_size(self.size)}, created at {self.create_time}, updated at {self.update_time}, accessed at {self.access_time}, n_files={self.n_files})"

@dataclasses.dataclass
class PathContents:
    dirs: list[DirectoryRecord] = dataclasses.field(default_factory=list)
    files: list[FileRecord] = dataclasses.field(default_factory=list)
    
FileSortKey = typing.Literal['', 'url', 'file_size', 'create_time', 'access_time', 'mime_type']
isValidFileSortKey = lambda x: x in typing.get_args(FileSortKey)
DirSortKey = typing.Literal['', 'dirname']
isValidDirSortKey = lambda x: x in typing.get_args(DirSortKey)