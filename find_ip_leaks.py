import sys, os
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

root_dir = "c:/Users/Admin/Documents/HUIT"
for r, dirs, files in os.walk(root_dir):
    for f in files:
        if f.endswith(".py") or f.endswith(".json") or f.endswith(".html"):
            p = os.path.join(r, f)
            try:
                with open(p, "r", encoding="utf-8", errors="ignore") as fp:
                    lines = fp.readlines()
                    for idx, line in enumerate(lines):
                        if "180.93.125.40" in line and not "HOST" in line and not "urlopen" in line and not "fetch" in line:
                            print(f"{p}:{idx+1} -> {line.strip()}")
            except Exception:
                pass
