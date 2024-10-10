from pathlib import Path
import os, hashlib

__default_dir = '.storage_data'

DATA_HOME = Path(os.environ.get('LFSS_DATA', __default_dir))
if not DATA_HOME.exists():
    DATA_HOME.mkdir()
    print(f"[init] Created data home at {DATA_HOME}")
DATA_HOME = DATA_HOME.resolve().absolute()
LARGE_BLOB_DIR = DATA_HOME / 'large_blobs'
LARGE_BLOB_DIR.mkdir(exist_ok=True)

# https://sqlite.org/fasterthanfs.html
LARGE_FILE_BYTES = 8 * 1024 * 1024   # 8MB
MAX_FILE_BYTES = 512 * 1024 * 1024   # 512MB
MAX_BUNDLE_BYTES = 512 * 1024 * 1024   # 512MB

def hash_credential(username, password):
    return hashlib.sha256((username + password).encode()).hexdigest()
