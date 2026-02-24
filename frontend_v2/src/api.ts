export interface Config {
    endpoint: string;
    token: string;
}

export interface UserRecord {
    id: number;
    username: string;
    credential: string;
    is_admin: boolean;
    create_time: string;
    last_active: string;
    max_storage: number;
    permission: number;
}

export interface FileRecord {
    url: string;        // full path of the file, e.g. "user1/dir1/file.txt"
    owner_id: number;
    file_id: string;
    file_size: number;
    create_time: string;
    access_time: string;
    permission: number;
    external: number;
    mime_type: string;
}

export interface DirectoryRecord {
    url: string;        // full path of the directory, e.g. "user1/dir1/"
    size: number;
    create_time: string;
    update_time: string;
    access_time: string;
    n_files: number;
}

export interface PathListResponse {
    dirs: DirectoryRecord[];
    files: FileRecord[];
}

export type FileSortKey = "" | "url" | "file_size" | "create_time" | "access_time" | "mime_type";
export type DirectorySortKey = "" | "dirname";

export const permMap: Record<number, string> = {
    0: 'unset',
    1: 'public',
    2: 'protected',
    3: 'private'
};

export const accessLevelMap: Record<number, string> = {
    0: 'none',
    1: 'read',
    2: 'write',
    10: 'all'
};

