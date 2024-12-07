# WebDAV

It is convinient to make LFSS WebDAV compatible, because they both use HTTP `GET`, `PUT`, `DELETE` methods to interact with files.

However, WebDAV utilize more HTTP methods, 
which are disabled by default in LFSS, because they may not be supported by many middlewares or clients.   

The WebDAV support can be enabled by setting the `LFSS_WEBDAV` environment variable to `1`. 
i.e. 
```sh
LFSS_WEBDAV=1 lfss-serve
```
Please note:
1. **WebDAV support is experimental, and is currently not well-tested.**
2. LFSS not allow creating files in the root directory, however some client such as [Finder](https://sabre.io/dav/clients/finder/) will try to create files in the root directory. Thus, it is safer to mount the user directory only, e.g. `http://localhost:8000/<username>/`.
3. LFSS not allow directory creation, instead it creates directoy implicitly when a file is uploaded to a non-exist directory. 
   i.e. `PUT http://localhost:8000/<username>/dir/file.txt` will create the `dir` directory if it does not exist. 
   However, the WebDAV `MKCOL` method requires the directory to be created explicitly, so WebDAV `MKCOL` method instead create a decoy file on the path (`.lfss-keep`), and hide the file from the file listing by `PROPFIND` method. 
   This leads to: 
   1) You may see a `.lfss-keep` file in the directory with native file listing (e.g. `/_api/list-files`), but it is hidden in WebDAV clients.
   2) The directory may be deleted if there is no file in it and the `.lfss-keep` file is not created by WebDAV client.  

