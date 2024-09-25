
/**
 * @typedef Config
 * @property {string} endpoint - the endpoint of the API
 * @property {string} token - the token to authenticate the user
 * 
 * Incomplete...
 * @typedef {Object} FileRecord
 * @property {string} url - the url of the file
 * @property {Number} file_size - the size of the file, in bytes
 * @property {string} create_time - the time the file was created
 * 
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

    /**
     * @param {string} path - the path to the file
     * @param {File} file - the file to upload
     * @returns {Promise} - the promise of the request
     */
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

    /**
     * @param {string} path - the path to the file
     * @returns {Promise} - the promise of the request
     */
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
     * @param {string} path - the path to the file directory
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