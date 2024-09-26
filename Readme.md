# File Storage Service (FSS)

A simple file/object storage service!

usage:
```sh
python -m cli.user add <username> <password>
python -m cli.serve
```

By default, the data will be stored in the `.storage_data` directory.  
The data storage can be set via environment variable `FSS_DATA`.

I provide a simple client to interact with the service.  
Just start a web server at `/frontend` and open `index.html` in your browser.

Currently, there is no file access-control, anyone can access any file with `GET` request.  
However, the path-listing is only available to the authenticated user (to their own files, under `<username>/`).  

Please refer to `frontend/api.js` for the API usage.  