import os, time
from threading import Lock
from concurrent.futures import ThreadPoolExecutor
from .api import Connector

def upload_directory(
    connector: Connector, 
    directory: str, 
    path: str, 
    n_concurrent: int = 1,
    n_reties: int = 0,
    interval: float = 0,
    verbose: bool = False,
    **put_kwargs
    ) -> list[str]:
    assert path.endswith('/'), "Path must end with a slash."
    if path.startswith('/'):
        path = path[1:]
    
    _counter = 0
    _counter_lock = Lock()

    faild_files = []
    def put_file(file_path):
        with _counter_lock:
            nonlocal _counter
            _counter += 1
            this_count = _counter
            dst_path = f"{path}{os.path.relpath(file_path, directory)}"
            if verbose:
                print(f"[{this_count}] Uploading {file_path} to {dst_path}")

        this_try = 0
        with open(file_path, 'rb') as f:
            blob = f.read()

        while this_try <= n_reties:
            try:
                connector.put(dst_path, blob, **put_kwargs)
                break
            except Exception as e:
                if verbose:
                    print(f"[{this_count}] Error uploading {file_path}: {e}, retrying...")
                this_try += 1
            finally:
                time.sleep(interval)

        if this_try > n_reties:
            faild_files.append(file_path)
            if verbose:
                print(f"[{this_count}] Failed to upload {file_path} after {n_reties} retries.")

    with ThreadPoolExecutor(n_concurrent) as executor:
        for root, dirs, files in os.walk(directory):
            for file in files:
                executor.submit(put_file, os.path.join(root, file))

    return faild_files