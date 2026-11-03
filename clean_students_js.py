import re

def clean_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()

    # 1. Remove Auto-Apply button on activity card
    btn_pattern = r'<div class="flex items-center gap-1\.5">\s*<button onclick="quickBatchRegister\([^)]*\)".*?</button>\s*</div>'
    text = re.sub(btn_pattern, '', text, flags=re.DOTALL)

    # 2. Remove entire STUDENTS TAB JS functions (fetchStudents, quickBatchRegister, etc.)
    js_pattern = r'// ================= STUDENTS TAB =================.*?// ================= TERMINAL CONSOLE LOG'
    text = re.sub(js_pattern, '// ================= TERMINAL CONSOLE LOG', text, flags=re.DOTALL)

    # 3. Remove let allStudents = [];
    text = text.replace('let allStudents = [];\n', '')
    text = text.replace('let allStudents = [];', '')

    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)
    print(f"Cleaned {path}")

clean_file('c:/Users/Admin/Documents/HUIT/vaa/ufm/templates/index.html')
clean_file('c:/Users/Admin/Documents/HUIT/generate_ufm_html.py')
