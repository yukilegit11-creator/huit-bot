import os
import sys

# 1. Patch web_app.py for Bot 1 (HUIT) and Bot 2 (VAA)
web_app_path = r'c:\Users\Admin\Documents\HUIT\web_app.py'
with open(web_app_path, 'r', encoding='utf-8') as f:
    webapp_code = f.read()

# Add sort toggle button to Bot 1 Console Toolbar
old_bot1_toolbar = '''          <div class="flex items-center space-x-3">
            <label class="text-xs text-slate-400 flex items-center gap-1.5 cursor-pointer select-none">
              <input type="checkbox" id="console-autoscroll" checked class="rounded text-blue-500 bg-slate-800 border-slate-700">
              Auto Scroll
            </label>
            <button onclick="clearConsoleView()" class="px-2.5 py-1 text-xs text-slate-400 hover:text-white bg-slate-800 hover:bg-slate-700 rounded-md transition">
              <i class="fa-solid fa-broom"></i> Xóa
            </button>'''

new_bot1_toolbar = '''          <div class="flex items-center space-x-3">
            <button onclick="toggleBot1LogSort()" id="bot1-sort-btn" class="px-2.5 py-1 text-xs text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-md transition flex items-center gap-1.5" title="Đổi thứ tự log: Mới nhất trên cùng hoặc cũ nhất trên cùng">
              <i class="fa-solid fa-arrow-down-short-wide text-cyan-400"></i>
              <span id="bot1-sort-text">Mới nhất trên</span>
            </button>
            <label class="text-xs text-slate-400 flex items-center gap-1.5 cursor-pointer select-none">
              <input type="checkbox" id="console-autoscroll" class="rounded text-blue-500 bg-slate-800 border-slate-700">
              Auto Scroll
            </label>
            <button onclick="clearConsoleView()" class="px-2.5 py-1 text-xs text-slate-400 hover:text-white bg-slate-800 hover:bg-slate-700 rounded-md transition">
              <i class="fa-solid fa-broom"></i> Xóa
            </button>'''

if old_bot1_toolbar in webapp_code:
    webapp_code = webapp_code.replace(old_bot1_toolbar, new_bot1_toolbar, 1)

# Replace Bot 1 renderLogs
old_bot1_render = '''    function renderLogs(logs) {
      const container = document.getElementById('console-stream');
      if (!logs || logs.length === 0) {
        container.innerHTML = '<div class="text-slate-500">Chưa có nhật ký ghi nhận...</div>';
        return;
      }

      const chronologicalLogs = [...logs].reverse();

      container.innerHTML = chronologicalLogs.map(l => {
        let badgeColor = 'bg-blue-900/60 text-blue-400 border-blue-800';
        if (l.level === 'SCAN') badgeColor = 'bg-cyan-950 text-cyan-400 border-cyan-800';
        else if (l.level === 'POST') badgeColor = 'bg-emerald-950 text-emerald-400 border-emerald-800';
        else if (l.level === 'FILTER') badgeColor = 'bg-amber-950 text-amber-300 border-amber-800';
        else if (l.level === 'ZALO') badgeColor = 'bg-indigo-950 text-indigo-300 border-indigo-800';
        else if (l.level === 'ERROR') badgeColor = 'bg-rose-950 text-rose-400 border-rose-800';

        const timeStr = l.created_at || '';
        const botBadge = (currentLogScope === 'ALL' && l.bot) ? `<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-indigo-300 border border-slate-700 shrink-0">[${l.bot}]</span>` : '';

        return `
          <div class="flex items-start gap-2 hover:bg-slate-800/40 px-2 py-1 rounded transition">
            <span class="text-slate-500 shrink-0 text-[11px] font-mono">${timeStr}</span>
            ${botBadge}
            <span class="px-1.5 py-0.5 rounded text-[10px] font-bold border ${badgeColor} shrink-0">${l.level}</span>
            <span class="text-slate-200 leading-relaxed break-all">${l.message}</span>
          </div>
        `;
      }).join('');

      if (document.getElementById('console-autoscroll').checked) {
        container.scrollTop = container.scrollHeight;
      }
    }'''

