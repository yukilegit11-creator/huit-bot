import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

with open("c:/Users/Admin/Documents/HUIT/run_all.py", "r", encoding="utf-8") as f:
    text = f.read()

print("Contents of run_all.py:")
print(text)
