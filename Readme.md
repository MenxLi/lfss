# Lightweight File Storage Service (LFSS)

A lightweight file/object storage service!

Usage: 
```sh
pip install .
lfss-user add <username> <password>
lfss-serve
```

By default, the data will be stored in the `.storage_data` directory, in a sqlite database.  
The data storage can be set via environment variable `LFSS_DATA`.

I provide a simple client to interact with the service.  
Just start a web server at `/frontend` and open `index.html` in your browser.

Currently, there is no file access-control, anyone can access any file with `GET` request.  
However, the path-listing is only available to the authenticated user (to their own files, under `<username>/`).  

The API usage is simple, just `GET`, `PUT`, `DELETE` to the `/<username>/file/url` path.  
Authentication is done via `Authorization` header, with the value `Bearer <token>`.  
Please refer to `frontend` as an application example, and `frontend/api.js` for the API usage.