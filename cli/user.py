import argparse, asyncio
from storage_service.database import Database, hash_credential



async def main():
    parser = argparse.ArgumentParser()
    sp = parser.add_subparsers(dest='subparser_name', required=True)
    sp_add = sp.add_parser('add')
    sp_add.add_argument('username', type=str)
    sp_add.add_argument('password', type=str)
    sp_add.add_argument('--admin', action='store_true')
    
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
    
    sp_list = sp.add_parser('list')
    sp_list.add_argument("-l", "--long", action="store_true")
    
    args = parser.parse_args()
    conn = await Database().init()
    
    if args.subparser_name == 'add':
        await conn.user.create_user(args.username, args.password, args.admin)
        print('User created')
    
    if args.subparser_name == 'delete':
        user = await conn.user.get_user(args.username)
        if user is None:
            print('User not found')
            exit(1)
        else:
            await conn.delete_user(user.id)
        print('User deleted')
    
    if args.subparser_name == 'set':
        user = await conn.user.get_user(args.username)
        if user is None:
            print('User not found')
            exit(1)
        await conn.user.set_user(user.username, args.password, args.admin)
        print('User updated')
    
    if args.subparser_name == 'list':
        async for user in conn.user.all():
            print(user)
            if args.long:
                print('  ', user.credential)
    
    await conn.commit()
    await conn.close()

if __name__ == '__main__':
    asyncio.run(main())