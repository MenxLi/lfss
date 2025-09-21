
/**
 * @typedef Config
 * @property {string} endpoint - the endpoint of the API
 * @property {string} token - the token to authenticate the user
 * 
 * Partially complete...
 * @typedef {Object} UserRecord
 * @property {number} id - the id of the user
 * @property {string} username - the username of the user
 * @property {boolean} is_admin - whether the user is an admin
 * @property {string} create_time - the time the user was created
 * @property {number} max_storage - the maximum storage the user can use
 * @property {number} permission - the default read permission of the files owned by the user
 * 
 * Partially complete...
 * @typedef {Object} FileRecord
 * @property {string} url - the url of the file
 * @property {number} owner_id - the id of the owner of the file
 * @property {number} file_size - the size of the file, in bytes
 * @property {string} create_time - the time the file was created
 * @property {string} access_time - the time the file was last accessed
 * @property {string} mime_type - the mime type of the file
 * 
 * Partially complete...
 * @typedef {Object} DirectoryRecord
 * @property {string} url - the url of the directory
 * @property {string} size - the size of the directory, in bytes
 * @property {string} create_time - the time the directory was created
 * @property {string} access_time - the time the directory was last accessed
 * @property {number} n_files - the number of total files in the directory, including subdirectories
 * 
 * @typedef {Object} PathListResponse
 * @property {DirectoryRecord[]} dirs - the list of directories in the directory
 * @property {FileRecord[]} files - the list of files in the directory
 * 
 * @typedef {"" | "url" | "file_size" | "create_time" | "access_time" | "mime_type"} FileSortKey
 * @typedef {"" | "dirname" } DirectorySortKey
 */

export const permMap = {
    0: 'unset',
    1: 'public',
    2: 'protected',
    3: 'private'
}

async function fmtFailedResponse(res){
    const raw = await res.text();
    const json = raw ? JSON.parse(raw) : {};
    const txt = JSON.stringify(json.detail || json || "No message");
    const maxWords = 32;
    if (txt.length > maxWords){
        return txt.slice(0, maxWords) + '...';
    }
    return txt;
}

export default class Connector {

    constructor(){
        /** @type {Config} */
        this.config = {
            endpoint: 'http://localhost:8000',
            token: ''
        }
    }

    /**
    * @param {string} path - the path to the file (url)
    * @param {File} file - the file to upload
    * @param {Object} [options] - Optional upload configuration.
    * @param {'abort' | 'overwrite' | 'skip'} [options.conflict='abort'] - Conflict resolution strategy:  
    * `'abort'` to cancel and raise 409, `'overwrite'` to replace.
    * @param {number} [options.permission=0] - Optional permission setting for the file (refer to backend impl).
    * @returns {Promise<string>} - the promise of the request, the url of the file
    */
    async put(path, file, {
        conflict = 'abort',
        permission = 0
    } = {}){
        if (path.startsWith('/')){ path = path.slice(1); }
        const fileBytes = await file.arrayBuffer();
        const dst = new URL(this.config.endpoint + '/' + path);
        dst.searchParams.append('conflict', conflict);
        dst.searchParams.append('permission', permission);
        const res = await fetch(dst.toString(), {
            method: 'PUT',
            headers: {
                'Authorization': 'Bearer ' + this.config.token, 
                'Content-Type': 'application/octet-stream', 
                'Content-Length': fileBytes.byteLength
            },
            body: fileBytes
        });
        if (res.status != 200 && res.status != 201){
            throw new Error(`Failed to upload file, status code: ${res.status}, message: ${await fmtFailedResponse(res)}`);
        }
        return (await res.json()).url;
    }

