import pytest
import subprocess
from lfss.src.bounded_pool import BoundedThreadPoolExecutor
from .common import get_conn, create_server_context
from ..config import SANDBOX_DIR

server = create_server_context()

def test_user_creation(server):
    s = subprocess.check_output(['lfss-user', 'add', 'u0', 'test', '--admin', '--max-storage', '1G'], cwd=SANDBOX_DIR)
    s = s.decode()
    assert 'User created' in s, "User creation failed {s}".format(s=s)
    c = get_conn('u0')
    assert c.whoami().is_admin, "User is not admin"
    assert c.whoami().username == 'u0', "Username is not correct"
    assert c.whoami().max_storage == 1024**3, "Max storage is not correct"

    s = subprocess.check_output(['lfss-user', 'add', 'u1', 'test', '--permission', 'public'], cwd=SANDBOX_DIR)
    s = s.decode()
    assert 'User created' in s, "User creation failed {s}".format(s=s)

def upload_basic(username: str):
    c = get_conn(username)
    c.put(f'{username}/test1.txt', b'hello world 1')
    c.put(f'{username}/a/test2.txt', b'hello world 2')
    c.put(f'{username}/a/test3.txt', b'hello world 3')
    c.put(f'{username}/a/b/test4.txt', b'hello world 4')
    c.put(f"{username}/b/test5.txt", b'hello world 5')
    p_list = c.list_path(f'{username}/')
    assert len(p_list.dirs) == 2, "Directory count is not correct"
    assert len(p_list.files) == 1, "File count is not correct"

def test_upload(server):
    upload_basic('u0')
    upload_basic('u1')

def test_dir_count(server):
    c = get_conn('u0')
    assert c.count_dirs('u0/') == 2, "Directory count is not correct"
    assert c.count_dirs('u0/a/') == 1, "Directory count is not correct"

def test_dir_list(server):
    c = get_conn('u0')
    u0_dir_lst = c.list_dirs('u0/', order_by='dirname')
    assert len(u0_dir_lst) == 2, "Directory count is not correct"
    assert u0_dir_lst[0].url == 'u0/a/', "Directory name is not correct"
    assert u0_dir_lst[1].url == 'u0/b/', "Directory name is not correct"

    u0_dir_lst_rev = c.list_dirs('u0/', order_by='dirname', order_desc=True)
    assert len(u0_dir_lst_rev) == 2, "Directory count is not correct"
    assert u0_dir_lst_rev[0].url == 'u0/b/', "Directory name is not correct"
    assert u0_dir_lst_rev[1].url == 'u0/a/', "Directory name is not correct"

    u0_dir_lst_rev_lim = c.list_dirs('u0/', order_by='dirname', order_desc=True, limit=1)
    assert len(u0_dir_lst_rev_lim) == 1, "Directory count is not correct"
    assert u0_dir_lst_rev_lim[0].url == 'u0/b/', "Directory name is not correct"

    u0_dir_lst_rev_lim = c.list_dirs('u0/', order_by='dirname', order_desc=True, limit=1, offset=1)
    assert len(u0_dir_lst_rev_lim) == 1, "Directory count is not correct"
    assert u0_dir_lst_rev_lim[0].url == 'u0/a/', "Directory name is not correct"

def test_file_count(server):
    c = get_conn('u0')
    assert c.count_files('u0/') == 1, "File count is not correct"
    assert c.count_files('u0/a/', flat=True) == 3, "File count is not correct"
    assert c.count_files('u0/a/', flat=False) == 2, "File count is not correct"

def test_file_list(server):
    c = get_conn('u0')
    u0_file_lst = c.list_files('u0/a/', order_by='url')
    assert len(u0_file_lst) == 2, "File count is not correct"
    assert u0_file_lst[0].url == 'u0/a/test2.txt', "File name is not correct"

    u0_file_lst_rev = c.list_files('u0/a/', order_by='url', order_desc=True)
    assert len(u0_file_lst_rev) == 2, "File count is not correct"
    assert u0_file_lst_rev[0].url == 'u0/a/test3.txt', "File name is not correct"
    
    u0_file_lst_rev_lim = c.list_files('u0/a/', order_by='url', order_desc=True, limit=1)
    assert len(u0_file_lst_rev_lim) == 1, "File count is not correct"
    assert u0_file_lst_rev_lim[0].url == 'u0/a/test3.txt', "File name is not correct"
    
    u0_file_lst_rev_lim = c.list_files('u0/a/', order_by='url', order_desc=True, limit=1, offset=1)
    assert len(u0_file_lst_rev_lim) == 1, "File count is not correct"
    assert u0_file_lst_rev_lim[0].url == 'u0/a/test2.txt', "File name is not correct"
    
    u0_file_lst_flat = c.list_files('u0/a/', order_by='url', order_desc=True, flat=True)
    assert len(u0_file_lst_flat) == 3, "File count is not correct"

def test_forbidden(server):
    c = get_conn('u1')
    with pytest.raises(Exception, match='403'):
        c.list_files('u0/a/', order_by='url', order_desc=True)

def _test_shorthand_list(server):
    import time
    c = get_conn('u0')
    
    def upload_one_file(i: int):
        c.put(f'u0/test-sl-{i}.txt', f'hello world {i}'.encode(), conflict='overwrite')
    
    s_time = time.time()
    concurrent = 32
    with c.session(concurrent):
        with BoundedThreadPoolExecutor(concurrent) as executor:
            for i in range(10001):
                executor.submit(upload_one_file, i)
    e_time = time.time()
    print(f"Time taken for file upload: {e_time - s_time}")

    with pytest.raises(Exception, match='400'):
        c.list_path('u0/')