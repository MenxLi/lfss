
/**
 * @import { FileRecord, DirectoryRecord } from './api.js'
 */
import Connector from './api.js';

// from: https://pictogrammers.com/library/mdi/
const ICON_FOLDER = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><title>folder-outline</title><path d="M20,18H4V8H20M20,6H12L10,4H4C2.89,4 2,4.89 2,6V18A2,2 0 0,0 4,20H20A2,2 0 0,0 22,18V8C22,6.89 21.1,6 20,6Z" /></svg>';
const ICON_FILE = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><title>file-document-outline</title><path d="M6,2A2,2 0 0,0 4,4V20A2,2 0 0,0 6,22H18A2,2 0 0,0 20,20V8L14,2H6M6,4H13V9H18V20H6V4M8,12V14H16V12H8M8,16V18H13V16H8Z" /></svg>'
const ICON_PDF = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><title>file-pdf-box</title><path d="M19 3H5C3.9 3 3 3.9 3 5V19C3 20.1 3.9 21 5 21H19C20.1 21 21 20.1 21 19V5C21 3.9 20.1 3 19 3M9.5 11.5C9.5 12.3 8.8 13 8 13H7V15H5.5V9H8C8.8 9 9.5 9.7 9.5 10.5V11.5M14.5 13.5C14.5 14.3 13.8 15 13 15H10.5V9H13C13.8 9 14.5 9.7 14.5 10.5V13.5M18.5 10.5H17V11.5H18.5V13H17V15H15.5V9H18.5V10.5M12 10.5H13V13.5H12V10.5M7 10.5H8V11.5H7V10.5Z" /></svg>'
const ICON_EXE = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><title>application-brackets-outline</title><path d="M9.5,8.5L11,10L8,13L11,16L9.5,17.5L5,13L9.5,8.5M14.5,17.5L13,16L16,13L13,10L14.5,8.5L19,13L14.5,17.5M21,2H3A2,2 0 0,0 1,4V20A2,2 0 0,0 3,22H21A2,2 0 0,0 23,20V4A2,2 0 0,0 21,2M21,20H3V6H21V20Z" /></svg>'
const ICON_ZIP = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><title>zip-box-outline</title><path d="M12 17V15H14V17H12M14 13V11H12V13H14M14 9V7H12V9H14M10 11H12V9H10V11M10 15H12V13H10V15M21 5V19C21 20.1 20.1 21 19 21H5C3.9 21 3 20.1 3 19V5C3 3.9 3.9 3 5 3H19C20.1 3 21 3.9 21 5M19 5H12V7H10V5H5V19H19V5Z" /></svg>'
const ICON_CODE = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><title>file-code-outline</title><path d="M14 2H6C4.89 2 4 2.9 4 4V20C4 21.11 4.89 22 6 22H18C19.11 22 20 21.11 20 20V8L14 2M18 20H6V4H13V9H18V20M9.54 15.65L11.63 17.74L10.35 19L7 15.65L10.35 12.3L11.63 13.56L9.54 15.65M17 15.65L13.65 19L12.38 17.74L14.47 15.65L12.38 13.56L13.65 12.3L17 15.65Z" /></svg>'
const ICON_VIDEO = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><title>television-play</title><path d="M21,3H3C1.89,3 1,3.89 1,5V17A2,2 0 0,0 3,19H8V21H16V19H21A2,2 0 0,0 23,17V5C23,3.89 22.1,3 21,3M21,17H3V5H21M16,11L9,15V7" /></svg>'
const ICON_IMAGE = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><title>image-outline</title><path d="M19,19H5V5H19M19,3H5A2,2 0 0,0 3,5V19A2,2 0 0,0 5,21H19A2,2 0 0,0 21,19V5A2,2 0 0,0 19,3M13.96,12.29L11.21,15.83L9.25,13.47L6.5,17H17.5L13.96,12.29Z" /></svg>'

function getIconSVGFromMimeType(mimeType){
    if (mimeType == 'directory'){
        return ICON_FOLDER;
    }
    if (mimeType.startsWith('video/')){
        return ICON_VIDEO;
    }
    if (mimeType.startsWith('image/')){
        return ICON_IMAGE;
    }

    if (['application/pdf', 'application/x-pdf'].includes(mimeType)){
        return ICON_PDF;
    }
    if (['application/x-msdownload', 'application/x-msdos-program', 'application/x-msi', 'application/x-ms-wim', 'application/octet-stream', 'application/x-apple-diskimage'].includes(mimeType)){
        return ICON_EXE;
    }
    if (['application/zip', 'application/x-zip-compressed', 'application/x-7z-compressed', 'application/x-rar-compressed', 'application/x-tar', 'application/x-gzip'].includes(mimeType)){
        return ICON_ZIP;
    }
    if ([
        "text/html", "application/xhtml+xml", "application/xml", "text/css", "application/javascript", "text/javascript", "application/json", "text/x-python", "text/x-java-source",
        "application/x-httpd-php", "text/x-ruby", "text/x-perl", "application/x-sh", "application/sql", "text/x-c", "text/x-c++", "text/x-csharp", "text/x-go", "text/x-haskell",
        "text/x-lua", "text/x-markdown", "application/wasm", "application/x-tcl", "text/x-yaml", "application/x-latex", "application/x-tex", "text/x-scss", "application/x-lisp",
        "application/x-rust", "application/x-ruby", "text/x-asm"
    ].includes(mimeType)){
        return ICON_CODE;
    }

    return ICON_FILE;
}

function getSafeIconUrl(icon_str){
    // change icon color
    const color = '#345';
    icon_str = icon_str
        .replace(/<svg/, `<svg fill="${color}"`)
        .replace(/<path/, `<path fill="${color}"`);
    return 'data:image/svg+xml,' + encodeURIComponent(icon_str);
}

let thumb_counter = 0;
/**
 * @param {Connector} c
 * @param {FileRecord | DirectoryRecord} r
 * @returns {string}
 */
export function makeThumbHtml(c, r){
    function ensureSlashEnd(url){ return url.endsWith('/')? url : url + '/'; }
    const token = c.config.token;
    const mtype = r.mime_type? r.mime_type : 'directory';
    const thumb_id = `thumb-${thumb_counter++}`;
    const url = mtype == 'directory'? ensureSlashEnd(r.url) : r.url;

    if (mtype.startsWith('image/')){
        return `
        <div class="thumb" id="${thumb_id}"> \
            <img src="${c.config.endpoint}/${url}?token=${token}&thumb=true" alt="${r.url}" class="thumb" \
            onerror="this.src='${getSafeIconUrl(getIconSVGFromMimeType(mtype))}';this.classList.add('thumb-svg');" \
            onclick="window.open('${c.config.endpoint}/${url}?token=${token}', '_blank');" \
            /> \
        </div>
        `;
    }
    else{
        return `
        <div class="thumb" id="${thumb_id}"> \
            <img src="${getSafeIconUrl(getIconSVGFromMimeType(mtype))}" alt="${r.url}" class="thumb thumb-svg" \
            onclick="window.open('${c.config.endpoint}/${url}?token=${token}', '_blank');" \
            / > \
        </div>
        `;
    }
}