import pytest
import subprocess
from lfss.client import Connector
from lfss.src.config import hash_credential
from lfss.src.datatype import FileReadPermission
from ..start_server import Server
from ..config import SANDBOX_DIR, SERVER_PORT, clear_sandbox

@pytest.fixture(scope='session')
def server():
    s = Server()
    s.start(cwd=str(SANDBOX_DIR), port=SERVER_PORT)
    yield s
    s.stop()
    clear_sandbox()

def get_conn(username, password = 'test'):
    return Connector(f"http://localhost:{SERVER_PORT}", token=hash_credential(username, password))

def test_user_creation(server):
    s = subprocess.check_output(['lfss-user', 'add', 'u0', 'test', '--admin', '--max-storage', '1G'], cwd=SANDBOX_DIR)
    s = s.decode()
    assert 'User created' in s, "User creation failed"
    c = get_conn('u0')
    assert c.whoami().is_admin, "User is not admin"
    assert c.whoami().username == 'u0', "Username is not correct"
    assert c.whoami().max_storage == 1024**3, "Max storage is not correct"

    s = subprocess.check_output(['lfss-user', 'add', 'u1', 'test'], cwd=SANDBOX_DIR)
    s = s.decode()
    assert 'User created' in s, "User creation failed"

    s = subprocess.check_output(['lfss-user', 'add', 'u2', 'test'], cwd=SANDBOX_DIR)
    s = s.decode()
    assert 'User created' in s, "User creation failed"

def upload_basic(username: str):
    c = get_conn(username)
    c.put(f'{username}/test1.txt', b'hello world 1')
    c.put(f'{username}/a/test2.txt', b'hello world 2')
    c.put(f'{username}/a/test3.txt', b'hello world 3')
    c.put(f'{username}/a/b/test4.txt', b'hello world 4')
    p_list = c.list_path(f'{username}/')
    assert len(p_list.dirs) == 1, "Directory count is not correct"
    assert len(p_list.files) == 1, "File count is not correct"
    assert p_list.dirs[0].url == f'{username}/a/', "Directory name is not correct"
    assert p_list.files[0].url == f'{username}/test1.txt', "File name is not correct"

def test_upload(server):
    upload_basic('u0')
    upload_basic('u1')
    upload_basic('u2')

def test_get_put_perm(server):
    # admin
    c = get_conn('u0')
    c.put(f'u2/test1_from_u0.txt', b'hello world 1')
    assert c.get(f'u2/test1_from_u0.txt') == b'hello world 1', "Admin get put failed"
    c.put(f'u2/test2_from_u0.txt', b'hello world 2, protected', permission=FileReadPermission.PROTECTED)
    c.put(f'u2/test3_from_u0.txt', b'hello world 3, private', permission=FileReadPermission.PRIVATE)

    # user
    c = get_conn('u1')
    with pytest.raises(Exception):
        c.put(f'u2/test1_from_u1.txt', b'hello world 1')
    assert c.get(f'u2/test2_from_u0.txt') == b'hello world 2, protected', "User get put failed"
    with pytest.raises(Exception):
        c.get(f'u2/test3_from_u0.txt')
    
    c = get_conn('u2')
    with pytest.raises(Exception):
        c.put(f'u2/test1_from_u0.txt', b'hello world 1', conflict='overwrite')

def test_user_deletion(server):
    s = subprocess.check_output(['lfss-user', 'delete', 'u2'], cwd=SANDBOX_DIR)
    s = s.decode()
    assert 'User deleted' in s, "User deletion failed"

    c = get_conn('u2')
    with pytest.raises(Exception):
        c.whoami()
    
    c0 = get_conn('u0')
    assert c0.get('u2/test1_from_u0.txt') is None