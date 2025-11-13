import argparse, asyncio, os
from contextlib import asynccontextmanager
from .cli import parse_permission, FileReadPermission
from ..eng.utils import parse_storage_size, fmt_storage_size, fmt_sec_time
from ..eng.datatype import AccessLevel
from ..eng.database import Database, FileReadPermission, transaction, UserConn, unique_cursor, FileConn
from ..eng.connection_pool import global_entrance
from ..eng.userman import UserCtl, parse_access_level

@global_entrance(1)
async def _main():
    parser = argparse.ArgumentParser()
    sp = parser.add_subparsers(dest='subparser_name', required=True)
    sp_add = sp.add_parser('add', help="Add a new user")
    sp_add.add_argument('username', type=str)
    sp_add.add_argument('password', nargs='?', type=str, default=None)
    sp_add.add_argument('--admin', action='store_true', help='Set user as admin')
    sp_add.add_argument("--permission", type=parse_permission, default=FileReadPermission.UNSET, help="File fallback read permission, can be public, protected, private, or unset")
    sp_add.add_argument('--max-storage', type=parse_storage_size, default="10G", help="Maximum storage size, e.g. 1G, 100M, 10K, default is 10G")

    sp_add_virtual = sp.add_parser('add-virtual', help="Add a virtual (hidden) user, username will be prefixed with '.v-'")
    sp_add_virtual.add_argument('--tag', type=str, default="", help="Tag for the virtual user, will be embedded in the username for easier identification")
    sp_add_virtual.add_argument('--peers', type=str, default="", help="Peer users and their access levels in the format 'READ:user1,user2;WRITE:user3'")
    sp_add_virtual.add_argument('--max-storage', type=parse_storage_size, default="1G", help="Maximum storage size for the virtual user, e.g. 1G, 100M, 10K, default is 1G")
    sp_add_virtual.add_argument('--expire', type=str, default=None, help="Expire time in seconds or a string like '1d2h3m4s'. If not provided, the user will never expire.")
    
    sp_delete = sp.add_parser('delete')
    sp_delete.add_argument('username', type=str)

    def parse_bool(s):
        if s.lower() == 'true':
            return True
        if s.lower() == 'false':
            return False
        raise ValueError('Not a boolean')
    sp_set = sp.add_parser('set', help="Set user properties, refer to 'add' subcommand for details on each argument")
    sp_set.add_argument('username', type=str)
    sp_set.add_argument('-p', '--password', type=str, default=None)
    sp_set.add_argument('-a', '--admin', type=parse_bool, default=None)
    sp_set.add_argument('--permission', type=parse_permission, default=None)
    sp_set.add_argument('--max-storage', type=parse_storage_size, default=None)

    sp_list = sp.add_parser('list', help="List specified users, or detailed info with -l")
    sp_list.add_argument("username", nargs='*', type=str, default=None)
    sp_list.add_argument("-l", "--long", action="store_true", help="Show detailed information, including credential and peer users")
    sp_list.add_argument("-a", '--all', action="store_true", dest="show_all", help="Show all users, include hidden users (virtual users) in the listing")
    
    sp_peer = sp.add_parser('set-peer', help="Set peer user relationship")
    sp_peer.add_argument('src_username', type=str)
    sp_peer.add_argument('dst_username', type=str)
    sp_peer.add_argument('--level', type=parse_access_level, default=AccessLevel.READ, help="Access level")

    sp_expire = sp.add_parser('set-expire', help="Set or clear user expire time")
    sp_expire.add_argument('username', type=str)
    sp_expire.add_argument('expire_time', type=str, nargs='?', default=None, help="Expire time in seconds or a string like '1d2h3m4s'. If not provided, the user will never expire.")
    
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
            admin=args.admin, 
            max_storage=args.max_storage, 
            permission=args.permission
        )
        print('User created. | credential:', user.credential)
    
    if args.subparser_name == 'add-virtual':
        user =  await UserCtl.add_virtual(
            tag=args.tag,
            peers=args.peers,
            max_storage=args.max_storage, 
            expire=args.expire
        )
        print('Virtual user created, username:', user.username, '| credential:', user.credential)
    
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
    
    if args.subparser_name == 'set-expire':
        await UserCtl.set_expire(args.username, args.expire_time)
        print(f"User [{args.username}] expire time set.")
    
    if args.subparser_name == 'list':
        async with get_uconn() as uconn:
            term_width = os.get_terminal_size().columns
            async def __iter_users():
                if args.show_all:
                    async for user in uconn.iter_all(): yield user
                    async for user in uconn.iter_hidden(): yield user
                else:
                    async for user in uconn.iter_all(): yield user
            async for user in __iter_users():
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
                    print(f'- Expire: {fmt_sec_time(exp_time) if (exp_time := await uconn.query_user_expire(user.id)) is not None else "never"}')
                    for p in AccessLevel:
                        if p > AccessLevel.NONE:
                            usernames = [x.username for x in await uconn.list_peer_users(user.id, p)]
                            if usernames:
                                print(f'- Peers [{p.name}]: {", ".join(usernames)}')
        
def main():
    asyncio.run(_main())

if __name__ == '__main__':
    main()