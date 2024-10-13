import subprocess
import random
from concurrent.futures import ThreadPoolExecutor
from ..config import SANDBOX_DIR
from .common import get_conn, create_server_context

server = create_server_context()

def test_user_creation(server):
    s = subprocess.check_output(['lfss-user', 'add', 'u0', 'test', '--admin', '--max-storage', '1G'], cwd=SANDBOX_DIR)
    s = s.decode()
    assert 'User created' in s, "User creation failed"
    c = get_conn('u0')
    assert c.whoami().is_admin, "User is not admin"
    assert c.whoami().username == 'u0', "Username is not correct"
    assert c.whoami().max_storage == 1024**3, "Max storage is not correct"

special_chars = '!@#$%^&*()_+-:.,<>? 你好あア'
def get_fpath(charset = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890' + special_chars)->str:
    def random_string(k = 10) -> str:
        return ''.join(random.choices(charset, k=k))
    suffix = random.choice(['.txt', '.bin', '.dat', '.json', '.xml', '.csv', '.html', '.md', ''])
    while True:
        path = f'{random_string(48)}' + suffix
        if not '..' in path:
            break
    return path

def put_get_delete(username: str, path: str):
    path = f"{username}/{path}"
    ascii_charset = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890!@#$%^&*()_+'
    def random_string(k = 10) -> str:
        return ''.join(random.choices(ascii_charset, k=k))

    c = get_conn(username)
    content = random_string(random.randint(1, 1024*1024*16)).encode('ascii')
    c.put(path, content)
    assert c.get(path) == content, "Put get failed"
    c.delete(path)
    assert c.get(path) is None, "Delete failed"


def test_fname(server):
    # use some wired characters...
    pathes = set([get_fpath(special_chars) for _ in range(3)])
    for i in pathes:
        put_get_delete('u0', i)

def test_concurrent(server):
    def task(username: str, path: str):
        put_get_delete(username, path)
    pathes = set([get_fpath() for i in range(16)])
    with ThreadPoolExecutor(max_workers=8) as executor:
        tasks = []
        for p in pathes:
            tasks.append(executor.submit(task, 'u0', p))
        for t in tasks:
            t.result()