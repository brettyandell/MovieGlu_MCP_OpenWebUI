import re
import sqlite3

row = sqlite3.connect("/app/backend/data/webui.db").execute(
    "select content from tool where id = 'reddit_tool'"
).fetchone()
content = row[0]

# Find the class + __init__ region
m = re.search(r"class Tools:.*?def __init__\(.*?\n(?=\n    def )", content, re.DOTALL)
print("==== __init__ region ====")
print(m.group(0)[:1200] if m else "not found")

print("\n==== first 2 public method signatures ====")
for mm in re.finditer(r"\n    def (\w+)\(", content):
    name = mm.group(1)
    if not name.startswith("_"):
        print(content[mm.start(): mm.start() + 200].splitlines()[:6])
        print("---")
        break

# confirm function_tool absence across the whole package
import subprocess
out = subprocess.run(
    ["grep", "-rl", "def function_tool", "/app/backend/open_webui/"],
    capture_output=True, text=True,
)
print("\n'function_tool' defs in package:", out.stdout.strip() or "NONE")

# How does the loader know it's a tool? show the Valves usage in this tool
print("\n==== 'Valves' mentions in reddit_tool ====")
for mm in re.finditer(r".*Valves.*", content):
    print(mm.group(0).strip()[:140])
    break
