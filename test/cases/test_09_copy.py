import subprocess, sqlite3
from ..config import SANDBOX_DIR
from .common import get_conn, create_server_context
import pytest

server = create_server_context()

def test_user_creation(server):
    s = subprocess.check_output(['lfss-user', 'add', 'u0', 'test', "--admin"], cwd=SANDBOX_DIR)
    s = s.decode()
    assert 'User created' in s, "User creation failed"
    c = get_conn('u0')
    assert c.whoami().username == 'u0', "Username is not correct"
    assert c.whoami().id == 1, "User id is not correct"

    subprocess.check_output(['lfss-user', 'add', 'u1', 'test'], cwd=SANDBOX_DIR)

def test_basic_upload(server):
    c = get_conn('u0')
    c.put('u0/test1.txt', b'hello world 1')
    c.post('u0/a/test2.txt', b'hello world 2')
    c.put('u0/a/test3.txt', b'hello world 3')
    c.put('u0/a/b/test4.txt', b'hello world 4')

    c1 = get_conn('u1')
    c1.put('u1/test1.txt', b'hello world 1')
    c1.post('u1/a/test2.txt', b'hello world 2')
    c1.put('u1/a/test3.txt', b'hello world 3')
    c1.put('u1/a/b/test4.txt', b'hello world 4')

def test_copy0(server):
    c = get_conn('u0')
    c.copy('u0/a/test2.txt', 'u0/a/test2.json')
    assert c.get('u0/a/test2.json') == b'hello world 2'
    assert c.get('u0/a/test2.txt') == b'hello world 2'
    with pytest.raises(Exception, match='409'):
        c.copy('u0/a/test2.json', 'u0/a/test3.txt')
    c.copy('u0/a/test2.json', 'u1/_a/test2.json')

    # copy path
    c.copy('u0/a/', 'u0/c/')
    assert c.get('u0/c/test3.txt') == b'hello world 3'
    assert c.count_files('u0/a/') != 0

    c.copy('u0/c/', 'u1/x/')
    assert c.get('u1/x/test3.txt') == b'hello world 3'

    # delete
    c.delete('u0/c/')
    assert c.count_files('u0/c/') == 0

    c.delete('u0/a/')
    assert c.count_files('u0/a/') == 0
    assert c.count_files('u1/x/') != 0

def test_copy1(server):
    c = get_conn('u1')
    c.copy('u1/a/test2.txt', 'u1/a/test2.json')
    assert c.get('u1/a/test2.json') == b'hello world 2'
    assert c.get('u1/a/test2.txt') == b'hello world 2'
    with pytest.raises(Exception, match='409'):
        c.copy('u1/a/test2.json', 'u1/a/test3.txt')
    with pytest.raises(Exception, match='403'):
        c.copy('u1/a/test2.json', 'u0/_a/test2.json')
    
    # copy path
    c.copy('u1/a/', 'u1/c/')
    assert c.get('u1/c/test3.txt') == b'hello world 3'

    with pytest.raises(Exception, match='403'):
        c.copy('u1/c/', 'u0/x/')

def test_user_delete(server):
    # make more copied before deleting
    c = get_conn('u0')
    c.copy('u1/x/', 'u0/a1/')
    c.copy('u1/x/', 'u0/a2/')

    subprocess.check_output(['lfss-user', 'delete', 'u0'], cwd=SANDBOX_DIR)
    subprocess.check_output(['lfss-user', 'delete', 'u1'], cwd=SANDBOX_DIR)

    with pytest.raises(Exception, match='401'):
        c = get_conn('u0')
        c.whoami()
    
    data_index_file = SANDBOX_DIR / '.storage_data' / 'index.db'
    assert data_index_file.exists()

    conn = sqlite3.connect(data_index_file)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM dupcount")
    assert cursor.fetchone() is None
