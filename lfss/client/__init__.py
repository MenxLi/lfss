import os, time, pathlib
from threading import Lock
from .api import Connector
from ..src.bounded_pool import BoundedThreadPoolExecutor

def upload_file(
    connector: Connector, 
    file_path: str, 
    dst_url: str, 
    n_retries: int = 0, 
    interval: float = 0, 
    verbose: bool = False, 
    **put_kwargs
    ):
    this_try = 0
    while this_try <= n_retries:
        try:
            with open(file_path, 'rb') as f:
                blob = f.read()
            connector.put(dst_url, blob, **put_kwargs)
            break
        except Exception as e:
            if isinstance(e, KeyboardInterrupt):
                raise e
            if verbose:
                print(f"Error uploading {file_path}: {e}, retrying...")
            this_try += 1
        finally:
            time.sleep(interval)

    if this_try > n_retries:
        if verbose:
            print(f"Failed to upload {file_path} after {n_retries} retries.")
        return False
    return True

def upload_directory(
    connector: Connector, 
    directory: str, 
    path: str, 
    n_concurrent: int = 1,
    n_retries: int = 0,
    interval: float = 0,
    verbose: bool = False,
    **put_kwargs
    ) -> list[str]:
    assert path.endswith('/'), "Path must end with a slash."
    if path.startswith('/'):
        path = path[1:]
    directory = str(directory)
    
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

        if not upload_file(
            connector, file_path, dst_path, 
            n_retries=n_retries, interval=interval, verbose=verbose, **put_kwargs
            ):
            faild_files.append(file_path)

    with BoundedThreadPoolExecutor(n_concurrent) as executor:
        for root, dirs, files in os.walk(directory):
            for file in files:
                executor.submit(put_file, os.path.join(root, file))

    return faild_files

def download_file(
    connector: Connector, 
    src_url: str, 
    file_path: str, 
    n_retries: int = 0, 
    interval: float = 0, 
    verbose: bool = False, 
    overwrite: bool = False
    ):
    this_try = 0
    while this_try <= n_retries:
        if not overwrite and os.path.exists(file_path):
            if verbose:
                print(f"File {file_path} already exists, skipping download.")
            return True
        try:
            blob = connector.get(src_url)
            if not blob:
                return False
            pathlib.Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'wb') as f:
                f.write(blob)
            break
        except Exception as e:
            if isinstance(e, KeyboardInterrupt):
                raise e
            if verbose:
                print(f"Error downloading {src_url}: {e}, retrying...")
            this_try += 1
        finally:
            time.sleep(interval)

    if this_try > n_retries:
        if verbose:
            print(f"Failed to download {src_url} after {n_retries} retries.")
        return False
    return True

def download_directory(
    connector: Connector,
    src_path: str,
    directory: str,
    n_concurrent: int = 1,
    n_retries: int = 0,
    interval: float = 0,
    verbose: bool = False,
    overwrite: bool = False
    ) -> list[str]:

    directory = str(directory)

    if not src_path.endswith('/'):
        src_path += '/'
    if not directory.endswith(os.sep):
        directory += os.sep
    
    _counter = 0
    _counter_lock = Lock()
    failed_files = []
    def get_file(src_url):
        nonlocal _counter, failed_files
        with _counter_lock:
            _counter += 1
            this_count = _counter
            dst_path = f"{directory}{os.path.relpath(src_url, src_path)}"
            if verbose:
                print(f"[{this_count}] Downloading {src_url} to {dst_path}")

        if not download_file(
            connector, src_url, dst_path, 
            n_retries=n_retries, interval=interval, verbose=verbose, overwrite=overwrite
            ):
            failed_files.append(src_url)
        
    with BoundedThreadPoolExecutor(n_concurrent) as executor:
        for file in connector.list_path(src_path, flat=True).files:
            executor.submit(get_file, file.url)
    return failed_files