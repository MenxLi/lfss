import argparse, asyncio
from contextlib import asynccontextmanager
from .cli import parse_permission, FileReadPermission
from ..src.utils import parse_storage_size
from ..src.database import Database, FileReadPermission, transaction, UserConn
from ..src.connection_pool import global_entrance

@global_entrance(1)
async def _main():
    parser = argparse.ArgumentParser()
    sp = parser.add_subparsers(dest='subparser_name', required=True)
    sp_add = sp.add_parser('add')
    sp_add.add_argument('username', type=str)
    sp_add.add_argument('password', type=str)
    sp_add.add_argument('--admin', action='store_true', help='Set user as admin')
    sp_add.add_argument("--permission", type=parse_permission, default=FileReadPermission.UNSET, help="File permission, can be public, protected, private, or unset")
    sp_add.add_argument('--max-storage', type=parse_storage_size, default="1G", help="Maximum storage size, e.g. 1G, 100M, 10K")
    
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
    sp_list.add_argument("-l", "--long", action="store_true")
    
    args = parser.parse_args()
    db = await Database().init()

    @asynccontextmanager
    async def get_uconn():
        async with transaction() as conn:
            yield UserConn(conn)
    
    if args.subparser_name == 'add':
        async with get_uconn() as uconn:
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
    
    if args.subparser_name == 'list':
        async with get_uconn() as uconn:
            async for user in uconn.all():
                print(user)
                if args.long:
                    print('  ', user.credential)
        
def main():
    asyncio.run(_main())

if __name__ == '__main__':
    main()