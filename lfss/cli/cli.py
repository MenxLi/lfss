from lfss.api import Connector, upload_directory, upload_file, download_file, download_directory
from pathlib import Path
import argparse
from lfss.src.datatype import FileReadPermission

def parse_permission(s: str) -> FileReadPermission:
    if s.lower() == "public":
        return FileReadPermission.PUBLIC
    if s.lower() == "protected":
        return FileReadPermission.PROTECTED
    if s.lower() == "private":
        return FileReadPermission.PRIVATE
    if s.lower() == "unset":
        return FileReadPermission.UNSET
    raise ValueError(f"Invalid permission {s}")

def parse_arguments():
    parser = argparse.ArgumentParser(description="Command line interface, please set LFSS_ENDPOINT and LFSS_TOKEN environment variables.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    sp = parser.add_subparsers(dest="command", required=True)

    # upload
    sp_upload = sp.add_parser("upload", help="Upload files")
    sp_upload.add_argument("src", help="Source file or directory", type=str)
    sp_upload.add_argument("dst", help="Destination url path", type=str)
    sp_upload.add_argument("-j", "--jobs", type=int, default=1, help="Number of concurrent uploads")
    sp_upload.add_argument("--interval", type=float, default=0, help="Interval between files, only works with directory upload")
    sp_upload.add_argument("--conflict", choices=["overwrite", "abort", "skip", "skip-ahead"], default="abort", help="Conflict resolution")
    sp_upload.add_argument("--permission", type=parse_permission, default=FileReadPermission.UNSET, help="File permission, can be public, protected, private, or unset")
    sp_upload.add_argument("--retries", type=int, default=0, help="Number of retries")

    # download
    sp_download = sp.add_parser("download", help="Download files")
    sp_download.add_argument("src", help="Source url path", type=str)
    sp_download.add_argument("dst", help="Destination file or directory", type=str)
    sp_download.add_argument("-j", "--jobs", type=int, default=1, help="Number of concurrent downloads")
    sp_download.add_argument("--interval", type=float, default=0, help="Interval between files, only works with directory download")
    sp_download.add_argument("--overwrite", action="store_true", help="Overwrite existing files")
    sp_download.add_argument("--retries", type=int, default=0, help="Number of retries")

    return parser.parse_args()

def main():
    args = parse_arguments()
    connector = Connector()
    if args.command == "upload":
        src_path = Path(args.src)
        if src_path.is_dir():
            failed_upload = upload_directory(
                connector, args.src, args.dst, 
                verbose=args.verbose,
                n_concurrent=args.jobs, 
                n_retries=args.retries, 
                interval=args.interval,
                conflict=args.conflict,
                permission=args.permission
            )
            if failed_upload:
                print("Failed to upload:")
                for path in failed_upload:
                    print(f"  {path}")
        else:
            success = upload_file(
                connector, 
                file_path = args.src, 
                dst_url = args.dst, 
                verbose=args.verbose,
                n_retries=args.retries, 
                interval=args.interval,
                conflict=args.conflict,
                permission=args.permission
            )
            if not success:
                print("Failed to upload.")
    
    elif args.command == "download":
        is_dir = args.src.endswith("/")
        if is_dir:
            failed_download = download_directory(
                connector, args.src, args.dst, 
                verbose=args.verbose,
                n_concurrent=args.jobs, 
                n_retries=args.retries, 
                interval=args.interval,
                overwrite=args.overwrite
            )
            if failed_download:
                print("Failed to download:")
                for path in failed_download:
                    print(f"  {path}")
        else:
            success = download_file(
                connector, 
                src_url = args.src, 
                file_path = args.dst, 
                verbose=args.verbose,
                n_retries=args.retries, 
                interval=args.interval,
                overwrite=args.overwrite
            )
            if not success:
                print("Failed to download.")
    else:
        raise NotImplementedError(f"Command {args.command} not implemented.")
    