async function fmtFailedResponse(res: Response): Promise<string> {
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
export class Fetcher {
    config: Config;

    constructor(config: Config) {
        this.config = config;
    }

    _buildUrl(path: string, params?: Record<string, any>): string {
        if (path.startsWith('/')) { path = path.slice(1); }
        const encodedPath = path.split('/').map(encodeURIComponent).join('/');
        const base = this.config.endpoint.endsWith('/') ? this.config.endpoint : this.config.endpoint + '/';
        const url = new URL(base + encodedPath);
        if (params) {
            for (const [key, value] of Object.entries(params)) {
                if (Array.isArray(value)) {
                    value.forEach(v => url.searchParams.append(key, String(v)));
                } else if (value !== undefined && value !== null) {
                    url.searchParams.append(key, String(value));
                }
            }
        }
        return url.toString();
    }

    async request(method: string, path: string, { params, headers, body }: { params?: Record<string, any>, headers?: Record<string, string>, body?: BodyInit | null } = {}): Promise<Response> {
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

    async get(path: string, options?: { params?: Record<string, any>, headers?: Record<string, string> }): Promise<Response> {
        return this.request('GET', path, options);
    }

    async head(path: string, options?: { params?: Record<string, any>, headers?: Record<string, string> }): Promise<Response> {
        return this.request('HEAD', path, options);
    }

    async post(path: string, body: BodyInit | null, options?: { params?: Record<string, any>, headers?: Record<string, string> }): Promise<Response> {
        return this.request('POST', path, { body, ...options });
    }

    async put(path: string, body: BodyInit | null, options?: { params?: Record<string, any>, headers?: Record<string, string> }): Promise<Response> {
        return this.request('PUT', path, { body, ...options });
    }

    async delete(path: string, options?: { params?: Record<string, any>, headers?: Record<string, string> }): Promise<Response> {
        return this.request('DELETE', path, options);
    }
}

export default class Connector {
    fetcher: Fetcher;

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

    get config(): Config {
        return this.fetcher.config;
    }

    set config(config: Config) {
        this.fetcher = new Fetcher(config);
    }

    async version(): Promise<string> {
        const res = await this.fetcher.get('_api/version');
        if (res.status != 200) {
            throw new Error('Failed to get version, status code: ' + res.status);
        }
        const data = await res.json();
        return data;
    }

    async exists(path: string): Promise<boolean> {
        const res = await this.fetcher.head(path);
        if (res.ok) {
            return true;
        } else if (res.status == 404) {
            return false;
        } else {
            throw new Error(`Failed to check file existence, status code: ${res.status}, message: ${await fmtFailedResponse(res)}`);
        }
    }

    async getText(path: string): Promise<string> {
        const res = await this.fetcher.get(path);
        if (res.status != 200) {
            throw new Error(`Failed to get file, status code: ${res.status}, message: ${await fmtFailedResponse(res)}`);
        }
        return await res.text();
    }

    async putText(path: string, text: string, {
        conflict = 'abort',
        type = 'text/plain'
    }: { conflict?: 'abort' | 'overwrite' | 'skip', type?: string } = {}): Promise<string> {
        const file = new Blob([text], { type: type });
        return await this.put(path, file, {
            conflict: conflict
        });
    }

    async put(path: string, file: Blob, {
        conflict = 'abort',
        permission = 0
    }: { conflict?: 'abort' | 'overwrite' | 'skip', permission?: number } = {}): Promise<string> {
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

    async post(path: string, file: File | Blob, {
        conflict = 'abort',
        permission = 0
    }: { conflict?: 'abort' | 'overwrite' | 'skip', permission?: number } = {}): Promise<string> {
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

    async putJson(path: string, data: any, {
        conflict = "overwrite",
        permission = 0
    }: { conflict?: 'abort' | 'overwrite' | 'skip', permission?: number } = {}): Promise<string> {
        if (!path.endsWith('.json')) { throw new Error('Upload object must end with .json'); }
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

    async getJson(path: string): Promise<any> {
        const res = await this.fetcher.get(path);
        if (res.status != 200) {
            throw new Error(`Failed to get object, status code: ${res.status}, message: ${await fmtFailedResponse(res)}`);
        }
        return await res.json();
    }

    async getMultipleText(paths: string[], {
        skipContent = false
    }: { skipContent?: boolean } = {}): Promise<Record<string, string | null>> {
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

    async delete(path: string): Promise<void> {
        const res = await this.fetcher.delete(path);
        if (res.status == 200) return;
        throw new Error(`Failed to delete file, status code: ${res.status}, message: ${await fmtFailedResponse(res)}`);
    }

    async getMetadata(path: string): Promise<FileRecord | DirectoryRecord | null> {
        const res = await this.fetcher.get('_api/meta', {
            params: { path }
        });
        if (res.status == 404) {
            return null;
        }
        return await res.json();
    }

    _sanitizeDirPath(path: string): string {
        if (path.startsWith('/')) { path = path.slice(1); }
        if (!path.endsWith('/')) { path += '/'; }
        return path;
    }

    async countFiles(path: string, {
        flat = false
    }: { flat?: boolean } = {}): Promise<number> {
        path = this._sanitizeDirPath(path);
        const res = await this.fetcher.get('_api/count-files', {
            params: { path, flat }
        });
        if (res.status != 200) {
            throw new Error(`Failed to count files, status code: ${res.status}, message: ${await fmtFailedResponse(res)}`);
        }
        return (await res.json()).count;
    }

    async listFiles(path: string, {
        offset = 0,
        limit = 1000,
        orderBy = 'create_time',
        orderDesc = false,
        flat = false
    }: {
        offset?: number;
        limit?: number;
        orderBy?: FileSortKey;
        orderDesc?: boolean;
        flat?: boolean;
    } = {}): Promise<FileRecord[]> {
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

    async countDirs(path: string): Promise<number> {
        path = this._sanitizeDirPath(path);
        const res = await this.fetcher.get('_api/count-dirs', {
            params: { path }
        });
        if (res.status != 200) {
            throw new Error(`Failed to count directories, status code: ${res.status}, message: ${await fmtFailedResponse(res)}`);
        }
        return (await res.json()).count;
    }

    async listDirs(path: string, {
        offset = 0,
        limit = 1000,
        orderBy = 'dirname',
        orderDesc = false,
        skim = true
    }: {
        offset?: number;
        limit?: number;
        orderBy?: DirectorySortKey;
        orderDesc?: boolean;
        skim?: boolean;
    } = {}): Promise<DirectoryRecord[]> {
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

    async whoami(): Promise<UserRecord> {
        const res = await this.fetcher.get('_api/user/whoami');
        if (res.status != 200) {
            throw new Error('Failed to get user info, status code: ' + res.status);
        }
        return await res.json();
    };

    async databaseID(): Promise<string> {
        const res = await this.fetcher.get('_api/database-id');
        if (res.status != 200) {
            throw new Error('Failed to get database ID, status code: ' + res.status);
        }
        return await res.json();
    }

    // level: access level to filter peer users, 1 for read-only, 2 for write
    // incoming: to list incoming peers, if false, list outgoing peers (default: false)
    // admin: whether to include admin users
    // as_user: list peers as if you are this user (admin only)
    async listPeers({
        level = 1,
        incoming = false,
        admin = false,
        as_user
    }: {
        level?: number,
        incoming?: boolean,
        admin?: boolean,
        as_user?: string
    } = {}): Promise<UserRecord[]> {
        const res = await this.fetcher.get('_api/user/list-peers', {
            params: { level, incoming, admin, as_user }
        });
        if (res.status != 200) {
            throw new Error('Failed to list peer users, status code: ' + res.status);
        }
        return await res.json();
    }

    async queryUser(userId: number): Promise<UserRecord> {
        const res = await this.fetcher.get('_api/user/query', {
            params: { userid: userId }
        });
        if (res.status != 200) {
            throw new Error('Failed to query user, status code: ' + res.status);
        }
        return await res.json();
    }

    async setFilePermission(path: string, permission: number): Promise<void> {
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

    async move(path: string, newPath: string): Promise<void> {
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

    async copy(srcPath: string, dstPath: string): Promise<void> {
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

    // admin only APIs below =========
    async listUsers({
        username_filter,
        include_virtual = false,
        order_by = 'create_time',
        order_desc = false,
        offset = 0,
        limit = 1000
    }: {
        username_filter?: string,
        include_virtual?: boolean,
        order_by?: 'username' | 'create_time' | 'is_admin' | 'last_active',
        order_desc?: boolean,
        offset?: number,
        limit?: number
    } = {}): Promise<UserRecord[]> {
        const res = await this.fetcher.get('_api/user/list', {
            params: { username_filter, include_virtual, order_by, order_desc, offset, limit }
        });
        if (res.status != 200) {
            throw new Error('Failed to list users, status code: ' + res.status);
        }
        return await res.json();
    }

    async addUser(params: { username: string, password?: string, admin?: boolean, max_storage?: string, permission?: string }): Promise<UserRecord> {
        const res = await this.fetcher.post('_api/user/add', null, { params });
        if (!res.ok) {
            throw new Error(`Failed to add user, status code: ${res.status}, message: ${await fmtFailedResponse(res)}`);
        }
        return await res.json();
    }

    async updateUser(params: { username: string, password?: string, admin?: boolean, max_storage?: string, permission?: string }): Promise<UserRecord> {
        const res = await this.fetcher.post('_api/user/update', null, { params });
        if (!res.ok) {
            throw new Error(`Failed to update user, status code: ${res.status}, message: ${await fmtFailedResponse(res)}`);
        }
        return await res.json();
    }

    async deleteUser(username: string): Promise<UserRecord> {
        const res = await this.fetcher.post('_api/user/delete', null, { params: { username } });
        if (!res.ok) {
            throw new Error(`Failed to delete user, status code: ${res.status}, message: ${await fmtFailedResponse(res)}`);
        }
        return await res.json();
    }

    async setPeer(src_username: string, dst_username: string, level: 'NONE' | 'READ' | 'WRITE'): Promise<void> {
        const res = await this.fetcher.post('_api/user/set-peer', null, {
            params: {
                src_username,
                dst_username,
                level
            }
        });
        if (!res.ok) {
            throw new Error(`Failed to set peer access, status code: ${res.status}, message: ${await fmtFailedResponse(res)}`);
        }
    }
}

export class ApiUtils {
    // a function to wrap the listDirs and listFiles function into one
    // it will return the list of directories and files in the directory
    static async listPath(conn: Connector, path: string, {
        offset = 0,
        limit = 1000,
        orderBy = '',
        orderDesc = false,
    }: {
        offset?: number;
        limit?: number;
        orderBy?: FileSortKey | 'none',
        orderDesc?: boolean;
    } = {}): Promise<[PathListResponse, { dirs: number, files: number }]> {

        if (path === '/' || path === '') {
            // this handles separate case for the root directory
            const myusername = (await conn.whoami()).username;
            let dirnames: string[] = [];
            if (!myusername.startsWith('.v-')) {
                dirnames = dirnames.concat([myusername + '/']);
            }
            dirnames = dirnames.concat(
                (await conn.listPeers({ level: 1, incoming: false })).map(u => u.username + '/')
            );
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
            ]
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
                        orderBy: dirOrderBy as DirectorySortKey,
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
                        orderBy: fileOrderBy as FileSortKey,
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

    // a function to wrap the upload function into one
    // it will return the url of the file
    static async uploadFile(conn: Connector, path: string, file: File, {
        conflict = 'abort',
        permission = 0
    }: {
        conflict?: 'abort' | 'overwrite' | 'skip';
        permission?: number;
    } = {}): Promise<string> {
        if (file.size < 1024 * 1024 * 10) {
            return await conn.put(path, file, { conflict, permission });
        }
        return await conn.post(path, file, { conflict, permission });
    }

    static encodePath(path: string): string {
        return path.split('/').map(encodeURIComponent).join('/');
    }

    static decodePath(path: string): string {
        return path.split('/').map(decodeURIComponent).join('/');
    }

    static getFileUrl(conn: Connector, url: string, includeToken: boolean = true): string {
        if (url.startsWith('/')) { url = url.slice(1); }
        return `${conn.config.endpoint}/${this.encodePath(url)}${includeToken ? `?token=${conn.config.token}` : ''}`;
    }

    static getDownloadUrl(conn: Connector, url: string, includeToken: boolean = true): string {
        return this.getFileUrl(conn, url, includeToken) + (includeToken ? `&download=true` : '?download=true');
    }

    static getThumbUrl(conn: Connector, url: string, includeToken: boolean = true): string {
        return this.getFileUrl(conn, url, includeToken) + (includeToken ? `&thumb=true` : '?thumb=true');
    }

    static getBundleUrl(conn: Connector, path: string): string {
        if (path.startsWith('/')) { path = path.slice(1); }
        return `${conn.config.endpoint}/_api/bundle?token=${conn.config.token}&path=${encodeURIComponent(path)}`
    }
}
