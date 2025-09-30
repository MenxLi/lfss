from __future__ import annotations
from typing import Optional, Literal
from collections.abc import Iterator
import os
import requests
import requests.adapters
import urllib.parse
from tempfile import SpooledTemporaryFile
from concurrent.futures import ThreadPoolExecutor, as_completed
from lfss.eng.error import PathNotFoundError
from lfss.eng.datatype import (
    FileReadPermission, FileRecord, DirectoryRecord, UserRecord, PathContents, AccessLevel, 
    FileSortKey, DirSortKey
    )
from lfss.eng.utils import ensure_uri_components

_default_endpoint = os.environ.get('LFSS_ENDPOINT', 'http://localhost:8000')
_default_token = os.environ.get('LFSS_TOKEN', '')
num_t = float | int

def _p(x: str) -> str:
    if x == '/':
        return x
    if x.startswith('/'):
        x = x[1:]
    return x

class Connector:
    class Session:
        def __init__(
            self, connector: Connector, pool_size: int = 10, 
            retry: int = 1, backoff_factor: num_t = 0.5, status_forcelist: list[int] = [503]
            ):
            self.connector = connector
            self.pool_size = pool_size
            self.retry_adapter = requests.adapters.Retry(
                total=retry, backoff_factor=backoff_factor, status_forcelist=status_forcelist, 
            )
        def open(self):
            self.close()
            if self.connector._session is None:
                s = requests.Session()
                adapter = requests.adapters.HTTPAdapter(pool_connections=self.pool_size, pool_maxsize=self.pool_size, max_retries=self.retry_adapter)
                s.mount('http://', adapter)
                s.mount('https://', adapter)
                self.connector._session = s
        def close(self):
            if self.connector._session is not None:
                self.connector._session.close()
            self.connector._session = None
        def __call__(self):
            return self.connector
        def __enter__(self):
            self.open()
            return self.connector
        def __exit__(self, exc_type, exc_value, traceback):
            self.close()

    def __init__(self, endpoint=_default_endpoint, token=_default_token, timeout: Optional[num_t | tuple[num_t, num_t]]=None, verify: Optional[bool | str] = None):
        """
        - endpoint: the URL of the LFSS server. Default to $LFSS_ENDPOINT or http://localhost:8000.
        - token: the access token. Default to $LFSS_TOKEN.
        - timeout: the timeout for each request, can be either a single value or a tuple of two values (connect, read), refer to requests.Session.request.
        - verify: either a boolean or a string, to control SSL verification. Default to True, refer to requests.Session.request.
        """
        assert token, "No token provided. Please set LFSS_TOKEN environment variable."
        self.config = {
            "endpoint": endpoint,
            "token": token
        }
        self._session: Optional[requests.Session] = None
        self.timeout = timeout
        self.verify = verify
    
    def session( self, pool_size: int = 10, **kwargs):
        """ avoid creating a new session for each request.  """
        return self.Session(self, pool_size, **kwargs)
    
    def _fetch_factory(
        self, method: Literal['GET', 'POST', 'PUT', 'DELETE', 'HEAD'], 
        path: str, search_params: dict = {}, extra_headers: dict = {}
    ):
        if path.startswith('/'):
            path = path[1:]
        path = ensure_uri_components(path)
        def f(**kwargs):
            search_params_t = [
                (k, str(v).lower() if isinstance(v, bool) else v)
                for k, v in search_params.items()
            ]   # tuple form
            url = f"{self.config['endpoint']}/{path}" + "?" + urllib.parse.urlencode(search_params_t, doseq=True)
            headers: dict = kwargs.pop('headers', {})
            headers.update({
                'Authorization': f"Bearer {self.config['token']}",
            })
            headers.update(extra_headers)
            if self._session is not None:
                response = self._session.request(method, url, headers=headers, timeout=self.timeout, verify=self.verify, **kwargs)
                response.raise_for_status()
            else:
                with requests.Session() as s:
                    response = s.request(method, url, headers=headers, timeout=self.timeout, verify=self.verify, **kwargs)
                    response.raise_for_status()
            return response
        return f
    
    def exists(self, path: str) -> bool:
        """Checks if a file/directory exists."""
        path = _p(path)
        try:
            response = self._fetch_factory('HEAD', path)()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return False
            raise e
        return response.status_code == 200

    def put(self, path: str, file_data: bytes, permission: int | FileReadPermission = 0, conflict: Literal['overwrite', 'abort', 'skip', 'skip-ahead'] = 'abort'):
        """Uploads a file to the specified path."""
        assert isinstance(file_data, bytes), "file_data must be bytes"
        path = _p(path)

        # Skip ahead by checking if the file already exists
        if conflict == 'skip-ahead':
            exists = self.get_meta(path)
            if exists is None:
                conflict = 'skip'
            else:
                return {'status': 'skipped', 'path': path}

        response = self._fetch_factory('PUT', path, search_params={
            'permission': int(permission),
            'conflict': conflict
            })(
            data=file_data, 
            headers={'Content-Type': 'application/octet-stream'}
        )
        return response.json()
    
    def post(self, path, file: str | bytes, permission: int | FileReadPermission = 0, conflict: Literal['overwrite', 'abort', 'skip', 'skip-ahead'] = 'abort'):
        """
        Uploads a file to the specified path, 
        using the POST method, with form-data/multipart.
        file can be a path to a file on disk, or bytes.
        """
        path = _p(path)

        # Skip ahead by checking if the file already exists
        if conflict == 'skip-ahead':
            exists = self.get_meta(path)
            if exists is None:
                conflict = 'skip'
            else:
                return {'status': 'skipped', 'path': path}
        
        if isinstance(file, str):
            assert os.path.exists(file), "File does not exist on disk"

        with open(file, 'rb') if isinstance(file, str) else SpooledTemporaryFile(max_size=1024*1024*32) as fp:

            if isinstance(file, bytes):
                fsize = len(file)
                fp.write(file)
                fp.seek(0)

            # https://stackoverflow.com/questions/12385179/
            response = self._fetch_factory('POST', path, search_params={
                'permission': int(permission),
                'conflict': conflict
                })(
                files={'file': fp},
            )
        return response.json()
    
    def put_json(self, path: str, data: dict, permission: int | FileReadPermission = 0, conflict: Literal['overwrite', 'abort', 'skip', 'skip-ahead'] = 'abort'):
        """Uploads a JSON file to the specified path."""
        assert path.endswith('.json'), "Path must end with .json"
        assert isinstance(data, dict), "data must be a dict"
        path = _p(path)

        # Skip ahead by checking if the file already exists
        if conflict == 'skip-ahead':
            exists = self.get_meta(path)
            if exists is None:
                conflict = 'skip'
            else:
                return {'status': 'skipped', 'path': path}

        response = self._fetch_factory('PUT', path, search_params={
            'permission': int(permission),
            'conflict': conflict
            })(
            json=data, 
            headers={'Content-Type': 'application/json'}
        )
        return response.json()
    
    def _get(self, path: str, stream: bool = False) -> Optional[requests.Response]:
        try:
            response = self._fetch_factory('GET', path)(stream=stream)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise e
        return response

    def get(self, path: str) -> Optional[bytes]:
        """Downloads a file from the specified path."""
        path = _p(path)
        response = self._get(path)
        if response is None: return None
        return response.content

    def get_partial(self, path: str, range_start: int = -1, range_end: int = -1) -> Optional[bytes]:
        """
        Downloads a partial file from the specified path.
        start and end are the byte offsets, both inclusive.
        """
        path = _p(path)
        response = self._fetch_factory('GET', path, extra_headers={
            'Range': f"bytes={range_start if range_start >= 0 else ''}-{range_end if range_end >= 0 else ''}"
        })()
        if response is None: return None
        return response.content
    
    def get_stream(self, path: str, chunk_size = 1024) -> Iterator[bytes]:
        """Downloads a file from the specified path, will raise PathNotFoundError if path not found."""
        path = _p(path)
        response = self._get(path, stream=True)
        if response is None: raise PathNotFoundError("Path not found: " + path)
        return response.iter_content(chunk_size)

    def get_json(self, path: str) -> Optional[dict]:
        path = _p(path)
        response = self._get(path)
        if response is None: return None
        assert response.headers['Content-Type'] == 'application/json'
        return response.json()
    
    def get_multiple_text(self, *paths: str, skip_content = False) -> dict[str, Optional[str]]:
        """ 
        Gets text contents of multiple files at once. Non-existing files will return None. 
        - skip_content: if True, the file contents will not be fetched, always be empty string ''.
        """
        response = self._fetch_factory(
            'GET', '_api/get-multiple', 
            {'path': [_p(p) for p in paths], "skip_content": skip_content}
            )()
        return response.json()
    
    def delete(self, path: str):
        """Deletes the file at the specified path."""
        path = _p(path)
        self._fetch_factory('DELETE', path)()
    
    def get_meta(self, path: str) -> Optional[FileRecord | DirectoryRecord]:
        """Gets the metadata for the file at the specified path."""
        path = _p(path)
        try:
            response = self._fetch_factory('GET', '_api/meta', {'path': path})()
            if path.endswith('/'):
                return DirectoryRecord(**response.json())
            else:
                return FileRecord(**response.json())
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise e
    # shorthand methods for type constraints
    def get_fmeta(self, path: str) -> Optional[FileRecord]: assert (f:=self.get_meta(path)) is None or isinstance(f, FileRecord); return f 
    def get_dmeta(self, path: str) -> Optional[DirectoryRecord]: assert (d:=self.get_meta(path)) is None or isinstance(d, DirectoryRecord); return d
    
    def count_files(self, path: str, flat: bool = False) -> int:
        assert path.endswith('/')
        path = _p(path)
        response = self._fetch_factory('GET', '_api/count-files', {'path': path, 'flat': flat})()
        return response.json()['count']

    def list_files(
        self, path: str, offset: int = 0, limit: int = 1000,
        order_by: FileSortKey = '', order_desc: bool = False, 
        flat: bool = False
    ) -> list[FileRecord]:
        assert path.endswith('/')
        path = _p(path)
        response = self._fetch_factory('GET', "_api/list-files", {
            'path': path,
            'offset': offset, 'limit': limit, 'order_by': order_by, 'order_desc': order_desc, 'flat': flat
        })()
        return [FileRecord(**f) for f in response.json()]
    
    def count_dirs(self, path: str) -> int:
        assert path.endswith('/')
        path = _p(path)
        response = self._fetch_factory('GET', '_api/count-dirs', {'path': path})()
        return response.json()['count']
        
    def list_dirs(
        self, path: str, offset: int = 0, limit: int = 1000,
        order_by: DirSortKey = '', order_desc: bool = False, 
        skim: bool = True
    ) -> list[DirectoryRecord]:
        assert path.endswith('/')
        path = _p(path)
        response = self._fetch_factory('GET', "_api/list-dirs", {
            'path': path,
            'offset': offset, 'limit': limit, 'order_by': order_by, 'order_desc': order_desc, 'skim': skim
        })()
        return [DirectoryRecord(**d) for d in response.json()]
    
    def list_path(
        self, path: str, offset: int = 0, limit: int = 1000,
        order_by: FileSortKey = '', order_desc: bool = False, 
        _workers: int = 2
    ) -> PathContents:
        """ Aggregately lists both files and directories under the given path.  """
        assert path.endswith('/')
        path = _p(path)
        if path == '/':
            # handle root path separately
            # TODO: change later
            response = self._fetch_factory('GET', path)()
            dirs = [DirectoryRecord(**d) for d in response.json()['dirs']]
            files = [FileRecord(**f) for f in response.json()['files']]
            return PathContents(dirs=dirs, files=files)

        dirs: list[DirectoryRecord] = []
        files: list[FileRecord] = []
        with ThreadPoolExecutor(max_workers=_workers) as executor:
            count_futures = {
                executor.submit(self.count_dirs, path): 'dirs',
                executor.submit(self.count_files, path, flat=False): 'files'
            }
            dir_count = 0
            file_count = 0
            for future in as_completed(count_futures):
                if count_futures[future] == 'dirs':
                    dir_count = future.result()
                else:
                    file_count = future.result()
            dir_offset = offset
            dir_limit = min(limit, max(0, dir_count - dir_offset))
            file_offset = max(0, offset - dir_count)
            file_limit = min(limit - dir_limit, max(0, file_count - file_offset))

            dir_order_by = 'dirname' if order_by == 'url' else ''
            file_order_by = order_by

            def fetch_dirs():
                nonlocal dirs
                if dir_limit > 0:
                    dirs = self.list_dirs(
                        path, offset=dir_offset, limit=dir_limit, 
                        order_by=dir_order_by, order_desc=order_desc
                    )
            def fetch_files():
                nonlocal files
                if file_limit > 0:
                    files = self.list_files(
                        path, offset=file_offset, limit=file_limit, 
                        order_by=file_order_by, order_desc=order_desc, flat=False
                    )
            futures = [
                executor.submit(fetch_dirs),
                executor.submit(fetch_files)
            ]
            for future in as_completed(futures):
                future.result()
        return PathContents(dirs=dirs, files=files)

    def set_file_permission(self, path: str, permission: int | FileReadPermission):
        """Sets the file permission for the specified path."""
        path = _p(path)
        self._fetch_factory('POST', '_api/meta', {'path': path, 'perm': int(permission)})(
            headers={'Content-Type': 'application/www-form-urlencoded'}
        )
        
    def move(self, path: str, new_path: str):
        """Move file or directory to a new path."""
        path = _p(path); new_path = _p(new_path)
        self._fetch_factory('POST', '_api/meta', {'path': path, 'new_path': new_path})(
            headers = {'Content-Type': 'application/www-form-urlencoded'}
        )
    
    def copy(self, src: str, dst: str):
        """Copy file from src to dst."""
        src = _p(src); dst = _p(dst)
        self._fetch_factory('POST', '_api/copy', {'src': src, 'dst': dst})(
            headers = {'Content-Type': 'application/www-form-urlencoded'}
        )
    
    def bundle(self, path: str) -> Iterator[bytes]:
        """Bundle a path into a zip file."""
        path = _p(path)
        response = self._fetch_factory('GET', '_api/bundle', {'path': path})(
            headers = {'Content-Type': 'application/www-form-urlencoded'}, 
            stream = True
        )
        return response.iter_content(chunk_size=1024)
        
    def whoami(self) -> UserRecord:
        """Gets information about the current user."""
        response = self._fetch_factory('GET', '_api/whoami')()
        return UserRecord(**response.json())

    def list_peers(self, level: AccessLevel = AccessLevel.READ, incoming: bool = False) -> list[UserRecord]:
        """List all users that have at least the given access level to the current user."""
        response = self._fetch_factory('GET', '_api/list-peers', {'level': int(level), 'incoming': incoming})()
        users = [UserRecord(**u) for u in response.json()]
        return users