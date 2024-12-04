"""
Code modified from: https://github.com/mowshon/bounded_pool_executor
"""

import multiprocessing
import concurrent.futures
import multiprocessing.synchronize
import threading
from typing import Optional

class _BoundedPoolExecutor:

    semaphore: Optional[multiprocessing.synchronize.BoundedSemaphore | threading.BoundedSemaphore] = None
    _max_workers: int

    def acquire(self):
        assert self.semaphore is not None
        self.semaphore.acquire()

    def release(self, fn):
        assert self.semaphore is not None
        self.semaphore.release()

    def submit(self, fn, *args, **kwargs):
        self.acquire()
        future = super().submit(fn, *args, **kwargs)    # type: ignore
        future.add_done_callback(self.release)

        return future


class BoundedProcessPoolExecutor(_BoundedPoolExecutor, concurrent.futures.ProcessPoolExecutor):

    def __init__(self, max_workers=None):
        super().__init__(max_workers)
        self.semaphore = multiprocessing.BoundedSemaphore(self._max_workers * 2)


class BoundedThreadPoolExecutor(_BoundedPoolExecutor, concurrent.futures.ThreadPoolExecutor):

    def __init__(self, max_workers=None):
        super().__init__(max_workers)
        self.semaphore = threading.BoundedSemaphore(self._max_workers * 2)

