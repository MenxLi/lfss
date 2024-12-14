
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