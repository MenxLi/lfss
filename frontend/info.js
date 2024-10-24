/**
 * @import { UserRecord, FileRecord, DirectoryRecord } from "./api.js";
 */
import Connector from "./api.js";
import { createFloatingWindow, showPopup } from "./popup.js";
import { cvtGMT2Local, formatSize, decodePathURI, copyToClipboard } from "./utils.js";

const ensureSlashEnd = (path) => {
    return path.endsWith('/') ? path : path + '/';
}

/**
 * @param {FileRecord} r
 * @param {UserRecord} u
 */
export function showInfoPanel(r, u){
    const innerHTML = `
<div class="info-container">
    <div class="info-container-left">
        <table class="info-table">
            <tr>
                <td class="info-table-key">Name</td>
                <td class="info-table-value">${decodePathURI(r.url).split('/').pop()}</td>
            </tr>
            <tr>
                <td class="info-table-key">Size</td>
                <td class="info-table-value">${formatSize(r.file_size)}</td>
            </tr>
            <tr>
                <td class="info-table-key">File-Type</td>
                <td class="info-table-value">${r.mime_type}</td>
            </tr>
            <tr>
                <td class="info-table-key">Owner-ID</td>
                <td class="info-table-value">${r.owner_id}</td>
            </tr>
            <tr>
                <td class="info-table-key">Access-Time</td>
                <td class="info-table-value">${cvtGMT2Local(r.access_time)}</td>
            </tr>
            <tr>
                <td class="info-table-key">Create-Time</td>
                <td class="info-table-value">${cvtGMT2Local(r.create_time)}</td>
            </tr>
        </table>
    </div>
    <div class="info-container-right">
        <div class="info-path-copy">
            <input type="text" value="${window.location.origin}/${r.url}" readonly>
            <button class="copy-button" id='copy-btn-full-path'>📋</button>
        </div>
        <div class="info-path-copy">
            <input type="text" value="${r.url}" readonly>
            <button class="copy-button" id='copy-btn-rel-path'>📋</button>
        </div>
    </div>
</div>
    `
    const [win, closeWin] = createFloatingWindow(innerHTML, {title: 'File Info'});
    document.getElementById('copy-btn-full-path').onclick = () => {
        copyToClipboard(window.location.origin + '/' + r.url);
        showPopup('Path copied to clipboard', {timeout: 2000, level: 'success'});
    }
    document.getElementById('copy-btn-rel-path').onclick = () => {
        copyToClipboard(r.url);
        showPopup('Path copied to clipboard', {timeout: 2000, level: 'success'});
    }
}

/**
 * @param {DirectoryRecord} r
 * @param {UserRecord} u
 * @param {Connector} c
 */
export function showDirInfoPanel(r, u, c){
    let fmtPath = decodePathURI(r.url);
    if (fmtPath.endsWith('/')) {
        fmtPath = fmtPath.slice(0, -1);
    }
    const innerHTML = `
<div class="info-container">
    <div class="info-container-left">
        <table class="info-table">
            <tr>
                <td class="info-table-key">Name</td>
                <td class="info-table-value" id="info-table-pathname">${fmtPath.split('/').pop()}</td>
            </tr>
            <tr>
                <td class="info-table-key">Size</td>
                <td class="info-table-value" id="info-table-pathsize">N/A</td>
            </tr>
            <tr>
                <td class="info-table-key">File-Count</td>
                <td class="info-table-value" id="info-table-nfiles">N/A</td>
            </tr>
            <tr>
                <td class="info-table-key">Access-Time</td>
                <td class="info-table-value" id="info-table-accesstime">1970-01-01 00:00:00</td>
            </tr>
            <tr>
                <td class="info-table-key">Create-Time</td>
                <td class="info-table-value" id="info-table-createtime">1970-01-01 00:00:00</td>
            </td>
        </table>
    </div>
    <div class="info-container-right">
        <div class="info-path-copy">
            <input type="text" value="${window.location.origin}/${ensureSlashEnd(r.url)}" readonly>
            <button class="copy-button" id='copy-btn-full-path'>📋</button>
        </div>
        <div class="info-path-copy">
            <input type="text" value="${ensureSlashEnd(r.url)}" readonly>
            <button class="copy-button" id='copy-btn-rel-path'>📋</button>
        </div>
    </div>
</div>
    `
    const [win, closeWin] = createFloatingWindow(innerHTML, {title: 'File Info'});
    document.getElementById('copy-btn-full-path').onclick = () => {
        copyToClipboard(window.location.origin + '/' + ensureSlashEnd(r.url));
        showPopup('Path copied to clipboard', {timeout: 2000, level: 'success'});
    }
    document.getElementById('copy-btn-rel-path').onclick = () => {
        copyToClipboard(ensureSlashEnd(r.url));
        showPopup('Path copied to clipboard', {timeout: 2000, level: 'success'});
    }

    const sizeValTd = document.querySelector('.info-table-value#info-table-pathsize');
    const createTimeValTd = document.querySelector('.info-table-value#info-table-createtime');
    const accessTimeValTd = document.querySelector('.info-table-value#info-table-accesstime');
    const countValTd = document.querySelector('.info-table-value#info-table-nfiles');
    // console.log(sizeValTd, createTimeValTd, accessTimeValTd)
    c.getMetadata(ensureSlashEnd(r.url)).then((meta) => {
        if (!meta) {
            console.error('Failed to fetch metadata for: ' + r.url);
            return;
        }
        sizeValTd.textContent = formatSize(meta.size);
        createTimeValTd.textContent = cvtGMT2Local(meta.create_time);
        accessTimeValTd.textContent = cvtGMT2Local(meta.access_time);
        countValTd.textContent = meta.n_files;
    });
}