import re
import sqlite3

db = sqlite3.connect("/app/backend/data/webui.db")
rows = db.execute("select id, content from tool").fetchall()

print(f"{'id':40} {'classTools':10} {'classTool':9} {'Valves':7} {'funcTool':9} {'__init__':8}")
for tid, content in rows:
    has = {
        "classTools": "class Tools" in content,
        "classTool": "class Tool:" in content,
        "Valves": "Valves" in content,
        "funcTool": "function_tool" in content,
        "__init__": "def __init__" in content,
    }
    print(f"{tid:40} " + " ".join(f"{str(v):10}" for v in has.values()))

# Find one with Valves, print its Valves class + __init__
print("\n==== Valves example (first tool that has Valves) ====")
for tid, content in rows:
    if "Valves" in content and "class " in content:
        m = re.search(r"class Valves.*?(?=\n    def |\nclass |\ndef )", content, re.DOTALL)
        print(f"[{tid}] Valves class:\n", (m.group(0)[:900] if m else "n/a"))
        m2 = re.search(r"def __init__\(self.*?\n(.*?)(?=\n    def |\n    class )", content, re.DOTALL)
        print(f"[{tid}] __init__:\n", (m2.group(0)[:600] if m2 else "n/a"))
        break
