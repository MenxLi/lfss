import datetime
import urllib.parse
import asyncio
import functools

def encode_uri_compnents(path: str):
    """
    Encode the path components to encode the special characters, 
    also to avoid path traversal attack
    """
    path_sp = path.split("/")
    mapped = map(lambda x: urllib.parse.quote(x), path_sp)
    return "/".join(mapped)

def decode_uri_compnents(path: str):
    """
    Decode the path components to decode the special characters
    """
    path_sp = path.split("/")
    mapped = map(lambda x: urllib.parse.unquote(x), path_sp)
    return "/".join(mapped)

def ensure_uri_compnents(path: str):
    """
    Ensure the path components are safe to use
    """
    return encode_uri_compnents(decode_uri_compnents(path))

def debounce_async(delay: float = 0):
    """
    Decorator to debounce the async function (procedure)
    The function must return None
    """
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

# https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Last-Modified
def format_last_modified(last_modified_gmt: str):
    """
    Format the last modified time to the HTTP standard format
    - last_modified_gmt: The last modified time in SQLite ISO 8601 GMT format: e.g. '2021-09-01 12:00:00'
    """
    dt = datetime.datetime.strptime(last_modified_gmt, '%Y-%m-%d %H:%M:%S')
    return dt.strftime('%a, %d %b %Y %H:%M:%S GMT')