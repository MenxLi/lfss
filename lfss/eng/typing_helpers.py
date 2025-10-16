import sys

if sys.version_info < (3, 12):
    def __create_override_decorator():
        from typing import Callable, TypeVar
        F = TypeVar('F', bound=Callable)
        def override(method: F) -> F:
            try: method.__override__ = True
            except (AttributeError, TypeError): pass
            return method
        return override
    override = __create_override_decorator()
else:
    from typing import override