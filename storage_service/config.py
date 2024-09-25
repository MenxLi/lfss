from pathlib import Path
import os

__default_dir = '.storage_data'

DATA_HOME = Path(os.environ.get('DATA_HOME', __default_dir))
if not DATA_HOME.exists():
    DATA_HOME.mkdir()
    print(f"[init] Created data home at {DATA_HOME}")

FILE_ROOT = DATA_HOME / 'files'