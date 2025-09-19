## 0.11

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