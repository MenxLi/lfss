from typing import Optional
import argparse
import rich.console
import logging
import sqlite3
from lfss.eng.log import eval_logline

console = rich.console.Console()
def levelstr2int(levelstr: str) -> int:
    import sys
    if sys.version_info < (3, 11):
        return logging.getLevelName(levelstr.upper())
    else:
        return logging.getLevelNamesMapping()[levelstr.upper()]

def view(
    db_file: str, 
    level: Optional[str] = None, 
    offset: int = 0,
    limit: int = 1000
    ):
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    if level is None:
        cursor.execute("SELECT * FROM log ORDER BY created DESC LIMIT ? OFFSET ?", (limit, offset))
    else:
        level_int = levelstr2int(level)
        cursor.execute("SELECT * FROM log WHERE level >= ? ORDER BY created DESC LIMIT ? OFFSET ?", (level_int, limit, offset))
    levelname_color = {
        'DEBUG': 'blue',
        'INFO': 'green',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'bold red', 
        'FATAL': 'bold red'
    }
    for row in cursor.fetchall():
        log = eval_logline(row)
        console.print(f"{log.created} [{levelname_color[log.levelname]}][{log.levelname}] [default]{log.message}")
    conn.close()

def trim(db_file: str, keep: int  = 1000, level: Optional[str] = None):
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    if level is None:
        cursor.execute("DELETE FROM log WHERE id NOT IN (SELECT id FROM log ORDER BY created DESC LIMIT ?)", (keep,))
    else:
        cursor.execute("DELETE FROM log WHERE levelname = ? and id NOT IN (SELECT id FROM log WHERE levelname = ? ORDER BY created DESC LIMIT ?)", (level.upper(), level.upper(), keep))
    conn.commit()
    conn.execute("VACUUM")
    conn.close()

def main():
    parser = argparse.ArgumentParser(description="Log operations utility")
    subparsers = parser.add_subparsers(title='subcommands', description='valid subcommands', help='additional help')

    parser_show = subparsers.add_parser('view', help='Show logs')
    parser_show.add_argument('db_file', type=str, help='Database file path')
    parser_show.add_argument('-l', '--level', type=str, required=False, help='Log level')
    parser_show.add_argument('--offset', type=int, default=0, help='Starting offset')
    parser_show.add_argument('--limit', type=int, default=1000, help='Maximum number of entries to display')
    parser_show.set_defaults(func=view)

    parser_trim = subparsers.add_parser('trim', help='Trim logs')
    parser_trim.add_argument('db_file', type=str, help='Database file path')
    parser_trim.add_argument('-l', '--level', type=str, required=False, help='Log level')
    parser_trim.add_argument('--keep', type=int, default=1000, help='Number of entries to keep')
    parser_trim.set_defaults(func=trim)

    args = parser.parse_args()
    if hasattr(args, 'func'):
        kwargs = vars(args)
        func = kwargs.pop('func')
        func(**kwargs)

if __name__ == '__main__':
    main()