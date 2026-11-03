with open("c:/Users/Admin/Documents/HUIT/web_app.py", "r", encoding="utf-8") as f:
    text = f.read()

import re
# Replace in all triple quotes:
text = text.replace(r'cleanMsg.replace(/^(\S+\s*)?\[\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\]\s*/', r'cleanMsg.replace(/^(\\S+\\s*)?\\[\\d{4}-\\d{2}-\\d{2}\\s+\\d{2}:\\d{2}:\\d{2}\\]\\s*/')
text = text.replace(r'cleanMsg.replace(/^\[\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\]\s*/', r'cleanMsg.replace(/^\\[\\d{4}-\\d{2}-\\d{2}\\s+\\d{2}:\\d{2}:\\d{2}\\]\\s*/')

with open("c:/Users/Admin/Documents/HUIT/web_app.py", "w", encoding="utf-8") as f:
    f.write(text)
