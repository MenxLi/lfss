import subprocess
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

def test_move0(server):
    c = get_conn('u0')
    c.move('u0/a/test2.txt', 'u0/a/test2.json')
    assert c.get('u0/a/test2.json') == b'hello world 2'
    assert c.get('u0/a/test2.txt') is None
    with pytest.raises(Exception, match='409'):
        c.move('u0/a/test2.json', 'u0/a/test3.txt')
    c.move('u0/a/test2.json', 'u1/_a/test2.json')

    # move path
    c.move('u0/a/', 'u0/c/')
    assert c.get('u0/c/test3.txt') == b'hello world 3'
    assert c.count_files('u0/a/') == 0

    c.move('u0/c/', 'u1/x/')
    assert c.get('u1/x/test3.txt') == b'hello world 3'

def test_move1(server):
    c = get_conn('u1')
    c.move('u1/a/test2.txt', 'u1/a/test2.json')
    assert c.get('u1/a/test2.json') == b'hello world 2'
    assert c.get('u1/a/test2.txt') is None
    with pytest.raises(Exception, match='409'):
        c.move('u1/a/test2.json', 'u1/a/test3.txt')
    with pytest.raises(Exception, match='403'):
        c.move('u1/a/test2.json', 'u0/_a/test2.json')
    
    # move path
    c.move('u1/a/', 'u1/c/')
    assert c.get('u1/c/test3.txt') == b'hello world 3'
    assert c.count_files('u1/a/') == 0

    with pytest.raises(Exception, match='403'):
        c.move('u1/c/', 'u0/x/')

