
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