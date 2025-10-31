import argparse, asyncio, os
from contextlib import asynccontextmanager
from .cli import parse_permission, FileReadPermission
from ..eng.utils import parse_storage_size, fmt_storage_size
from ..eng.datatype import AccessLevel
from ..eng.database import Database, FileReadPermission, transaction, UserConn, unique_cursor, FileConn
from ..eng.connection_pool import global_entrance
from ..eng.userman import UserCtl, parse_access_level

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
        user = await UserCtl.add(
            username=args.username, 
            password=args.password, 
            is_admin=args.admin, 
            max_storage=args.max_storage, 
            permission=args.permission
        )
        print('User created, credential:', user.credential)
    
    if args.subparser_name == 'delete':
        user = await UserCtl.delete(args.username)
        print('User deleted')
    
    if args.subparser_name == 'set':
        user = await UserCtl.update(
            username=args.username,
            password=args.password,
            admin=args.admin,
            max_storage=args.max_storage,
            permission=args.permission
        )
        print('User updated, credential:', user.credential)
    
    if args.subparser_name == 'set-peer':
        await UserCtl.set_peer(args.src_username, args.dst_username, args.level)
        print(f"Peer set: [{args.src_username}] now have [{args.level.name}] access to [{args.dst_username}]")
    
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