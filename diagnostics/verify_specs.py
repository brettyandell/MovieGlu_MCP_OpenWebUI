"""Full verification: exec the tool exactly like the loader, then run the REAL
get_tool_specs from open_webui.utils.tools (requires WEBUI_SECRET_KEY set)."""
import re
import sys
import types

content = open("/tmp/movieglu_tool_test.py", encoding="utf-8").read()

replacements = {
    "from utils": "from open_webui.utils",
    "from apps": "from open_webui.apps",
    "from main": "from open_webui.main",
    "from config": "from open_webui.config",
}
for old, new in replacements.items():
    content = content.replace(old, new)

module_name = "tool_movieglu_test"
module = types.ModuleType(module_name)
sys.modules[module_name] = module
module.__dict__["__file__"] = "/tmp/movieglu_tool_test.py"

try:
    exec(content, module.__dict__)
except Exception as e:
    print(f"EXEC FAILED: {type(e).__name__}: {e}")
    sys.exit(1)

print("EXEC OK")
print("hasattr Tools:", hasattr(module, "Tools"))

inst = module.Tools()
print("instantiated:", type(inst).__name__)

from open_webui.utils.tools import get_functions_from_tool, get_tool_specs

funcs = get_functions_from_tool(inst)
print("detected tool functions:", [f.__name__ for f in funcs])
specs = get_tool_specs(inst)
print("spec names:", [s["name"] for s in specs])
print("spec count:", len(specs))

# sample one spec
import json
print("\nsample spec (movies_now_showing):")
print(json.dumps(specs[0], indent=2)[:600])
