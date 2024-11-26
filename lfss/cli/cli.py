from lfss.api import Connector, upload_directory, upload_file, download_file, download_directory
from pathlib import Path
import argparse, requests, typing
from lfss.src.datatype import FileReadPermission, FileSortKey, DirSortKey
from lfss.src.utils import term_line_sep, decode_uri_compnents
from contextlib import contextmanager

@contextmanager
def catch_request_error():
    try:
        yield
    except requests.RequestException as e:
        print(f"\033[31m[Request error]: {e}\033[0m")
        if e.response is not None:
            print(f"\033[91m[Error message]: {e.response.text}\033[0m")

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

    # query
    sp_query = sp.add_parser("query", help="Query files or directories metadata from the server")
    sp_query.add_argument("path", help="Path to query", nargs="*", type=str)

    # list directories
    sp_list_d = sp.add_parser("list-dirs", help="List directories of a given path")
    sp_list_d.add_argument("path", help="Path to list", type=str)
    sp_list_d.add_argument("--offset", type=int, default=0, help="Offset of the list")
    sp_list_d.add_argument("--limit", type=int, default=100, help="Limit of the list")
    sp_list_d.add_argument("-l", "--long", action="store_true", help="Detailed list, including all metadata")
    sp_list_d.add_argument("--order", "--order-by", type=str, help="Order of the list", default="", choices=typing.get_args(DirSortKey))
    sp_list_d.add_argument("--reverse", "--order-desc", action="store_true", help="Reverse the list order")

    # list files
    sp_list_f = sp.add_parser("list-files", help="List files of a given path")
    sp_list_f.add_argument("path", help="Path to list", type=str)
    sp_list_f.add_argument("--offset", type=int, default=0, help="Offset of the list")
    sp_list_f.add_argument("--limit", type=int, default=100, help="Limit of the list")
    sp_list_f.add_argument("-r", "--recursive", "--flat", action="store_true", help="List files recursively")
    sp_list_f.add_argument("-l", "--long", action="store_true", help="Detailed list, including all metadata")
    sp_list_f.add_argument("--order", "--order-by", type=str, help="Order of the list", default="", choices=typing.get_args(FileSortKey))
    sp_list_f.add_argument("--reverse", "--order-desc", action="store_true", help="Reverse the list order")

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
    
    elif args.command == "query":
        for path in args.path:
            with catch_request_error():
                res = connector.get_metadata(path)
                if res is None:
                    print(f"\033[31mNot found\033[0m ({path})")
                else:
                    print(res)
    
    elif args.command == "list-files":
        with catch_request_error():
            res = connector.list_files(
                args.path, 
                offset=args.offset, 
                limit=args.limit, 
                flat=args.recursive, 
                order_by=args.order,
                order_desc=args.reverse,
            )
            for i, f in enumerate(term_line_sep(res)):
                f.url = decode_uri_compnents(f.url)
                print(f"[{i+1}] {f if args.long else f.url}")

            if len(res) == args.limit:
                print(f"\033[33m[Warning] List limit reached, use --offset and --limit to list more files.")
        
    elif args.command == "list-dirs":
        with catch_request_error():
            res = connector.list_dirs(
                args.path, 
                offset=args.offset, 
                limit=args.limit, 
                skim=not args.long, 
                order_by=args.order,
                order_desc=args.reverse,
            )
            for i, d in enumerate(term_line_sep(res)):
                d.url = decode_uri_compnents(d.url)
                print(f"[{i+1}] {d if args.long else d.url}")

            if len(res) == args.limit:
                print(f"\033[33m[Warning] List limit reached, use --offset and --limit to list more directories.")
    
    else:
        raise NotImplementedError(f"Command {args.command} not implemented.")
    