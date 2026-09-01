import re
import sqlite3

db = sqlite3.connect("/app/backend/data/webui.db")
content = db.execute("select content from tool where id = 'ltx_generate_video'").fetchone()[0]

i = content.find("def __init__")
print("==== __init__ (raw) ====")
print(content[i : i + 500])

# first public method with signature + docstring
print("\n==== first public tool method ====")
m = re.search(r"\n    def (?!_)(\w+)\(.*?\n(?:.*?\n){0,12}?(?=\n    def |\nclass |\Z)", content, re.DOTALL)
if m:
    print(m.group(0)[:900])

# how methods reference valves
print("\n==== 'self.valves' / 'valves' usage (first 5) ====")
for mm in list(re.finditer(r".*valves.*", content))[:8]:
    print(mm.group(0).strip()[:120])
