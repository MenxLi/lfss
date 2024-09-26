
/**
 * @typedef Config
 * @property {string} endpoint - the endpoint of the API
 * @property {string} token - the token to authenticate the user
 * 
 * Partially complete...
 * @typedef {Object} FileRecord
 * @property {string} url - the url of the file
 * @property {Number} file_size - the size of the file, in bytes
 * @property {string} create_time - the time the file was created
 * 
 * Partially complete...
 * @typedef {Object} DirectoryRecord
 * @property {string} url - the url of the directory
 * @property {string} size - the size of the directory, in bytes
 * 
 * @typedef {Object} PathListResponse
 * @property {DirectoryRecord[]} dirs - the list of directories in the directory
 * @property {FileRecord[]} files - the list of files in the directory
 * 
 */


export default class Connector {
    /**
     * @type {Config}
     */
    config;

    constructor(){
        this.config = {
            endpoint: 'http://localhost:8000',
            token: ''
        }
    }

    async put(path, file){
        if (!path.startsWith('/')){ path = '/' + path; }
        const fileBytes = await file.arrayBuffer();
        return fetch(this.config.endpoint + path, {
            method: 'PUT',
            headers: {
                'Authorization': 'Bearer ' + this.config.token, 
                'Content-Type': 'application/octet-stream'
            },
            body: fileBytes
        });
    }

    async delete(path){
        if (!path.startsWith('/')){ path = '/' + path; }
        return fetch(this.config.endpoint + path, {
            method: 'DELETE',
            headers: {
                'Authorization': 'Bearer ' + this.config.token
            }, 
        });
    }

    /**
     * @param {string} path - the path to the file directory, should ends with '/'
     * @returns {Promise<PathListResponse>} - the promise of the request
     */
    async listPath(path){
        if (!path.startsWith('/')){ path = '/' + path; }
        if (!path.endsWith('/')){ path += '/'; }
        return fetch(this.config.endpoint + path, {
            method: 'GET',
            headers: {
                'Authorization': 'Bearer ' + this.config.token
            },
        }).then(response => response.json());
    }
}