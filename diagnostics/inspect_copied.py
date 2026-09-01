c = open("/tmp/movieglu_tool_test.py", encoding="utf-8").read()
lines = c.splitlines()
print("line0:", repr(lines[0]))
print("line1:", repr(lines[1]))
print("CRLF:", "\r\n" in c)

import sqlite3
row = sqlite3.connect("/app/backend/data/webui.db").execute(
    "select content from tool where id = 'reddit_tool'"
).fetchone()
if row:
    content = row[0]
    print("==== reddit_tool head (first 1600 chars) ====")
    print(content[:1600])
    print("==== class names found ====")
    for name in ("class Tool:", "class Tools:", "function_tool", "def __init__"):
        print(name, "->", name in content)
else:
    print("reddit_tool NOT FOUND")
