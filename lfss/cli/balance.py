"""
Balance the storage by ensuring that large file thresholds are met.
"""

from lfss.src.config import DATA_HOME, LARGE_BLOB_DIR, LARGE_FILE_BYTES
import argparse, time
from functools import wraps
from asyncio import Semaphore
import aiosqlite, aiofiles, asyncio

sem = Semaphore(1)
db_file = DATA_HOME / 'lfss.db'

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
    async with aiosqlite.connect(db_file, timeout = 60) as c:
        async with c.execute( "SELECT data FROM fdata WHERE file_id = ?", (f_id,)) as cursor:
            blob_row = await cursor.fetchone()
            if blob_row is None:
                print(f"{flag}File {f_id} not found in fdata")
                return
        await c.execute("BEGIN")
        blob: bytes = blob_row[0]
        try:
            async with aiofiles.open(LARGE_BLOB_DIR / f_id, 'wb') as f:
                await f.write(blob)
            await c.execute( "UPDATE fmeta SET external = 1 WHERE file_id = ?", (f_id,))
            await c.execute( "DELETE FROM fdata WHERE file_id = ?", (f_id,))
            await c.commit()
            print(f"{flag}Moved {f_id} to external storage")
        except Exception as e:
            await c.rollback()
            print(f"{flag}Error moving {f_id}: {e}")

            if isinstance(e, KeyboardInterrupt):
                raise e

@barriered
async def move_to_internal(f_id: str, flag: str = ''):
    async with aiosqlite.connect(db_file, timeout = 60) as c:
        if not (LARGE_BLOB_DIR / f_id).exists():
            print(f"{flag}File {f_id} not found in external storage")
            return
        async with aiofiles.open(LARGE_BLOB_DIR / f_id, 'rb') as f:
            blob = await f.read()

        await c.execute("BEGIN")
        try:
            await c.execute("INSERT INTO fdata (file_id, data) VALUES (?, ?)", (f_id, blob))
            await c.execute("UPDATE fmeta SET external = 0 WHERE file_id = ?", (f_id,))
            await c.commit()
            (LARGE_BLOB_DIR / f_id).unlink(missing_ok=True)
            print(f"{flag}Moved {f_id} to internal storage")
        except Exception as e:
            await c.rollback()
            print(f"{flag}Error moving {f_id}: {e}")
            if isinstance(e, KeyboardInterrupt):
                raise e


async def _main():

    tasks = []
    start_time = time.time()
    async with aiosqlite.connect(db_file) as conn:
        exceeded_rows = await (await conn.execute( 
            "SELECT file_id FROM fmeta WHERE file_size > ? AND external = 0",
            (LARGE_FILE_BYTES,)
        )).fetchall()
        
    for i in range(0, len(exceeded_rows)):
        row = exceeded_rows[i]
        f_id = row[0]
        tasks.append(move_to_external(f_id, flag=f"[e-{i+1}/{len(exceeded_rows)}] "))

    async with aiosqlite.connect(db_file) as conn:
        under_rows = await (await conn.execute(
            "SELECT file_id, file_size, external FROM fmeta WHERE file_size <= ? AND external = 1",
            (LARGE_FILE_BYTES,)
        )).fetchall()

    for i in range(0, len(under_rows)):
        row = under_rows[i]
        f_id = row[0]
        tasks.append(move_to_internal(f_id, flag=f"[i-{i+1}/{len(under_rows)}] "))
        
    await asyncio.gather(*tasks)
    end_time = time.time()
    print(f"Balancing complete, took {end_time - start_time:.2f} seconds. "
          f"{len(exceeded_rows)} files moved to external storage, {len(under_rows)} files moved to internal storage.")
            
def main():
    global sem
    parser = argparse.ArgumentParser(description="Balance the storage by ensuring that large file thresholds are met.")
    parser.add_argument("-j", "--jobs", type=int, default=2, help="Number of concurrent jobs")
    args = parser.parse_args()
    sem = Semaphore(args.jobs)
    asyncio.run(_main())

if __name__ == '__main__':
    main()