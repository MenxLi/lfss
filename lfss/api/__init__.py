import os, time, pathlib
from threading import Lock
from .connector import Connector
from ..src.datatype import FileRecord
from ..src.utils import decode_uri_compnents
from ..src.bounded_pool import BoundedThreadPoolExecutor

def upload_file(
    connector: Connector, 
    file_path: str, 
    dst_url: str, 
    n_retries: int = 0, 
    interval: float = 0, 
    verbose: bool = False, 
    **put_kwargs
    ) -> tuple[bool, str]:
    this_try = 0
    error_msg = ""
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
                error_msg = str(e)
            this_try += 1
        finally:
            time.sleep(interval)

    if this_try > n_retries:
        if verbose:
            print(f"Failed to upload {file_path} after {n_retries} retries.")
        return False, error_msg
    return True, error_msg

def upload_directory(
    connector: Connector, 
    directory: str, 
    path: str, 
    n_concurrent: int = 1,
    n_retries: int = 0,
    interval: float = 0,
    verbose: bool = False,
    **put_kwargs
    ) -> list[tuple[str, str]]:
    assert path.endswith('/'), "Path must end with a slash."
    if path.startswith('/'):
        path = path[1:]
    directory = str(directory)
    
    _counter = 0
    _counter_lock = Lock()

    faild_items = []
    def put_file(c: Connector, file_path):
        with _counter_lock:
            nonlocal _counter
            _counter += 1
            this_count = _counter
            dst_path = f"{path}{os.path.relpath(file_path, directory)}"
            if verbose:
                print(f"[{this_count}] Uploading {file_path} to {dst_path}")

        if not (res:=upload_file(
            c, file_path, dst_path, 
            n_retries=n_retries, interval=interval, verbose=verbose, **put_kwargs
            ))[0]:
            faild_items.append((file_path, res[1]))

    with connector.session(n_concurrent) as c:
        with BoundedThreadPoolExecutor(n_concurrent) as executor:
            for root, dirs, files in os.walk(directory):
                for file in files:
                    executor.submit(put_file, c, os.path.join(root, file))

    return faild_items

def download_file(
    connector: Connector, 
    src_url: str, 
    file_path: str, 
    n_retries: int = 0, 
    interval: float = 0, 
    verbose: bool = False, 
    overwrite: bool = False
    ) -> tuple[bool, str]:
    this_try = 0
    error_msg = ""
    while this_try <= n_retries:
        if not overwrite and os.path.exists(file_path):
            if verbose:
                print(f"File {file_path} already exists, skipping download.")
            return True, error_msg
        try:
            blob = connector.get(src_url)
            if blob is None:
                error_msg = "File not found."
                return False, error_msg
            pathlib.Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'wb') as f:
                f.write(blob)
            break
        except Exception as e:
            if isinstance(e, KeyboardInterrupt):
                raise e
            if verbose:
                print(f"Error downloading {src_url}: {e}, retrying...")
                error_msg = str(e)
            this_try += 1
        finally:
            time.sleep(interval)

    if this_try > n_retries:
        if verbose:
            print(f"Failed to download {src_url} after {n_retries} retries.")
        return False, error_msg
    return True, error_msg

def download_directory(
    connector: Connector,
    src_path: str,
    directory: str,
    n_concurrent: int = 1,
    n_retries: int = 0,
    interval: float = 0,
    verbose: bool = False,
    overwrite: bool = False
    ) -> list[tuple[str, str]]:

    directory = str(directory)

    if not src_path.endswith('/'):
        src_path += '/'
    if not directory.endswith(os.sep):
        directory += os.sep
    
    _counter = 0
    _counter_lock = Lock()
    failed_items: list[tuple[str, str]] = []
    def get_file(c, src_url):
        nonlocal _counter, failed_items
        with _counter_lock:
            _counter += 1
            this_count = _counter
            dst_path = f"{directory}{os.path.relpath(decode_uri_compnents(src_url), decode_uri_compnents(src_path))}"
            if verbose:
                print(f"[{this_count}] Downloading {src_url} to {dst_path}")

        if not (res:=download_file(
            c, src_url, dst_path, 
            n_retries=n_retries, interval=interval, verbose=verbose, overwrite=overwrite
            ))[0]:
            failed_items.append((src_url, res[1]))
        
    batch_size = 10000
    file_list: list[FileRecord] = []
    with connector.session(n_concurrent) as c:
        file_count = c.count_files(src_path, flat=True)
        for offset in range(0, file_count, batch_size):
            file_list.extend(c.list_files(
                src_path, offset=offset, limit=batch_size, flat=True
            ))

        with BoundedThreadPoolExecutor(n_concurrent) as executor:
            for file in file_list:
                executor.submit(get_file, c, file.url)
    return failed_items