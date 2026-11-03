import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

with open("c:/Users/Admin/Documents/HUIT/web_app.py", "r", encoding="utf-8") as f:
    text = f.read()

# Fix regex escapes in js inside python f-strings
text = text.replace(r"(\S+\s*)?\[\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\]\s*", r"(\\S+\\s*)?\\[\\d{4}-\\d{2}-\\d{2}\\s+\\d{2}:\\d{2}:\\d{2}\\]\\s*")
text = text.replace(r"\[\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\]\s*", r"\\[\\d{4}-\\d{2}-\\d{2}\\s+\\d{2}:\\d{2}:\\d{2}\\]\\s*")

with open("c:/Users/Admin/Documents/HUIT/web_app.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Cleaned regex warnings in web_app.py!")
