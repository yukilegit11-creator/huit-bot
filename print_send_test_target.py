import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

with open("c:/Users/Admin/Documents/HUIT/vaa/ufm/zalo_sender.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for idx, line in enumerate(lines):
    if "def send_test_message_to_target" in line:
        start = max(0, idx - 5)
        end = min(len(lines), idx + 50)
        print(f"=== Lines {start+1} to {end} ===")
        for j in range(start, end):
            print(f"{j+1}: {lines[j]}", end="")
        break
