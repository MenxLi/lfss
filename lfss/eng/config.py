import os
from pathlib import Path
from .utils import parse_storage_size

__default_dir = '.storage_data'

DATA_HOME = Path(os.environ.get('LFSS_DATA', __default_dir))
if not DATA_HOME.exists():
    DATA_HOME.mkdir()
    print(f"[init] Created data home at {DATA_HOME}")
DATA_HOME = DATA_HOME.resolve().absolute()
LARGE_BLOB_DIR = DATA_HOME / 'large_blobs'
LARGE_BLOB_DIR.mkdir(exist_ok=True)
LOG_DIR = DATA_HOME / 'logs'

DISABLE_LOGGING = os.environ.get('DISABLE_LOGGING', '0') == '1'

# https://sqlite.org/fasterthanfs.html
__env_large_file = os.environ.get('LFSS_LARGE_FILE', None)
if __env_large_file is not None:
    LARGE_FILE_BYTES = parse_storage_size(__env_large_file)
else:
    LARGE_FILE_BYTES = 1 * 1024 * 1024  # 1MB
MAX_MEM_FILE_BYTES = 128 * 1024 * 1024  # 128MB
CHUNK_SIZE = 1024 * 1024   # 1MB chunks for streaming (on large files)
DEBUG_MODE = os.environ.get('LFSS_DEBUG', '0') == '1'

THUMB_DB = DATA_HOME / 'thumbs.v0-11.db'
THUMB_SIZE = (64, 64)