from pathlib import Path
import argparse, typing, sys
from lfss.api import Connector, upload_directory, upload_file, download_file, download_directory
from lfss.eng.datatype import FileReadPermission, FileSortKey, DirSortKey, AccessLevel
from lfss.eng.utils import decode_uri_components, fmt_storage_size
from . import catch_request_error, line_sep as _line_sep

# monkey patch to avoid printing line separators...may remove line_sep in the future
line_sep = lambda *args, **kwargs: _line_sep(*args, enable=False, **kwargs)

def parse_permission(s: str) -> FileReadPermission:
    for p in FileReadPermission:
        if p.name.lower() == s.lower():
            return p
    raise ValueError(f"Invalid permission {s}")
def parse_access_level(s: str) -> AccessLevel:
    for p in AccessLevel:
        if p.name.lower() == s.lower():
            return p
    raise ValueError(f"Invalid access level {s}")
def default_error_handler_dict(path: str):
    return {
        401: lambda _: print(f"\033[31mUnauthorized\033[0m ({path})", file=sys.stderr),
        403: lambda _: print(f"\033[31mForbidden\033[0m ({path})", file=sys.stderr),
        404: lambda _: print(f"\033[31mNot found\033[0m ({path})", file=sys.stderr), 
        409: lambda _: print(f"\033[31mConflict\033[0m ({path})", file=sys.stderr),
    }

