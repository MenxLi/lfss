from contextlib import contextmanager
from typing import Iterable, TypeVar, Generator, Callable, Optional
import requests, os

@contextmanager
def catch_request_error(error_code_handler: Optional[ dict[int, Callable[[requests.Response], None]] ] = None):
    try:
        yield
    except requests.RequestException as e:
        if error_code_handler is not None:
            if e.response is not None and e.response.status_code in error_code_handler:
                error_code_handler[e.response.status_code](e.response)
                return
        print(f"\033[31m[Request error]: {e}\033[0m")
        if e.response is not None:
            print(f"\033[91m[Error message]: {e.response.text}\033[0m")

T = TypeVar('T')
def line_sep(iter: Iterable[T], enable=True, start=True, end=True, color="\033[90m") -> Generator[T, None, None]:
    screen_width = os.get_terminal_size().columns
    def print_ln():
        if enable: print(color + "-" * screen_width + "\033[0m")

    if start:
        print_ln()
    for i, line in enumerate(iter):
        if i > 0:
            print_ln()
        yield line
    if end:
        print_ln()
