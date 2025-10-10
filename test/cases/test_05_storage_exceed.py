import subprocess
import os
from ..config import SANDBOX_DIR
from .common import get_conn, create_server_context
import pytest

server = create_server_context()

def test_user_creation(server):
    s = subprocess.check_output(['lfss-user', 'add', 'u0', 'test', '--admin', '--max-storage', '1k'], cwd=SANDBOX_DIR)
    s = s.decode()
    assert 'User created' in s, "User creation failed"
    c = get_conn('u0')
    assert c.whoami().is_admin, "User is not admin"
    assert c.whoami().username == 'u0', "Username is not correct"
    assert c.whoami().max_storage == 1024, "Max storage is not correct"

def test_upload(server):
    c = get_conn('u0')
    blob = os.urandom(1024 + 1)
    with pytest.raises(Exception, match='413'):
        c.put('u0/test-max-upload.bin', blob)
    assert not c.exists('u0/test-max-upload.bin')
