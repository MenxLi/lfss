from concurrent.futures import ThreadPoolExecutor
from threading import Lock
import argparse
import time
from lfss.api import Connector

c = Connector()

def read_single_file(url):
    global counter, batch_size_sum, batch_start_time
    try:
        b = c.get(url)
        assert b is not None

        with lock:
            counter += 1
            batch_size_sum += len(b)
            if counter % 100 == 0:
                print(f"Read {counter} files, avg-size: {batch_size_sum / 1024 / 1024 / 100:.2f} MB, speed: {batch_size_sum / (time.time() - batch_start_time) / 1024 / 1024:.2f} MB/s")
                batch_start_time = time.time()
                batch_size_sum = 0

    except Exception as e:
        print("[ERROR] Failed to read: ", url, e)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('path', type=str, help='Path to read')
    parser.add_argument('-j', '--jobs', type=int, default=32)
    args = parser.parse_args()

    counter = 0
    batch_size_sum = 0
    batch_start_time = time.time()
    lock = Lock()

    with c.session(pool_size=args.jobs):
        file_list = c.list_files(args.path, flat=True, limit=int(1e6))
        path_meta = c.get_meta(args.path)
        assert path_meta is not None, "Path not found"
        total_bytes = path_meta.size    # type: ignore
        s_time = time.time()
        with ThreadPoolExecutor(max_workers=args.jobs) as executor:
            executor.map(read_single_file, [f.url for f in file_list])
        e_time = time.time()

    print(f"Total size: {total_bytes} bytes, num-files: {len(file_list)}, time: {e_time - s_time:.2f}s, avg-speed: {total_bytes / (e_time - s_time) / 1024 / 1024:.2f} MB/s")
