import pytest
import subprocess
from .common import get_conn, upload_basic, create_server_context
from lfss.src.datatype import FileReadPermission
from ..config import SANDBOX_DIR

server = create_server_context()

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

def test_move(server):
    c = get_conn('u0')
    c.move('u0/a/test2.txt', 'u0/test2.txt')
    p_list = c.list_path('u0/')
    assert len(p_list.files) == 1, "File move failed"
    assert p_list.files[0].url == 'u0/test2.txt', "File move failed"

def test_put_get_perm(server):
    # admin
    c = get_conn('u0')
    c.put(f'u2/test1_from_u0.txt', b'hello world 1', permission=FileReadPermission.PUBLIC)
    c.put(f'u2/test2_from_u0.txt', b'hello world 2, protected', permission=FileReadPermission.PROTECTED)
    c.put(f'u2/test3_from_u0.txt', b'hello world 3, private', permission=FileReadPermission.PRIVATE)
    assert c.get(f'u2/test1_from_u0.txt') == b'hello world 1', "Admin get put failed"

    # user
    c = get_conn('u1')
    with pytest.raises(Exception):
        c.put(f'u2/test1_from_u1.txt', b'hello world 1')
    assert c.get(f'u2/test2_from_u0.txt') == b'hello world 2, protected', "User get put failed"
    with pytest.raises(Exception, match='403'):
        c.get(f'u2/test3_from_u0.txt')
    
    c = get_conn('u2')
    with pytest.raises(Exception, match='403'):
        c.put(f'u2/test1_from_u0.txt', b'hello world 1', conflict='overwrite')
    
    with pytest.raises(Exception, match='403'):
        c.delete('u2/test1_from_u0.txt')

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