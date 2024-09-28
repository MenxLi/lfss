from typing import TYPE_CHECKING
import urllib.parse

if TYPE_CHECKING:
    from .database import Database, FileReadPermission, DBUserRecord, FileDBRecord

def encode_uri_compnents(path: str):
    """
    Encode the path components to encode the special characters, 
    also to avoid path traversal attack
    """
    path_sp = path.split("/")
    mapped = map(lambda x: urllib.parse.quote(x), path_sp)
    return "/".join(mapped)

def decode_uri_compnents(path: str):
    """
    Decode the path components to decode the special characters
    """
    path_sp = path.split("/")
    mapped = map(lambda x: urllib.parse.unquote(x), path_sp)
    return "/".join(mapped)

def ensure_uri_compnents(path: str):
    """
    Ensure the path components are safe to use
    """
    return encode_uri_compnents(decode_uri_compnents(path))

def check_user_permission(user: DBUserRecord, owner: DBUserRecord, file: FileDBRecord) -> tuple[bool, str]:
    if user.is_admin:
        return True, ""
    
    # check permission of the file
    if file.permission == FileReadPermission.PRIVATE:
        if user.id != owner.id:
            return False, "Permission denied, private file"
    elif file.permission == FileReadPermission.PROTECTED:
        if user.id == 0:
            return False, "Permission denied, protected file"
    elif file.permission == FileReadPermission.PUBLIC:
        return True, ""
    else:
        assert file.permission == FileReadPermission.UNSET

    # use owner's permission as fallback
    if owner.permission == FileReadPermission.PRIVATE:
        if user.id != owner.id:
            return False, "Permission denied, private user file"
    elif owner.permission == FileReadPermission.PROTECTED:
        if user.id == 0:
            return False, "Permission denied, protected user file"
    else:
        assert owner.permission == FileReadPermission.PUBLIC or owner.permission == FileReadPermission.UNSET

    return True, ""