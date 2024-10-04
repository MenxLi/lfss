import Connector from './api.js';
import { permMap } from './api.js';
import { showFloatingWindowLineInput, showPopup } from './popup.js';
import { formatSize, decodePathURI, ensurePathURI, copyToClipboard, getRandomString, cvtGMT2Local, debounce, encodePathURI } from './utils.js';

const conn = new Connector();
let userRecord = null;

const endpointInput = document.querySelector('input#endpoint');
const tokenInput = document.querySelector('input#token');
const pathInput = document.querySelector('input#path');
const pathBackButton = document.querySelector('span#back-btn');
const pathHintDiv = document.querySelector('#position-hint');
const pathHintLabel = document.querySelector('#position-hint label');
const tbody = document.querySelector('#files-table-body');
const uploadFilePrefixLabel = document.querySelector('#upload-file-prefix');
const uploadFileSelector = document.querySelector('#file-selector');
const uploadFileNameInput = document.querySelector('#file-name');
const uploadButton = document.querySelector('#upload-btn');
const randomizeFnameButton = document.querySelector('#randomize-fname-btn');

conn.config.endpoint = endpointInput.value;
conn.config.token = tokenInput.value;

{
    const endpoint = window.localStorage.getItem('endpoint');
    if (endpoint){
        endpointInput.value = endpoint;
        conn.config.endpoint = endpoint;
    }
    const token = window.localStorage.getItem('token');
    if (token){
        tokenInput.value = token;
        conn.config.token = token;
    }
    const path = window.localStorage.getItem('path');
    if (path){
        pathInput.value = path;
    }
    uploadFilePrefixLabel.textContent = pathInput.value;
    maybeRefreshUserRecord().then(
        () => maybeRefreshFileList()
    );
}

function onPathChange(){
    uploadFilePrefixLabel.textContent = pathInput.value;
    window.localStorage.setItem('path', pathInput.value);
    maybeRefreshFileList();
}

endpointInput.addEventListener('blur', () => {
    conn.config.endpoint = endpointInput.value;
    window.localStorage.setItem('endpoint', endpointInput.value);
    maybeRefreshUserRecord().then(
        () => maybeRefreshFileList()
    );
});
tokenInput.addEventListener('blur', () => {
    conn.config.token = tokenInput.value;
    window.localStorage.setItem('token', tokenInput.value);
    maybeRefreshUserRecord().then(
        () => maybeRefreshFileList()
    );
});
pathInput.addEventListener('input', () => {
    onPathChange();
});
pathBackButton.addEventListener('click', () => {
    const path = pathInput.value;
    if (path.endsWith('/')){
        pathInput.value = path.split('/').slice(0, -2).join('/') + '/';
    }
    else {
        pathInput.value = path.split('/').slice(0, -1).join('/') + '/';
    }
    onPathChange();
});

function onFileNameInpuChange(){
    const fileName = uploadFileNameInput.value;
    if (fileName.length === 0){
        uploadFileNameInput.classList.remove('duplicate');
    }
    else {
        const p = ensurePathURI(pathInput.value + fileName);
        conn.getMetadata(p).then(
            (data) => {
                console.log("Got file meta", data);
                if (data===null) uploadFileNameInput.classList.remove('duplicate');
                else if (data.url) uploadFileNameInput.classList.add('duplicate');
                else throw new Error('Invalid response');
            }
        );
    }
}

randomizeFnameButton.addEventListener('click', () => {
    let currentName = uploadFileNameInput.value;
    let newName = getRandomString(24);
    const dotSplit = currentName.split('.');
    let ext = '';
    if (dotSplit.length > 1){
        ext = dotSplit.pop();
    }
    if (ext.length > 0){
        newName += '.' + ext;
    }
    uploadFileNameInput.value = newName;
    onFileNameInpuChange();
});
uploadFileSelector.addEventListener('change', () => {
    uploadFileNameInput.value = uploadFileSelector.files[0].name;
    onFileNameInpuChange();
});
uploadButton.addEventListener('click', () => {
    const file = uploadFileSelector.files[0];
    let path = pathInput.value;
    let fileName = uploadFileNameInput.value;
    if (fileName.length === 0){
        throw new Error('File name cannot be empty');
    }
    if (fileName.endsWith('/')){
        throw new Error('File name cannot end with /');
    }
    path = path + fileName;
    conn.put(path, file)
        .then(() => {
            refreshFileList();
            uploadFileNameInput.value = '';
            onFileNameInpuChange();
        }, 
        (err) => {
            showPopup('Failed to upload file: ' + err, {level: 'error', timeout: 5000});
        }
    );
});

uploadFileNameInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.isComposing){
        e.preventDefault();
        uploadButton.click();
    }
});
uploadFileNameInput.addEventListener('input', debounce(onFileNameInpuChange, 500));

