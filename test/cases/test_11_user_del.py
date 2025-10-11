
import subprocess
from .common import get_conn, create_server_context
from ..config import SANDBOX_DIR

server = create_server_context()

def test_user_creation(server):
    subprocess.check_output(['lfss-user', 'add', 'u0', 'test'], cwd=SANDBOX_DIR)
    subprocess.check_output(['lfss-user', 'add', 'u1', 'test'], cwd=SANDBOX_DIR)
    subprocess.check_output(['lfss-user', 'set-peer', 'u0', 'u1', '--level', 'write'], cwd=SANDBOX_DIR)
    subprocess.check_output(['lfss-user', 'set-peer', 'u1', 'u0', '--level', 'read'], cwd=SANDBOX_DIR)

def test_file_emit(server):
    c0 = get_conn('u0')
    c0.put('u0/test1.txt', b'hello world 1')
    c0.put('u1/from_u0.txt', b'hello world 1')

    c1 = get_conn('u1')
    c1.put('u1/test2.txt', b'hello world 2')

    assert c1.exists('u0/test1.txt'), "User u1 should see u0's file"
    assert c1.exists('u0/'), "User u1 should see u0's directory"
    assert c1.exists('u1/test2.txt'), "User u1 should see its own file"

    assert c1.get_fmeta('u1/from_u0.txt').owner_id == c0.whoami().id, "File owner should be u0"

def test_del_u0(server):
    c1 = get_conn('u1')
    c1_size_before = c1.storage_used()

    s = subprocess.check_output(['lfss-user', 'delete', 'u0'], cwd=SANDBOX_DIR)
    s = s.decode()
    assert 'User deleted' in s, "User deletion failed"

    assert not c1.exists('u0/'), "User u1 should not see u0's directory after u0 deletion"
    assert c1.get_fmeta('u1/from_u0.txt').owner_id == c1.whoami().id, "File owner should be u1 after u0 deletion"

    c1_size_after = c1.storage_used()
    assert c1_size_after > c1_size_before, "Storage used should increase after u0 deletion"