import datetime, time
import urllib.parse
import pathlib
import functools
import hashlib
import aiofiles
import asyncio
from asyncio import Lock
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from typing import TypeVar, Callable, Awaitable
from functools import wraps, partial
from uuid import uuid4
import os

async def copy_file(source: str|pathlib.Path, destination: str|pathlib.Path):
    async with aiofiles.open(source, mode='rb') as src:
        async with aiofiles.open(destination, mode='wb') as dest:
            while chunk := await src.read(1024):
                await dest.write(chunk)

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

class TaskManager:
    def __init__(self):
        self._tasks: OrderedDict[str, asyncio.Task] = OrderedDict()
    
    def push(self, task: asyncio.Task) -> str:
        tid = uuid4().hex
        if tid in self._tasks:
            raise ValueError("Task ID collision")
        self._tasks[tid] = task
        return tid
    
    def cancel(self, task_id: str):
        task = self._tasks.pop(task_id, None)
        if task is not None:
            task.cancel()
    
    def truncate(self):
        new_tasks = OrderedDict()
        for tid, task in self._tasks.items():
            if not task.done():
                new_tasks[tid] = task
        self._tasks = new_tasks
    
    async def wait_all(self):
        async def stop_task(task: asyncio.Task):
            if not task.done():
                await task
        await asyncio.gather(*map(stop_task, self._tasks.values()))
        self._tasks.clear()
    
    def __len__(self): return len(self._tasks)

g_debounce_tasks: TaskManager = TaskManager()
async def wait_for_debounce_tasks():
    await g_debounce_tasks.wait_all()

def debounce_async(delay: float = 0.1, max_wait: float = 1.):
    """ 
    Debounce the async procedure, 
    ensuring execution at least once every `max_wait` seconds. 
    """
    def debounce_wrap(func):
        # task_record: tuple[str, asyncio.Task] | None = None
        prev_task_id = None
        fn_execution_lock = Lock()
        last_execution_time = 0

        async def delayed_func(*args, **kwargs):
            nonlocal last_execution_time
            await asyncio.sleep(delay)
            async with fn_execution_lock:
                await func(*args, **kwargs)
                last_execution_time = time.monotonic()

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            nonlocal prev_task_id, last_execution_time

            if prev_task_id is not None:
                g_debounce_tasks.cancel(prev_task_id)
                prev_task_id = None
            
            async with fn_execution_lock:
                if time.monotonic() - last_execution_time > max_wait:
                    await func(*args, **kwargs)
                    last_execution_time = time.monotonic()
                    return

            task = asyncio.create_task(delayed_func(*args, **kwargs))
            prev_task_id = g_debounce_tasks.push(task)
            if len(g_debounce_tasks) > 1024:
                # finished tasks are not removed from the dict
                # so we need to clear it periodically
                g_debounce_tasks.truncate()

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
    """ Get the current timestamp, in seconds """
    return datetime.datetime.now().timestamp()

def stamp_to_str(stamp: float) -> str:
    return datetime.datetime.fromtimestamp(stamp).strftime('%Y-%m-%d %H:%M:%S')

def parse_storage_size(s: str) -> int:
    """ Parse the file size string to bytes """
    if s[-1].isdigit():
        return int(s)
    unit = s[-1].lower()
    match unit:
        case 'b': return int(s[:-1])
        case 'k': return int(s[:-1]) * 1024
        case 'm': return int(s[:-1]) * 1024**2
        case 'g': return int(s[:-1]) * 1024**3
        case 't': return int(s[:-1]) * 1024**4
        case _: raise ValueError(f"Invalid file size string: {s}")
def fmt_storage_size(size: int) -> str:
    """ Format the file size to human-readable format """
    if size < 1024:
        return f"{size}B"
    if size < 1024**2:
        return f"{size/1024:.2f}K"
    if size < 1024**3:
        return f"{size/1024**2:.2f}M"
    if size < 1024**4:
        return f"{size/1024**3:.2f}G"
    return f"{size/1024**4:.2f}T"

_FnReturnT = TypeVar('_FnReturnT')
_AsyncReturnT = Awaitable[_FnReturnT]
_g_executor = None
def get_global_executor():
    global _g_executor
    if _g_executor is None:
        _g_executor = ThreadPoolExecutor(max_workers=4 if (cpu_count:=os.cpu_count()) and cpu_count > 4 else cpu_count)
    return _g_executor
def async_wrap(executor=None):
    if executor is None:
        executor = get_global_executor()
    def _async_wrap(func: Callable[..., _FnReturnT]) -> Callable[..., Awaitable[_FnReturnT]]:
        @wraps(func)
        async def run(*args, **kwargs):
            loop = asyncio.get_event_loop()
            pfunc = partial(func, *args, **kwargs)
            return await loop.run_in_executor(executor, pfunc)
        return run
    return _async_wrap
def concurrent_wrap(executor=None):
    def _concurrent_wrap(func: Callable[..., _AsyncReturnT]) -> Callable[..., _AsyncReturnT]:
        @async_wrap(executor)
        def sync_fn(*args, **kwargs):
            loop = asyncio.new_event_loop()
            return loop.run_until_complete(func(*args, **kwargs))
        return sync_fn
    return _concurrent_wrap

# https://stackoverflow.com/a/279586/6775765
def static_vars(**kwargs):
    def decorate(func):
        for k in kwargs:
            setattr(func, k, kwargs[k])
        return func
    return decorate