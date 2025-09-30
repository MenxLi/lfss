import { store } from './state.js';
import { maybeShowLoginPanel } from './login.js';

const MAX_FILE_SIZE_MB = 5;

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

// disable until file is loaded
saveBtn.disabled = true;
textArea.disabled = true;

backhomeBtn.addEventListener('click', () => {
    const urlFrom = new URL(window.location.href);
    if (urlFrom.searchParams.has('from')) {
        const from = urlFrom.searchParams.get('from');
        window.location.href = from;
        return;
    }
    window.location.href = './index.html';
});

// make textarea tab insert spaces
textArea.addEventListener('keydown', (e) => {
    const TAB_SIZE = 4;
    if (e.key === 'Tab') {
        e.preventDefault();
        const start = textArea.selectionStart;
        const end = textArea.selectionEnd;
        textArea.value = textArea.value.substring(0, start) + ' '.repeat(TAB_SIZE) + textArea.value.substring(end);
        textArea.selectionStart = textArea.selectionEnd = start + TAB_SIZE;
    }
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

async function loadContent() {
    content = await store.conn.getText(filePath).catch((e) => {
        raiseError(`Failed to read file "${filePath}": ${e.message}`);
    });
    textArea.value = content;
    return content;
}

// check existence
let ftype='';
let content = '';

const fmeta = await store.conn.getMetadata(filePath).catch((e) => {
    raiseError(`File "${filePath}" does not exist or cannot be accessed.`);
});
filePathLabel.textContent = filePath;
if (fmeta != null) {
    ftype = fmeta.mime_type || '';
    saveHint.style.opacity = 1;
    if (fmeta.file_size && fmeta.file_size > MAX_FILE_SIZE_MB * 1024 * 1024) {
        raiseError(`File too large (${(fmeta.file_size / (1024 * 1024)).toFixed(2)} MB). Max allowed size is ${MAX_FILE_SIZE_MB} MB.`);
    }
    content = await loadContent();
}
else {
    const newHint = document.createElement('span');
    newHint.id = 'new-hint';
    newHint.textContent = 'new';
    filePathLabel.appendChild(newHint);
    textArea.focus();
}

async function saveFile() {
    const content = textArea.value;
    try {
        await store.conn.putText(filePath, content, {conflict: 'overwrite', type: ftype? ftype : 'text/plain'});
        saveHint.style.opacity = 1;
        // remove new file hint if exists
        const newHint = document.getElementById('new-hint');
        if (newHint) { newHint.remove(); }
    }
    catch (e) {
        raiseError(`Failed to save file "${filePath}": ${e.message}`);
    }
}

// unfreeze elements
saveBtn.disabled = false;
textArea.disabled = false;

saveBtn.addEventListener('click', saveFile);
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
