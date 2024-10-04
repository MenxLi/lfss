from lfss.client.api import Connector, FileRecord
from concurrent.futures import ThreadPoolExecutor
import random, string

def _random_string(length: int) -> str:
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def test_put_get_delete(conn: Connector):
    random_path = '/'.join([_random_string(8) for _ in range(random.randint(1, 4))])
    random_ext = random.choice(['.txt', '.bin', '.jpg', '.png', '.mp4', ""])

    path = f'test/{random_path}{random_ext}'
    random_data = _random_string(random.randint(1, 1024)).encode()

    try:
        assert conn.put(path, random_data)
        assert conn.get(path) == random_data
        assert (meta:=conn.get_metadata(path))
        assert isinstance(meta, FileRecord)
        assert meta.file_size == len(random_data)
        conn.delete(path)
        assert not conn.get_metadata(path)
        assert not conn.get(path)
        return True
    except Exception as e:
        print(f"[error] Failed test for path: {path}")
        return False

def concurrency_test(conn: Connector, n: int) -> int:
    with ThreadPoolExecutor(max_workers=16) as executor:
        results = list(executor.map(lambda _: test_put_get_delete(conn), range(n)))
    return sum(results)

if __name__ == '__main__':
    conn = Connector()
    n_tests = 1000
    n_success = concurrency_test(conn, n_tests)
    print(f"Success: {n_success}/{n_tests}")