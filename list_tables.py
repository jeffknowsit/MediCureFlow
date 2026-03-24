import sqlite3
import os

db_path = 'd:\\hospitalmanagment\\wellcarepluscure\\db.sqlite3'
conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = [r[0] for r in cur.fetchall()]
with open('tables_detailed.txt', 'w') as f:
    for table in sorted(tables):
        f.write(f"Table: {table}\n")
        cur.execute(f"PRAGMA table_info({table});")
        columns = cur.fetchall()
        for col in columns:
            f.write(f"  - {col[1]} ({col[2]})\n")
        f.write("\n")
conn.close()
print("Detailed table info written to tables_detailed.txt")
