"""Replicate the container's tool-module exec exactly, without importing open_webui.env
(which requires the app's env vars). Mirrors open_webui/utils/plugin.py:
  replace_imports() -> 4 string replacements
  exec(content, module.__dict__) -> then the loader checks for a 'Tools' class
"""
import re
import sys
import types

content = open("/tmp/movieglu_tool_test.py", encoding="utf-8").read()

# --- replace_imports (verbatim from open_webui/utils/plugin.py) ---
replacements = {
    "from utils": "from open_webui.utils",
    "from apps": "from open_webui.apps",
    "from main": "from open_webui.main",
    "from config": "from open_webui.config",
}
for old, new in replacements.items():
    content = content.replace(old, new)

# --- frontmatter extraction (same regex as the loader) ---
fm = {}
lines = content.splitlines()
if lines and lines[0].strip() == '"""':
    pat = re.compile(r"^\s*([a-z_]+):\s*(.*)\s*$", re.IGNORECASE)
    started = False
    ended = False
    for line in lines[1:]:
        if '"""' in line:
            if started:
                ended = True
                break
        if started and not ended:
            m = pat.match(line)
            if m:
                fm[m.group(1).strip()] = m.group(2).strip()
print("frontmatter:", fm)

# --- exec, exactly like load_tool_module_by_id ---
module_name = "tool_movieglu_test"
module = types.ModuleType(module_name)
sys.modules[module_name] = module
module.__dict__["__file__"] = "/tmp/movieglu_tool_test.py"

try:
    exec(content, module.__dict__)
    print("EXEC OK")
    print("  hasattr(module, 'Tools'):", hasattr(module, "Tools"))
    print("  hasattr(module, 'Tool'):", hasattr(module, "Tool"))
    cls = getattr(module, "Tools", None) or getattr(module, "Tool", None)
    if cls:
        try:
            inst = cls()  # loader instantiates with NO args
            print("  instantiation OK:", type(inst).__name__)
        except Exception as e:
            print(f"  instantiation FAILED: {type(e).__name__}: {e}")
except Exception as e:
    print(f"EXEC FAILED: {type(e).__name__}: {e}")
