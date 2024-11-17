import { permMap, listPath } from './api.js';
import { showFloatingWindowLineInput, showPopup } from './popup.js';
import { formatSize, decodePathURI, ensurePathURI, getRandomString, cvtGMT2Local, debounce, encodePathURI, asHtmlText } from './utils.js';
import { showInfoPanel, showDirInfoPanel } from './info.js';
import { makeThumbHtml } from './thumb.js';
import { store } from './state.js';
import { maybeShowLoginPanel } from './login.js';

/** @type {import('./api.js').UserRecord}*/
let userRecord = null;

const ensureSlashEnd = (path) => {
    return path.endsWith('/') ? path : path + '/';
}

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
const pageLimitSelect = document.querySelector('#page-limit-sel');
const pageNumInput = document.querySelector('#page-num-input');
const pageCountLabel = document.querySelector('#page-count-lbl');
const sortBySelect = document.querySelector('#sort-by-sel');
const sortOrderSelect = document.querySelector('#sort-order-sel');

const conn = store.conn;

{
    // initialization
    store.init();
    pathInput.value = store.dirpath;
    uploadFilePrefixLabel.textContent = pathInput.value;
    sortBySelect.value = store.orderby;
    sortOrderSelect.value = store.sortorder;
    pageLimitSelect.value = store.pagelim;
    pageNumInput.value = store.pagenum;

    maybeShowLoginPanel(store,).then(
        (user) => {
            console.log("User record", user);
            userRecord = user;
            maybeRefreshFileList();
        }
    )
}

pathHintDiv.addEventListener('click', () => {
    maybeShowLoginPanel(store, true).then(
        (user) => {
            console.log("User record", user);
            userRecord = user;
            maybeRefreshFileList();
        }
    );
});

function onPathChange(){
    uploadFilePrefixLabel.textContent = pathInput.value;
    store.dirpath = pathInput.value;
    maybeRefreshFileList();
}

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
    if (fileName.endsWith('/')){
        uploadFileNameInput.classList.add('duplicate');
        return;
    }
    if (fileName.length === 0){
        uploadFileNameInput.classList.remove('duplicate');
    }
    else {
        const p = ensurePathURI(store.dirpath + fileName);
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
    let path = store.dirpath;
    let fileName = uploadFileNameInput.value;
    if (fileName.length === 0){
        throw new Error('File name cannot be empty');
    }
    if (fileName.endsWith('/')){
        throw new Error('File name cannot end with /');
    }
    path = path + fileName;
    showPopup('Uploading...', {level: 'info', timeout: 3000});
    conn.put(path, file, {'conflict': 'overwrite'})
        .then(() => {
            refreshFileList();
            uploadFileNameInput.value = '';
            onFileNameInpuChange();
            showPopup('Upload success.', {level: 'success', timeout: 3000});
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
            let dstPath = store.dirpath + uploadFileNameInput.value;
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
                    await conn.put(path, file, {conflict: 'overwrite'});
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
            showPopup('Uploading multiple files...', {level: 'info', timeout: 3000});
            Promise.all(promises).then(
                () => {
                    showPopup('Upload success.', {level: 'success', timeout: 3000});
                    refreshFileList();
                }, 
                (err) => {
                    showPopup('Failed to upload some files: ' + err, {level: 'error', timeout: 5000});
                }
            );
        }
    });
}

function maybeRefreshFileList(){
    if (
        store.dirpath && store.dirpath.length > 0 && store.dirpath.endsWith('/')
    ){
        refreshFileList();
    }
}

sortBySelect.addEventListener('change', (elem) => {store.orderby = elem.target.value; refreshFileList();});
sortOrderSelect.addEventListener('change', (elem) => {store.sortorder = elem.target.value; refreshFileList();});
pageLimitSelect.addEventListener('change', (elem) => {store.pagelim = elem.target.value; refreshFileList();});
pageNumInput.addEventListener('change', (elem) => {store.pagenum = elem.target.value; refreshFileList();});

window.addEventListener('keydown', (e) => {
    if (document.activeElement !== document.body){
        return;
    }
    if (e.key === 'ArrowLeft'){
        const num = Math.max(store.pagenum - 1, 1);
        pageNumInput.value = num;
        store.pagenum = num;
        refreshFileList();
    }
    else if (e.key === 'ArrowRight'){
        const num = Math.min(Math.max(store.pagenum + 1, 1), parseInt(pageCountLabel.textContent));
        pageNumInput.value = num;
        store.pagenum = num;
        refreshFileList();
    }
})

