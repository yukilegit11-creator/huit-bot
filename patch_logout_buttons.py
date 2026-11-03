import re

# 1. Update web_app.py
p1 = r'c:\Users\Admin\Documents\HUIT\web_app.py'
with open(p1, 'r', encoding='utf-8') as f:
    text1 = f.read()

old_pill1 = '''          <a href="/ufm" class="px-3 py-1.5 rounded-lg text-emerald-700 hover:text-emerald-900 transition">
            🏛️ Bot 4: UFM (Yuki 4)
          </a>
        </div>'''

new_pill1 = '''          <a href="/ufm" class="px-3 py-1.5 rounded-lg text-emerald-700 hover:text-emerald-900 transition">
            🏛️ Bot 4: UFM (Yuki 4)
          </a>
          <a href="/logout" class="px-2.5 py-1.5 rounded-lg text-rose-600 hover:text-rose-800 hover:bg-rose-50 transition flex items-center gap-1 font-bold" title="Đăng xuất khỏi hệ thống">
            <i class="fa-solid fa-right-from-bracket"></i>
            <span class="hidden sm:inline">Thoát</span>
          </a>
        </div>'''

text1 = text1.replace(old_pill1, new_pill1)
with open(p1, 'w', encoding='utf-8') as f:
    f.write(text1)
print("Updated logout button in web_app.py")

# 2. Update vaa/ufm/templates/index.html
p2 = r'c:\Users\Admin\Documents\HUIT\vaa\ufm\templates\index.html'
with open(p2, 'r', encoding='utf-8') as f:
    text2 = f.read()

old_pill2 = '''          <a href="/ufm" class="px-3 py-1.5 rounded-lg bg-white text-emerald-700 shadow-xs">
            🏛️ Bot 4: UFM (Yuki 4)
          </a>
        </div>'''

new_pill2 = '''          <a href="/ufm" class="px-3 py-1.5 rounded-lg bg-white text-emerald-700 shadow-xs">
            🏛️ Bot 4: UFM (Yuki 4)
          </a>
          <a href="/logout" class="px-2.5 py-1.5 rounded-lg text-rose-600 hover:text-rose-800 hover:bg-rose-50 transition flex items-center gap-1 font-bold" title="Đăng xuất khỏi hệ thống">
            <i class="fa-solid fa-right-from-bracket"></i>
            <span class="hidden sm:inline">Thoát</span>
          </a>
        </div>'''

text2 = text2.replace(old_pill2, new_pill2)
with open(p2, 'w', encoding='utf-8') as f:
    f.write(text2)
print("Updated logout button in vaa/ufm/templates/index.html")
