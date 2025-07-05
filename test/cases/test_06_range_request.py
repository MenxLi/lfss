import subprocess
import os
from ..config import SANDBOX_DIR
from lfss.eng.config import LARGE_FILE_BYTES
from .common import get_conn, create_server_context
import pytest

server = create_server_context()

def test_user_creation(server):
    s = subprocess.check_output(['lfss-user', 'add', 'u0', 'test'], cwd=SANDBOX_DIR)
    s = s.decode()
    assert 'User created' in s, "User creation failed"
    c = get_conn('u0')
    assert c.whoami().username == 'u0', "Username is not correct"

def test_small(server):
    c = get_conn('u0')
    blob = os.urandom(1024)
    c.put('u0/1.bin', blob)
    partial_blob = c.get_partial('u0/1.bin', 0, 1023)
    assert partial_blob == blob, "Partial blob is not correct"

    for (s, e) in [(0, 0), (10, 20), (25, 32), (1023, 1023)]:
        partial_blob = c.get_partial('u0/1.bin', s, e)
        assert partial_blob == blob[s:e+1], "Partial blob is not correct"
    
    partial_blob = c.get_partial('u0/1.bin', -1, 10)
    assert partial_blob == blob[:11], "Partial blob is not correct"

    partial_blob = c.get_partial('u0/1.bin', 10, -1)
    assert partial_blob == blob[10:], "Partial blob is not correct"

def test_large(server):
    c = get_conn('u0')
    fsize = LARGE_FILE_BYTES + 1
    blob = os.urandom(fsize)
    c.put('u0/1l.bin', blob)
    partial_blob = c.get_partial('u0/1l.bin', 0, fsize - 1)
    assert partial_blob == blob, "Partial blob is not correct"

    partial_blob = c.get_partial('u0/1l.bin', 10, 20)
    assert partial_blob == blob[10:21], "Partial blob is not correct"

    for (s, e) in [(0, 0), (10, 20), (25, 32), (fsize // 2, fsize - 1), (fsize - 1, fsize - 1)]:
        partial_blob = c.get_partial('u0/1l.bin', s, e)
        assert partial_blob == blob[s:e+1], "Partial blob is not correct"
    
    partial_blob = c.get_partial('u0/1l.bin', -1, 10)
    assert partial_blob == blob[:11], "Partial blob is not correct"
    
    partial_blob = c.get_partial('u0/1l.bin', 10, -1)
    assert partial_blob == blob[10:], "Partial blob is not correct"

def test_invalid_range(server):
    c = get_conn('u0')
    blob = os.urandom(1024)
    c.put('u0/2.bin', blob)
    partial_blob = c.get_partial('u0/2.bin', 1023, 1023)
    assert partial_blob == blob[1023:1024], "Partial blob is not correct"
    with pytest.raises(Exception, match='416'):
        partial_blob = c.get_partial('u0/2.bin', 0, 1024)
    with pytest.raises(Exception, match='416'):
        partial_blob = c.get_partial('u0/2.bin', 1024, 1025)
    with pytest.raises(Exception, match='416'):
        partial_blob = c.get_partial('u0/2.bin', 200, 100)


