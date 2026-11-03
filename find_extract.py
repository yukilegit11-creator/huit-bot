
import os
for root, dirs, files in os.walk('/usr/local/lib/python3.10/dist-packages/fbchat_muqit'):
    for f in files:
        if f.endswith('.py'):
            fp = os.path.join(root, f)
            with open(fp, 'r') as code_f:
                for idx, line in enumerate(code_f):
                    if 'extract_tokens_from_html' in line:
                        print(f"{fp}:{idx+1} {line.strip()}")
