from importlib.metadata import version as _importlib_version

try:
    __version__ = _importlib_version("lfss")
except Exception:
    __version__ = "unknown"

version_info = tuple(int(x) for x in __version__.split('.') if x.isdigit()) if __version__ != "unknown" else ()