{
    window.addEventListener('dragover', (e) => {
        e.preventDefault();
        e.stopPropagation();
    });
    window.addEventListener('drop', (e) => {
        e.preventDefault();
        e.stopPropagation();
        const files = e.dataTransfer.files;
        if (files.length == 1){
            uploadFileSelector.files = files;
            uploadFileNameInput.value = files[0].name;
            uploadFileNameInput.focus();
        }
        else if (files.length > 1){
            let dstPath = pathInput.value + uploadFileNameInput.value;
            if (!dstPath.endsWith('/')){ dstPath += '/'; }
            if (!confirm(`
You are trying to upload multiple files at once. 
This will directly upload the files to the [${dstPath}] directory without renaming. 
Note that same name files will be overwritten.
Are you sure you want to proceed?
                `)){ return; }
            
            let counter = 0;
            async function uploadFile(...args){
                const [file, path] = args;
                try{
                    await conn.put(path, file, {overwrite: true});
                }
                catch (err){
                    showPopup('Failed to upload file [' + file.name + ']: ' + err, {level: 'error', timeout: 5000});
                }
                counter += 1;
                console.log("Uploading file: ", counter, "/", files.length);
            }
            
            let promises = [];
            for (let i = 0; i < files.length; i++){
                const file = files[i];
                const path = dstPath + file.name;
                promises.push(uploadFile(file, path));
            }
            Promise.all(promises).then(
                () => {
                    refreshFileList();
                }
            );
        }
    });
}

function maybeRefreshFileList(){
    if (
        pathInput.value && pathInput.value.length > 0 && pathInput.value.endsWith('/')
    ){
        refreshFileList();
    }
}

