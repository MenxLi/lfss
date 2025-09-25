import { store } from './state.js';
import { maybeShowLoginPanel } from './login.js';

{
    // initialization
    store.init();
    maybeShowLoginPanel(store, ).then(
        (user) => {
            console.log("User record", user);
        }
    )
}

const filePathLabel = document.getElementById('file-path-label');
const textArea = document.querySelector('#editor');
const backhomeBtn = document.getElementById('home-btn');
const saveBtn = document.getElementById('save-btn');
const saveHint = document.getElementById('save-hint');

backhomeBtn.addEventListener('click', () => {
    window.location.href = './index.html';
});

const urlParams = new URLSearchParams(window.location.search);
const filePath = urlParams.get('p') || urlParams.get('path');

function raiseError(msg) {
    filePathLabel.textContent = `Error: ${msg}`;
    filePathLabel.style.color = 'darkred';
    textArea.disabled = true;
    throw new Error(msg);
}


if (!filePath) {
    raiseError('No file specified');
}
if (filePath.endsWith('/')) {
    raiseError('Path cannot be a directory');
}
// check existence
let ftype='';
const fmeta = await store.conn.getMetadata(filePath).catch((e) => {
    raiseError(`File "${filePath}" does not exist or cannot be accessed.`);
});
if (fmeta != null) {
    ftype = fmeta.mime_type || '';
    saveHint.style.opacity = 1;
}

// get content
let content = '';
async function loadContent() {
    content = await store.conn.getText(filePath).catch((e) => {
        raiseError(`Failed to read file "${filePath}": ${e.message}`);
    });
    textArea.value = content;
}
await loadContent();

async function saveFile() {
    const content = textArea.value;
    try {
        await store.conn.putText(filePath, content, {conflict: 'overwrite'});
        saveHint.style.opacity = 1;
    }
    catch (e) {
        raiseError(`Failed to save file "${filePath}": ${e.message}`);
    }
}
saveBtn.addEventListener('click', saveFile);

filePathLabel.textContent = filePath;

textArea.addEventListener('input', () => {
    saveHint.style.opacity = 0;
    if (content == textArea.value){
        saveHint.style.opacity = 1;
    }
});

// bind Ctrl+S to save
document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        saveBtn.click();
    }
});
