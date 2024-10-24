from concurrent.futures import ProcessPoolExecutor
import time
import multiprocessing
from multiprocessing.managers import ValueProxy
from threading import Lock
import uuid
import random
import argparse
import time
from lfss.client import Connector
from lfss.src.utils import parse_storage_size

c = Connector()

def put_single_file(
    path: str, size: int, 
    shared_counter: ValueProxy[int], 
    shared_size: ValueProxy[int], 
    shared_batch_start_time: ValueProxy[float], 
    lock: Lock
    ):
    assert size > 0
    assert path.endswith('/')

    _blob = bytearray(random.getrandbits(8) for _ in range(size))
    blob = bytes(_blob)
    fname = uuid.uuid4().hex
    try:
        c.put(path + fname, blob)
    except Exception as e:
        print("[ERROR] Failed to write: ", path, e)

    with lock:
        shared_counter.value += 1
        shared_size.value += size
        if shared_counter.value % 100 == 0:
            print(f"Written {shared_counter.value} files, avg-size: {shared_size.value / 1024 / 1024 / 100:.2f} MB, speed: {shared_size.value / (time.time() - shared_batch_start_time.value) / 1024 / 1024:.2f} MB/s")
            shared_size.value = 0
            shared_batch_start_time.value = time.time()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('path', type=str, help='Path to read')
    parser.add_argument('-j', '--jobs', type=int, default=32)
    parser.add_argument('-n', '--num-files', type=int, default=1000)
    parser.add_argument('-s', '--size', type=parse_storage_size, default=1024*1024)
    parser.add_argument('--delete', action='store_true', help='Delete path after writing, be careful!!')
    args = parser.parse_args()

    c = Connector()
    if args.delete and c.get_metadata(args.path):
        ans = input(f"Path: {args.path} already exists, are you sure you wan to delete it after testing? (y/n): ")
        if ans.lower() != 'y':
            print("Aborted.")
            exit(1)

    with multiprocessing.Manager() as manager:
        lock = manager.Lock()
        counter = manager.Value('i', 0)
        size = manager.Value('i', 0)
        batch_start_time = manager.Value('d', time.time())

        with ProcessPoolExecutor(max_workers=args.jobs) as executor:
            tasks = [
                executor.submit(put_single_file, args.path, args.size, counter, size, batch_start_time, lock)
                for _ in range(args.num_files)
            ]
            for task in tasks:
                task.result()
    
    if args.delete:
        print("Deleting path: ", args.path)
        c.delete(args.path)
    print("Done.")
