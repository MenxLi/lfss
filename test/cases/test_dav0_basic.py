import subprocess
from ..config import SANDBOX_DIR, SERVER_PORT
from .common import get_conn, create_server_context
import pytest
import webdav3.client as wc

server = create_server_context()

@pytest.fixture(scope='module')
def client():
    config = {
        'webdav_hostname': f'http://localhost:{SERVER_PORT}',
        'webdav_login': 'u0',
        'webdav_password': 'test',
    }
    client = wc.Client(config)
    return client

def test_user_creation(server):
    s = subprocess.check_output(['lfss-user', 'add', 'u0', 'test', "--admin"], cwd=SANDBOX_DIR)
    s = s.decode()
    assert 'User created' in s, "User creation failed"
    c = get_conn('u0')
    assert c.whoami().username == 'u0', "Username is not correct"
    assert c.whoami().id == 1, "User id is not correct"

    subprocess.check_output(['lfss-user', 'add', 'u1', 'test'], cwd=SANDBOX_DIR)

def test_root_list(server, client: wc.Client):
    items = client.list('/u0')
    assert len(items) == 0