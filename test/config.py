import pathlib
import shutil

__this_dir = pathlib.Path(__file__).parent

SANDBOX_DIR = __this_dir / '.sandbox'
SANDBOX_DIR = SANDBOX_DIR.resolve().absolute()
SANDBOX_DIR.mkdir(exist_ok=True)

SERVER_PORT = 17435

def clear_sandbox():
    for p in SANDBOX_DIR.iterdir():
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()
    print(f"[sandbox] Cleared sandbox at {SANDBOX_DIR}")