def parse_arguments():
    parser = argparse.ArgumentParser(description="Client-side command line interface, set LFSS_ENDPOINT and LFSS_TOKEN environment variables for authentication.")

    sp = parser.add_subparsers(dest="command", required=True)

    # whoami
    sp_whoami = sp.add_parser("whoami", help="Show current user information")

    # list peers
    sp_peers = sp.add_parser("peers", help="Query users that you have access to or users that have access to you")
    sp_peers.add_argument('-l', "--level", type=parse_access_level, default=AccessLevel.READ, help="Access level filter")
    sp_peers.add_argument('-i', '--incoming', action='store_true', help="List users that have access to you (rather than you have access to them")

    # upload
    sp_upload = sp.add_parser("upload", help="Upload a file or directory", aliases=["up"])
    sp_upload.add_argument("src", help="Source file or directory", type=str)
    sp_upload.add_argument("dst", help="Destination url path", type=str)
    sp_upload.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    sp_upload.add_argument("-j", "--jobs", type=int, default=1, help="Number of concurrent uploads")
    sp_upload.add_argument("--interval", type=float, default=0, help="Interval between files, only works with directory upload")
    sp_upload.add_argument("--conflict", choices=["overwrite", "abort", "skip", "skip-ahead"], default="abort", help="Conflict resolution")
    sp_upload.add_argument("--permission", type=parse_permission, default=FileReadPermission.UNSET, help="File permission, can be public, protected, private, or unset")
    sp_upload.add_argument("--retries", type=int, default=0, help="Number of retries")

    # download
    sp_download = sp.add_parser("download", help="Download a file or directory", aliases=["down"])
    sp_download.add_argument("src", help="Source url path", type=str)
    sp_download.add_argument("dst", help="Destination file or directory", type=str)
    sp_download.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    sp_download.add_argument("-j", "--jobs", type=int, default=1, help="Number of concurrent downloads")
    sp_download.add_argument("--interval", type=float, default=0, help="Interval between files, only works with directory download")
    sp_download.add_argument("--overwrite", action="store_true", help="Overwrite existing files")
    sp_download.add_argument("--retries", type=int, default=0, help="Number of retries")

    # query
    sp_query = sp.add_parser("info", help="Query file or directories metadata from the server", aliases=["i"])
    sp_query.add_argument("path", help="Path to query", nargs="+", type=str)

    # delete
    sp_delete = sp.add_parser("delete", help="Delete files or directories", aliases=["del"])
    sp_delete.add_argument("path", help="Path to delete", nargs="+", type=str)
    sp_delete.add_argument("-y", "--yes", action="store_true", help="Confirm deletion without prompt")

    # aggregate list
    sp_list = sp.add_parser("list", help="Aggregately list files and directories of a given path", aliases=["ls"])
    sp_list.add_argument("path", help="Path to list", type=str)
    sp_list.add_argument("--offset", type=int, default=0, help="Offset of the list")
    sp_list.add_argument("--limit", type=int, default=100, help="Limit of the list")
    sp_list.add_argument("-l", "--long", action="store_true", help="Detailed list, including all metadata")
    sp_list.add_argument("--order", "--order-by", type=str, help="Order of the list", default="", choices=typing.get_args(FileSortKey))
    sp_list.add_argument("--reverse", "--order-desc", action="store_true", help="Reverse the list order")

    # list directories
    sp_list_d = sp.add_parser("list-d", help="List directories of a given path", aliases=["lsd"])
    sp_list_d.add_argument("path", help="Path to list", type=str)
    sp_list_d.add_argument("--offset", type=int, default=0, help="Offset of the list")
    sp_list_d.add_argument("--limit", type=int, default=100, help="Limit of the list")
    sp_list_d.add_argument("-l", "--long", action="store_true", help="Detailed list, including all metadata")
    sp_list_d.add_argument("--order", "--order-by", type=str, help="Order of the list", default="", choices=typing.get_args(DirSortKey))
    sp_list_d.add_argument("--reverse", "--order-desc", action="store_true", help="Reverse the list order")

    # list files
    sp_list_f = sp.add_parser("list-f", help="List files of a given path", aliases=["lsf"])
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
    if args.command == "whoami":
        with catch_request_error():
            user = connector.whoami()
            print("Username:", user.username)
            print("User ID:", user.id)
            print("Is Admin:", bool(user.is_admin))
            print("Max Storage:", fmt_storage_size(user.max_storage))
            print("Default Permission:", user.permission.name)
            print("Created At:", user.create_time)
            print("Last Active:", user.last_active)
    
    elif args.command == "peers":
        with catch_request_error():
            users = connector.list_peers(level=args.level, incoming=args.incoming)
            if not args.incoming:
                print(f"Peers that you have {args.level.name} access to:")
            else:
                print(f"Peers that have {args.level.name} access to you:")
            for i, u in enumerate(line_sep(users)):
                print(f"[{i+1}] {u.username} (id={u.id})")

    elif args.command in ["upload", "up"]:
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
                print("\033[91mFailed to upload:\033[0m", file=sys.stderr)
                for path in failed_upload:
                    print(f"  {path}", file=sys.stderr)
        else:
            success, msg = upload_file(
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
                print("\033[91mFailed to upload: \033[0m", msg, file=sys.stderr)
    
    elif args.command in ["download", "down"]:
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
                print("\033[91mFailed to download:\033[0m", file=sys.stderr)
                for path in failed_download:
                    print(f"  {path}", file=sys.stderr)
        else:
            success, msg = download_file(
                connector, 
                src_url = args.src, 
                file_path = args.dst, 
                verbose=args.verbose,
                n_retries=args.retries, 
                interval=args.interval,
                overwrite=args.overwrite
            )
            if not success:
                print("\033[91mFailed to download: \033[0m", msg, file=sys.stderr)
    
    elif args.command == "delete":
        if not args.yes:
            print("You are about to delete the following paths:")
            for path in args.path:
                print("[D]" if path.endswith("/") else "[F]", path)
            confirm = input("Are you sure? ([yes]/no): ")
            if confirm.lower() not in ["", "y", "yes"]:
                print("Aborted.")
                exit(0)
        for path in args.path:
            with catch_request_error(default_error_handler_dict(path)):
                connector.delete(path)
                print(f"\033[32mDeleted\033[0m ({path})")
    
    elif args.command in ["info", "i"]:
        for path in args.path:
            with catch_request_error(default_error_handler_dict(path)):
                res = connector.get_meta(path)
                if res is None:
                    print(f"\033[31mNot found\033[0m ({path})")
                else:
                    print(res)
    
    elif args.command in ["ls", "list"]:
        with catch_request_error(default_error_handler_dict(args.path)):
            res = connector.list_path(
                args.path, 
                offset=args.offset, 
                limit=args.limit, 
                order_by=args.order,
                order_desc=args.reverse,
            )
            for i, d in enumerate(line_sep(res.dirs, end=False)):
                d.url = decode_uri_components(d.url)
                print(f"[d{i+1}] {d if args.long else d.url}")
            for i, f in enumerate(line_sep(res.files)):
                f.url = decode_uri_components(f.url)
                print(f"[f{i+1}] {f if args.long else f.url}")

            if len(res.dirs) + len(res.files) == args.limit:
                print(f"\033[33m[Warning] List limit reached, use --offset and --limit to list more items.\033[0m")
    
    elif args.command in ["lsf", "list-f"]:
        with catch_request_error(default_error_handler_dict(args.path)):
            res = connector.list_files(
                args.path, 
                offset=args.offset, 
                limit=args.limit, 
                flat=args.recursive, 
                order_by=args.order,
                order_desc=args.reverse,
            )
            for i, f in enumerate(line_sep(res)):
                f.url = decode_uri_components(f.url)
                print(f"[{i+1}] {f if args.long else f.url}")

            if len(res) == args.limit:
                print(f"\033[33m[Warning] List limit reached, use --offset and --limit to list more files.\033[0m")
        
    elif args.command in ["lsd", "list-d"]:
        with catch_request_error(default_error_handler_dict(args.path)):
            res = connector.list_dirs(
                args.path, 
                offset=args.offset, 
                limit=args.limit, 
                skim=not args.long, 
                order_by=args.order,
                order_desc=args.reverse,
            )
            for i, d in enumerate(line_sep(res)):
                d.url = decode_uri_components(d.url)
                print(f"[{i+1}] {d if args.long else d.url}")

            if len(res) == args.limit:
                print(f"\033[33m[Warning] List limit reached, use --offset and --limit to list more directories.\033[0m")
    
    else:
        raise NotImplementedError(f"Command {args.command} not implemented.")
    