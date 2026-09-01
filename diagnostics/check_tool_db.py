"""Inspect the OpenWebUI container DB for MovieGlu tool traces. Run inside the container."""
import sqlite3
import json

c = sqlite3.connect("/app/backend/data/webui.db")

hits = c.execute(
    "select id, name from tool where lower(name) like '%movie%' or lower(name) like '%glu%' or lower(content) like '%movieglu%' or lower(content) like '%movieglu%'"
).fetchall()
print("movie/glu tool rows:", hits or "NONE")

tables = [
    r[0]
    for r in c.execute(
        """select name from sqlite_master where type='table'
           and (lower(name) like '%tool%' or lower(name) like '%server%'
                or lower(name) like '%connection%' or lower(name) like '%mcp%')"""
    ).fetchall()
]
print("related tables:", tables)

for t in tables:
    if t == "tool":
        continue
    try:
        cols = [r[1] for r in c.execute(f"PRAGMA table_info({t})").fetchall()]
        rows = c.execute(f"select * from {t}").fetchall()
        for row in rows:
            rowd = dict(zip(cols, row))
            compact = json.dumps(rowd, default=str)
            if "glu" in compact.lower() or "movie" in compact.lower():
                print(f"MATCH in {t}:", compact[:800])
        print(f"{t}: {len(rows)} rows, cols={cols}")
    except Exception as e:
        print(f"{t}: error {e}")

# recent tool rows (any) to see timestamps
try:
    cols = [r[1] for r in c.execute("PRAGMA table_info(tool)").fetchall()]
    print("tool table cols:", cols)
except Exception as e:
    print("pragma tool:", e)
