import datetime
import urllib.parse
import asyncio
import functools
import hashlib

def hash_credential(username: str, password: str):
    return hashlib.sha256((username + password).encode()).hexdigest()

def encode_uri_compnents(path: str):
    path_sp = path.split("/")
    mapped = map(lambda x: urllib.parse.quote(x), path_sp)
    return "/".join(mapped)

def decode_uri_compnents(path: str):
    path_sp = path.split("/")
    mapped = map(lambda x: urllib.parse.unquote(x), path_sp)
    return "/".join(mapped)

def ensure_uri_compnents(path: str):
    """ Ensure the path components are safe to use """
    return encode_uri_compnents(decode_uri_compnents(path))

def debounce_async(delay: float = 0):
    """ Debounce the async procedure """
    def debounce_wrap(func):
        # https://docs.python.org/3/library/asyncio-task.html#asyncio.Task.cancel
        async def delayed_func(*args, **kwargs):
            await asyncio.sleep(delay)
            await func(*args, **kwargs)

        task_record: asyncio.Task | None = None
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            nonlocal task_record
            if task_record is not None:
                task_record.cancel()
            task_record = asyncio.create_task(delayed_func(*args, **kwargs))
            try:
                await task_record
            except asyncio.CancelledError:
                pass
        return wrapper
    return debounce_wrap

def format_last_modified(last_modified_gmt: str):
    """
    Format the last modified time to the [HTTP standard format](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Last-Modified)
    - last_modified_gmt: The last modified time in SQLite ISO 8601 GMT format: e.g. '2021-09-01 12:00:00'
    """
    assert len(last_modified_gmt) == 19
    dt = datetime.datetime.strptime(last_modified_gmt, '%Y-%m-%d %H:%M:%S')
    return dt.strftime('%a, %d %b %Y %H:%M:%S GMT')

def now_stamp() -> float:
    return datetime.datetime.now().timestamp()

def stamp_to_str(stamp: float) -> str:
    return datetime.datetime.fromtimestamp(stamp).strftime('%Y-%m-%d %H:%M:%S')