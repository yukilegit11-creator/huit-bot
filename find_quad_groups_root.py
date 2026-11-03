import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

with open("c:/Users/Admin/Documents/HUIT/web_app.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for idx, line in enumerate(lines):
    if "api_quad_target_groups" in line or "/api/zalo/quad-target-groups" in line:
        start = max(0, idx - 5)
        end = min(len(lines), idx + 35)
        print(f"=== Root lines {start+1} to {end} ===")
        for j in range(start, end):
            print(f"{j+1}: {lines[j]}", end="")
        break
