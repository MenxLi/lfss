# Lite File Storage Service (LFSS)
[![PyPI](https://img.shields.io/pypi/v/lfss)](https://pypi.org/project/lfss/) [![PyPI - Downloads](https://img.shields.io/pypi/dm/lfss)](https://pypi.org/project/lfss/)

My experiment on a lightweight and high-performance file/object storage service...  

**Highlights:**

- User storage limit and access control.
- Pagination and sorted file listing for vast number of files.  
- High performance: high concurrency, near-native speed on stress tests.
- Support range requests, so you can stream large files / resume download.
- WebDAV compatible ([NOTE](./docs/Webdav.md)).

It stores small files and metadata in sqlite, large files in the filesystem.  
Tested on 2 million files, and it is still fast.

Usage: 
```sh
pip install "lfss[all]"
lfss-user add <username> <password>
lfss-serve
```

By default, the data will be stored in `.storage_data`. 
You can change storage directory using the `LFSS_DATA` environment variable.

I provide a simple client to interact with the service: 
```sh
lfss-panel --open
```
Or, you can start a web server at `/frontend` and open `index.html` in your browser. 

The API usage is simple, just `GET`, `PUT`, `DELETE` to the `/<username>/file/url` path.  
The authentication can be acheived through one of the following methods:
1. `Authorization` header with the value `Bearer sha256(<username>:<password>)`.
2. `token` query parameter with the value `sha256(<username>:<password>)`.
3. HTTP Basic Authentication with the username and password (If WebDAV is enabled).

You can refer to `frontend` as an application example, `lfss/api/connector.py` for more APIs. 

By default, the service exposes all files to the public for `GET` requests, 
but file-listing is restricted to the user's own files.  
Please refer to [docs/Permission.md](./docs/Permission.md) for more details on the permission system. 

More can be found in the [docs](./docs) directory.