new_bot1_render = '''    let bot1LogSortAsc = false; // Mặc định: false = Mới nhất ở trên cùng

    function toggleBot1LogSort() {
      bot1LogSortAsc = !bot1LogSortAsc;
      const t = document.getElementById('bot1-sort-text');
      if (t) t.innerText = bot1LogSortAsc ? 'Cũ nhất trên' : 'Mới nhất trên';
      fetchLogs();
    }

    function renderLogs(logs) {
      const container = document.getElementById('console-stream');
      if (!logs || logs.length === 0) {
        container.innerHTML = '<div class="text-slate-500">Chưa có nhật ký ghi nhận...</div>';
        return;
      }

      // Thứ tự chính xác: mặc định mới nhất ở trên cùng (false), hoặc cũ nhất ở trên cùng (true)
      const displayLogs = bot1LogSortAsc ? [...logs].reverse() : [...logs];

      container.innerHTML = displayLogs.map(l => {
        let badgeColor = 'bg-blue-900/60 text-blue-400 border-blue-800';
        if (l.level === 'SCAN') badgeColor = 'bg-cyan-950 text-cyan-400 border-cyan-800';
        else if (l.level === 'POST') badgeColor = 'bg-emerald-950 text-emerald-400 border-emerald-800';
        else if (l.level === 'FILTER') badgeColor = 'bg-amber-950 text-amber-300 border-amber-800';
        else if (l.level === 'ZALO') badgeColor = 'bg-indigo-950 text-indigo-300 border-indigo-800';
        else if (l.level === 'ERROR') badgeColor = 'bg-rose-950 text-rose-400 border-rose-800';

        const timeStr = l.created_at || '';
        const botBadge = (currentLogScope === 'ALL' && l.bot) ? `<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-indigo-300 border border-slate-700 shrink-0">[${l.bot}]</span>` : '';

        // Tự động làm sạch timestamp lặp lại bên trong message để dễ nhìn
        const cleanMsg = (l.message || '').replace(/^([🔄✅⚠️❌🚨💡📌⚡🔥]?\s*)\[\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\]\s*/, '$1');

        return `
          <div class="flex items-start gap-2 hover:bg-slate-800/40 px-2 py-1 rounded transition border-b border-slate-800/20">
            <span class="text-slate-400 shrink-0 text-[11px] font-mono select-none">${timeStr}</span>
            ${botBadge}
            <span class="px-1.5 py-0.5 rounded text-[10px] font-bold border ${badgeColor} shrink-0">${l.level}</span>
            <span class="text-slate-200 leading-relaxed break-all">${cleanMsg}</span>
          </div>
        `;
      }).join('');

      if (bot1LogSortAsc && document.getElementById('console-autoscroll') && document.getElementById('console-autoscroll').checked) {
        container.scrollTop = container.scrollHeight;
      }
    }'''

if old_bot1_render in webapp_code:
    webapp_code = webapp_code.replace(old_bot1_render, new_bot1_render, 1)

# Add sort toggle to Bot 2 Console Toolbar
old_bot2_toolbar = '''          <div class="flex items-center space-x-3">
            <label class="text-xs text-slate-400 flex items-center gap-1.5 cursor-pointer select-none">
              <input type="checkbox" id="console2-autoscroll" checked class="rounded text-sky-500 bg-slate-800 border-slate-700">
              Auto Scroll
            </label>
            <button onclick="clearConsole2View()" class="px-2.5 py-1 text-xs text-slate-400 hover:text-white bg-slate-800 hover:bg-slate-700 rounded-md transition">
              <i class="fa-solid fa-broom"></i> Xóa
            </button>'''

new_bot2_toolbar = '''          <div class="flex items-center space-x-3">
            <button onclick="toggleBot2LogSort()" id="bot2-sort-btn" class="px-2.5 py-1 text-xs text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-md transition flex items-center gap-1.5" title="Đổi thứ tự log: Mới nhất trên cùng hoặc cũ nhất trên cùng">
              <i class="fa-solid fa-arrow-down-short-wide text-sky-400"></i>
              <span id="bot2-sort-text">Mới nhất trên</span>
            </button>
            <label class="text-xs text-slate-400 flex items-center gap-1.5 cursor-pointer select-none">
              <input type="checkbox" id="console2-autoscroll" class="rounded text-sky-500 bg-slate-800 border-slate-700">
              Auto Scroll
            </label>
            <button onclick="clearConsole2View()" class="px-2.5 py-1 text-xs text-slate-400 hover:text-white bg-slate-800 hover:bg-slate-700 rounded-md transition">
              <i class="fa-solid fa-broom"></i> Xóa
            </button>'''

if old_bot2_toolbar in webapp_code:
    webapp_code = webapp_code.replace(old_bot2_toolbar, new_bot2_toolbar, 1)

# Replace Bot 2 renderLogs
old_bot2_render = '''    function renderLogs(logs) {
      const container = document.getElementById('console-stream');
      if (!logs || logs.length === 0) {
        container.innerHTML = '<div class="text-slate-500">Chưa có nhật ký ghi nhận...</div>';
        return;
      }

      const chronologicalLogs = [...logs].reverse();

      container.innerHTML = chronologicalLogs.map(l => {
        let badgeColor = 'bg-blue-900/60 text-blue-400 border-blue-800';
        if (l.level === 'SCAN') badgeColor = 'bg-cyan-950 text-cyan-400 border-cyan-800';
        else if (l.level === 'POST') badgeColor = 'bg-emerald-950 text-emerald-400 border-emerald-800';
        else if (l.level === 'FILTER') badgeColor = 'bg-amber-950 text-amber-300 border-amber-800';
        else if (l.level === 'ZALO') badgeColor = 'bg-indigo-950 text-indigo-300 border-indigo-800';
        else if (l.level === 'ERROR') badgeColor = 'bg-rose-950 text-rose-400 border-rose-800';

        const timeStr = l.created_at || '';
        const botBadge = (currentLog2Scope === 'ALL' && l.bot) ? `<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-sky-300 border border-slate-700 shrink-0">[${l.bot}]</span>` : '';

        return `
          <div class="flex items-start gap-2 hover:bg-slate-800/40 px-2 py-1 rounded transition">
            <span class="text-slate-500 shrink-0 text-[11px] font-mono">${timeStr}</span>
            ${botBadge}
            <span class="px-1.5 py-0.5 rounded text-[10px] font-bold border ${badgeColor} shrink-0">${l.level}</span>
            <span class="text-slate-200 leading-relaxed break-all">${l.message}</span>
          </div>
        `;
      }).join('');

      if (document.getElementById('console2-autoscroll').checked) {
        container.scrollTop = container.scrollHeight;
      }
    }'''

