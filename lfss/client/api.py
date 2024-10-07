from typing import Optional, Literal
import os
import requests
import urllib.parse
from lfss.src.datatype import (
    FileReadPermission, FileRecord, DirectoryRecord, UserRecord, PathContents
    )

_default_endpoint = os.environ.get('LFSS_ENDPOINT', 'http://localhost:8000')
_default_token = os.environ.get('LFSS_TOKEN', '')

class Connector:
    def __init__(self, endpoint=_default_endpoint, token=_default_token):
        assert token, "No token provided. Please set LFSS_TOKEN environment variable."
        self.config = {
            "endpoint": endpoint,
            "token": token
        }
    
    def _fetch(
        self, method: Literal['GET', 'POST', 'PUT', 'DELETE'], 
        path: str, search_params: dict = {}
    ):
        if path.startswith('/'):
            path = path[1:]
        def f(**kwargs):
            url = f"{self.config['endpoint']}/{path}" + "?" + urllib.parse.urlencode(search_params)
            headers: dict = kwargs.pop('headers', {})
            headers.update({
                'Authorization': f"Bearer {self.config['token']}",
            })
            response = requests.request(method, url, headers=headers, **kwargs)
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

        response = self._fetch('PUT', path, search_params={
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

        response = self._fetch('PUT', path, search_params={
            'permission': int(permission),
            'conflict': conflict
            })(
            json=data, 
            headers={'Content-Type': 'application/json'}
        )
        return response.json()
    
    def _get(self, path: str) -> Optional[requests.Response]:
        try:
            response = self._fetch('GET', path)()
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

    def get_json(self, path: str) -> Optional[dict]:
        response = self._get(path)
        if response is None: return None
        assert response.headers['Content-Type'] == 'application/json'
        return response.json()
    
    def delete(self, path: str):
        """Deletes the file at the specified path."""
        self._fetch('DELETE', path)()
    
    def get_metadata(self, path: str) -> Optional[FileRecord | DirectoryRecord]:
        """Gets the metadata for the file at the specified path."""
        try:
            response = self._fetch('GET', '_api/meta', {'path': path})()
            if path.endswith('/'):
                return DirectoryRecord(**response.json())
            else:
                return FileRecord(**response.json())
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise e
    
    def list_path(self, path: str) -> PathContents:
        assert path.endswith('/')
        response = self._fetch('GET', path)()
        return PathContents(**response.json())

    def set_file_permission(self, path: str, permission: int | FileReadPermission):
        """Sets the file permission for the specified path."""
        self._fetch('POST', '_api/meta', {'path': path, 'perm': int(permission)})(
            headers={'Content-Type': 'application/www-form-urlencoded'}
        )
        
    def move(self, path: str, new_path: str):
        """Move file or directory to a new path."""
        self._fetch('POST', '_api/meta', {'path': path, 'new_path': new_path})(
            headers = {'Content-Type': 'application/www-form-urlencoded'}
        )
        
    def whoami(self) -> UserRecord:
        """Gets information about the current user."""
        response = self._fetch('GET', '_api/whoami')()
        return UserRecord(**response.json())