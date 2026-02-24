import Connector from '@/api'

export function resolveEndpoint(endpoint?: string): string {
    return endpoint?.trim() || localStorage.getItem('endpoint') || window.location.origin;
}

export function createConnector(token: string, endpoint?: string): Connector {
    const conn = new Connector();
    conn.config = {
        endpoint: resolveEndpoint(endpoint),
        token
    };
    return conn;
}

export function formatBytes(bytes: number): string {
    if (bytes === -1) return '-';
    if (bytes === 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const idx = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
    return `${(bytes / Math.pow(1024, idx)).toFixed(2).replace(/\.00$/, '')} ${units[idx]}`;
}

export function formatDateTime(value: string | number | Date, fromUtc = true): string {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return '-';
    }
    if (fromUtc) {
        date.setHours(date.getHours() - date.getTimezoneOffset() / 60);
    }
    return date.toLocaleString(undefined, {
        dateStyle: 'short',
        timeStyle: 'short',
        hour12: false
    });
}

export function copyToClipboard(text: string) {
    function secureCopy(text: string) {
        navigator.clipboard.writeText(text);
    }
    function unsecureCopy(text: string) {
        const el = document.createElement('textarea');
        el.value = text;
        document.body.appendChild(el);
        el.select();
        document.execCommand('copy');
        document.body.removeChild(el);
    }
    if (navigator.clipboard) {
        secureCopy(text);
    } else {
        unsecureCopy(text);
    }
}

export function ensureDirPath(path: string): string {
    if (!path) return '';
    return path.endsWith('/') ? path : `${path}/`;
}

export function stripTrailingSlash(path: string): string {
    if (!path || path === '/') return path;
    return path.endsWith('/') ? path.slice(0, -1) : path;
}

export function getLastPathComponentRange(path: string): [number, number] {
    if (!path) return [0, 0];
    const normalized = stripTrailingSlash(path);
    const lastSlash = normalized.lastIndexOf('/');
    return [Math.max(lastSlash + 1, 0), normalized.length];
}

export function getLastFilenameStemRange(path: string): [number, number] {
    if (!path) return [0, 0];
    const normalized = stripTrailingSlash(path);
    const lastSlash = normalized.lastIndexOf('/');
    const start = Math.max(lastSlash + 1, 0);
    const fname = normalized.slice(start);
    const lastDot = fname.lastIndexOf('.');
    if (lastDot <= 0) {
        return [start, normalized.length];
    }
    return [start, start + lastDot];
}

export function selectInputRange(input: HTMLInputElement, start: number, end: number) {
    input.focus();
    input.setSelectionRange(Math.max(start, 0), Math.max(end, 0));
}

export async function forEachFile(e: DragEvent, callback: (relPath: string, filePromiseFn: () => Promise<File>) => Promise<void>, maxConcurrent = 8) {
    const results: Promise<void>[] = [];

    let activeCount = 0;
    const queue: (() => void)[] = [];

    async function runWithLimit(task: () => Promise<any>) {
        if (activeCount >= maxConcurrent) {
            await new Promise<void>(resolve => queue.push(resolve));
        }
        activeCount++;
        try {
            return await task();
        } finally {
            activeCount--;
            if (queue.length) {
                const next = queue.shift();
                if (next) next();
            }
        }
    }

    async function traverse(entry: any, path: string) {
        if (entry.isFile) {
            const filePromiseFn = () =>
                new Promise<File>((resolve, reject) => entry.file(resolve, reject));
            results.push(runWithLimit(() => callback(path + entry.name, filePromiseFn)));
        } else if (entry.isDirectory) {
            const reader = entry.createReader();

            async function readAllEntries(reader: any) {
                const entries: any[] = [];
                while (true) {
                    const chunk = await new Promise<any[]>((resolve, reject) => {
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
        Array.from(e.dataTransfer.files).forEach(file => {
            results.push(runWithLimit(() => callback(file.name, () => Promise.resolve(file))));
        });
    }
    return results;
}