async function refreshFileList(){

    listPath(conn, store.dirpath, {
        offset: (store.pagenum - 1) * store.pagelim,
        limit: store.pagelim,
        orderBy: store.orderby,
        orderDesc: store.sortorder === 'desc'
    })
        .then(async (res) => {
            pathHintDiv.classList.remove('disconnected');
            pathHintDiv.classList.add('connected');
            pathHintLabel.textContent = `[${userRecord.username}] ${store.endpoint}/${store.dirpath.startsWith('/') ? store.dirpath.slice(1) : store.dirpath}`;
            tbody.innerHTML = '';
            console.log("Got data", res);

            const [data, count] = res;

            {
                const total = count.dirs + count.files;
                const pageCount = Math.max(Math.ceil(total / store.pagelim), 1);
                pageCountLabel.textContent = pageCount;
                if (store.pagenum > pageCount){
                    store.pagenum = pageCount;
                    pageNumInput.value = pageCount;

                    await refreshFileList();
                    return;
                }
            }

            // maybe undefined
            if (!data.dirs){ data.dirs = []; }
            if (!data.files){ data.files = []; }

            data.dirs.forEach(dir => {
                const tr = document.createElement('tr');
                const sizeTd = document.createElement('td');
                const accessTimeTd = document.createElement('td');
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
                    const nameDiv = document.createElement('div');
                    nameDiv.classList.add('filename-container');
                    nameDiv.innerHTML = makeThumbHtml(conn, dir);
                    nameDiv.appendChild(dirLink);
                    nameTd.appendChild(nameDiv);

                    tr.appendChild(nameTd);
                    tbody.appendChild(tr);
                }
                {
                    // these are initialized meta
                    sizeTd.textContent = formatSize(dir.size);
                    tr.appendChild(sizeTd);
                    accessTimeTd.textContent = cvtGMT2Local(dir.access_time);
                    tr.appendChild(accessTimeTd);
                }
                {
                    const accessTd = document.createElement('td');
                    tr.appendChild(accessTd);
                }
                {
                    const dirurl = ensureSlashEnd(dir.url);
                    const actTd = document.createElement('td');
                    const actContainer = document.createElement('div');
                    actContainer.classList.add('action-container');

                    const infoButton = document.createElement('a');
                    infoButton.style.cursor = 'pointer';
                    infoButton.textContent = 'Details';
                    infoButton.style.width = '100%';
                    infoButton.style.display = 'block';
                    infoButton.style.textAlign = 'center';
                    infoButton.addEventListener('click', () => {
                        showDirInfoPanel(dir, userRecord, conn);
                    });
                    actContainer.appendChild(infoButton);

                    const moveButton = document.createElement('a');
                    moveButton.textContent = 'Move';
                    moveButton.style.cursor = 'pointer';
                    moveButton.addEventListener('click', () => {
                        showFloatingWindowLineInput((dstPath) => {
                            dstPath = encodePathURI(dstPath);
                            console.log("Moving", dirurl, "to", dstPath);
                            conn.move(dirurl, dstPath)
                                .then(() => {
                                    refreshFileList();
                                }, 
                                (err) => {
                                    showPopup('Failed to move path: ' + err, {level: 'error'});
                                }
                            );
                        }, {
                            text: 'Enter the destination path: ',
                            placeholder: 'Destination path',
                            value: decodePathURI(dirurl), 
                            select: "last-pathname"
                        });
                    });
                    actContainer.appendChild(moveButton);

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

                    nameTd.innerHTML = `
                    <div class="filename-container">
                        ${makeThumbHtml(conn, file)}
                        <span>${asHtmlText(fileName)}</span>
                    </div>
                    `
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

                    const infoButton = document.createElement('a');
                    infoButton.style.cursor = 'pointer';
                    infoButton.textContent = 'Details';
                    infoButton.addEventListener('click', () => {
                        showInfoPanel(file, userRecord);
                    });
                    actContainer.appendChild(infoButton);

                    const moveButton = document.createElement('a');
                    moveButton.textContent = 'Move';
                    moveButton.style.cursor = 'pointer';
                    moveButton.addEventListener('click', () => {
                        showFloatingWindowLineInput((dstPath) => {
                            dstPath = encodePathURI(dstPath);
                            conn.move(file.url, dstPath)
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
            pathHintLabel.textContent = store.dirpath;
            tbody.innerHTML = '';
            console.log("Error");
            console.error(err);
        }
    );
}

console.log("Hello World");