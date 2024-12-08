
# Enviroment variables

**Server**
- `LFSS_DATA`: The directory to store the data. Default is `.storage_data`.
- `LFSS_WEBDAV`: Enable WebDAV support. Default is `0`, set to `1` to enable.
- `LFSS_LARGE_FILE`: The size limit of the file to store in the database. Default is `8m`.
- `LFSS_DEBUG`: Enable debug mode for more verbose logging. Default is `0`, set to `1` to enable.

**Client**
- `LFSS_ENDPOINT`: The fallback server endpoint. Default is `http://localhost:8000`.
- `LFSS_TOKEN`: The fallback token to authenticate. Should be `sha256(<username><password>)`.