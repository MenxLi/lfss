from lfss.client.api import Connector

def test():
    conn = Connector()
    print(conn.whoami())
    print(conn.list_path('test/'))
    print(conn.put('test/test.txt', b'hello world', overwrite=True))
    print(conn.get('test/test.txt'))
    print(conn.get_metadata('test/'))
    print(conn.get_metadata('test/test.txt'))
    print(conn.delete('test/test.txt'))
    print(conn.get_metadata('test/test.txt'))

if __name__ == '__main__':
    test()