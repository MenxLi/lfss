"""
Vacuum the database and external storage to ensure that the storage is consistent and minimal.
"""

from lfss.src.config import LARGE_BLOB_DIR
import argparse, time
from functools import wraps
from asyncio import Semaphore
import aiofiles, asyncio
import aiofiles.os
from contextlib import contextmanager
from lfss.src.database import transaction, unique_cursor
from lfss.src.stat import RequestDB
from lfss.src.utils import now_stamp
from lfss.src.connection_pool import global_entrance

sem: Semaphore

@contextmanager
def indicator(name: str):
    print(f"\033[1;33mRunning {name}... \033[0m")
    s = time.time()
    yield
    print(f"{name} took {time.time() - s:.2f} seconds.")

def barriered(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        global sem
        async with sem:
            return await func(*args, **kwargs)
    return wrapper

@global_entrance()
async def vacuum_main(index: bool = False, blobs: bool = False):

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
    with indicator("Clearing un-referenced files in external storage"):
        async with transaction() as c:
            await c.execute("CREATE INDEX IF NOT EXISTS fmeta_file_id ON fmeta (file_id)")
        for i, f in enumerate(LARGE_BLOB_DIR.iterdir()):
            f_id = f.name
            await ensure_external_consistency(f_id)
            if (i+1) % 1_000 == 0:
                print(f"Checked {(i+1)//1000}k files in external storage.", end='\r')
        async with transaction() as c:
            await c.execute("DROP INDEX IF EXISTS fmeta_file_id")

    async with unique_cursor(is_write=True) as c:
        if index:
            with indicator("VACUUM-index"):
                await c.execute("VACUUM main")
        if blobs:
            with indicator("VACUUM-blobs"):
                await c.execute("VACUUM blobs")

async def vacuum_requests():
    with indicator("VACUUM-requests"):
        async with RequestDB().connect() as req_db:
            await req_db.shrink(max_rows=1_000_000, time_before=now_stamp() - 7*24*60*60)
            await req_db.conn.execute("VACUUM")
            
def main():
    global sem
    parser = argparse.ArgumentParser(description="Balance the storage by ensuring that large file thresholds are met.")
    parser.add_argument("-j", "--jobs", type=int, default=2, help="Number of concurrent jobs")
    parser.add_argument("-m", "--metadata", action="store_true", help="Vacuum metadata")
    parser.add_argument("-d", "--data", action="store_true", help="Vacuum blobs")
    parser.add_argument("-r", "--requests", action="store_true", help="Vacuum request logs to only keep at most recent 1M rows in 7 days")
    args = parser.parse_args()
    sem = Semaphore(args.jobs)
    asyncio.run(vacuum_main(index=args.metadata, blobs=args.data))

    if args.requests:
        asyncio.run(vacuum_requests())

if __name__ == '__main__':
    main()