from pathlib import Path
import os

__default_dir = '.storage_data'

DATA_HOME = Path(os.environ.get('FSS_DATA', __default_dir))
if not DATA_HOME.exists():
    DATA_HOME.mkdir()
    print(f"[init] Created data home at {DATA_HOME}")