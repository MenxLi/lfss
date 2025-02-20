
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
 * Iterates over all files dropped in the event,
 * including files inside directories, and processes them
 * using the provided callback with a concurrency limit.
 *
 * @param {Event} e The drop event.
 * @param {(relPath: string, file: Promise<File>) => Promise<void>} callback A function
 *        that receives the relative path and a promise for the File.
 * @param {number} [maxConcurrent=5] Maximum number of concurrent callback executions.
 * @returns {Promise<Promise<void>[]>} A promise resolving to an array of callback promises.
 */
export async function forEachFile(e, callback, maxConcurrent = 5) {
    const results = []; // to collect callback promises

    // Concurrency barrier variables.
    let activeCount = 0;
    const queue = [];

    /**
     * Runs the given async task when below the concurrency limit.
     * If at limit, waits until a slot is free.
     *
     * @param {() => Promise<any>} task An async function returning a promise.
     * @returns {Promise<any>}
     */
    async function runWithLimit(task) {
        // If we reached the concurrency limit, wait for a free slot.
        if (activeCount >= maxConcurrent) {
            await new Promise(resolve => queue.push(resolve));
        }
        activeCount++;
        try {
            return await task();
        } finally {
            activeCount--;
            // If there are waiting tasks, allow the next one to run.
            if (queue.length) {
                queue.shift()();
            }
        }
    }

    /**
     * Recursively traverses a file system entry.
     *
     * @param {FileSystemEntry} entry The entry (file or directory).
     * @param {string} path The current relative path.
     */
    async function traverse(entry, path) {
        if (entry.isFile) {
            // Wrap file retrieval in a promise.
            const filePromise = new Promise((resolve, reject) => {
                entry.file(resolve, reject);
            });
            // Use the concurrency barrier for the callback invocation.
            results.push(runWithLimit(() => callback(path + entry.name, filePromise)));
        } else if (entry.isDirectory) {
            const reader = entry.createReader();

            async function readAllEntries(reader) {
                const entries = [];
                while (true) {
                const chunk = await new Promise((resolve, reject) => {
                    reader.readEntries(resolve, reject);
                });
                if (chunk.length === 0) break;
                entries.push(...chunk);
                }
                return entries;
            }

            const entries = await readAllEntries(reader);
            await Promise.all(
                entries.map(ent => traverse(ent, path + entry.name + '/'))
            );
        }
    }

    // Process using DataTransfer items if available.
    if (e.dataTransfer && e.dataTransfer.items) {
        await Promise.all(
        Array.from(e.dataTransfer.items).map(async item => {
            const entry = item.webkitGetAsEntry && item.webkitGetAsEntry();
            if (entry) {
            await traverse(entry, '');
            }
        })
        );
    } else if (e.dataTransfer && e.dataTransfer.files) {
        // Fallback for browsers that support only dataTransfer.files.
        Array.from(e.dataTransfer.files).forEach(file => {
        results.push(runWithLimit(() => callback(file.name, Promise.resolve(file))));
        });
    }
    return results;
}