    /**
    * @param {string} path - the path to the file (url), should end with .json
    * @param {File} file - the file to upload
    * @param {Object} [options] - Optional upload configuration.
    * @param {'abort' | 'overwrite' | 'skip'} [options.conflict='abort'] - Conflict resolution strategy:  
    * `'abort'` to cancel and raise 409, `'overwrite'` to replace, `'skip'` to ignore if already exists.
    * @param {number} [options.permission=0] - Optional permission setting for the file (refer to backend impl).
    * @returns {Promise<string>} - the promise of the request, the url of the file
    */
    async post(path, file, {
        conflict = 'abort',
        permission = 0
    } = {}){
        if (path.startsWith('/')){ path = path.slice(1); }
        const dst = new URL(this.config.endpoint + '/' + path);
        dst.searchParams.append('conflict', conflict);
        dst.searchParams.append('permission', permission);
        // post as multipart form data
        const formData = new FormData();
        formData.append('file', file);
        const res = await fetch(dst.toString(), {
            method: 'POST',
            // don't include the content type, let the browser handle it
            // https://muffinman.io/blog/uploading-files-using-fetch-multipart-form-data/
            headers: {
                'Authorization': 'Bearer ' + this.config.token, 
            },
            body: formData
        });
                
        if (res.status != 200 && res.status != 201){
            throw new Error(`Failed to upload file, status code: ${res.status}, message: ${await fmtFailedResponse(res)}`);
        }
        return (await res.json()).url;
    }

