from pathlib import Path
import os

__default_dir = '.storage_data'

DATA_HOME = Path(os.environ.get('LFSS_DATA', __default_dir))
if not DATA_HOME.exists():
    DATA_HOME.mkdir()
    print(f"[init] Created data home at {DATA_HOME}")
LARGE_BLOB_DIR = DATA_HOME / 'large_blobs'
LARGE_BLOB_DIR.mkdir(exist_ok=True)

LARGE_FILE_BYTES = 64 * 1024 * 1024   # 64MB
MAX_FILE_BYTES = 1024 * 1024 * 1024   # 1GB
MAX_BUNDLE_BYTES = 1024 * 1024 * 1024   # 1GB