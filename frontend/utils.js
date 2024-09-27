
export function formatSize(size){
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