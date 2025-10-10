from lfss.eng.utils import hash_credential
from lfss.api import Client
from ..config import SERVER_PORT, SANDBOX_DIR, clear_sandbox
from ..start_server import Server
import pytest, os

def get_conn(username, password = 'test'):
    return Client(f"http://localhost:{SERVER_PORT}", token=hash_credential(username, password))

def create_server_context():
    # clear environment variables
    os.environ.pop('LFSS_DATA', None)
    os.environ.pop('LFSS_LARGE_FILE', None)
    os.environ['LFSS_DEBUG'] = '1'
    os.environ['LFSS_WEBDAV'] = '1'

    @pytest.fixture(scope='module')
    def server():
        s = Server()
        s.start(cwd=str(SANDBOX_DIR), port=SERVER_PORT)
        # TODO: Somehow the server is not ready when the test starts...
        import time; time.sleep(1)
        yield s
        s.stop()
        time.sleep(1)
        clear_sandbox()
    return server
