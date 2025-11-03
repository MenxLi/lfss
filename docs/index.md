

LFSS stands for **Lite File Storage Service**,

It is a lightweight and high-performance object storage service, 
using sqlite and filesystem as the backend storage.

**Highlights:**

- User storage limit and access control.
- Pagination and sorted file listing for vast number of files.  
- High performance: high concurrency, near-native speed on stress tests.
- Support range requests, so you can stream large files / resume download.
- WebDAV compatible ([NOTE](./webdav.md)).