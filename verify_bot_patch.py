import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

with open("c:/Users/Admin/Documents/HUIT/bot.py", "r", encoding="utf-8") as f:
    text = f.read()

print("Contains Đang quét:", "Đang quét: {page_name}" in text)
print("Contains Hoàn thành:", "Hoàn thành: {page_name}" in text)
print("Contains Chu kỳ #:", "🎉 Chu kỳ #{cycle}" in text)
