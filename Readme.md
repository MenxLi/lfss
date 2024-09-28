# Lightweight File Storage Service (LFSS)
[![PyPI](https://img.shields.io/pypi/v/lfss)](https://pypi.org/project/lfss/)

A lightweight file/object storage service!

Usage: 
```sh
pip install .
lfss-user add <username> <password>
lfss-serve
```

By default, the data will be stored in `.storage_data`. 
You can change storage directory using the `LFSS_DATA` environment variable.

I provide a simple client to interact with the service.  
Just start a web server at `/frontend` and open `index.html` in your browser.

The API usage is simple, just `GET`, `PUT`, `DELETE` to the `/<username>/file/url` path.  
Authentication is done via `Authorization` header, with the value `Bearer <token>`.  
You can refer to `frontend` as an application example, and `frontend/api.js` for the API usage.

By default, the service exposes all files to the public for `GET` requests, 
but file-listing is restricted to the user's own files.  
Please refer to [docs/Permission.md](./docs/Permission.md) for more details on the permission system.