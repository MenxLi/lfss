from __future__ import annotations
from typing import Optional, Literal, Iterator
import os
import requests
import requests.adapters
import urllib.parse
from lfss.src.error import PathNotFoundError
from lfss.src.datatype import (
    FileReadPermission, FileRecord, DirectoryRecord, UserRecord, PathContents, 
    FileSortKey, DirSortKey
    )
from lfss.src.utils import ensure_uri_compnents

_default_endpoint = os.environ.get('LFSS_ENDPOINT', 'http://localhost:8000')
_default_token = os.environ.get('LFSS_TOKEN', '')

class Connector:
    class Session:
        def __init__(self, connector: Connector, pool_size: int = 10):
            self.connector = connector
            self.pool_size = pool_size
        def open(self):
            self.close()
            if self.connector._session is None:
                s = requests.Session()
                adapter = requests.adapters.HTTPAdapter(pool_connections=self.pool_size, pool_maxsize=self.pool_size)
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

    def __init__(self, endpoint=_default_endpoint, token=_default_token):
        assert token, "No token provided. Please set LFSS_TOKEN environment variable."
        self.config = {
            "endpoint": endpoint,
            "token": token
        }
        self._session: Optional[requests.Session] = None
    
    def session(self, pool_size: int = 10):
        """ avoid creating a new session for each request.  """
        return self.Session(self, pool_size)
    
    def _fetch_factory(
        self, method: Literal['GET', 'POST', 'PUT', 'DELETE'], 
        path: str, search_params: dict = {}
    ):
        if path.startswith('/'):
            path = path[1:]
        path = ensure_uri_compnents(path)
        def f(**kwargs):
            url = f"{self.config['endpoint']}/{path}" + "?" + urllib.parse.urlencode(search_params)
            headers: dict = kwargs.pop('headers', {})
            headers.update({
                'Authorization': f"Bearer {self.config['token']}",
            })
            if self._session is not None:
                response = self._session.request(method, url, headers=headers, **kwargs)
                response.raise_for_status()
            else:
                with requests.Session() as s:
                    response = s.request(method, url, headers=headers, **kwargs)
                    response.raise_for_status()
            return response
        return f

    def put(self, path: str, file_data: bytes, permission: int | FileReadPermission = 0, conflict: Literal['overwrite', 'abort', 'skip', 'skip-ahead'] = 'abort'):
        """Uploads a file to the specified path."""
        assert isinstance(file_data, bytes), "file_data must be bytes"

        # Skip ahead by checking if the file already exists
        if conflict == 'skip-ahead':
            exists = self.get_metadata(path)
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
    
    def put_json(self, path: str, data: dict, permission: int | FileReadPermission = 0, conflict: Literal['overwrite', 'abort', 'skip', 'skip-ahead'] = 'abort'):
        """Uploads a JSON file to the specified path."""
        assert path.endswith('.json'), "Path must end with .json"
        assert isinstance(data, dict), "data must be a dict"

        # Skip ahead by checking if the file already exists
        if conflict == 'skip-ahead':
            exists = self.get_metadata(path)
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
    
    def delete(self, path: str):
        """Deletes the file at the specified path."""
        self._fetch_factory('DELETE', path)()
    
    def get_metadata(self, path: str) -> Optional[FileRecord | DirectoryRecord]:
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
        
    def whoami(self) -> UserRecord:
        """Gets information about the current user."""
        response = self._fetch_factory('GET', '_api/whoami')()
        return UserRecord(**response.json())