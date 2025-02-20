
export function formatSize(size){
    if (size < 0){
        return '';
    }
    const sizeInKb = size / 1024;
    const sizeInMb = sizeInKb / 1024;
    const sizeInGb = sizeInMb / 1024;
    if (sizeInGb > 1){
        return sizeInGb.toFixed(2) + ' GB';
    }
    else if (sizeInMb > 1){
        return sizeInMb.toFixed(2) + ' MB';
    }
    else if (sizeInKb > 1){
        return sizeInKb.toFixed(2) + ' KB';
    }
    else {
        return size + ' B';
    }
}

export function copyToClipboard(text){
    function secureCopy(text){
        navigator.clipboard.writeText(text);
    }
    function unsecureCopy(text){
        const el = document.createElement('textarea');
        el.value = text;
        document.body.appendChild(el);
        el.select();
        document.execCommand('copy');
        document.body.removeChild(el);
    }
    if (navigator.clipboard){
        secureCopy(text);
    }
    else {
        unsecureCopy(text);
    }
}

export function encodePathURI(path){
    return path.split('/').map(encodeURIComponent).join('/');
}

export function decodePathURI(path){
    return path.split('/').map(decodeURIComponent).join('/');
}

export function ensurePathURI(path){
    return encodePathURI(decodePathURI(path));
}

export function getRandomString(n, additionalCharset='0123456789_-(=)[]{}'){
    let result = '';
    let charset = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ';
    const firstChar = charset[Math.floor(Math.random() * charset.length)];
    const lastChar = charset[Math.floor(Math.random() * charset.length)];
    result += firstChar;
    charset += additionalCharset;
    for (let i = 0; i < n-2; i++){
        result += charset[Math.floor(Math.random() * charset.length)];
    }
    result += lastChar;
    return result;
};

/**
 * @param {string} dateStr 
 * @returns {string}
 */
export function cvtGMT2Local(dateStr){
    if (!dateStr || dateStr === 'N/A'){
        return '';
    }
    const gmtdate = new Date(dateStr);
    const localdate = new Date(gmtdate.getTime() + gmtdate.getTimezoneOffset() * 60000);
    return localdate.toISOString().slice(0, 19).replace('T', ' ');
}

export function debounce(fn,wait){
    let timeout;
    return function(...args){
        const context = this;
        if (timeout) clearTimeout(timeout);
        timeout = setTimeout(() => fn.apply(context, args), wait);
    }
}

export function asHtmlText(text){
    const anonElem = document.createElement('div');
    anonElem.textContent = text;
    const htmlText = anonElem.innerHTML;
    return htmlText;
}

/**
 * @param {Event} e 
 * @param {(relPath: string, file: Promise<File>) => Promise<void>} callback 
 * @returns {Promise<void>[]}
 */
export async function forEachFile(e, callback){
    /** @param {DataTransferItem} item */
    function inferFileType(item){
        let ftype = '';
        if (item.webkitGetAsEntry){
            const entry = item.webkitGetAsEntry();
            if (entry.isFile){ ftype = 'file'; }
            if (entry.isDirectory){ ftype = 'directory'; }
        }
        else{
            if (item.kind === 'file'){
                if (item.type === '' && item.size % 4096 === 0){
                    // https://stackoverflow.com/a/25095250/24720063
                    console.log("Infer directory from size", item);
                    ftype = 'directory';
                }
                else{
                    ftype = 'file';
                }
            }
        }
        return ftype;
    }
    /** 
     * @param {FileSystemEntry} entry 
     * @param {function(string, File): Promise<void>} uploadFn
     */
    async function handleOneEntry(entry, promises){
        if (entry.isFile){
            const relPath = entry.fullPath.startsWith('/') ? entry.fullPath.slice(1) : entry.fullPath;
            const filePromise = new Promise((resolve, reject) => {
                entry.file(resolve, reject);
            });
            promises.push(callback(relPath, filePromise));
        }
        if (entry.isDirectory){
            const reader = entry.createReader();
            const entries = await new Promise((resolve, reject) => {
                reader.readEntries(resolve, reject);
            });
            for (let i = 0; i < entries.length; i++){
                await handleOneEntry(entries[i], promises);
            }
        }
    }

    const promises = [];
    const items = e.dataTransfer.items;
    for (let i = 0; i < items.length; i++){
        const item = items[i];
        const ftype = inferFileType(item);
        if (ftype === 'file' || ftype === 'directory'){
            const entry = item.webkitGetAsEntry();
            await handleOneEntry(entry, promises);
        }
        else{
            console.error("Unknown file type", item);
        }
    }

    return promises;
}