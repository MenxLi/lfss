from .config import DATA_HOME
from typing import TypeVar, Callable, Literal, Optional
from functools import wraps
import logging, pathlib, asyncio
from logging import handlers

class BCOLORS:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    OKGRAY = '\033[90m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

    # Additional colors
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    LIGHTGRAY = '\033[37m'
    DARKGRAY = '\033[90m'
    LIGHTRED = '\033[91m'
    LIGHTGREEN = '\033[92m'
    LIGHTYELLOW = '\033[93m'
    LIGHTBLUE = '\033[94m'
    LIGHTMAGENTA = '\033[95m'
    LIGHTCYAN = '\033[96m'

class BaseLogger(logging.Logger):
    def finalize(self):
        for handler in self.handlers:
            handler.flush()
            handler.close()
            self.removeHandler(handler)

_fh_T = Literal['rotate', 'simple', 'daily']

__g_logger_dict: dict[str, BaseLogger] = {}
def get_logger(
    name = 'default', 
    log_home = pathlib.Path(DATA_HOME) / 'logs', 
    level = 'DEBUG',
    file_handler_type: _fh_T = 'rotate', 
    buffer_size = -1, 
    global_instance = True
    ):
    if global_instance and name in __g_logger_dict:
        return __g_logger_dict[name]

    def setupLogger(logger: logging.Logger):
        logger.setLevel(level)

        format_str = BCOLORS.LIGHTMAGENTA + ' %(asctime)s ' +BCOLORS.OKCYAN + '[%(name)s][%(levelname)s] ' + BCOLORS.ENDC + ' %(message)s'
        formatter = logging.Formatter(format_str)
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # format_str_plain = format_str.replace(BCOLORS.LIGHTMAGENTA, '').replace(BCOLORS.OKCYAN, '').replace(BCOLORS.ENDC, '')
        format_str_plain = format_str
        for color in BCOLORS.__dict__.values():
            if isinstance(color, str) and color.startswith('\033'):
                format_str_plain = format_str_plain.replace(color, '')

        formatter_plain = logging.Formatter(format_str_plain)
        log_home.mkdir(exist_ok=True)
        log_file = log_home / f'{name}.log'
        if file_handler_type == 'simple':
            file_handler = logging.FileHandler(log_file)
        elif file_handler_type == 'daily':
            file_handler = handlers.TimedRotatingFileHandler(
                log_file, when='midnight', interval=1, backupCount=5
            )
        elif file_handler_type == 'rotate':
            file_handler = handlers.RotatingFileHandler(
                log_file, maxBytes=1000000, backupCount=5
            )

        if buffer_size > 0:
            file_handler = handlers.MemoryHandler(
                capacity=buffer_size, flushLevel=logging.WARNING, target=file_handler
            )
        
        file_handler.setFormatter(formatter_plain)
        logger.addHandler(file_handler)
    
    logger = BaseLogger(name)
    setupLogger(logger)
    if global_instance:
        __g_logger_dict[name] = logger

    return logger

def clear_handlers(logger: logging.Logger):
    for handler in logger.handlers:
        handler.flush()
        handler.close()
        logger.removeHandler(handler)
    __g_logger_dict.pop(logger.name, None)
    # print(f'Cleared handlers for logger {logger.name}')

FUNCTION_T = TypeVar('FUNCTION_T', bound=Callable)
def log_access(
    include_args: bool = True,
    logger: Optional[logging.Logger] = None, 
):
    if logger is None:
        logger = get_logger()

    def _log_access(fn: FUNCTION_T) -> FUNCTION_T:
        if asyncio.iscoroutinefunction(fn):
            @wraps(fn)
            async def async_wrapper(*args, **kwargs):
                if include_args:
                    logger.info(f'[func] <{fn.__name__}> called with: {args}, {kwargs}')
                else:
                    logger.info(f'[func] <{fn.__name__}>')
                    
                return await fn(*args, **kwargs)
            return async_wrapper    # type: ignore
        else:
            @wraps(fn)
            def wrapper(*args, **kwargs):
                logger = get_logger()
                if include_args:
                    logger.info(f'[func] <{fn.__name__}> called with: {args}, {kwargs}')
                else:
                    logger.info(f'[func] <{fn.__name__}>')
                    
                return fn(*args, **kwargs)
            return wrapper          # type: ignore
    return _log_access

def get_dummy_logger() -> BaseLogger:
    return BaseLogger('dummy')

__ALL__ = [
    'get_logger', 'clear_handlers', 'logger_as_textiowrapper', 'log_access', 'get_dummy_logger'
]