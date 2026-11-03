import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

with open("c:/Users/Admin/Documents/HUIT/ufm_bot.py", "r", encoding="utf-8") as f:
    text1 = f.read()
print("=== ROOT ufm_bot.py ===")
print(text1[:1000])

with open("c:/Users/Admin/Documents/HUIT/vaa/ufm/bot.py", "r", encoding="utf-8") as f:
    text2 = f.read()
print("\n=== vaa/ufm/bot.py ===")
print(text2[:1000])
