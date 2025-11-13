
import subprocess
import pytest
from lfss.api import AccessLevel
from .common import create_server_context, get_conn, get_conn_bytoken, get_conn
from ..config import SANDBOX_DIR

server = create_server_context()
v0_name = ""
v0_token = ""
v1_name = ""
v1_token = ""


def test_init_user_creation(server):
    global v0_token, v1_token, v0_name, v1_name
    subprocess.check_output(['lfss-user', 'add', 'u0', 'test', "--admin"], cwd=SANDBOX_DIR)

    u0 = get_conn('u0')
    u0.add_user('u1', 'test', permission='public')

    v0 = u0.add_virtual_user(tag="session1", peers={AccessLevel.READ: ['u1']}, expire='10d')
    v0_token = v0.credential
    v0_name = v0.username

    v1 = u0.add_virtual_user(peers=f"write:u1,{v0_name}")
    v1_token = v1.credential
    v1_name = v1.username

def test_v1_put(server):
    v1 = get_conn_bytoken(v1_token)

    with pytest.raises(Exception, match="403"):
        v1.put_json(f'{v1_name}/data.json', {'message': 'Hello from v0'})
    
    with pytest.raises(Exception, match="403"):
        v1.put_json(f'{v0_name}/data.json', {'message': 'Hello from v0'})
    
    v1.put_json('u1/data_from_v1.json', {'message': 'Hello from v1'})

def test_admin_put(server):
    u0 = get_conn('u0')
    with pytest.raises(Exception, match="403"):
        u0.put_json(f'{v0_name}/data.json', {'message': 'Hello from admin to v0'})

def test_expire(server):
    u0 = get_conn('u0')
    v3_info = u0.add_virtual_user(tag="toexpire", expire='2s', peers={AccessLevel.WRITE: ['u1']}, max_storage=10240)

    v3 = get_conn_bytoken(v3_info.credential)
    v3.put_json(f'u1/data.json', {'message': 'Hello from v3'})

    import time
    time.sleep(2)

    with pytest.raises(Exception, match="401"):
        v3.put_json(f'u1/data.json', {'message': 'Hello from v3'})
