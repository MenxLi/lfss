import subprocess
from ..config import SANDBOX_DIR
from .common import get_conn, create_server_context
import pytest

server = create_server_context()

def test_user_creation(server):
    s = subprocess.check_output(['lfss-user', 'add', 'u0', 'test'], cwd=SANDBOX_DIR)
    s = s.decode()
    assert 'User created' in s, "User creation failed"
    c = get_conn('u0')
    assert c.whoami().username == 'u0', "Username is not correct"
    assert c.whoami().id == 1, "User id is not correct"

    subprocess.check_output(['lfss-user', 'add', 'u1', 'test'], cwd=SANDBOX_DIR)
    subprocess.check_output(['lfss-user', 'add', 'u2', 'test'], cwd=SANDBOX_DIR)

    s = subprocess.check_output(['lfss-user', 'set-peer', 'u0', 'u2', '--level', 'write'], cwd=SANDBOX_DIR)
    s = subprocess.check_output(['lfss-user', 'set-peer', 'u1', 'u2', '--level', 'read'], cwd=SANDBOX_DIR)

def test_list_peers(server):
    c0 = get_conn('u0')
    peers0 = c0.list_peers()
    assert len(peers0) == 1, "Peer count is not correct"
    assert peers0[0].username == 'u2', "Peer username is not correct"

    c2 = get_conn('u2')
    peers2 = c2.list_peers(incoming=True)
    assert len(peers2) == 2, "Peer count is not correct"

def test_u2_upload(server):
    c2 = get_conn('u2')
    c2.put('u2/1.bin', b"hello world")

def test_cross_write(server):
    c0 = get_conn('u0')
    c0.put('u2/1.bin', b"hello world", conflict='overwrite')
    c0.put('u2/2.bin', b'hello world')
    c0.post('u2/3.bin', b'hello world')

    c1 = get_conn('u1')
    with pytest.raises(Exception, match='403'):
        c1.put('u2/4.bin', b'hello world')
    with pytest.raises(Exception, match='403'):
        c1.post('u2/5.bin', b'hello world')

def test_cross_read(server):
    c0 = get_conn('u0')
    assert c0.get('u2/1.bin') == b'hello world'
    assert c0.get('u2/3.bin') == b'hello world'
    assert c0.get_meta('u2/1.bin')

    c1 = get_conn('u1')
    assert c1.get('u2/1.bin') == b'hello world'
    assert c1.get('u2/2.bin') == b'hello world'
    assert c1.get_meta('u2/1.bin').owner_id == 1    #type: ignore

def test_list(server):
    def check_ls(user: str):
        c = get_conn(user)
        p_list = c.list_path('u2/')
        assert len(p_list.files) == 3, "File count is not correct"
        assert len(p_list.dirs) == 0, "Directory count is not correct"
        
        p_list_files = c.list_files('u2/')
        assert len(p_list_files) == 3, "File count is not correct"
        
        p_list_dirs = c.list_dirs('u2/')
        assert len(p_list_dirs) == 0, "Directory count is not correct"

    check_ls('u0')
    check_ls('u1')
    check_ls('u2')

def test_list_root(server):
    def check_ls_root(username, expect_dirs_count):
        c = get_conn(username)
        p_list = c.list_path('/')
        assert len(p_list.files) == 0, "File count is not correct"
        assert len(p_list.dirs) == expect_dirs_count, "Directory count is not correct"
    
    check_ls_root('u0', 2)
    check_ls_root('u1', 2)
    check_ls_root('u2', 1)

def test_delete(server):
    c1 = get_conn('u1')
    with pytest.raises(Exception, match='403'):
        c1.delete('u2/1.bin')
    with pytest.raises(Exception, match='403'):
        c1.delete('u2/2.bin')
    with pytest.raises(Exception, match='403'):
        c1.delete('u2/3.bin')
    with pytest.raises(Exception, match='403'):
        c1.delete('u2/')

    c0 = get_conn('u0')
    c0.delete('u2/1.bin')
    c0.delete('u2/2.bin')

    c2 = get_conn('u2')
    c2.delete('u2/3.bin')

    c2.put('u2/1.bin', b'hello world')
    c0.delete('u2/')

    c2.put('u2/1.bin', b'hello world')
    c2.delete('u2/')