function refreshFileList(){
    conn.listPath(pathInput.value)
        .then(data => {
            pathHintDiv.classList.remove('disconnected');
            pathHintDiv.classList.add('connected');
            pathHintLabel.textContent = pathInput.value;
            tbody.innerHTML = '';

            console.log("Got data", data);

            if (!data.dirs){ data.dirs = []; }
            if (!data.files){ data.files = []; }

            data.dirs.forEach(dir => {
                const tr = document.createElement('tr');
                {
                    const nameTd = document.createElement('td');
                    if (dir.url.endsWith('/')){
                        dir.url = dir.url.slice(0, -1);
                    }
                    const dirName = dir.url.split('/').pop();
                    const dirLink = document.createElement('a');
                    dirLink.textContent = decodePathURI(dirName);
                    dirLink.addEventListener('click', () => {
                        let dstUrl = dir.url + (dir.url.endsWith('/') ? '' : '/');
                        dstUrl = decodePathURI(dstUrl);
                        pathInput.value = dstUrl;
                        onPathChange();
                    });
                    dirLink.href = '#';
                    nameTd.appendChild(dirLink);

                    tr.appendChild(nameTd);
                    tbody.appendChild(tr);
                }

                {
                    const sizeTd = document.createElement('td');
                    sizeTd.textContent = formatSize(dir.size);
                    tr.appendChild(sizeTd);
                }
                {
                    const dateTd = document.createElement('td');
                    dateTd.textContent = cvtGMT2Local(dir.access_time);
                    tr.appendChild(dateTd);
                }
                {
                    const dateTd = document.createElement('td');
                    dateTd.textContent = cvtGMT2Local(dir.create_time);
                    tr.appendChild(dateTd);
                }
                {
                    const accessTd = document.createElement('td');
                    tr.appendChild(accessTd);
                }
                {
                    const actTd = document.createElement('td');
                    const actContainer = document.createElement('div');
                    actContainer.classList.add('action-container');

                    const downloadButton = document.createElement('a');
                    downloadButton.textContent = 'Download';
                    downloadButton.href = conn.config.endpoint + '/_api/bundle?' + 
                        'token=' + conn.config.token + '&' +
                        'path=' + dir.url + (dir.url.endsWith('/') ? '' : '/');
                    actContainer.appendChild(downloadButton);

                    const deleteButton = document.createElement('a');
                    deleteButton.textContent = 'Delete';
                    deleteButton.classList.add('delete-btn');
                    deleteButton.href = '#';
                    deleteButton.addEventListener('click', () => {
                        const dirurl = dir.url + (dir.url.endsWith('/') ? '' : '/');
                        if (!confirm('[Important] Are you sure you want to delete path ' + dirurl + '?')){
                            return;
                        }
                        conn.delete(dirurl)
                            .then(() => {
                                refreshFileList();
                            }, (err)=>{
                                showPopup('Failed to delete path: ' + err, {level: 'error', timeout: 5000});
                            });
                    });
                    actContainer.appendChild(deleteButton);
                    actTd.appendChild(actContainer);
                    tr.appendChild(actTd);
                }

            });
            data.files.forEach(file => {
                const tr = document.createElement('tr');
                {
                    const nameTd = document.createElement('td');
                    const plainUrl = decodePathURI(file.url);
                    const fileName = plainUrl.split('/').pop();
                    nameTd.textContent = fileName;
                    tr.appendChild(nameTd);
                    tbody.appendChild(tr);
                }

                {
                    const sizeTd = document.createElement('td');
                    const fileSize = file.file_size;
                    sizeTd.textContent = formatSize(fileSize);
                    tr.appendChild(sizeTd);
                }

                {
                    const dateTd = document.createElement('td');
                    const accessTime = file.access_time;
                    dateTd.textContent = cvtGMT2Local(accessTime);
                    tr.appendChild(dateTd);
                }

                {
                    const dateTd = document.createElement('td');
                    const createTime = file.create_time;
                    dateTd.textContent = cvtGMT2Local(createTime);
                    tr.appendChild(dateTd);
                }

                {
                    const accessTd = document.createElement('td');
                    if (file.owner_id === userRecord.id || userRecord.is_admin){
                        const select = document.createElement('select');
                        select.classList.add('access-select');
                        const options = ['unset', 'public', 'protected', 'private'];
                        options.forEach(opt => {
                            const option = document.createElement('option');
                            option.textContent = opt;
                            select.appendChild(option);
                        });
                        select.value = permMap[file.permission];
                        select.addEventListener('change', () => {
                            const perm = options.indexOf(select.value);
                            {
                                // ensure the permission is correct!
                                const permStr = options[perm];
                                const permStrFromMap = permMap[perm];
                                if (permStr !== permStrFromMap){
                                    console.warn("Permission string mismatch", permStr, permStrFromMap);
                                }
                            }
                            conn.setFilePermission(file.url, perm).then(
                                () => {},
                                (err) => {
                                    showPopup('Failed to set permission: ' + err, {level: 'error', timeout: 5000});
                                }
                            );
                        });
                            
                        accessTd.appendChild(select);
                    }
                    tr.appendChild(accessTd);
                }

                {
                    const actTd = document.createElement('td');
                    const actContainer = document.createElement('div');
                    actContainer.classList.add('action-container');

                    const copyButton = document.createElement('a');
                    copyButton.style.cursor = 'pointer';
                    copyButton.textContent = 'Share';
                    copyButton.addEventListener('click', () => {
                        copyToClipboard(conn.config.endpoint + '/' + file.url);
                        showPopup('Link copied to clipboard', {level: "success"});
                    });
                    actContainer.appendChild(copyButton);

                    const viewButton = document.createElement('a');
                    viewButton.textContent = 'View';
                    viewButton.href = conn.config.endpoint + '/' + file.url + '?token=' + conn.config.token;
                    viewButton.target = '_blank';
                    actContainer.appendChild(viewButton);

                    const moveButton = document.createElement('a');
                    moveButton.textContent = 'Move';
                    moveButton.style.cursor = 'pointer';
                    moveButton.addEventListener('click', () => {
                        showFloatingWindowLineInput((dstPath) => {
                            dstPath = encodePathURI(dstPath);
                            if (dstPath.endsWith('/')){
                                dstPath = dstPath.slice(0, -1);
                            }
                            conn.moveFile(file.url, dstPath)
                                .then(() => {
                                    refreshFileList();
                                }, 
                                (err) => {
                                    showPopup('Failed to move file: ' + err, {level: 'error'});
                                }
                            );
                        }, {
                            text: 'Enter the destination path: ',
                            placeholder: 'Destination path',
                            value: decodePathURI(file.url), 
                            select: "last-filename"
                        });
                    });
                    actContainer.appendChild(moveButton);

                    const downloadBtn = document.createElement('a');
                    downloadBtn.textContent = 'Download';
                    downloadBtn.href = conn.config.endpoint + '/' + file.url + '?download=true&token=' + conn.config.token;
                    actContainer.appendChild(downloadBtn);

                    const deleteButton = document.createElement('a');
                    deleteButton.textContent = 'Delete';
                    deleteButton.classList.add('delete-btn');
                    deleteButton.href = '#';
                    deleteButton.addEventListener('click', () => {
                        if (!confirm('Are you sure you want to delete ' + file.url + '?')){
                            return;
                        }
                        conn.delete(file.url)
                            .then(() => {
                                refreshFileList();
                            }, (err) => {
                                showPopup('Failed to delete file: ' + err, {level: 'error', timeout: 5000});
                            });
                    });
                    actContainer.appendChild(deleteButton);

                    actTd.appendChild(actContainer);
                    tr.appendChild(actTd);
                }

            });
        }, 
        (err) => {
            pathHintDiv.classList.remove('connected');
            pathHintDiv.classList.add('disconnected');
            pathHintLabel.textContent = pathInput.value;
            tbody.innerHTML = '';
            console.log("Error");
            console.error(err);
        }
    );
}


async function maybeRefreshUserRecord(){
    if (endpointInput.value && tokenInput.value){
        await refreshUserRecord();
    }
}

async function refreshUserRecord(){
    try{
        userRecord = await conn.whoami();
        console.log("User record: ", userRecord);
    }
    catch (err){
        userRecord = null;
        console.error("Failed to get user record");
        return false;
    }

    // UI updates.

    return true;
}

console.log("Hello World");