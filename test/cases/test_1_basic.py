import pytest
import subprocess, os
from tempfile import NamedTemporaryFile
from .common import get_conn, create_server_context
from lfss.eng.datatype import FileReadPermission
from lfss.eng.config import MAX_MEM_FILE_BYTES
from ..config import SANDBOX_DIR

server = create_server_context()

def upload_basic(username: str):
    c = get_conn(username)
    c.put(f'{username}/test1.txt', b'hello world 1')
    c.post(f'{username}/a/test2.txt', b'hello world 2')
    c.put(f'{username}/a/test3.txt', b'hello world 3')
    c.put(f'{username}/a/b/test4.txt', b'hello world 4')
    p_list = c.list_path(f'{username}/')
    assert len(p_list.dirs) == 1, "Directory count is not correct"
    assert len(p_list.files) == 1, "File count is not correct"
    assert p_list.dirs[0].url == f'{username}/a/', "Directory name is not correct"
    assert p_list.files[0].url == f'{username}/test1.txt', "File name is not correct"

def test_user_creation(server):
    s = subprocess.check_output(['lfss-user', 'add', 'u0', 'test', '--admin', '--max-storage', '1G'], cwd=SANDBOX_DIR)
    s = s.decode()
    assert 'User created' in s, "User creation failed {s}".format(s=s)
    c = get_conn('u0')
    assert c.whoami().is_admin, "User is not admin"
    assert c.whoami().username == 'u0', "Username is not correct"
    assert c.whoami().max_storage == 1024**3, "Max storage is not correct"

    s = subprocess.check_output(['lfss-user', 'add', 'u1', 'test', '--permission', 'public'], cwd=SANDBOX_DIR)
    s = s.decode()
    assert 'User created' in s, "User creation failed {s}".format(s=s)

    s = subprocess.check_output(['lfss-user', 'add', 'u2', 'test'], cwd=SANDBOX_DIR)
    s = s.decode()
    assert 'User created' in s, "User creation failed {s}".format(s=s)

def test_upload(server):
    upload_basic('u0')
    upload_basic('u1')
    upload_basic('u2')

def test_delete(server):
    c = get_conn('u0')
    c.delete('u0/test1.txt')
    p_list = c.list_path('u0/')
    assert len(p_list.files) == 0, "File deletion failed"

def test_empty_file(server):
    c = get_conn('u0')
    c.put('u0/empty.txt', b'')
    assert c.get('u0/empty.txt') == b'', "Empty file failed"
    c.delete('u0/empty.txt')

def test_move(server):
    c = get_conn('u0')
    c.move('u0/a/test2.txt', 'u0/test2.json')
    p_list = c.list_path('u0/')
    assert len(p_list.files) == 1, "File move failed"
    assert p_list.files[0].url == 'u0/test2.json', "File move failed"
    assert p_list.files[0].mime_type == 'application/json', "Mime type is not correct"

def test_put_get_perm(server):
    # admin
    c = get_conn('u0')
    c.put(f'u2/test1_from_u0.txt', b'hello world 1', permission=FileReadPermission.PUBLIC)
    c.put(f'u2/test2_from_u0.txt', b'hello world 2, protected', permission=FileReadPermission.PROTECTED)
    c.put(f'u2/test3_from_u0.txt', b'hello world 3, private', permission=FileReadPermission.PRIVATE)
    assert c.get(f'u2/test1_from_u0.txt') == b'hello world 1', "Admin get put failed"

    # test stream get
    blobs = b""
    for chunk in c.get_stream(f'u2/test1_from_u0.txt'):
        blobs += chunk
    assert blobs == b'hello world 1', "Get stream failed"

    # user
    c = get_conn('u1')
    with pytest.raises(Exception):
        c.put(f'u2/test1_from_u1.txt', b'hello world 1')
    assert c.get(f'u2/test2_from_u0.txt') == b'hello world 2, protected', "User get put failed"
    with pytest.raises(Exception, match='403'):
        c.get(f'u2/test3_from_u0.txt')
    
    c = get_conn('u2')
    c.put(f'u2/test1_from_u0.txt', b'hello world 1', conflict='overwrite')