new_bot2_render = '''    let bot2LogSortAsc = false;

    function toggleBot2LogSort() {
      bot2LogSortAsc = !bot2LogSortAsc;
      const t = document.getElementById('bot2-sort-text');
      if (t) t.innerText = bot2LogSortAsc ? 'Cũ nhất trên' : 'Mới nhất trên';
      fetchLogs();
    }

    function renderLogs(logs) {
      const container = document.getElementById('console-stream');
      if (!logs || logs.length === 0) {
        container.innerHTML = '<div class="text-slate-500">Chưa có nhật ký ghi nhận...</div>';
        return;
      }

      const displayLogs = bot2LogSortAsc ? [...logs].reverse() : [...logs];

      container.innerHTML = displayLogs.map(l => {
        let badgeColor = 'bg-blue-900/60 text-blue-400 border-blue-800';
        if (l.level === 'SCAN') badgeColor = 'bg-cyan-950 text-cyan-400 border-cyan-800';
        else if (l.level === 'POST') badgeColor = 'bg-emerald-950 text-emerald-400 border-emerald-800';
        else if (l.level === 'FILTER') badgeColor = 'bg-amber-950 text-amber-300 border-amber-800';
        else if (l.level === 'ZALO') badgeColor = 'bg-indigo-950 text-indigo-300 border-indigo-800';
        else if (l.level === 'ERROR') badgeColor = 'bg-rose-950 text-rose-400 border-rose-800';

        const timeStr = l.created_at || '';
        const botBadge = (currentLog2Scope === 'ALL' && l.bot) ? `<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-sky-300 border border-slate-700 shrink-0">[${l.bot}]</span>` : '';

        const cleanMsg = (l.message || '').replace(/^([🔄✅⚠️❌🚨💡📌⚡🔥]?\s*)\[\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\]\s*/, '$1');

        return `
          <div class="flex items-start gap-2 hover:bg-slate-800/40 px-2 py-1 rounded transition border-b border-slate-800/20">
            <span class="text-slate-400 shrink-0 text-[11px] font-mono select-none">${timeStr}</span>
            ${botBadge}
            <span class="px-1.5 py-0.5 rounded text-[10px] font-bold border ${badgeColor} shrink-0">${l.level}</span>
            <span class="text-slate-200 leading-relaxed break-all">${cleanMsg}</span>
          </div>
        `;
      }).join('');

      if (bot2LogSortAsc && document.getElementById('console2-autoscroll') && document.getElementById('console2-autoscroll').checked) {
        container.scrollTop = container.scrollHeight;
      }
    }'''

if old_bot2_render in webapp_code:
    webapp_code = webapp_code.replace(old_bot2_render, new_bot2_render, 1)

# Clean timestamp in Bot 3 fetchLogs
old_bot3_fetch = '''            const timeStr = l.created_at || '';
            const botBadge = (currentLog3Scope === 'ALL' && l.bot) ? `<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-rose-300 border border-slate-700 shrink-0">[${l.bot}]</span> ` : '';

            return `<div class="flex items-start gap-1.5 py-0.5"><span class="text-slate-500 font-mono shrink-0">[${timeStr}]</span> ${botBadge}<span class="font-bold ${color} shrink-0">[${l.level}]</span> <span class="break-all text-slate-200">${l.message}</span></div>`;'''

new_bot3_fetch = '''            const timeStr = l.created_at || '';
            const botBadge = (currentLog3Scope === 'ALL' && l.bot) ? `<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-rose-300 border border-slate-700 shrink-0">[${l.bot}]</span> ` : '';
            const cleanMsg = (l.message || '').replace(/^([🔄✅⚠️❌🚨💡📌⚡🔥]?\s*)\[\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\]\s*/, '$1');

            return `<div class="flex items-start gap-1.5 py-0.5 border-b border-slate-800/20"><span class="text-slate-400 font-mono shrink-0 select-none">[${timeStr}]</span> ${botBadge}<span class="font-bold ${color} shrink-0">[${l.level}]</span> <span class="break-all text-slate-200">${cleanMsg}</span></div>`;'''

if old_bot3_fetch in webapp_code:
    webapp_code = webapp_code.replace(old_bot3_fetch, new_bot3_fetch, 1)

with open(web_app_path, 'w', encoding='utf-8') as f:
    f.write(webapp_code)
print("Patched web_app.py successfully!")
