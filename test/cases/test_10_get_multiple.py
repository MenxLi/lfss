import subprocess, pytest, json
from lfss.eng.datatype import FileReadPermission
from ..config import SANDBOX_DIR
from .common import get_conn, create_server_context

server = create_server_context()

def test_user_creation(server):
    s = subprocess.check_output(['lfss-user', 'add', 'u0', 'test', "--admin", "--permission", "private"], cwd=SANDBOX_DIR)
    s = s.decode()
    assert 'User created' in s, "User creation failed"
    c = get_conn('u0')
    assert c.whoami().username == 'u0', "Username is not correct"
    assert c.whoami().id == 1, "User id is not correct"

    subprocess.check_output(['lfss-user', 'add', 'u1', 'test'], cwd=SANDBOX_DIR)

def test_basic_upload(server):
    c = get_conn('u0')
    c.put('u0/test1.txt', b'hello world 1')
    c.post('u0/a/test2.txt', b'hello world 2', permission=FileReadPermission.PUBLIC)
    c.put_json('u0/a/test3.json', {"hello": "world 3"})

    c1 = get_conn('u1')
    c1.put('u1/test1.txt', b'hello world 1')
    c1.post('u1/a/test2.txt', b'hello world 2')
    c1.put_json('u1/a/test3.json', {"hello": "world 3"})

def test_basic_multiple(server):
    c = get_conn('u0')
    r = c.get_multiple_text('u0/test1.txt', 'u0/a/test2.txt', 'u0/a/test3.json', 'u0/non-exist.txt')
    assert len(r) == 4, "File count is not correct"
    assert r['u0/non-exist.txt'] is None, "Non-existing file should return None"
    assert r['u0/test1.txt'] == 'hello world 1', "File content is not correct"

    r1 = c.get_multiple_text('u1/test1.txt', 'u1/a/test2.txt', 'u1/a/test3.json', 'u1/non-exist.txt')
    assert len(r1) == 4, "File count is not correct"
    assert r1['u1/non-exist.txt'] is None, "Non-existing file should return None"
    assert r1['u1/a/test2.txt'] == 'hello world 2', "File content is not correct"
    assert json.loads(r1['u1/a/test3.json']) == {"hello": "world 3"}, "File content is not correct"

def test_get_perm(server):
    c = get_conn('u1')
    with pytest.raises(Exception, match='403'):
        r = c.get_multiple_text('u1/test1.txt', 'u1/a/test2.txt', 'u0/a/test3.json', 'u0/non-exist.txt')
    
    r1 = c.get_multiple_text('u0/a/test2.txt')
    assert r1['u0/a/test2.txt'] == 'hello world 2', "File content is not correct"

def test_get_empty(server):
    c = get_conn('u0')
    r = c.get_multiple_text('u0/test1.txt', 'u0/a/test2.txt', 'u0/a/test3.json', 'u0/non-exist.txt', skip_content=True)
    assert len(r) == 4, "File count is not correct"
    assert r['u0/test1.txt'] == '', "File content is not correct"

def test_nameparse(server):
    c = get_conn('u0')
    fname = "test 1你好.txt"
    c.put(f'u0/{fname}', b'hello world 1')

    r = c.get_multiple_text(f'u0/{fname}')
    assert len(r) == 1, "File count is not correct"
    assert r[f'u0/{fname}'] == 'hello world 1', "File content is not correct"