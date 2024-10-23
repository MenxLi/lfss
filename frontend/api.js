
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
 * 
 * @typedef {Object} PathListResponse
 * @property {DirectoryRecord[]} dirs - the list of directories in the directory
 * @property {FileRecord[]} files - the list of files in the directory
 * 
 */

export const permMap = {
    0: 'unset',
    1: 'public',
    2: 'protected',
    3: 'private'
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
                'Content-Type': 'application/octet-stream'
            },
            body: fileBytes
        });
        if (res.status != 200 && res.status != 201){
            throw new Error(`Failed to upload file, status code: ${res.status}, message: ${await res.json()}`);
        }
        return (await res.json()).url;
    }

    /**
    * @param {string} path - the path to the file (url), should end with .json
    * @param {Objec} data - the data to upload
    * @returns {Promise<string>} - the promise of the request, the url of the file
    */
    async putJson(path, data){
        if (!path.endsWith('.json')){ throw new Error('Upload object must end with .json'); }
        if (path.startsWith('/')){ path = path.slice(1); }
        const res = await fetch(this.config.endpoint + '/' + path, {
            method: 'PUT',
            headers: {
                'Authorization': 'Bearer ' + this.config.token,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });
        if (res.status != 200 && res.status != 201){
            throw new Error(`Failed to upload object, status code: ${res.status}, message: ${await res.json()}`);
        }
        return (await res.json()).url;
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
        throw new Error(`Failed to delete file, status code: ${res.status}, message: ${await res.json()}`);
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

    /**
     * @param {string} path - the path to the file directory, should ends with '/'
     * @param {Object} options - the options for the request
     * @returns {Promise<PathListResponse>} - the promise of the request
     */
    async listPath(path, {
        flat = false
    } = {}){
        if (path.startsWith('/')){ path = path.slice(1); }
        if (!path.endsWith('/')){ path += '/'; }
        const dst = new URL(this.config.endpoint + '/' + path);
        dst.searchParams.append('flat', flat);
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
            throw new Error(`Failed to set permission, status code: ${res.status}, message: ${await res.json()}`);
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
            throw new Error(`Failed to move file, status code: ${res.status}, message: ${await res.json()}`);
        }
    }

}