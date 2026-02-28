import aiosqlite
from typing import Literal
from .error import InvalidInputError
from .datatype import HttpTraffic, HttpRecord
from .config import DATA_HOME
from .utils import debounce_async

class RequestDB:
    def __init__(self):
        self.db_path = DATA_HOME / 'requests.db'
        self.http_logs: list[tuple[float, HttpRecord]] = []
        self.minutes_cache: dict[int, HttpTraffic] = {}
        self.hours_cache: dict[int, HttpTraffic] = {}
        self.days_cache: dict[int, HttpTraffic] = {}
    
    async def get_traffics(
        self, resolution: Literal['minute', 'hour', 'day'], time: int, count: int = 1
        ) -> list[HttpTraffic]:
        if resolution == 'minute':
            interval = 60
        elif resolution == 'hour':
            interval = 3600
        elif resolution == 'day':
            interval = 86400
        else:
            raise InvalidInputError("Resolution must be 'minute', 'hour', or 'day'.")

        time = int(time // interval) * interval
        def row2traffic(row) -> HttpTraffic:
            if not row:
                return HttpTraffic.zeros()
            assert len(row) == 9, f"Expected 9 columns in the result, got {len(row)}"
            return HttpTraffic(
                code_100_count=row[0],
                code_200_count=row[1],
                code_300_count=row[2],
                code_400_count=row[3],
                code_500_count=row[4],
                total_count=row[5],
                bytes_in=row[6],
                bytes_out=row[7],
                response_time_sum=row[8]
            )

        res = []
        async with aiosqlite.connect(self.db_path) as conn:
            for i in range(count):
                cursor = await conn.execute(f'''
                    SELECT 
                        code_100_count, code_200_count, code_300_count, code_400_count, code_500_count, 
                        total_count, bytes_in, bytes_out, response_time_sum
                    FROM requests_count_{resolution}
                    WHERE time = ?
                ''', (time + i * interval, ))
                row = await cursor.fetchone()
                res.append(row2traffic(row))
        return res

    async def init(self):
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    time FLOAT DEFAULT (strftime('%s', 'now')),
                    method TEXT,
                    path TEXT,
                    headers TEXT,
                    query TEXT,
                    client TEXT,
                    duration REAL, 
                    request_size INTEGER, 
                    response_size INTEGER, 
                    status INTEGER
                )
            ''')
            for unit in ['minute', 'hour', 'day']:
                await conn.execute(f'''
                    CREATE TABLE IF NOT EXISTS requests_count_{unit} (
                        time INTEGER PRIMARY KEY, 
                        code_100_count INTEGER DEFAULT 0,
                        code_200_count INTEGER DEFAULT 0,
                        code_300_count INTEGER DEFAULT 0,
                        code_400_count INTEGER DEFAULT 0,
                        code_500_count INTEGER DEFAULT 0, 
                        total_count INTEGER DEFAULT 0,
                        bytes_in INTEGER DEFAULT 0,
                        bytes_out INTEGER DEFAULT 0, 
                        response_time_sum REAL DEFAULT 0
                    )
                ''')
            await conn.commit()
        return self
    
    async def flush(self):
        if self.http_logs:
            async with aiosqlite.connect(self.db_path) as conn:
                await conn.execute('BEGIN')
                for time, record in self.http_logs:
                    await conn.execute('''
                        INSERT INTO requests (
                            time, method, path, headers, query, client, duration, request_size, response_size, status
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        time, record.method, record.path, record.headers, record.query, record.client, 
                        record.duration, record.request_size, record.response_size, record.status
                    ))
                await conn.commit()
            self.http_logs.clear()

        async def _flush_metric(conn: aiosqlite.Connection, unit: str, cache: dict[int, HttpTraffic]):
            for time, metric in cache.items():
                await conn.execute(f'''
                    INSERT INTO requests_count_{unit} (
                        time, code_100_count, code_200_count, code_300_count, code_400_count, code_500_count, 
                    total_count, bytes_in, bytes_out, response_time_sum
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(time) DO UPDATE SET 
                    code_100_count = code_100_count + excluded.code_100_count,
                    code_200_count = code_200_count + excluded.code_200_count,
                    code_300_count = code_300_count + excluded.code_300_count,
                    code_400_count = code_400_count + excluded.code_400_count,
                    code_500_count = code_500_count + excluded.code_500_count,
                    total_count = total_count + excluded.total_count,
                    bytes_in = bytes_in + excluded.bytes_in,
                    bytes_out = bytes_out + excluded.bytes_out,
                    response_time_sum = response_time_sum + excluded.response_time_sum
            ''', (
                time, metric.code_100_count, metric.code_200_count, metric.code_300_count, 
                metric.code_400_count, metric.code_500_count, metric.total_count, 
                metric.bytes_in, metric.bytes_out, metric.response_time_sum
            ))
        
        if self.minutes_cache or self.hours_cache:
            async with aiosqlite.connect(self.db_path) as conn:
                await _flush_metric(conn, 'minute', self.minutes_cache)
                await _flush_metric(conn, 'hour', self.hours_cache)
                await _flush_metric(conn, 'day', self.days_cache)
                await conn.commit()
            self.minutes_cache.clear()
            self.hours_cache.clear()
            self.days_cache.clear()
    
    @debounce_async(delay=1)
    async def ensure_flush_once(self):
        await self.flush()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc, tb):
        await self.flush()
    
    async def log_request(
        self, time: float, 
        r: HttpRecord,
        ):
        self.http_logs.append((time, r))
        minute = int(time // 60) * 60
        hour = int(time // 3600) * 3600
        day = int(time // 86400) * 86400
        self.minutes_cache.setdefault(minute, HttpTraffic.zeros()).add_inplace(r)
        self.hours_cache.setdefault(hour, HttpTraffic.zeros()).add_inplace(r)
        self.days_cache.setdefault(day, HttpTraffic.zeros()).add_inplace(r)

    async def shrink(self, max_rows: int = 1_000_000, time_before: float = 0, vacuum: bool = True):
        async with aiosqlite.connect(self.db_path) as conn:

            async def shirnk_table_by_time(table_name: str):
                if time_before > 0:
                    await conn.execute(f'''
                        DELETE FROM {table_name} WHERE time < ?
                    ''', (int(time_before),))

            await shirnk_table_by_time('requests')
            await shirnk_table_by_time('requests_count_minute')
            await shirnk_table_by_time('requests_count_hour')
            await shirnk_table_by_time('requests_count_day')

            await conn.execute(f'''
                DELETE FROM requests WHERE id NOT IN (
                    SELECT id FROM requests ORDER BY time DESC LIMIT ?
                )
            ''', (max_rows,))

            await conn.commit()

        if vacuum:
            async with aiosqlite.connect(self.db_path) as conn:
                await conn.execute("VACUUM")
        