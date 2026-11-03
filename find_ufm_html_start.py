import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

with open("c:/Users/Admin/Documents/HUIT/vaa/ufm/web_app.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

print(f"Total lines in vaa/ufm/web_app.py: {len(lines)}")
# Find where the HTML template starts
for idx, line in enumerate(lines[:600]):
    if '"""<!DOCTYPE html>' in line or '<!DOCTYPE html>' in line:
        print(f"HTML starts at line {idx+1}")
        break
