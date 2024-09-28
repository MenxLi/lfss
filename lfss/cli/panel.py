""" A static file server to serve frontend panel """
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

import argparse
from contextlib import asynccontextmanager
from pathlib import Path

__this_dir = Path(__file__).parent
__frontend_dir = __this_dir.parent.parent / "frontend"

browser_open_config = {
    "enabled": True,
    "host": "",
    "port": 0
}

@asynccontextmanager
async def app_lifespan(app: FastAPI):
    if browser_open_config["enabled"]:
        import webbrowser
        webbrowser.open(f"http://{browser_open_config['host']}:{browser_open_config['port']}")
    yield

assert (__frontend_dir / "index.html").exists(), "Frontend panel not found"

app = FastAPI(lifespan=app_lifespan)
app.mount("/", StaticFiles(directory=__frontend_dir, html=True), name="static")

def main():
    parser = argparse.ArgumentParser(description="Serve frontend panel")
    parser.add_argument("--host", default="127.0.0.1", help="Host to serve")
    parser.add_argument("--port", type=int, default=8009, help="Port to serve")
    parser.add_argument("--open", action="store_true", help="Open browser")
    args = parser.parse_args()

    browser_open_config["enabled"] = args.open
    browser_open_config["host"] = args.host
    browser_open_config["port"] = args.port
    
    uvicorn.run(app, host=args.host, port=args.port)

if __name__ == "__main__":
    main()