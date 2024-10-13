import subprocess
import os, pathlib
import tempfile
from ..config import SANDBOX_DIR
from .common import get_conn, create_server_context
from lfss.client import upload_directory, download_directory
import pytest

server = create_server_context()

@pytest.fixture(scope='module')
def temp_dir():
    def _prepare_files(d):
        files = [ pathlib.Path(f"{d}/f{i}.bin") for i in range(5) ] + [ pathlib.Path(f"{d}/d{i}/f{j}.bin") for i in range(5) for j in range(5) ]
        for f in files:
            f.parent.mkdir(exist_ok=True)
            with open(f, 'wb') as fp:
                rand_data = os.urandom(1024)
                fp.write(rand_data)
        return files
    with tempfile.TemporaryDirectory() as d_str:
        d = pathlib.Path(d_str)
        _prepare_files(d)
        yield d

def test_user_creation(server):
    s = subprocess.check_output(['lfss-user', 'add', 'u0', 'test', '--admin', '--max-storage', '1G'], cwd=SANDBOX_DIR)
    s = s.decode()
    assert 'User created' in s, "User creation failed"
    c = get_conn('u0')
    assert c.whoami().is_admin, "User is not admin"
    assert c.whoami().username == 'u0', "Username is not correct"
    assert c.whoami().max_storage == 1024**3, "Max storage is not correct"

def test_dir_upload(server, temp_dir):
    c = get_conn('u0')
    failed_path = upload_directory(c, temp_dir, 'u0/test-dir-upload/', n_concurrent=4, verbose=True)
    assert not failed_path, "Failed to upload some files"

def test_dir_download(server, temp_dir):
    c = get_conn('u0')
    with tempfile.TemporaryDirectory() as d:
        failed_path = download_directory(c, 'u0/test-dir-upload/', d, n_concurrent=4, verbose=True)
        assert not failed_path, "Failed to download some files: " + str(failed_path)
        for f in pathlib.Path(temp_dir).rglob('*.bin'):
            assert f.exists(), f"File {f} not found"
            rel_path = f.relative_to(temp_dir)
            assert (d / rel_path).exists(), f"File {f} not found in download directory"
            with open(f, 'rb') as fp:
                assert fp.read() == open(d / rel_path, 'rb').read(), f"File {f} content mismatch"