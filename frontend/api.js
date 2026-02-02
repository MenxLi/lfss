export const permMap = {
    0: 'unset',
    1: 'public',
    2: 'protected',
    3: 'private'
};
async function fmtFailedResponse(res) {
    const raw = await res.text();
    const json = raw ? JSON.parse(raw) : {};
    const txt = JSON.stringify(json.detail || json || "No message");
    const maxWords = 32;
    if (txt.length > maxWords) {
        return txt.slice(0, maxWords) + '...';
    }
    return txt;
}
// A wrapper class for fetch API to handle common tasks like authentication and error handling.
class Fetcher {
    constructor(config) {
        this.config = config;
    }
    _buildUrl(path, params) {
        if (path.startsWith('/')) {
            path = path.slice(1);
        }
        const base = this.config.endpoint.endsWith('/') ? this.config.endpoint : this.config.endpoint + '/';
        const url = new URL(base + path);
        if (params) {
            for (const [key, value] of Object.entries(params)) {
                if (Array.isArray(value)) {
                    value.forEach(v => url.searchParams.append(key, String(v)));
                }
                else if (value !== undefined && value !== null) {
                    url.searchParams.append(key, String(value));
                }
            }
        }
        return url.toString();
    }
    async request(method, path, { params, headers, body } = {}) {
        const url = this._buildUrl(path, params);
        return await fetch(url, {
            method,
            headers: {
                "Authorization": 'Bearer ' + this.config.token,
                ...headers
            },
            body
        });
    }
    async get(path, options) {
        return this.request('GET', path, options);
    }
    async head(path, options) {
        return this.request('HEAD', path, options);
    }
    async post(path, body, options) {
        return this.request('POST', path, { body, ...options });
    }
    async put(path, body, options) {
        return this.request('PUT', path, { body, ...options });
    }
    async delete(path, options) {
        return this.request('DELETE', path, options);
    }
}
export default class Connector {
    constructor() {
        // get default endpoint from url
        const searchParams = (new URL(window.location.href)).searchParams;
        const defaultToken = searchParams.get('lfss-token') || '';
        const origin = window.location.origin;
        const defaultEndpoint = searchParams.get('lfss-endpoint') || (origin ? origin : 'http://localhost:8000');
        const config = {
            endpoint: defaultEndpoint,
            token: defaultToken
        };
        this.fetcher = new Fetcher(config);
    }
    get config() {
        return this.fetcher.config;
    }
    set config(config) {
        this.fetcher = new Fetcher(config);
    }
    async version() {
        const res = await this.fetcher.get('_api/version');
        if (res.status != 200) {
            throw new Error('Failed to get version, status code: ' + res.status);
        }
        const data = await res.json();
        return data;
    }
    async exists(path) {
        const res = await this.fetcher.head(path);
        if (res.ok) {
            return true;
        }
        else if (res.status == 404) {
            return false;
        }
        else {
            throw new Error(`Failed to check file existence, status code: ${res.status}, message: ${await fmtFailedResponse(res)}`);
        }
    }
    async getText(path) {
        const res = await this.fetcher.get(path);
        if (res.status != 200) {
            throw new Error(`Failed to get file, status code: ${res.status}, message: ${await fmtFailedResponse(res)}`);
        }
        return await res.text();
    }
    async putText(path, text, { conflict = 'abort', type = 'text/plain' } = {}) {
        const file = new Blob([text], { type: type });
        return await this.put(path, file, {
            conflict: conflict
        });
    }
    async put(path, file, { conflict = 'abort', permission = 0 } = {}) {
        const fileBytes = await file.arrayBuffer();
        const res = await this.fetcher.put(path, fileBytes, {
            params: { conflict, permission },
            headers: {
                'Content-Type': 'application/octet-stream',
                'Content-Length': String(fileBytes.byteLength)
            }
        });
        if (res.status != 200 && res.status != 201) {
            throw new Error(`Failed to upload file, status code: ${res.status}, message: ${await fmtFailedResponse(res)}`);
        }
        return (await res.json()).url;
    }
    async post(path, file, { conflict = 'abort', permission = 0 } = {}) {
        // post as multipart form data
        const formData = new FormData();
        formData.append('file', file);
        const res = await this.fetcher.post(path, formData, {
            params: { conflict, permission }
        });
        if (res.status != 200 && res.status != 201) {
            throw new Error(`Failed to upload file, status code: ${res.status}, message: ${await fmtFailedResponse(res)}`);
        }
        return (await res.json()).url;
    }
    async putJson(path, data, { conflict = "overwrite", permission = 0 } = {}) {
        if (!path.endsWith('.json')) {
            throw new Error('Upload object must end with .json');
        }
        const res = await this.fetcher.put(path, JSON.stringify(data), {
            params: { conflict, permission },
            headers: {
                'Content-Type': 'application/json'
            }
        });
        if (res.status != 200 && res.status != 201) {
            throw new Error(`Failed to upload object, status code: ${res.status}, message: ${await fmtFailedResponse(res)}`);
        }
        return (await res.json()).url;
    }
    async getJson(path) {
        const res = await this.fetcher.get(path);
        if (res.status != 200) {
            throw new Error(`Failed to get object, status code: ${res.status}, message: ${await fmtFailedResponse(res)}`);
        }
        return await res.json();
    }
    async getMultipleText(paths, { skipContent = false } = {}) {
        const res = await this.fetcher.get('_api/get-multiple', {
            params: {
                skip_content: skipContent,
                path: paths
            }
        });
        if (res.status != 200 && res.status != 206) {
            throw new Error(`Failed to get multiple files, status code: ${res.status}, message: ${await fmtFailedResponse(res)}`);
        }
        return await res.json();
    }
    async delete(path) {
        const res = await this.fetcher.delete(path);
        if (res.status == 200)
            return;
        throw new Error(`Failed to delete file, status code: ${res.status}, message: ${await fmtFailedResponse(res)}`);
    }
    async getMetadata(path) {
        const res = await this.fetcher.get('_api/meta', {
            params: { path }
        });
        if (res.status == 404) {
            return null;
        }
        return await res.json();
    }
    _sanitizeDirPath(path) {
        if (path.startsWith('/')) {
            path = path.slice(1);
        }
        if (!path.endsWith('/')) {
            path += '/';
        }
        return path;
    }
    async countFiles(path, { flat = false } = {}) {
        path = this._sanitizeDirPath(path);
        const res = await this.fetcher.get('_api/count-files', {
            params: { path, flat }
        });
        if (res.status != 200) {
            throw new Error(`Failed to count files, status code: ${res.status}, message: ${await fmtFailedResponse(res)}`);
        }
        return (await res.json()).count;
    }
    async listFiles(path, { offset = 0, limit = 1000, orderBy = 'create_time', orderDesc = false, flat = false } = {}) {
        path = this._sanitizeDirPath(path);
        const res = await this.fetcher.get('_api/list-files', {
            params: {
                path,
                offset,
                limit,
                order_by: orderBy,
                order_desc: orderDesc,
                flat
            }
        });
        if (res.status != 200) {
            throw new Error(`Failed to list files, status code: ${res.status}, message: ${await fmtFailedResponse(res)}`);
        }
        return await res.json();
    }
    async countDirs(path) {
        path = this._sanitizeDirPath(path);
        const res = await this.fetcher.get('_api/count-dirs', {
            params: { path }
        });
        if (res.status != 200) {
            throw new Error(`Failed to count directories, status code: ${res.status}, message: ${await fmtFailedResponse(res)}`);
        }
        return (await res.json()).count;
    }
    async listDirs(path, { offset = 0, limit = 1000, orderBy = 'dirname', orderDesc = false, skim = true } = {}) {
        path = this._sanitizeDirPath(path);
        const res = await this.fetcher.get('_api/list-dirs', {
            params: {
                path,
                offset,
                limit,
                order_by: orderBy,
                order_desc: orderDesc,
                skim
            }
        });
        if (res.status != 200) {
            throw new Error(`Failed to list directories, status code: ${res.status}, message: ${await fmtFailedResponse(res)}`);
        }
        return await res.json();
    }
    async whoami() {
        const res = await this.fetcher.get('_api/user/whoami');
        if (res.status != 200) {
            throw new Error('Failed to get user info, status code: ' + res.status);
        }
        return await res.json();
    }
    ;
    async listPeers({ level = 1, incoming = false } = {}) {
        const res = await this.fetcher.get('_api/user/list-peers', {
            params: { level, incoming }
        });
        if (res.status != 200) {
            throw new Error('Failed to list peer users, status code: ' + res.status);
        }
        return await res.json();
    }
    async setFilePermission(path, permission) {
        const res = await this.fetcher.post('_api/set-perm', null, {
            params: {
                path,
                perm: permission
            }
        });
        if (res.status != 200) {
            throw new Error(`Failed to set permission, status code: ${res.status}, message: ${await fmtFailedResponse(res)}`);
        }
    }
    async move(path, newPath) {
        const res = await this.fetcher.post('_api/move', null, {
            params: {
                src: path,
                dst: newPath
            },
            headers: {
                'Content-Type': 'application/www-form-urlencoded'
            }
        });
        if (res.status != 200) {
            throw new Error(`Failed to move file, status code: ${res.status}, message: ${await fmtFailedResponse(res)}`);
        }
    }
    async copy(srcPath, dstPath) {
        const res = await this.fetcher.post('_api/copy', null, {
            params: {
                src: srcPath,
                dst: dstPath
            },
            headers: {
                'Content-Type': 'application/www-form-urlencoded'
            }
        });
        if (!(res.status == 200 || res.status == 201)) {
            throw new Error(`Failed to copy file, status code: ${res.status}, message: ${await fmtFailedResponse(res)}`);
        }
    }
}
// a function to wrap the listDirs and listFiles function into one
// it will return the list of directories and files in the directory
export async function listPath(conn, path, { offset = 0, limit = 1000, orderBy = '', orderDesc = false, } = {}) {
    if (path === '/' || path === '') {
        // this handles separate case for the root directory
        const myusername = (await conn.whoami()).username;
        let dirnames = [];
        if (!myusername.startsWith('.v-')) {
            dirnames = dirnames.concat([myusername + '/']);
        }
        dirnames = dirnames.concat((await conn.listPeers({ level: 1, incoming: false })).map(u => u.username + '/'));
        return [
            {
                dirs: dirnames.map(dirname => ({
                    url: dirname,
                    size: -1,
                    create_time: '',
                    update_time: '',
                    access_time: '',
                    n_files: -1
                })),
                files: []
            }, {
                dirs: dirnames.length,
                files: 0
            }
        ];
    }
    const orderByStr = orderBy == 'none' ? '' : orderBy;
    console.debug('listPath', path, offset, limit, orderByStr, orderDesc);
    const [dirCount, fileCount] = await Promise.all([
        conn.countDirs(path),
        conn.countFiles(path)
    ]);
    const dirOffset = offset;
    const fileOffset = Math.max(offset - dirCount, 0);
    const dirThispage = Math.max(Math.min(dirCount - dirOffset, limit), 0);
    const fileLimit = limit - dirThispage;
    console.debug('dirCount', dirCount, 'dirOffset', dirOffset, 'fileOffset', fileOffset, 'dirThispage', dirThispage, 'fileLimit', fileLimit);
    const dirOrderBy = orderByStr == 'url' ? 'dirname' : '';
    const fileOrderBy = orderByStr;
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
}
;
// a function to wrap the upload function into one
// it will return the url of the file
export async function uploadFile(conn, path, file, { conflict = 'abort', permission = 0 } = {}) {
    if (file.size < 1024 * 1024 * 10) {
        return await conn.put(path, file, { conflict, permission });
    }
    return await conn.post(path, file, { conflict, permission });
}
