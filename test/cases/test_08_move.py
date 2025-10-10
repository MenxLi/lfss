import subprocess
from ..config import SANDBOX_DIR
from .common import get_conn, create_server_context
import pytest
from lfss.api import Client

server = create_server_context()

def test_user_creation(server):
    s = subprocess.check_output(['lfss-user', 'add', 'u0', 'test', "--admin"], cwd=SANDBOX_DIR)
    s = s.decode()
    assert 'User created' in s, "User creation failed"
    c = get_conn('u0')
    assert c.whoami().username == 'u0', "Username is not correct"
    assert c.whoami().id == 1, "User id is not correct"

    subprocess.check_output(['lfss-user', 'add', 'u1', 'test'], cwd=SANDBOX_DIR)

def _upload_random_files(c: Client, dir_path, n):
    import random
    import string
    if dir_path.endswith('/'):
        dir_path = dir_path[:-1]
    for i in range(n):
        if random.random() < 0.2: # nest directory
            dir_path += '/' + ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))
        fname = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10)) + '.txt'
        fpath = dir_path + '/' + fname
        content = ''.join(random.choices(string.ascii_lowercase + string.digits, k=20)).encode()
        c.put(fpath, content)

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
    assert not c.exists('u0/a/test2.txt')
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
    assert not c.exists('u1/a/test2.txt')
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

def test_move_transfer(server):
    c1 = get_conn('u1')
    _upload_random_files(c1, 'u1/move_test/', 20)

    c0 = get_conn('u0')
    f0 = c0.list_files('u1/move_test/', flat=True, limit=1)[0]
    assert f0.owner_id == c1.whoami().id
    f0_mv_pth = 'u1/move_test_moved/' + f0.name()
    c0.move(f0.url, f0_mv_pth)
    f0_mv = c0.get_fmeta(f0_mv_pth)
    assert f0_mv is not None
    assert f0_mv.owner_id == c0.whoami().id

    c0.move('u1/move_test/', 'u1/move_test_moved2/')
    f1 = c0.list_files('u1/move_test_moved2/', flat=True)[0]
    assert f1.owner_id == c0.whoami().id

def test_reject_move(server):
    c0 = get_conn('u0')

    c0.put('u0/reject_move/test.txt', b'hello')
    c0.put('u0/reject_move/test1.txt', b'hello')

    c0.put('u0/reject_move_dir1/test.txt', b'hello')
    with pytest.raises(Exception, match='409'):
        c0.move('u0/reject_move/', 'u0/reject_move_dir1/')
    
    c0.put('u0/reject_move_dir2/test_else.txt', b'hello')
    c0.move('u0/reject_move/', 'u0/reject_move_dir2/')
    # this should be fine, will merge directories
    assert not c0.exists('u0/reject_move/')
    assert c0.count_files('u0/reject_move_dir2/') == 3

def test_final_size_check(server):
    c0 = get_conn('u0')
    c1 = get_conn('u1')

    c0_storage = c0.storage_used()
    c1_storage = c1.storage_used()

    all_files = c0.list_files('u0/', flat=True) + c0.list_files('u1/', flat=True)
    total_size_u0 = sum([f.file_size for f in all_files if f.owner_id == c0.whoami().id])
    total_size_u1 = sum([f.file_size for f in all_files if f.owner_id == c1.whoami().id])
    
    assert c0_storage == total_size_u0, f"User u0 storage used mismatch: {c0_storage} vs {total_size_u0}"
    assert c1_storage == total_size_u1, f"User u1 storage used mismatch: {c1_storage} vs {total_size_u1}"