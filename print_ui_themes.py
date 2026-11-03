import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

with open("c:/Users/Admin/Documents/HUIT/web_app.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

print("--- BOT 1 HEADER & NAV (lines 1350-1430) ---")
for j in range(1350, 1430):
    print(f"{j+1}: {lines[j]}", end="")

print("\n--- BOT 3 HEADER & NAV (lines 4540-4630) ---")
for j in range(4540, 4630):
    print(f"{j+1}: {lines[j]}", end="")