def test_meta_perm(server):
    c0 = get_conn('u0')
    assert c0.get_metadata('u2/test1_from_u0.txt') is not None, "Get metadata failed, should have admin permission"
    assert c0.get_metadata('u2/non-exists.txt') is None, "Get metadata failed, should return None"
    assert c0.get_metadata('u2/') is not None, "Get metadata failed, should have admin permission"
    assert c0.get_metadata('u2/non-exists-dir/') is None, "Get metadata failed, should not exist"

    c1 = get_conn('u1')
    assert c1.get_metadata('u2/test1_from_u0.txt') is not None, "Get metadata failed, should have permission"
    assert c1.get_metadata('u2/test2_from_u0.txt') is not None, "Get metadata failed, should have permission"
    with pytest.raises(Exception, match='403'): c1.get_metadata('u2/test3_from_u0.txt')
    with pytest.raises(Exception, match='403'): c1.get_metadata('u2/')

    c2 = get_conn('u2')
    assert c2.get_metadata('u2/test1_from_u0.txt') is not None, "Get metadata failed, should have permission"
    assert c2.get_metadata('u2/test2_from_u0.txt') is not None, "Get metadata failed, should have permission"
    assert c2.get_metadata('u2/test3_from_u0.txt') is not None, "Get metadata failed, should have permission"
    assert c2.get_metadata('u2/') is not None, "Get metadata failed, should have permission"

def test_user_deletion(server):
    s = subprocess.check_output(['lfss-user', 'delete', 'u2'], cwd=SANDBOX_DIR)
    s = s.decode()
    assert 'User deleted' in s, "User deletion failed"

    c = get_conn('u2')
    with pytest.raises(Exception):
        c.whoami()
    
    c0 = get_conn('u0')
    assert c0.get('u2/test1_from_u0.txt') is None

def test_post(server):
    c = get_conn('u0')
    with NamedTemporaryFile() as f:
        f.write(b'hello world 1')
        f.flush()
        c.post('u0/test1_post_file.txt', f.name, permission=FileReadPermission.PROTECTED)

    assert c.get('u0/test1_post_file.txt') == b'hello world 1', "Post file failed"
    assert c.get_metadata('u0/test1_post_file.txt').permission == FileReadPermission.PROTECTED, "Post file permission failed"   # type: ignore
    
    c.post('u0/test1_post_bytes.txt', b'hello world 2')
    c.post('u0/test1_post_bytes.txt', b'hello world 2', conflict='skip')
    c.post('u0/test1_post_bytes.txt', b'hello world 2', conflict='skip-ahead')
    with pytest.raises(Exception, match='409'):
        c.post('u0/test1_post_bytes.txt', b'hello world 2', conflict='abort')

def test_large_file(server):
    c = get_conn('u0')
    content = os.urandom(MAX_MEM_FILE_BYTES + 1)
    with NamedTemporaryFile() as f:
        f.write(content)
        f.flush()
        c.post('u0/test_large_file.txt', f.name, permission=FileReadPermission.PROTECTED)
    assert c.get('u0/test_large_file.txt') == content, "Large file failed"

def test_set_perm(server):
    c = get_conn('u0')
    c.put('u0/test1_set_perm.txt', b'hello world 1', permission=FileReadPermission.PUBLIC)

    c1 = get_conn('u1')
    assert c1.get('u0/test1_set_perm.txt') == b'hello world 1', "Initial permission failed"

    c.set_file_permission('u0/test1_set_perm.txt', FileReadPermission.PROTECTED)
    assert c1.get('u0/test1_set_perm.txt') == b'hello world 1', "Protected permission failed"
    
    c.set_file_permission('u0/test1_set_perm.txt', FileReadPermission.PRIVATE)
    with pytest.raises(Exception, match='403'):
        c1.get('u0/test1_set_perm.txt')

def test_path_deletion(server):
    c = get_conn('u0')
    c.delete('u0/')
    p_list = c.list_path('u0/')
    assert len(p_list.dirs) == 0, "Directory deletion failed"
    assert len(p_list.files) == 0, "File deletion failed"

    c.put('u1/upload_by_u0.txt', b'hello world 1')

    c1 = get_conn('u1')
    c1.delete('u1/')

    assert c.get('u1/upload_by_u0.txt') == None