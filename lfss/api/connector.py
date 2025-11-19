from __future__ import annotations
import dataclasses
from typing import Optional, Literal
from collections.abc import Iterator
import os
import requests
import requests.adapters
import urllib.parse
from tempfile import SpooledTemporaryFile
from concurrent.futures import ThreadPoolExecutor, as_completed
DIR_CONFIG_FNAME = '.lfssdir.json'  # avoid create DATA_HOME, should be same as in config.py
from lfss.eng.datatype import (
    FileReadPermission, FileRecord, DirectoryRecord, UserRecord, PathContents, AccessLevel, 
    DirConfig, FileSortKey, DirSortKey
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

@dataclasses.dataclass
class ClientConfig:
    endpoint: str
    token: str

    verify: Optional[bool | str]
    timeout: Optional[num_t | tuple[num_t, num_t]]

    # backward compatibility
    def __getitem__(self, key):
        return getattr(self, key)

class Client:
    class Session:
        def __init__(
            self, client: Client, pool_size: int = 10, 
            retry: int = 1, backoff_factor: num_t = 0.5, status_forcelist: list[int] = [503]
            ):
            self.client = client
            self.pool_size = pool_size
            self.retry_adapter = requests.adapters.Retry(
                total=retry, backoff_factor=backoff_factor, status_forcelist=status_forcelist, 
            )
        def open(self):
            self.close()
            if self.client._session is None:
                s = requests.Session()
                adapter = requests.adapters.HTTPAdapter(pool_connections=self.pool_size, pool_maxsize=self.pool_size, max_retries=self.retry_adapter)
                s.mount('http://', adapter)
                s.mount('https://', adapter)
                self.client._session = s
        def close(self):
            if self.client._session is not None:
                self.client._session.close()
            self.client._session = None
        def __call__(self):
            return self.client
        def __enter__(self):
            self.open()
            return self.client
        def __exit__(self, exc_type, exc_value, traceback):
            self.close()

    def __init__(
        self, endpoint=_default_endpoint, token=_default_token, 
        timeout: Optional[num_t | tuple[num_t, num_t]]=None, 
        verify: Optional[bool | str] = None
        ):
        """
        - endpoint: the URL of the LFSS server. Default to $LFSS_ENDPOINT or http://localhost:8000.
        - token: the access token. Default to $LFSS_TOKEN.
        - timeout: the timeout for each request, can be either a single value or a tuple of two values (connect, read), refer to `requests.Session.request`.
        - verify: either a boolean or a string, to control SSL verification. Default to True, refer to `requests.Session.request`.
        """
        assert token, "No token provided. Please set LFSS_TOKEN environment variable."
        if verify is None and (v:= os.environ.get('LFSS_CLIENT_VERIFY', None)) is not None:
            if v in ['0', 'false', 'False']:
                verify = False
            elif v in ['1', 'true', 'True']:
                verify = True
            else:
                verify = v    # path to CA bundle

        self._config = ClientConfig(
            endpoint=endpoint,
            token=token, 
            timeout=timeout,
            verify=verify
        )
        self._session: Optional[requests.Session] = None
    
    @property
    def config(self): 
        return self._config
    
    def session(self, pool_size: int = 10, **kwargs):
        """ 
        Creates a session context manager for making multiple requests with connection pooling.
        This also provides automatic retries on failed requests. 
        Typical usage:
        ```python
        with client.session(pool_size=20, retry=3) as c, ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(c.get, f"/path/to/file_{i}.txt") for i in range(100)]
            for future in as_completed(futures):
                ...
        ```
        Please refer to `Client.Session` for the parameters.
        """
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
            url = f"{self.config.endpoint}/{path}" + "?" + urllib.parse.urlencode(search_params_t, doseq=True)
            headers: dict = kwargs.pop('headers', {})
            headers.update({
                'Authorization': f"Bearer {self.config.token}",
            })
            headers.update(extra_headers)
            if self._session is not None:
                response = self._session.request(
                    method, url, headers=headers, 
                    timeout=self.config.timeout, verify=self.config.verify, 
                    **kwargs
                    )
                response.raise_for_status()
            else:
                with requests.Session() as s:
                    response = s.request(
                        method, url, headers=headers, 
                        timeout=self.config.timeout, verify=self.config.verify, 
                        **kwargs
                    )
                    response.raise_for_status()
            return response
        return f
    
    def version(self) -> str:
        """
        Get the version of the LFSS server.
        To get the client version, use `lfss.__version__`.
        """
        response = self._fetch_factory('GET', '_api/version')()
        return response.json()
    
    def exists(self, path: str) -> bool:
        """Checks if a file/directory exists."""
        path = _p(path)
        try:
            self._fetch_factory('HEAD', path)()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return False
            raise e
        return True

    def put(self, path: str, file_data: bytes, permission: int | FileReadPermission = 0, conflict: Literal['overwrite', 'abort', 'skip', 'skip-ahead'] = 'abort'):
        """Upload a file to the specified path."""
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
        **This method is preferred for large files**  
        Upload a file to the specified path, using the POST method with form-data/multipart.  
        File can be a path to a file on disk, or bytes.
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
        """Upload a JSON file to the specified path."""
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
    
    def _get(self, path: str, stream: bool = False) -> requests.Response:
        return self._fetch_factory('GET', path)(stream=stream)

    def get(self, path: str) -> bytes:
        """Download a file from the specified path."""
        path = _p(path)
        response = self._get(path)
        return response.content

    def get_partial(self, path: str, range_start: int = -1, range_end: int = -1) -> bytes:
        """
        Download a partial file from the specified path.
        start and end are the byte offsets, both inclusive.
        """
        path = _p(path)
        response = self._fetch_factory('GET', path, extra_headers={
            'Range': f"bytes={range_start if range_start >= 0 else ''}-{range_end if range_end >= 0 else ''}"
        })()
        return response.content
    
    def get_stream(self, path: str, chunk_size = 1024) -> Iterator[bytes]:
        """Download a file from the specified path, as a stream of bytes."""
        path = _p(path)
        return self._get(path, stream=True).iter_content(chunk_size)

    def get_json(self, path: str) -> dict:
        """ Get the JSON content of a file at the specified path. """
        path = _p(path)
        response = self._get(path)
        return response.json()
    
    def get_text(self, path: str) -> str:
        """ Get the text content of a file at the specified path. """
        path = _p(path)
        response = self._get(path)
        return response.text
    
    def get_multiple_text(self, *paths: str, skip_content = False) -> dict[str, Optional[str]]:
        """ 
        Get text contents of multiple files at once. Non-existing files will return None. 
        - skip_content: if True, the file contents will not be fetched, always be empty string ''.
        If some of the files do not exist, they will be returned as None.  
        """
        response = self._fetch_factory(
            'GET', '_api/get-multiple', 
            {'path': [_p(p) for p in paths], "skip_content": skip_content}
            )()
        return response.json()
    
    def delete(self, path: str):
        """Delete the file or directory at the specified path."""
        path = _p(path)
        self._fetch_factory('DELETE', path)()
    
    def get_meta(self, path: str) -> FileRecord | DirectoryRecord:
        """Get the metadata for the file at the specified path."""
        path = _p(path)
        response = self._fetch_factory('GET', '_api/meta', {'path': path})()
        if path.endswith('/'):
            return DirectoryRecord(**response.json())
        else:
            return FileRecord(**response.json())
    # shorthand methods for type constraints
    def get_fmeta(self, path: str) -> FileRecord: assert isinstance(f:=self.get_meta(path), FileRecord); return f
    def get_dmeta(self, path: str) -> DirectoryRecord: assert isinstance(d:=self.get_meta(path), DirectoryRecord); return d

    def count_files(self, path: str, flat: bool = False) -> int:
        """
        Count files under the given path.   
        If flat is True, count all files under the path recursively.
        """
        assert path.endswith('/')
        path = _p(path)
        response = self._fetch_factory('GET', '_api/count-files', {'path': path, 'flat': flat})()
        return response.json()['count']

    def list_files(
        self, path: str, offset: int = 0, limit: int = 1000,
        order_by: FileSortKey = '', order_desc: bool = False, 
        flat: bool = False
    ) -> list[FileRecord]:
        """
        List files under the given path.   
        If flat is True, list all files under the path recursively.
        """
        assert path.endswith('/')
        path = _p(path)
        response = self._fetch_factory('GET', "_api/list-files", {
            'path': path,
            'offset': offset, 'limit': limit, 'order_by': order_by, 'order_desc': order_desc, 'flat': flat
        })()
        return [FileRecord(**f) for f in response.json()]
    
    def count_dirs(self, path: str) -> int:
        """ Count directories under the given path."""
        assert path.endswith('/')
        path = _p(path)
        response = self._fetch_factory('GET', '_api/count-dirs', {'path': path})()
        return response.json()['count']
        
    def list_dirs(
        self, path: str, offset: int = 0, limit: int = 1000,
        order_by: DirSortKey = '', order_desc: bool = False, 
        skim: bool = True
    ) -> list[DirectoryRecord]:
        """
        List directories under the given path.
        If skim is True, only fetch basic information -- url.
        """
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
            my_username = self.whoami().username
            dirnames = ([f'{my_username}/'] if not my_username.startswith('.') else []) + [f'{p.username}/' for p in self.peers(AccessLevel.READ)]
            return PathContents(
                dirs = [DirectoryRecord(url = d) for d in dirnames], 
                files = []
            )

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
        """Set the file permission for the specified path."""
        path = _p(path)
        self._fetch_factory('POST', '_api/set-perm', {'path': path, 'perm': int(permission)})(
            headers={'Content-Type': 'application/www-form-urlencoded'}
        )
        
    def move(self, path: str, new_path: str):
        """Move file or directory to a new path."""
        path = _p(path); new_path = _p(new_path)
        self._fetch_factory('POST', '_api/move', {'src': path, 'dst': new_path})(
            headers = {'Content-Type': 'application/www-form-urlencoded'}
        )
    
    def copy(self, src: str, dst: str):
        """Copy file or directory from src to dst."""
        src = _p(src); dst = _p(dst)
        self._fetch_factory('POST', '_api/copy', {'src': src, 'dst': dst})(
            headers = {'Content-Type': 'application/www-form-urlencoded'}
        )
    
    def bundle(self, path: str) -> Iterator[bytes]:
        """Bundle a directory into a zip file."""
        path = _p(path)
        response = self._fetch_factory('GET', '_api/bundle', {'path': path})(
            headers = {'Content-Type': 'application/www-form-urlencoded'}, 
            stream = True
        )
        return response.iter_content(chunk_size=1024)
        
    def whoami(self) -> UserRecord:
        """Get information about the current user."""
        response = self._fetch_factory('GET', '_api/user/whoami')()
        return UserRecord(**response.json())
    
    # ========================== Quasi-Admin APIs ==========================

    # only admin/owner access
    def query_dir_config(self, dir_path: str) -> DirConfig:
        assert dir_path.endswith('/'), "Path must be a directory (end with '/')"
        cpath = _p(dir_path + DIR_CONFIG_FNAME)
        if not self.exists(cpath):
            return DirConfig()
        json_obj = self.get_json(cpath)
        return DirConfig.from_json(json_obj)

    # only admin/owner access
    def set_dir_config(self, dir_path: str, config: DirConfig):
        assert dir_path.endswith('/'), "Path must be a directory (end with '/')"
        return self.put(
            _p(dir_path + DIR_CONFIG_FNAME),
            config.to_json_str().encode('utf-8'),
            permission=FileReadPermission.PRIVATE, 
            conflict='overwrite'
        )

    # only admin access if as_user is provided
    def storage_used(self, as_user: Optional[str] = None) -> int:
        """Get the storage used by the current user, in bytes."""
        response = self._fetch_factory(
            'GET', '_api/user/storage', {'as_user': as_user} if as_user else {}
            )()
        return response.json()['used']

    # only admin access if as_user is provided
    def peers(
        self, 
        level: AccessLevel = AccessLevel.READ, 
        incoming: bool = False, 
        admin: bool = True, 
        as_user: Optional[str] = None
        ) -> list[UserRecord]:
        """
        if incoming is False (default): 
            list all users that the current user has at least the given access level to, 
        if incoming is True: 
            list all users that have at least the given access level to the current user
        if admin is True (default):
            include admin users in the result / list all users if the current user is admin.

        - as_user: if provided, perform the operation as the specified user (caller must be admin).
        """
        params = { 'level': int(level), 'incoming': incoming, 'admin': admin }
        if as_user is not None:
            params['as_user'] = as_user
        response = self._fetch_factory('GET', '_api/list-peers', params)()
        users = [UserRecord(**u) for u in response.json()]
        return users
    
    def query_user(self, u: int | str) -> UserRecord:
        """ 
        Query user information by username or userid. 
        If the current user is admin, the returned UserRecord is not desensitized.
        """
        params = {}
        if isinstance(u, int):
            params['userid'] = u
        else:
            params['username'] = u
        response = self._fetch_factory('GET', '_api/user/query', params)()
        return UserRecord(**response.json())

    # ========================== Admin APIs ==========================
    def add_user(
        self, 
        username: str, 
        password: Optional[str] = None, 
        admin: bool = False, 
        max_storage: int | str = '10G', 
        permission: FileReadPermission | str = 'unset'
        ) -> UserRecord:
        """ Admin API: Add a new user to the system. """
        data = {
            'username': username,
            'admin': admin,
            'max_storage': str(max_storage),
            'permission': str(permission).upper()
        }
        if password is not None:
            data['password'] = password
        response = self._fetch_factory('POST', '_api/user/add', search_params=data)()
        return UserRecord(**response.json())
    
    def add_virtual_user(
        self, 
        tag: str = "", 
        peers: dict[AccessLevel, list[str]] | str = {},
        max_storage: int | str = '1G', 
        expire: Optional[int | str] = None, 
        ) -> UserRecord:
        """ Admin API: Add a new virtual (hidden) user to the system. """
        data = {
            'tag': tag,
            'max_storage': str(max_storage),
        }
        if isinstance(peers, dict):
            peer_strs = []
            for level, users in peers.items():
                peer_strs.append(f"{level.name}:{','.join(users)}")
            data['peers'] = ';'.join(peer_strs)
        else:
            data['peers'] = peers
        if expire is not None:
            data['expire'] = str(expire)
        response = self._fetch_factory('POST', '_api/user/add-virtual', search_params=data)()
        return UserRecord(**response.json())
    
    def set_user(
        self, 
        username: str, 
        password: Optional[str] = None, 
        admin: Optional[bool] = None, 
        max_storage: Optional[int | str] = None, 
        permission: Optional[FileReadPermission | str] = None
        ) -> UserRecord:
        """ Admin API: Update user information. """
        data = {}
        data['username'] = username
        if password is not None:
            data['password'] = password
        if admin is not None:
            data['admin'] = admin
        if max_storage is not None:
            data['max_storage'] = str(max_storage)
        if permission is not None:
            data['permission'] = permission.name \
                if isinstance(permission, FileReadPermission) else permission
        response = self._fetch_factory('POST', '_api/user/update', search_params=data)()
        return UserRecord(**response.json())
    
    def delete_user(self, username: str) -> UserRecord:
        """ Admin API: Delete a user from the system. """
        response = self._fetch_factory('POST', '_api/user/delete', {'username': username})()
        return UserRecord(**response.json())
    
    def set_peer(
        self, 
        src_username: str, 
        dst_username: str, 
        level: AccessLevel | str = AccessLevel.READ
        ):
        """ Admin API: Set peer access level between two users. """
        self._fetch_factory('POST', '_api/user/set-peer', {
            'src_username': src_username,
            'dst_username': dst_username,
            'level': level.name if isinstance(level, AccessLevel) else level
        })()