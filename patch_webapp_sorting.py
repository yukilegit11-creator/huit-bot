import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

with open("c:/Users/Admin/Documents/HUIT/web_app.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Patch Bot 1 renderLogs
old_b1 = """    function renderLogs(logs) {{
      const container = document.getElementById('console-stream');
      if (!logs || logs.length === 0) {{
        container.innerHTML = '<div class="text-slate-500">Chưa có nhật ký ghi nhận...</div>';
        return;
      }}

      const chronologicalLogs = [...logs].reverse();

      container.innerHTML = chronologicalLogs.map(l => {{
        let badgeColor = 'bg-blue-900/60 text-blue-400 border-blue-800';
        if (l.level === 'SCAN') badgeColor = 'bg-cyan-950 text-cyan-400 border-cyan-800';
        else if (l.level === 'POST') badgeColor = 'bg-emerald-950 text-emerald-400 border-emerald-800';
        else if (l.level === 'FILTER') badgeColor = 'bg-amber-950 text-amber-300 border-amber-800';
        else if (l.level === 'ZALO') badgeColor = 'bg-indigo-950 text-indigo-300 border-indigo-800';
        else if (l.level === 'ERROR') badgeColor = 'bg-rose-950 text-rose-400 border-rose-800';

        const timeStr = l.created_at || '';
        const botBadge = (currentLogScope === 'ALL' && l.bot) ? `<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-indigo-300 border border-slate-700 shrink-0">[${{l.bot}}]</span>` : '';

        return `
          <div class="flex items-start gap-2 hover:bg-slate-800/40 px-2 py-1 rounded transition">
            <span class="text-slate-500 shrink-0 text-[11px] font-mono">${{timeStr}}</span>
            ${{botBadge}}
            <span class="px-1.5 py-0.5 rounded text-[10px] font-bold border ${{badgeColor}} shrink-0">${{l.level}}</span>
            <span class="text-slate-200 leading-relaxed break-all">${{l.message}}</span>
          </div>
        `;
      }}).join('');

      if (document.getElementById('console-autoscroll').checked) {{
        container.scrollTop = container.scrollHeight;
      }}
    }}"""

new_b1 = """    let bot1LogSortAsc = false; // Mặc định: false (Mới nhất trên cùng)

    function toggleBot1LogSort() {{
      bot1LogSortAsc = !bot1LogSortAsc;
      const btnText = document.getElementById('bot1-sort-text');
      const btnIcon = document.querySelector('#bot1-sort-btn i');
      if (bot1LogSortAsc) {{
        if (btnText) btnText.innerText = 'Cũ nhất trên';
        if (btnIcon) btnIcon.className = 'fa-solid fa-arrow-up-short-wide text-amber-400';
      }} else {{
        if (btnText) btnText.innerText = 'Mới nhất trên';
        if (btnIcon) btnIcon.className = 'fa-solid fa-arrow-down-short-wide text-cyan-400';
      }}
      fetchLogs();
    }}

    function renderLogs(logs) {{
      const container = document.getElementById('console-stream');
      if (!logs || logs.length === 0) {{
        container.innerHTML = '<div class="text-slate-500">Chưa có nhật ký ghi nhận...</div>';
        return;
      }}

      // Nếu bot1LogSortAsc = true (Cũ nhất trên) -> reverse; ngược lại giữ nguyên DESC (Mới nhất trên)
      const sortedLogs = bot1LogSortAsc ? [...logs].reverse() : [...logs];

      container.innerHTML = sortedLogs.map(l => {{
        let badgeColor = 'bg-blue-900/60 text-blue-400 border-blue-800';
        if (l.level === 'SCAN') badgeColor = 'bg-cyan-950 text-cyan-400 border-cyan-800';
        else if (l.level === 'POST') badgeColor = 'bg-emerald-950 text-emerald-400 border-emerald-800';
        else if (l.level === 'FILTER') badgeColor = 'bg-amber-950 text-amber-300 border-amber-800';
        else if (l.level === 'ZALO') badgeColor = 'bg-indigo-950 text-indigo-300 border-indigo-800';
        else if (l.level === 'ERROR') badgeColor = 'bg-rose-950 text-rose-400 border-rose-800';

        const timeStr = l.created_at || '';
        const botBadge = (currentLogScope === 'ALL' && l.bot) ? `<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-indigo-300 border border-slate-700 shrink-0">[${{l.bot}}]</span>` : '';

        // Xóa timestamp trùng lặp trong nội dung message
        let cleanMsg = String(l.message || '');
        cleanMsg = cleanMsg.replace(/^(\\S+\\s*)?\\[\\d{{4}}-\\d{{2}}-\\d{{2}}\\s+\\d{{2}}:\\d{{2}}:\\d{{2}}\\]\\s*/, '$1');
        cleanMsg = cleanMsg.replace(/^\\[\\d{{4}}-\\d{{2}}-\\d{{2}}\\s+\\d{{2}}:\\d{{2}}:\\d{{2}}\\]\\s*/, '');

        return `
          <div class="flex items-start gap-2 hover:bg-slate-800/40 px-2 py-1 rounded transition">
            <span class="text-slate-500 shrink-0 text-[11px] font-mono">${{timeStr}}</span>
            ${{botBadge}}
            <span class="px-1.5 py-0.5 rounded text-[10px] font-bold border ${{badgeColor}} shrink-0">${{l.level}}</span>
            <span class="text-slate-200 leading-relaxed break-all">${{cleanMsg}}</span>
          </div>
        `;
      }}).join('');

      if (bot1LogSortAsc && document.getElementById('console-autoscroll') && document.getElementById('console-autoscroll').checked) {{
        container.scrollTop = container.scrollHeight;
      }}
    }}"""

# 2. Patch Bot 2 renderLogs
old_b2 = """    function renderLogs(logs) {{
      const container = document.getElementById('console-stream');
      if (!logs || logs.length === 0) {{
        container.innerHTML = '<div class="text-slate-500">Chưa có nhật ký ghi nhận...</div>';
        return;
      }}

      const chronologicalLogs = [...logs].reverse();

      container.innerHTML = chronologicalLogs.map(l => {{
        let badgeColor = 'bg-blue-900/60 text-blue-400 border-blue-800';
        if (l.level === 'SCAN') badgeColor = 'bg-cyan-950 text-cyan-400 border-cyan-800';
        else if (l.level === 'POST') badgeColor = 'bg-emerald-950 text-emerald-400 border-emerald-800';
        else if (l.level === 'FILTER') badgeColor = 'bg-amber-950 text-amber-300 border-amber-800';
        else if (l.level === 'ZALO') badgeColor = 'bg-indigo-950 text-indigo-300 border-indigo-800';
        else if (l.level === 'ERROR') badgeColor = 'bg-rose-950 text-rose-400 border-rose-800';

        const timeStr = l.created_at || '';
        const botBadge = (currentLog2Scope === 'ALL' && l.bot) ? `<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-sky-300 border border-slate-700 shrink-0">[${{l.bot}}]</span>` : '';

        return `
          <div class="flex items-start gap-2 hover:bg-slate-800/40 px-2 py-1 rounded transition">
            <span class="text-slate-500 shrink-0 text-[11px] font-mono">${{timeStr}}</span>
            ${{botBadge}}
            <span class="px-1.5 py-0.5 rounded text-[10px] font-bold border ${{badgeColor}} shrink-0">${{l.level}}</span>
            <span class="text-slate-200 leading-relaxed break-all">${{l.message}}</span>
          </div>
        `;
      }}).join('');

      if (document.getElementById('console-autoscroll').checked) {{
        container.scrollTop = container.scrollHeight;
      }}
    }}"""

new_b2 = """    let bot2LogSortAsc = false; // Mặc định: false (Mới nhất trên cùng)

    function toggleBot2LogSort() {{
      bot2LogSortAsc = !bot2LogSortAsc;
      const btnText = document.getElementById('bot2-sort-text');
      const btnIcon = document.querySelector('#bot2-sort-btn i');
      if (bot2LogSortAsc) {{
        if (btnText) btnText.innerText = 'Cũ nhất trên';
        if (btnIcon) btnIcon.className = 'fa-solid fa-arrow-up-short-wide text-amber-400';
      }} else {{
        if (btnText) btnText.innerText = 'Mới nhất trên';
        if (btnIcon) btnIcon.className = 'fa-solid fa-arrow-down-short-wide text-cyan-400';
      }}
      fetchLogs();
    }}

    function renderLogs(logs) {{
      const container = document.getElementById('console-stream');
      if (!logs || logs.length === 0) {{
        container.innerHTML = '<div class="text-slate-500">Chưa có nhật ký ghi nhận...</div>';
        return;
      }}

      // Nếu bot2LogSortAsc = true (Cũ nhất trên) -> reverse; ngược lại giữ nguyên DESC (Mới nhất trên)
      const sortedLogs = bot2LogSortAsc ? [...logs].reverse() : [...logs];

      container.innerHTML = sortedLogs.map(l => {{
        let badgeColor = 'bg-blue-900/60 text-blue-400 border-blue-800';
        if (l.level === 'SCAN') badgeColor = 'bg-cyan-950 text-cyan-400 border-cyan-800';
        else if (l.level === 'POST') badgeColor = 'bg-emerald-950 text-emerald-400 border-emerald-800';
        else if (l.level === 'FILTER') badgeColor = 'bg-amber-950 text-amber-300 border-amber-800';
        else if (l.level === 'ZALO') badgeColor = 'bg-indigo-950 text-indigo-300 border-indigo-800';
        else if (l.level === 'ERROR') badgeColor = 'bg-rose-950 text-rose-400 border-rose-800';

        const timeStr = l.created_at || '';
        const botBadge = (currentLog2Scope === 'ALL' && l.bot) ? `<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-sky-300 border border-slate-700 shrink-0">[${{l.bot}}]</span>` : '';

        // Xóa timestamp trùng lặp trong nội dung message
        let cleanMsg = String(l.message || '');
        cleanMsg = cleanMsg.replace(/^(\\S+\\s*)?\\[\\d{{4}}-\\d{{2}}-\\d{{2}}\\s+\\d{{2}}:\\d{{2}}:\\d{{2}}\\]\\s*/, '$1');
        cleanMsg = cleanMsg.replace(/^\\[\\d{{4}}-\\d{{2}}-\\d{{2}}\\s+\\d{{2}}:\\d{{2}}:\\d{{2}}\\]\\s*/, '');

        return `
          <div class="flex items-start gap-2 hover:bg-slate-800/40 px-2 py-1 rounded transition">
            <span class="text-slate-500 shrink-0 text-[11px] font-mono">${{timeStr}}</span>
            ${{botBadge}}
            <span class="px-1.5 py-0.5 rounded text-[10px] font-bold border ${{badgeColor}} shrink-0">${{l.level}}</span>
            <span class="text-slate-200 leading-relaxed break-all">${{cleanMsg}}</span>
          </div>
        `;
      }}).join('');

      if (bot2LogSortAsc && document.getElementById('console-autoscroll') && document.getElementById('console-autoscroll').checked) {{
        container.scrollTop = container.scrollHeight;
      }}
    }}"""

# Check and replace
p1 = old_b1 in content
p2 = old_b2 in content
print(f"Match Bot 1: {p1}, Match Bot 2: {p2}")

if p1:
    content = content.replace(old_b1, new_b1, 1)
if p2:
    content = content.replace(old_b2, new_b2, 1)

# Also ensure Bot 2 header has the sort button if not present
if 'id="bot2-sort-btn"' not in content and '<span id="bot2-sort-text">' in content:
    content = content.replace('<span id="bot2-sort-text">', '<button onclick="toggleBot2LogSort()" id="bot2-sort-btn" class="px-2.5 py-1 text-xs text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-md transition flex items-center gap-1.5"><i class="fa-solid fa-arrow-down-short-wide text-cyan-400"></i><span id="bot2-sort-text">')

with open("c:/Users/Admin/Documents/HUIT/web_app.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Web app logs patched successfully!")
