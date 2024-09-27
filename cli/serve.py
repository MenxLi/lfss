import argparse
from uvicorn import Config, Server
from uvicorn.config import LOGGING_CONFIG
from storage_service.server import *

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('--host', type=str, default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--workers', type=int, default=None)
    parser.add_argument('--enable-uvicorn-log', action='store_true')
    args = parser.parse_args()

    default_logging_config = LOGGING_CONFIG.copy()
    if not args.enable_uvicorn_log:
        default_logging_config["loggers"]["uvicorn"]["handlers"] = []

    config = Config(
        app=app,
        host=args.host,
        port=args.port,
        access_log=False,
        workers=args.workers,
        log_config=default_logging_config
    )
    server = Server(config=config)
    logger.info(f"Starting server at {args.host}:{args.port}, with {args.workers} workers")
    server.run()