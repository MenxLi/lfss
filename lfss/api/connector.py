from __future__ import annotations
from typing import Optional, Literal
from collections.abc import Iterator
import os, json
import requests
import requests.adapters
import urllib.parse
from tempfile import SpooledTemporaryFile
from lfss.eng.error import PathNotFoundError
from lfss.eng.datatype import (
    FileReadPermission, FileRecord, DirectoryRecord, UserRecord, PathContents, 
    FileSortKey, DirSortKey
    )
from lfss.eng.utils import ensure_uri_compnents

_default_endpoint = os.environ.get('LFSS_ENDPOINT', 'http://localhost:8000')
_default_token = os.environ.get('LFSS_TOKEN', '')
num_t = float | int

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
        self, method: Literal['GET', 'POST', 'PUT', 'DELETE'], 
        path: str, search_params: dict = {}, extra_headers: dict = {}
    ):
        if path.startswith('/'):
            path = path[1:]
        path = ensure_uri_compnents(path)
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

    def put(self, path: str, file_data: bytes, permission: int | FileReadPermission = 0, conflict: Literal['overwrite', 'abort', 'skip', 'skip-ahead'] = 'abort'):
        """Uploads a file to the specified path."""
        assert isinstance(file_data, bytes), "file_data must be bytes"

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
        response = self._get(path)
        if response is None: return None
        return response.content

    def get_partial(self, path: str, range_start: int = -1, range_end: int = -1) -> Optional[bytes]:
        """
        Downloads a partial file from the specified path.
        start and end are the byte offsets, both inclusive.
        """
        response = self._fetch_factory('GET', path, extra_headers={
            'Range': f"bytes={range_start if range_start >= 0 else ''}-{range_end if range_end >= 0 else ''}"
        })()
        if response is None: return None
        return response.content
    
    def get_stream(self, path: str) -> Iterator[bytes]:
        """Downloads a file from the specified path, will raise PathNotFoundError if path not found."""
        response = self._get(path, stream=True)
        if response is None: raise PathNotFoundError("Path not found: " + path)
        return response.iter_content(chunk_size=1024)

    def get_json(self, path: str) -> Optional[dict]:
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
            {'path': paths, "skip_content": skip_content}
            )()
        return response.json()
    
    def delete(self, path: str):
        """Deletes the file at the specified path."""
        self._fetch_factory('DELETE', path)()
    
    def get_meta(self, path: str) -> Optional[FileRecord | DirectoryRecord]:
        """Gets the metadata for the file at the specified path."""
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
    
    def list_path(self, path: str) -> PathContents:
        """ 
        shorthand list with limited options, 
        for large directories / more options, use list_files and list_dirs instead.
        """
        assert path.endswith('/')
        response = self._fetch_factory('GET', path)()
        dirs = [DirectoryRecord(**d) for d in response.json()['dirs']]
        files = [FileRecord(**f) for f in response.json()['files']]
        return PathContents(dirs=dirs, files=files)
    
    def count_files(self, path: str, flat: bool = False) -> int:
        assert path.endswith('/')
        response = self._fetch_factory('GET', '_api/count-files', {'path': path, 'flat': flat})()
        return response.json()['count']

    def list_files(
        self, path: str, offset: int = 0, limit: int = 1000,
        order_by: FileSortKey = '', order_desc: bool = False, 
        flat: bool = False
    ) -> list[FileRecord]:
        assert path.endswith('/')
        response = self._fetch_factory('GET', "_api/list-files", {
            'path': path,
            'offset': offset, 'limit': limit, 'order_by': order_by, 'order_desc': order_desc, 'flat': flat
        })()
        return [FileRecord(**f) for f in response.json()]
    
    def count_dirs(self, path: str) -> int:
        assert path.endswith('/')
        response = self._fetch_factory('GET', '_api/count-dirs', {'path': path})()
        return response.json()['count']
        
    def list_dirs(
        self, path: str, offset: int = 0, limit: int = 1000,
        order_by: DirSortKey = '', order_desc: bool = False, 
        skim: bool = True
    ) -> list[DirectoryRecord]:
        assert path.endswith('/')
        response = self._fetch_factory('GET', "_api/list-dirs", {
            'path': path,
            'offset': offset, 'limit': limit, 'order_by': order_by, 'order_desc': order_desc, 'skim': skim
        })()
        return [DirectoryRecord(**d) for d in response.json()]

    def set_file_permission(self, path: str, permission: int | FileReadPermission):
        """Sets the file permission for the specified path."""
        self._fetch_factory('POST', '_api/meta', {'path': path, 'perm': int(permission)})(
            headers={'Content-Type': 'application/www-form-urlencoded'}
        )
        
    def move(self, path: str, new_path: str):
        """Move file or directory to a new path."""
        self._fetch_factory('POST', '_api/meta', {'path': path, 'new_path': new_path})(
            headers = {'Content-Type': 'application/www-form-urlencoded'}
        )
    
    def copy(self, src: str, dst: str):
        """Copy file from src to dst."""
        self._fetch_factory('POST', '_api/copy', {'src': src, 'dst': dst})(
            headers = {'Content-Type': 'application/www-form-urlencoded'}
        )
    
    def bundle(self, path: str) -> Iterator[bytes]:
        """Bundle a path into a zip file."""
        response = self._fetch_factory('GET', '_api/bundle', {'path': path})(
            headers = {'Content-Type': 'application/www-form-urlencoded'}, 
            stream = True
        )
        return response.iter_content(chunk_size=1024)
        
    def whoami(self) -> UserRecord:
        """Gets information about the current user."""
        response = self._fetch_factory('GET', '_api/whoami')()
        return UserRecord(**response.json())