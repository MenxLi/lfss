from contextlib import contextmanager
from typing import Iterable, TypeVar, Generator
import requests, os

@contextmanager
def catch_request_error():
    try:
        yield
    except requests.RequestException as e:
        print(f"\033[31m[Request error]: {e}\033[0m")
        if e.response is not None:
            print(f"\033[91m[Error message]: {e.response.text}\033[0m")

T = TypeVar('T')
def line_sep(iter: Iterable[T], enable=True, start=True, end=True, color="\033[90m") -> Generator[T, None, None]:
    screen_width = os.get_terminal_size().columns
    def print_ln():
        print(color + "-" * screen_width + "\033[0m")

    if start and enable:
        print_ln()
    for i, line in enumerate(iter):
        if enable and i > 0:
            print_ln()
        yield line
    if end and enable:
        print_ln()
