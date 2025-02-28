"""
Vacuum the database and external storage to ensure that the storage is consistent and minimal.
"""

from lfss.eng.config import LARGE_BLOB_DIR, THUMB_DB, LOG_DIR
import argparse, time, itertools
from functools import wraps
from asyncio import Semaphore
import aiosqlite
import aiofiles, asyncio
import aiofiles.os
from contextlib import contextmanager
from lfss.eng.database import transaction, unique_cursor
from lfss.svc.request_log import RequestDB
from lfss.eng.utils import now_stamp
from lfss.eng.connection_pool import global_entrance
from lfss.cli.log import trim

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
async def vacuum_main(index: bool = False, blobs: bool = False, thumbs: bool = False, logs: bool = False, vacuum_all: bool = False):

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
        try:
            async with transaction() as c:
                await c.execute("CREATE INDEX IF NOT EXISTS fmeta_file_id ON fmeta (file_id)")
            for i, f in enumerate(LARGE_BLOB_DIR.iterdir()):
                f_id = f.name
                await ensure_external_consistency(f_id)
                if (i+1) % 1_000 == 0:
                    print(f"Checked {(i+1)//1000}k files in external storage.", end='\r')
        finally:
            async with transaction() as c:
                await c.execute("DROP INDEX IF EXISTS fmeta_file_id")

    if index or vacuum_all:
        with indicator("VACUUM-index"):
            async with transaction() as c:
                await c.execute("DELETE FROM dupcount WHERE count = 0")
            async with unique_cursor(is_write=True) as c:
                await c.execute("VACUUM main")
    if blobs or vacuum_all:
        with indicator("VACUUM-blobs"):
            async with unique_cursor(is_write=True) as c:
                await c.execute("VACUUM blobs")
    
    if logs or vacuum_all:
        with indicator("VACUUM-logs"):
            for log_file in LOG_DIR.glob("*.log.db"):
                trim(str(log_file), keep=10_000)
    
    if thumbs or vacuum_all:
        try:
            async with transaction() as c:
                await c.execute("CREATE INDEX IF NOT EXISTS fmeta_file_id ON fmeta (file_id)")
            with indicator("VACUUM-thumbs"):
                if not THUMB_DB.exists():
                    raise FileNotFoundError("Thumbnail database not found.")
                async with unique_cursor() as db_c:
                    async with aiosqlite.connect(THUMB_DB) as t_conn:
                        batch_size = 10_000
                        for batch_count in itertools.count(start=0):
                            exceeded_rows = list(await (await t_conn.execute(
                                "SELECT file_id FROM thumbs LIMIT ? OFFSET ?",
                                (batch_size, batch_size * batch_count)
                            )).fetchall())
                            if not exceeded_rows:
                                break
                            batch_ids = [row[0] for row in exceeded_rows]
                            for f_id in batch_ids:
                                cursor = await db_c.execute("SELECT file_id FROM fmeta WHERE file_id = ?", (f_id,))
                                if not await cursor.fetchone():
                                    print(f"Thumbnail {f_id} not found in database, removing from thumb cache.")
                                    await t_conn.execute("DELETE FROM thumbs WHERE file_id = ?", (f_id,))
                            print(f"Checked {batch_count+1} batches of {batch_size} thumbnails.")

                        await t_conn.commit()
                        await t_conn.execute("VACUUM")
        except FileNotFoundError as e:
            if "Thumbnail database not found." in str(e):
                print("Thumbnail database not found, skipping.")
            
        finally:
            async with transaction() as c:
                await c.execute("DROP INDEX IF EXISTS fmeta_file_id")

async def vacuum_requests():
    with indicator("VACUUM-requests"):
        async with RequestDB().connect() as req_db:
            await req_db.shrink(max_rows=1_000_000, time_before=now_stamp() - 7*24*60*60)
            await req_db.conn.execute("VACUUM")
            
def main():
    global sem
    parser = argparse.ArgumentParser(description="Balance the storage by ensuring that large file thresholds are met.")
    parser.add_argument("--all", action="store_true", help="Vacuum all")
    parser.add_argument("-j", "--jobs", type=int, default=2, help="Number of concurrent jobs")
    parser.add_argument("-m", "--metadata", action="store_true", help="Vacuum metadata")
    parser.add_argument("-d", "--data", action="store_true", help="Vacuum blobs")
    parser.add_argument("-t", "--thumb", action="store_true", help="Vacuum thumbnails")
    parser.add_argument("-r", "--requests", action="store_true", help="Vacuum request logs to only keep at most recent 1M rows in 7 days")
    parser.add_argument("-l", "--logs", action="store_true", help="Trim log to keep at most recent 10k rows for each category")
    args = parser.parse_args()
    sem = Semaphore(args.jobs)
    asyncio.run(vacuum_main(index=args.metadata, blobs=args.data, thumbs=args.thumb, logs = args.logs, vacuum_all=args.all))

    if args.requests or args.all:
        asyncio.run(vacuum_requests())

if __name__ == '__main__':
    main()