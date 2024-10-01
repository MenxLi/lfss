from typing import Callable
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