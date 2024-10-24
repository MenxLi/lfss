"""
Balance the storage by ensuring that large file thresholds are met.
"""

from lfss.src.config import LARGE_BLOB_DIR, LARGE_FILE_BYTES
import argparse, time, itertools
from functools import wraps
from asyncio import Semaphore
import aiofiles, asyncio
import aiofiles.os
from contextlib import contextmanager
from lfss.src.database import transaction, unique_cursor
from lfss.src.connection_pool import global_entrance

@contextmanager
def indicator(name: str):
    print(f"\033[1;33mRunning {name}... \033[0m")
    s = time.time()
    yield
    print(f"{name} took {time.time() - s:.2f} seconds.")

sem = Semaphore(1)

def _get_sem():
    return sem

def barriered(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        async with _get_sem():
            return await func(*args, **kwargs)
    return wrapper

@barriered
async def move_to_external(f_id: str, flag: str = ''):
    async with transaction() as c:
        cursor = await c.execute( "SELECT data FROM blobs.fdata WHERE file_id = ?", (f_id,))
        blob_row = await cursor.fetchone()
        if blob_row is None:
            print(f"{flag}File {f_id} not found in blobs.fdata")
            return
        blob: bytes = blob_row[0]
        async with aiofiles.open(LARGE_BLOB_DIR / f_id, 'wb') as f:
            await f.write(blob)
        await c.execute( "UPDATE fmeta SET external = 1 WHERE file_id = ?", (f_id,))
        await c.execute( "DELETE FROM blobs.fdata WHERE file_id = ?", (f_id,))
        print(f"{flag}Moved {f_id} to external storage")

@barriered
async def move_to_internal(f_id: str, flag: str = ''):
    async with transaction() as c:
        if not (LARGE_BLOB_DIR / f_id).exists():
            print(f"{flag}File {f_id} not found in external storage")
            return
        async with aiofiles.open(LARGE_BLOB_DIR / f_id, 'rb') as f:
            blob = await f.read()

        await c.execute("INSERT INTO blobs.fdata (file_id, data) VALUES (?, ?)", (f_id, blob))
        await c.execute("UPDATE fmeta SET external = 0 WHERE file_id = ?", (f_id,))
        (LARGE_BLOB_DIR / f_id).unlink(missing_ok=True)
        print(f"{flag}Moved {f_id} to internal storage")

@global_entrance()
async def _main(batch_size: int = 10000):
    tasks = []

    e_cout = 0
    for batch_count in itertools.count(start=0):
        async with unique_cursor() as conn:
            exceeded_rows = list(await (await conn.execute( 
                "SELECT file_id FROM fmeta WHERE file_size > ? AND external = 0 LIMIT ? OFFSET ?",
                (LARGE_FILE_BYTES, batch_size, batch_size * batch_count)
            )).fetchall())
            if not exceeded_rows:
                break
        e_cout += len(exceeded_rows)
        for i in range(0, len(exceeded_rows)):
            row = exceeded_rows[i]
            f_id = row[0]
            tasks.append(move_to_external(f_id, flag=f"[b{batch_count+1}-e{i+1}/{len(exceeded_rows)}] "))
        await asyncio.gather(*tasks)

    i_count = 0
    for batch_count in itertools.count(start=0):
        async with unique_cursor() as conn:
            under_rows = list(await (await conn.execute(
                "SELECT file_id, file_size, external FROM fmeta WHERE file_size <= ? AND external = 1 LIMIT ? OFFSET ?",
                (LARGE_FILE_BYTES, batch_size, batch_size * batch_count)
            )).fetchall())
            if not under_rows:
                break
        i_count += len(under_rows)
        for i in range(0, len(under_rows)):
            row = under_rows[i]
            f_id = row[0]
            tasks.append(move_to_internal(f_id, flag=f"[b{batch_count+1}-i{i+1}/{len(under_rows)}] "))
        await asyncio.gather(*tasks)

    print(f"Finished. {e_cout} files moved to external storage, {i_count} files moved to internal storage.")

@global_entrance()
async def vacuum(index: bool = False, blobs: bool = False):

    # check if any file in the Large Blob directory is not in the database
    # the reverse operation is not necessary, because by design, the database should be the source of truth...
    # we allow un-referenced files in the Large Blob directory on failure, but not the other way around (unless manually deleted)
    async def ensure_external_consistency(f_id: str):
        @barriered
        async def fn():
            async with unique_cursor() as c:
                cursor = await c.execute("SELECT file_id FROM fmeta WHERE file_id = ?", (f_id,))
                if not await cursor.fetchone():
                    print(f"File {f_id} not found in database, removing from external storage.")
                    await aiofiles.os.remove(f)
        await asyncio.create_task(fn())

    # create a temporary index to speed up the process...
    with indicator("Ensuring external storage consistancy"):
        async with transaction() as c:
            await c.execute("CREATE INDEX IF NOT EXISTS fmeta_file_id ON fmeta (file_id)")
        for i, f in enumerate(LARGE_BLOB_DIR.iterdir()):
            f_id = f.name
            await ensure_external_consistency(f_id)
            if (i+1) % 100_000 == 0:
                print(f"Checked {i//1000}k files in external storage.")
        async with transaction() as c:
            await c.execute("DROP INDEX IF EXISTS fmeta_file_id")

    async with unique_cursor(is_write=True) as c:

        if index:
            with indicator("VACUUM-index"):
                await c.execute("VACUUM main")
        if blobs:
            with indicator("VACUUM-blobs"):
                await c.execute("VACUUM blobs")
            
def main():
    global sem
    parser = argparse.ArgumentParser(description="Balance the storage by ensuring that large file thresholds are met.")
    parser.add_argument("-j", "--jobs", type=int, default=2, help="Number of concurrent jobs")
    parser.add_argument("-b", "--batch-size", type=int, default=10000, help="Batch size for processing files")
    parser.add_argument("--vacuum", action="store_true", help="Run VACUUM only on index.db after balancing")
    parser.add_argument("--vacuum-all", action="store_true", help="Run VACUUM on both index.db and blobs.db after balancing")
    args = parser.parse_args()
    sem = Semaphore(args.jobs)
    with indicator("Balancing"):
        asyncio.run(_main(args.batch_size))
    if args.vacuum or args.vacuum_all:
        asyncio.run(vacuum(index=args.vacuum or args.vacuum_all, blobs=args.vacuum_all))

if __name__ == '__main__':
    main()