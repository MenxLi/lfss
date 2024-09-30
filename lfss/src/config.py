from pathlib import Path
import os

__default_dir = '.storage_data'

DATA_HOME = Path(os.environ.get('LFSS_DATA', __default_dir))
if not DATA_HOME.exists():
    DATA_HOME.mkdir()
    print(f"[init] Created data home at {DATA_HOME}")

MAX_FILE_BYTES = 256 * 1024 * 1024   # 256MB
MAX_BUNDLE_BYTES = 256 * 1024 * 1024   # 256MB