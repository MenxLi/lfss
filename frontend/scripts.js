import Connector from './api.js';
import { formatSize, decodePathURI } from './utils.js';

const conn = new Connector();

const endpointInput = document.querySelector('input#endpoint');
const tokenInput = document.querySelector('input#token');
const pathInput = document.querySelector('input#path');
const pathBackButton = document.querySelector('span#back-btn');
const pathHintDiv = document.querySelector('#position-hint');
const tbody = document.querySelector('#files-table-body');
const uploadFilePrefixLabel = document.querySelector('#upload-file-prefix');
const uploadFileSelector = document.querySelector('#file-selector');
const uploadFileNameInput = document.querySelector('#file-name');
const uploadButton = document.querySelector('#upload-button');

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
    maybeRefreshFileList();
}

function onPathChange(){
    uploadFilePrefixLabel.textContent = pathInput.value;
    window.localStorage.setItem('path', pathInput.value);
    maybeRefreshFileList();
}

endpointInput.addEventListener('blur', () => {
    conn.config.endpoint = endpointInput.value;
    window.localStorage.setItem('endpoint', endpointInput.value);
    maybeRefreshFileList();
});
tokenInput.addEventListener('blur', () => {
    conn.config.token = tokenInput.value;
    window.localStorage.setItem('token', tokenInput.value);
    maybeRefreshFileList();
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
        }
    });
}

uploadFileSelector.addEventListener('change', () => {
    uploadFileNameInput.value = uploadFileSelector.files[0].name;
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
        });
});

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
            console.log("Got data", data);

            if (!data.dirs){ data.dirs = []; }
            if (!data.files){ data.files = []; }

            tbody.innerHTML = '';
            pathHintDiv.textContent = pathInput.value;
            data.dirs.forEach(dir => {
                const tr = document.createElement('tr');
                {
                    const nameTd = document.createElement('td');
                    if (dir.url.endsWith('/')){
                        dir.url = dir.url.slice(0, -1);
                    }
                    const dirName = dir.url.split('/').pop();
                    const dirLink = document.createElement('a');
                    dirLink.textContent = dirName;
                    dirLink.addEventListener('click', () => {
                        pathInput.value = dir.url + (dir.url.endsWith('/') ? '' : '/');
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
                    tr.appendChild(dateTd);
                }
                {
                    const actTd = document.createElement('td');
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
                    const createTime = file.create_time;
                    dateTd.textContent = createTime;
                    tr.appendChild(dateTd);
                }

                {
                    const actTd = document.createElement('td');
                    const actContainer = document.createElement('div');
                    actContainer.classList.add('action-container');

                    const copyButton = document.createElement('a');
                    copyButton.textContent = 'Copy';
                    copyButton.href = '#';
                    copyButton.addEventListener('click', () => {
                        navigator.clipboard.writeText(conn.config.endpoint + '/' + file.url);
                    });
                    actContainer.appendChild(copyButton);

                    const viewButton = document.createElement('a');
                    viewButton.textContent = 'View';
                    viewButton.href = conn.config.endpoint + '/' + file.url;
                    viewButton.target = '_blank';
                    actContainer.appendChild(viewButton);

                    const downloadBtn = document.createElement('a');
                    downloadBtn.textContent = 'Download';
                    downloadBtn.href = conn.config.endpoint + '/' + file.url + '?asfile=true';
                    actContainer.appendChild(downloadBtn);

                    const deleteButton = document.createElement('a');
                    deleteButton.textContent = 'Delete';
                    deleteButton.href = '#';
                    deleteButton.addEventListener('click', () => {
                        if (!confirm('Are you sure you want to delete ' + file.url + '?')){
                            return;
                        }
                        conn.delete(file.url)
                            .then(() => {
                                refreshFileList();
                            });
                    });
                    actContainer.appendChild(deleteButton);

                    actTd.appendChild(actContainer);
                    tr.appendChild(actTd);
                }

            });
        }, 
        (err) => {
            console.log("Error");
            console.error(err);
        }
    );
}

console.log("Hello World");