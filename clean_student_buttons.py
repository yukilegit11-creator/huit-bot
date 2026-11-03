for path in ['c:/Users/Admin/Documents/HUIT/vaa/ufm/templates/index.html', 'c:/Users/Admin/Documents/HUIT/generate_ufm_html.py']:
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()

    target = '''      <div class="flex items-center gap-2">
        <a href="/ufm/submit-cookie" target="_blank" class="px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200 rounded-xl text-xs font-bold transition flex items-center gap-1.5">
          <i class="fa-solid fa-arrow-up-right-from-square"></i>
          <span>Mở Form Nạp Sinh Viên</span>
        </a>
        <button onclick="copyStudentSubmitLink()" class="px-3 py-2 bg-white hover:bg-slate-100 text-emerald-700 border border-emerald-200 rounded-xl text-xs font-bold transition flex items-center gap-1.5" title="Sao chép link gửi sinh viên">
          <i class="fa-solid fa-copy"></i>
          <span>Sao chép Link</span>
        </button>
      </div>'''

    if target in text:
        text = text.replace(target, '')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(text)
        print(f"Removed from {path}")
    else:
        print(f"Target not found in {path}")