    /**
    * @param {string} path - the path to the file (url), should end with .json
    * @param {Object} data - the data to upload
    * @param {Object} [options] - Optional upload configuration.
    * @param {'abort' | 'overwrite' | 'skip'} [options.conflict='abort'] - Conflict resolution strategy:  
    * `'abort'` to cancel and raise 409, `'overwrite'` to replace, `'skip'` to ignore if already exists.
    * @param {number} [options.permission=0] - Optional permission setting for the file (refer to backend impl).
    * @returns {Promise<string>} - the promise of the request, the url of the file
    */
    async putJson(path, data, {
        conflict = "overwrite", 
        permission = 0
    } = {}){
        if (!path.endsWith('.json')){ throw new Error('Upload object must end with .json'); }
        if (path.startsWith('/')){ path = path.slice(1); }
        const dst = new URL(this.config.endpoint + '/' + path);
        dst.searchParams.append('conflict', conflict);
        dst.searchParams.append('permission', permission);
        const res = await fetch(dst.toString(), {
            method: 'PUT',
            headers: {
                'Authorization': 'Bearer ' + this.config.token,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });
        if (res.status != 200 && res.status != 201){
            throw new Error(`Failed to upload object, status code: ${res.status}, message: ${await fmtFailedResponse(res)}`);
        }
        return (await res.json()).url;
    }

    /**
     * @param {string} path - the path to the file (url), should have content type application/json
     * @returns {Promise<Object>} - return the json object
    */
    async getJson(path){
        if (path.startsWith('/')){ path = path.slice(1); }
        const res = await fetch(this.config.endpoint + '/' + path, {
            method: 'GET',
            headers: {
             "Authorization": 'Bearer ' + this.config.token
            },
        });
        if (res.status != 200){
            throw new Error(`Failed to get object, status code: ${res.status}, message: ${await fmtFailedResponse(res)}`);
        }
        return await res.json();
    }

    /**
     * @param {string[]} paths - the paths to the files (url), should have content type plain/text, application/json, etc.
     * @param {Object} [options] - Optional configuration.
     * @param {boolean} [options.skipContent=false] - If true, skips fetching content and returns a record of <path, ''>.
     * @returns {Promise<Record<string, string | null>>} - return the mapping of path to text content, non-existing paths will be ignored
     */
    async getMultipleText(paths, {
        skipContent = false
    } = {}){
        const url = new URL(this.config.endpoint + '/_api/get-multiple');
        url.searchParams.append('skip_content', skipContent);
        for (const path of paths){
            url.searchParams.append('path', path);
        }
        const res = await fetch(url.toString(), {
            method: 'GET',
            headers: {
                "Authorization": 'Bearer ' + this.config.token,
            }
        });
        if (res.status != 200 && res.status != 206){
            throw new Error(`Failed to get multiple files, status code: ${res.status}, message: ${await fmtFailedResponse(res)}`);
        }
        return await res.json();
    }

    async delete(path){
        if (path.startsWith('/')){ path = path.slice(1); }
        const res = await fetch(this.config.endpoint + '/' + path, {
            method: 'DELETE',
            headers: {
                'Authorization': 'Bearer ' + this.config.token
            }, 
        });
        if (res.status == 200) return;
        throw new Error(`Failed to delete file, status code: ${res.status}, message: ${await fmtFailedResponse(res)}`);
    }

    /**
     * @param {string} path - the path to the file or directory
     * @returns {Promise<FileRecord | DirectoryRecord | null>} - the promise of the request
     */
    async getMetadata(path){
        if (path.startsWith('/')){ path = path.slice(1); }
        const res = await fetch(this.config.endpoint + '/_api/meta?path=' + path, {
            method: 'GET',
            headers: {
                'Authorization': 'Bearer ' + this.config.token
            },
        });
        if (res.status == 404){
            return null;
        }
        return await res.json();
    }

    _sanitizeDirPath(path){
        if (path.startsWith('/')){ path = path.slice(1); }
        if (!path.endsWith('/')){ path += '/'; }
        return path;
    }
    /**
     * @param {string} path - the path to the file directory, should ends with '/'
     * @returns {Promise<PathListResponse>} - the promise of the request
     * NOTE: will deprecated in future
     */
    async listPath(path){
        path = this._sanitizeDirPath(path);
        const dst = new URL(this.config.endpoint + '/' + path);
        const res = await fetch(dst.toString(), {
            method: 'GET',
            headers: {
                'Authorization': 'Bearer ' + this.config.token
            },
        });
        if (res.status == 403 || res.status == 401){
            throw new Error(`Access denied to ${path}`);
        }
        return await res.json();
    }

    /**
     * @param {string} path - the path to the file directory, should ends with '/'
     * @param {boolean} flat - whether to list the files in subdirectories
     * @returns {Promise<number>} - the promise of the request
     * */
    async countFiles(path, {
        flat = false
    } = {}){
        path = this._sanitizeDirPath(path);
        const dst = new URL(this.config.endpoint + '/_api/count-files');
        dst.searchParams.append('path', path);
        dst.searchParams.append('flat', flat);
        const res = await fetch(dst.toString(), {
            method: 'GET',
            headers: {
                'Authorization': 'Bearer ' + this.config.token
            },
        });
        if (res.status != 200){
            throw new Error(`Failed to count files, status code: ${res.status}, message: ${await fmtFailedResponse(res)}`);
        }
        return (await res.json()).count;
    }

    /**
     * @typedef {Object} ListFilesOptions
     * @property {number} offset - the offset of the list
     * @property {number} limit - the limit of the list
     * @property {FileSortKey} orderBy - the key to order the files
     * @property {boolean} orderDesc - whether to order the files in descending order
     * @property {boolean} flat - whether to list the files in subdirectories
     * 
     * @param {string} path - the path to the file directory, should ends with '/'
     * @param {ListFilesOptions} options - the options for the request
     * @returns {Promise<FileRecord[]>} - the promise of the request
     */
    async listFiles(path, {
        offset = 0,
        limit = 1000,
        orderBy = 'create_time',
        orderDesc = false,
        flat = false
    } = {}){
        path = this._sanitizeDirPath(path);
        const dst = new URL(this.config.endpoint + '/_api/list-files');
        dst.searchParams.append('path', path);
        dst.searchParams.append('offset', offset);
        dst.searchParams.append('limit', limit);
        dst.searchParams.append('order_by', orderBy);
        dst.searchParams.append('order_desc', orderDesc);
        dst.searchParams.append('flat', flat);
        const res = await fetch(dst.toString(), {
            method: 'GET',
            headers: {
                'Authorization': 'Bearer ' + this.config.token
            },
        });
        if (res.status != 200){
            throw new Error(`Failed to list files, status code: ${res.status}, message: ${await fmtFailedResponse(res)}`);
        }
        return await res.json();
    }

    /**
     * @param {string} path - the path to the file directory, should ends with '/'
     * @returns {Promise<number>} - the promise of the request
     **/
    async countDirs(path){
        path = this._sanitizeDirPath(path);
        const dst = new URL(this.config.endpoint + '/_api/count-dirs');
        dst.searchParams.append('path', path);
        const res = await fetch(dst.toString(), {
            method: 'GET',
            headers: {
                'Authorization': 'Bearer ' + this.config.token
            },
        });
        if (res.status != 200){
            throw new Error(`Failed to count directories, status code: ${res.status}, message: ${await fmtFailedResponse(res)}`);
        }
        return (await res.json()).count;
    }

    /**
     * @typedef {Object} ListDirsOptions
     * @property {number} offset - the offset of the list
     * @property {number} limit - the limit of the list
     * @property {DirectorySortKey} orderBy - the key to order the directories
     * @property {boolean} orderDesc - whether to order the directories in descending order
     * @property {boolean} skim - whether to skim the directories
     * 
     * @param {string} path - the path to the file directory, should ends with '/'
     * @param {ListDirsOptions} options - the options for the request
     * @returns {Promise<DirectoryRecord[]>} - the promise of the request
     **/
    async listDirs(path, {
        offset = 0,
        limit = 1000,
        orderBy = 'dirname',
        orderDesc = false, 
        skim = true
    } = {}){
        path = this._sanitizeDirPath(path);
        const dst = new URL(this.config.endpoint + '/_api/list-dirs');
        dst.searchParams.append('path', path);
        dst.searchParams.append('offset', offset);
        dst.searchParams.append('limit', limit);
        dst.searchParams.append('order_by', orderBy);
        dst.searchParams.append('order_desc', orderDesc);
        dst.searchParams.append('skim', skim);
        const res = await fetch(dst.toString(), {
            method: 'GET',
            headers: {
                'Authorization': 'Bearer ' + this.config.token
            },
        });
        if (res.status != 200){
            throw new Error(`Failed to list directories, status code: ${res.status}, message: ${await fmtFailedResponse(res)}`);
        }
        return await res.json();
    }

    /**
     * Check the user information by the token
     * @returns {Promise<UserRecord>} - the promise of the request
     */
    async whoami(){
        const res = await fetch(this.config.endpoint + '/_api/whoami', {
            method: 'GET',
            headers: {
                'Authorization': 'Bearer ' + this.config.token
            },
        });
        if (res.status != 200){
            throw new Error('Failed to get user info, status code: ' + res.status);
        }
        return await res.json();
    };

    /**
     * @param {string} path - file path(url)
     * @param {number} permission - please refer to the permMap
     */
    async setFilePermission(path, permission){
        if (path.startsWith('/')){ path = path.slice(1); }
        const dst = new URL(this.config.endpoint + '/_api/meta');
        dst.searchParams.append('path', path);
        dst.searchParams.append('perm', permission);
        const res = await fetch(dst.toString(), {
            method: 'POST',
            headers: {
                'Authorization': 'Bearer ' + this.config.token
            },
        });
        if (res.status != 200){
            throw new Error(`Failed to set permission, status code: ${res.status}, message: ${await fmtFailedResponse(res)}`);
        }
    }

    /**
     * @param {string} path - file path(url)
     * @param {string} newPath - new file path(url)
     */
    async move(path, newPath){
        if (path.startsWith('/')){ path = path.slice(1); }
        if (newPath.startsWith('/')){ newPath = newPath.slice(1); }
        const dst = new URL(this.config.endpoint + '/_api/meta');
        dst.searchParams.append('path', path);
        dst.searchParams.append('new_path', newPath);
        const res = await fetch(dst.toString(), {
            method: 'POST',
            headers: {
                'Authorization': 'Bearer ' + this.config.token, 
                'Content-Type': 'application/www-form-urlencoded'
            },
        });
        if (res.status != 200){
            throw new Error(`Failed to move file, status code: ${res.status}, message: ${await fmtFailedResponse(res)}`);
        }
    }

    /**
     * @param {string} srcPath - file path(url)
     * @param {string} dstPath - new file path(url)
     */
    async copy(srcPath, dstPath){
        if (srcPath.startsWith('/')){ srcPath = srcPath.slice(1); }
        if (dstPath.startsWith('/')){ dstPath = dstPath.slice(1); }
        const dst = new URL(this.config.endpoint + '/_api/copy');
        dst.searchParams.append('src', srcPath);
        dst.searchParams.append('dst', dstPath);
        const res = await fetch(dst.toString(), {
            method: 'POST',
            headers: {
                'Authorization': 'Bearer ' + this.config.token,
                'Content-Type': 'application/www-form-urlencoded'
            },
        });
        if (!(res.status == 200 || res.status == 201)){
            throw new Error(`Failed to copy file, status code: ${res.status}, message: ${await fmtFailedResponse(res)}`);
        }
    }
}

/**
 * a function to wrap the listDirs and listFiles function into one
 * it will return the list of directories and files in the directory, 
 * making directories first (if the offset is less than the number of directories), 
 * and files after that.
 * 
 * 
 * @typedef {Object} ListPathOptions
 * @property {number} offset - the offset of the list
 * @property {number} limit - the limit of the list
 * @property {ListFilesOptions} orderBy - the key to order the files (if set to url, will list the directories using dirname)
 * @property {boolean} orderDesc - whether to order the files in descending order
 * 
 * @param {Connector} conn - the connector to the API
 * @param {string} path - the path to the file directory
 * @param {Object} options - the options for the request
 * @returns {Promise<[PathListResponse, {dirs: number, files: number}]>} - the promise of the request
 */
export async function listPath(conn, path, {
    offset = 0,
    limit = 1000,
    orderBy = '',
    orderDesc = false,
} = {}){

    if (path === '/' || path === ''){
        // this handles separate case for the root directory... please refer to the backend implementation
        return [await conn.listPath(''), {dirs: 0, files: 0}];
    }

    orderBy = orderBy == 'none' ? '' : orderBy;
    console.debug('listPath', path, offset, limit, orderBy, orderDesc);

    const [dirCount, fileCount] = await Promise.all([
        conn.countDirs(path),
        conn.countFiles(path)
    ]);

    const dirOffset = offset;
    const fileOffset = Math.max(offset - dirCount, 0);
    const dirThispage = Math.max(Math.min(dirCount - dirOffset, limit), 0);
    const fileLimit = limit - dirThispage;

    console.debug('dirCount', dirCount, 'dirOffset', dirOffset, 'fileOffset', fileOffset, 'dirThispage', dirThispage, 'fileLimit', fileLimit);

    const dirOrderBy = orderBy == 'url' ? 'dirname' : '';
    const fileOrderBy = orderBy;

    const [dirList, fileList] = await Promise.all([
        (async () => {
            if (offset < dirCount) {
                return await conn.listDirs(path, {
                    offset: dirOffset,
                    limit: dirThispage,
                    orderBy: dirOrderBy,
                    orderDesc: orderDesc
                });
            }
            return [];
        })(), 
        (async () => {
            if (fileLimit >= 0 && fileCount > fileOffset) {
                return await conn.listFiles(path, {
                    offset: fileOffset,
                    limit: fileLimit,
                    orderBy: fileOrderBy,
                    orderDesc: orderDesc
                });
            }
            return [];
        })()
    ]);

    return [{
        dirs: dirList,
        files: fileList
    }, {
        dirs: dirCount,
        files: fileCount
    }];
};

/**
 * a function to wrap the upload function into one
 * it will return the url of the file
 * 
 * @typedef {Object} UploadOptions
 * @property {string} conflict - the conflict resolution strategy, can be 'abort', 'replace', 'rename'
 * @property {number} permission - the permission of the file, can be 0, 1, 2, 3
 * 
 * @param {Connector} conn - the connector to the API
 * @param {string} path - the path to the file (url)
 * @param {File} file - the file to upload
 * @param {UploadOptions} options - the options for the request
 * @returns {Promise<string>} - the promise of the request, the url of the file
 */
export async function uploadFile(conn, path, file, {
    conflict = 'abort',
    permission = 0
} = {}){
    if (file.size < 1024 * 1024 * 10){
        return await conn.put(path, file, {conflict, permission});
    }
    return await conn.post(path, file, {conflict, permission});
}