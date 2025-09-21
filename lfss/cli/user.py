import argparse, asyncio, os, secrets
from contextlib import asynccontextmanager
from .cli import parse_permission, FileReadPermission
from ..eng.utils import parse_storage_size, fmt_storage_size
from ..eng.datatype import AccessLevel
from ..eng.database import Database, FileReadPermission, transaction, UserConn, unique_cursor, FileConn
from ..eng.connection_pool import global_entrance

def parse_access_level(s: str) -> AccessLevel:
    for p in AccessLevel:
        if p.name.lower() == s.lower():
            return p
    raise ValueError(f"Invalid access level {s}")

@global_entrance(1)
async def _main():
    parser = argparse.ArgumentParser()
    sp = parser.add_subparsers(dest='subparser_name', required=True)
    sp_add = sp.add_parser('add')
    sp_add.add_argument('username', type=str)
    sp_add.add_argument('password', nargs='?', type=str, default=None)
    sp_add.add_argument('--admin', action='store_true', help='Set user as admin')
    sp_add.add_argument("--permission", type=parse_permission, default=FileReadPermission.UNSET, help="File permission, can be public, protected, private, or unset")
    sp_add.add_argument('--max-storage', type=parse_storage_size, default="10G", help="Maximum storage size, e.g. 1G, 100M, 10K, default is 10G")
    
    sp_delete = sp.add_parser('delete')
    sp_delete.add_argument('username', type=str)

    def parse_bool(s):
        if s.lower() == 'true':
            return True
        if s.lower() == 'false':
            return False
        raise ValueError('Not a boolean')
    sp_set = sp.add_parser('set')
    sp_set.add_argument('username', type=str)
    sp_set.add_argument('-p', '--password', type=str, default=None)
    sp_set.add_argument('-a', '--admin', type=parse_bool, default=None)
    sp_set.add_argument('--permission', type=parse_permission, default=None)
    sp_set.add_argument('--max-storage', type=parse_storage_size, default=None)

    sp_list = sp.add_parser('list')
    sp_list.add_argument("username", nargs='*', type=str, default=None)
    sp_list.add_argument("-l", "--long", action="store_true")
    
    sp_peer = sp.add_parser('set-peer')
    sp_peer.add_argument('src_username', type=str)
    sp_peer.add_argument('dst_username', type=str)
    sp_peer.add_argument('--level', type=parse_access_level, default=AccessLevel.READ, help="Access level")
    
    args = parser.parse_args()
    db = await Database().init()

    @asynccontextmanager
    async def get_uconn():
        async with transaction() as conn:
            yield UserConn(conn)
    
    if args.subparser_name == 'add':
        async with get_uconn() as uconn:
            if args.password is None:
                passwd = secrets.token_urlsafe(16)
                args.password = passwd
            await uconn.create_user(args.username, args.password, args.admin, max_storage=args.max_storage, permission=args.permission)
            user = await uconn.get_user(args.username)
            assert user is not None
            print('User created, credential:', user.credential)
    
    if args.subparser_name == 'delete':
        async with get_uconn() as uconn:
            user = await uconn.get_user(args.username)
        if user is None:
            print('User not found')
            exit(1)
        else:
            await db.delete_user(user.id)
        print('User deleted')
    
    if args.subparser_name == 'set':
        async with get_uconn() as uconn:
            user = await uconn.get_user(args.username)
            if user is None:
                print('User not found')
                exit(1)
            await uconn.update_user(user.username, args.password, args.admin, max_storage=args.max_storage, permission=args.permission)
            user = await uconn.get_user(args.username)
            assert user is not None
            print('User updated, credential:', user.credential)
    
    if args.subparser_name == 'set-peer':
        async with get_uconn() as uconn:
            src_user = await uconn.get_user(args.src_username)
            dst_user = await uconn.get_user(args.dst_username)
            if src_user is None or dst_user is None:
                print('User not found')
                exit(1)
            await uconn.set_peer_level(src_user.id, dst_user.id, args.level)
            print(f"Peer set: [{src_user.username}] now have [{args.level.name}] access to [{dst_user.username}]")
    
    if args.subparser_name == 'list':
        async with get_uconn() as uconn:
            term_width = os.get_terminal_size().columns
            async for user in uconn.all():
                if args.username and not user.username in args.username:
                    continue
                print("\033[90m-\033[0m" * term_width)
                print(user)
                if args.long:
                    async with unique_cursor() as c:
                        fconn = FileConn(c)
                        user_size_used = await fconn.user_size(user.id)
                    print('- Credential: ', user.credential)
                    print(f'- Storage: {fmt_storage_size(user_size_used)} / {fmt_storage_size(user.max_storage)}')
                    for p in AccessLevel:
                        if p > AccessLevel.NONE:
                            usernames = [x.username for x in await uconn.list_peer_users(user.id, p)]
                            if usernames:
                                print(f'- Peers [{p.name}]: {", ".join(usernames)}')
        
def main():
    asyncio.run(_main())

if __name__ == '__main__':
    main()