from lfss.client import Connector, upload_directory
from lfss.src.database import FileReadPermission
from pathlib import Path
import argparse

def parse_arguments():
    parser = argparse.ArgumentParser(description="Command line interface, please set LFSS_ENDPOINT and LFSS_TOKEN environment variables.")

    sp = parser.add_subparsers(dest="command", required=True)

    # upload
    sp_upload = sp.add_parser("upload", help="Upload files")
    sp_upload.add_argument("src", help="Source file or directory", type=str)
    sp_upload.add_argument("dst", help="Destination path", type=str)
    sp_upload.add_argument("-j", "--jobs", type=int, default=1, help="Number of concurrent uploads")
    sp_upload.add_argument("--interval", type=float, default=0, help="Interval between retries, only works with directory upload")
    sp_upload.add_argument("--overwrite", action="store_true", help="Overwrite existing files")
    sp_upload.add_argument("--permission", type=FileReadPermission, default=FileReadPermission.UNSET, help="File permission")
    sp_upload.add_argument("--retries", type=int, default=0, help="Number of retries, only works with directory upload")

    return parser.parse_args()

def main():
    args = parse_arguments()
    connector = Connector()
    if args.command == "upload":
        src_path = Path(args.src)
        if src_path.is_dir():
            upload_directory(
                connector, args.src, args.dst, 
                verbose=True, 
                n_concurrent=args.jobs, 
                n_reties=args.retries, 
                interval=args.interval,
                overwrite=args.overwrite, 
                permission=args.permission
            )
        else:
            with open(args.src, 'rb') as f:
                connector.put(
                    args.dst, 
                    f.read(), 
                    overwrite=args.overwrite, 
                    permission=args.permission
                    )
    else:
        raise NotImplementedError(f"Command {args.command} not implemented.")
    