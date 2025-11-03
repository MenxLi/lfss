
import subprocess
import pytest
from lfss.api import AccessLevel, DirConfig
from .common import create_server_context, get_conn
from ..config import SANDBOX_DIR

server = create_server_context()

def test_init_user_creation(server):
    subprocess.check_output(['lfss-user', 'add', 'u0', 'test', "--admin"], cwd=SANDBOX_DIR)

    u0 = get_conn('u0')
    u0.add_user('u1', 'test', permission='public')
    u0.add_user('u2', 'test')
    u0.add_user('u3', 'test')

def test_index_file_creation(server):
    u1 = get_conn('u1')
    u1.set_dir_config(
        'u1/test/', 
        DirConfig().
            set_index('index.json').
            set_access('u2', AccessLevel.WRITE).
            set_access('u3', AccessLevel.NONE)
        )

def test_index_file_access(server):
    u1 = get_conn('u1')
    u2 = get_conn('u2')
    u3 = get_conn('u3')

    u1.put_json('u1/test/index.json', {'message': 'Hello from index file!'})

    # u2 should be able to access index file
    resp = u2.get_json('u1/test/')
    assert resp['message'] == 'Hello from index file!', "Index file access failed for u2"

    # u3 should not be able to access index file
    with pytest.raises(Exception, match="403"):
        resp = u3.get_json('u1/test/')

    # now change u1 permission to private
    get_conn("u0").set_user('u1', permission='private')
    # u2 should still be able to access index file
    resp = u2.get_json('u1/test/')
    assert resp['message'] == 'Hello from index file!', "Index file access failed for u2 after permission change"
    
    # u3 should NOT be able to access index file
    with pytest.raises(Exception, match="403"):
        resp = u3.get_json('u1/test/')

def test_write_access(server):
    u2 = get_conn('u2')
    # u2 should be able to write to the directory
    u2.put_json('u1/test/data_from_u2.json', {'data': 'This is from u2'})
    resp = u2.get_json('u1/test/data_from_u2.json')
    assert resp['data'] == 'This is from u2', "Write access failed for u2"

    u3 = get_conn('u3')
    # u3 should NOT be able to write to the directory
    with pytest.raises(Exception, match="403"):
        u3.put_json('u1/test/data_from_u3.json', {'data': 'This is from u3'})

def test_config_override_forbidden(server):
    u2 = get_conn('u2')
    # u2 should not be able read or write the config file
    with pytest.raises(Exception, match="403"):
        u2.get_json('u1/test/.lfssdir.json')
    with pytest.raises(Exception, match="403"):
        u2.put_json('u1/test/.lfssdir.json', {'index': 'new_index.json'})

def test_alias_override(server):
    u0 = get_conn('u0')
    u0.set_peer('u3', 'u1', 'write')

    u3 = get_conn('u3')
    # now u3 should still be able to read and write to the directory due to alias override
    with pytest.raises(Exception, match="403"):
        resp = u3.get_json('u1/test/')

    with pytest.raises(Exception, match="403"):
        u3.get_json('u1/test/.lfssdir.json')

    with pytest.raises(Exception, match="403"):
        u3.put_json('u1/test/data_from_u3.json', {'data': 'This is from u3 after alias override'})

def test_copy_out_attack(server):
    u2 = get_conn('u2')
    # u2 tries to make a copy of the config file by copy whole directory out
    u2.copy('u1/test/', 'u2/test_copy/')
    assert not u2.exists('u2/test_copy/.lfssdir.json'), "Directory config file copy attack should have been prevented"

def test_copy_in_attack(server):
    u0 = get_conn('u0')
    u0.set_peer('u3', 'u1', 'none')          # revoke all access for u3
    u0.set_peer('u2', 'u1', 'write')         # grant write access for u2

    u1 = get_conn('u1')
    u1.delete('u1/test/')                   # clean up first

    u2 = get_conn('u2')
    u2.set_dir_config('u2/test/', DirConfig().set_index('index.json').set_access('u3', AccessLevel.WRITE))
    u2.put_json('u2/test/index.json', {'message': 'Hacked by u2'})
    u2.copy('u2/test/', 'u1/test/')

    assert not u2.exists('u1/test/.lfssdir.json'), "Directory config file copy attack should have been prevented"

    u3 = get_conn('u3')
    # u3 should still NOT be able to access the directory
    with pytest.raises(Exception, match="403"):
        resp = u3.put_json('u1/test/data_from_u3.json', {'data': 'This is from u3 after copy attack'})
