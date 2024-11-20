from lfss.src.utils import hash_credential
from lfss.api import Connector
from ..config import SERVER_PORT, SANDBOX_DIR, clear_sandbox
from ..start_server import Server
import pytest, os

def get_conn(username, password = 'test'):
    return Connector(f"http://localhost:{SERVER_PORT}", token=hash_credential(username, password))

def upload_basic(username: str):
    c = get_conn(username)
    c.put(f'{username}/test1.txt', b'hello world 1')
    c.put(f'{username}/a/test2.txt', b'hello world 2')
    c.put(f'{username}/a/test3.txt', b'hello world 3')
    c.put(f'{username}/a/b/test4.txt', b'hello world 4')
    p_list = c.list_path(f'{username}/')
    assert len(p_list.dirs) == 1, "Directory count is not correct"
    assert len(p_list.files) == 1, "File count is not correct"
    assert p_list.dirs[0].url == f'{username}/a/', "Directory name is not correct"
    assert p_list.files[0].url == f'{username}/test1.txt', "File name is not correct"

def create_server_context():
    # clear environment variables
    os.environ.pop('LFSS_DATA', None)
    os.environ.pop('LFSS_LARGE_FILE', None)

    @pytest.fixture(scope='module')
    def server():
        s = Server()
        s.start(cwd=str(SANDBOX_DIR), port=SERVER_PORT)
        # TODO: Somehow the server is not ready when the test starts...
        import time; time.sleep(1)
        yield s
        s.stop()
        clear_sandbox()
    return server
