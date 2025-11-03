
import subprocess
import pytest
from lfss.eng.datatype import FileReadPermission
from .common import create_server_context, get_conn
from ..config import SANDBOX_DIR

server = create_server_context()

def test_init_user_creation(server):
    subprocess.check_output(['lfss-user', 'add', 'u0', 'test', "--admin"], cwd=SANDBOX_DIR)

def test_user1_creation(server):
    c0 = get_conn('u0')
    c0.add_user('u1', 'test', max_storage='500M')
    assert c0.query_user('u1').username == 'u1', "User u1 creation failed"
    assert c0.query_user('u1').max_storage == 500*1024*1024, "User u1 max storage is not correct"

    c1 = get_conn('u1')
    assert c0.query_user('u1').credential == c1.config.token

def test_user1_update(server):
    c0 = get_conn('u0')
    c0.set_user('u1', admin=True, max_storage='2G', permission=FileReadPermission.PROTECTED)
    u1_info = c0.query_user('u1')
    assert u1_info.is_admin, "User u1 should be admin now"
    assert u1_info.max_storage == 2*1024*1024*1024, "User u1 max storage is not correct"
    assert u1_info.permission == FileReadPermission.PROTECTED, "User u1 permission is not correct"

    c0.set_user('u1', admin=False, permission='public')
    u1_info = c0.query_user('u1')
    assert not u1_info.is_admin, "User u1 should not be admin now"
    assert u1_info.permission == FileReadPermission.PUBLIC, "User u1 permission is not correct"

def test_nonadmin_user_creation_failure(server):
    c1 = get_conn('u1')
    with pytest.raises(Exception, match="403"):
        c1.add_user('u2', 'test')

def test_user_deletion(server):
    c0 = get_conn('u0')
    c0.delete_user('u1')
    with pytest.raises(Exception, match="404"):
        c0.query_user('u1')

def test_set_peer_access(server):
    c0 = get_conn('u0')
    c0.add_user('u2', 'test')
    c0.add_user('u3', 'test')

    c0.set_peer('u2', 'u3', 'READ')

    with pytest.raises(Exception, match="400"):
        c0.set_peer('u2', 'u3', 'GUEST')
    
    assert c0.peers(as_user='u2', admin=False)[0].username == 'u3', "Peer listing failed"
    assert c0.peers(as_user='u3', incoming=True, admin=False)[0].username == 'u2', "Peer listing failed"