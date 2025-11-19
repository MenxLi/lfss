## 0.16
### 0.16.1
- Add systemd file generation tool.
- Mime-type detection for markdown files.
- Add version cli to show client and server version.
- Fix py api version method return type.
- Fix origin environment variable name. 

### 0.16.0
- Add virtual user support.
- Remove peer relationships if set to none.
- Fix user deletion not remove user storage statistics.

## 0.15
### 0.15.6
- Fix static file missing for package distribution.

### 0.15.5
- Fix: Py API should not create data home directory.
- Fix: Load directory config from external storage.

### 0.15.4 
- Add docs for single directory config.
- Panel layout more compact.
- Fix docs build layout bug.

### 0.15.3
- Panel updates. 
- Fix: JS API default origin endpoint.

### 0.15.2
- Fix: Include static files in package distribution (fix previous release).

### 0.15.1
- Fix: Include static files in package distribution.

### 0.15.0
- Include `.docs` and `.panel` routes.
- Remove `lfss-panel`. 
- Fix: Public index file visibility. 

## 0.14
### 0.14.1
- Break: Change `.lfss-dir.json` to `.lfssdir.json` for directory config file (Yank previous release).

### 0.14.0
- Break: Remove `GET` directory path to list content. 
- Add directory config to control single directory permission and behavior.
- Add `parent` method to path record classes.
- Add version info to the package and server.
- Add http apis for user management. 
- Make `.api` alias for `_api` endpoints.
- Refactors on engine file structure.
- Fix list peers may include self. 

## 0.13
### 0.13.3
- Get multiple files can receive blank file list.
- Javascript api add `exists` method.
- Defer external blob deletion.

### 0.13.2
- Deferred external blob deletion.

### 0.13.1
- Include admin by default in `list_peers`. 
- Py client `config` as `dataclass` property.  

### 0.13.0
- Break: Py client GET API not handle 404 as None. 
- Break & Fix: Move will transfer ownership.
- Delete user transfer ownership of files outside their directory.
- In favor of `Client` instead of `Connector` for API client class.
- Add `/move` and `/set-perm` api for moving files and setting file permission.
- Add `/user` prefix for user related api.
- Add CLI command `mv`, `cp`, and `perm`. 
- Add `name` method for record classes. 
- Improve assertion error handling. 
- Add user storage query api and query exists api.
- Non-exist user path will return 404 instead of 400.
- Frontend add editor page for text files.

## 0.12

### 0.12.3
- Show partial list hint
- Delete command alias `rm`
- Fix download single file with overwrite option

### 0.12.2
- Setup optional dependencies
- Present only the name by default for CLI list command

### 0.12.1
- Add `cat` command
- Use unicode icons for CLI list command

### 0.12.0
- Change default script to client CLI
- Client CLI default to verbose output
- Client CLI subcommand rename and alias
- Add delete path and more error handling for client CLI

## 0.11

### 0.11.6
- Hint copy and move success for frontend.
- Add query user info and list peers api.
- Add user with random password if not specified.

### 0.11.5
- Script entry default to client CLI. 
- Fix single file download name deduce with decoding.
- Fix code misspell (minor).

### 0.11.4
- Fix SQL query for LIKE clause to escape special characters in path.

### 0.11.3
- Add method to get multiple files, maybe with content, at once.
- Allow copy directory files that the user is not the owner of.
- Environment variables to set origin and disable file logging.
- Fix error handling for some endpoints.
- Redirect CLI error output to stderr.
- Increase thumb image size to 64x64.

### 0.11.2
- Improve frontend directory upload feedback. 
- Set default large file threashold to 1M. 
- Increase default concurrent threads. 
- Use sqlite for logging.
- Add vacuum logs. 
- Refactor: use dir for directory path. 

### 0.11.1
- Rename api `get_meta` function.
- Frontend support upload directory.  
- Fix admin put to non-exists user path. 

### 0.11.0
- Copy file as hard link. 
- Add vacuum thumb and all.
- Thumb database use file_id as index. 
- improve username and url check with regular expression.

## 0.10

### 0.10.0
- Inherit permission from path owner for `unset` permission files.
- Add timeout and verify options for client api.
- Bundle small files in memory.

## 0.9

### 0.9.5
- Stream bundle path as zip file.
- Update authentication token hash format (need to reset password).

### 0.9.4
- Decode WebDAV file name. 
- Allow root-listing for WebDAV.
- Always return 207 status code for propfind.
- Refactor debounce utility. 

### 0.9.3
- Fix empty file getting.
- HTTP `PUT/POST` default to overwrite the file.
- Use shared implementations for `PUT`, `GET`, `DELETE` methods.
- Inherit permission on overwriting `unset` permission files.

### 0.9.2
- Native copy function.
- Only enable basic authentication if WebDAV is enabled.
- `WWW-Authenticate` header is now added to the response when authentication fails.

### 0.9.1
- Add WebDAV support.
- Code refactor, use `lfss.eng` and `lfss.svc`.

### 0.9.0
- User peer access control, now user can share their path with other users.
- Fix high concurrency database locking on file getting.