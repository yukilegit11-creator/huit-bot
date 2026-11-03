import os

ufm_app_path = r'c:\Users\Admin\Documents\HUIT\vaa\ufm\web_app.py'
with open(ufm_app_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add missing Zalo test endpoints to vaa/ufm/web_app.py so both /ufm/api/... and /api/... work 100%
zalo_routes = """
@app.post("/api/zalo/send-test-target")
async def api_ufm_send_test_target(req: Request):
    \"\"\"Gửi tin nhắn test tới 1 nhóm hoặc người nhận Zalo của UFM.\"\"\"
    try:
        data = await req.json()
    except Exception:
        data = {}
    target_id = str(data.get("target_id", "")).strip() or "7456361874031804652"
    target_type = data.get("target_type", "GROUP")
    target_name = data.get("target_name", target_id)
    custom_msg = data.get("custom_message", None)
    
    try:
        from zalo_sender import ZaloDispatcher
        dispatcher = ZaloDispatcher(CONFIG_FILE, db_file=database.UFM_DB_FILE)
        dispatcher.bot_name = "Bot 4 - UFM (Yuki 4 ĐRL)"
        
        test_msg = custom_msg or (
            f"🧪 [UFM - TIN NHẮN THỬ NGHIỆM KẾT NỐI ZALO] 🧪\\n"
            f"━━━━━━━━━━━━━━━━━━━━\\n"
            f"🤖 Bot: Yuki 4 (UFM ĐRL)\\n"
            f"🎯 Nhóm nhận: {target_name} ({target_id})\\n"
            f"⏰ Thời gian: {datetime.now(timezone(timedelta(hours=7))).strftime('%H:%M:%S %d/%m/%Y')}\\n"
            f"━━━━━━━━━━━━━━━━━━━━\\n"
            f"✅ Kết nối Zalo Bot 4 hoạt động hoàn hảo!"
        )
        ok = dispatcher.send_custom_notification(test_msg, target_thread_id=target_id, target_thread_type=target_type)
        if ok:
            return {"status": "ok", "success": True, "message": f"Đã gửi tin nhắn test tới [{target_name}] thành công!"}
        else:
            return {"status": "error", "success": False, "message": f"Không thể gửi tin nhắn tới [{target_name}]. Hãy kiểm tra Cookie Zalo!"}
    except Exception as e:
        return {"status": "error", "success": False, "message": f"Lỗi gửi tin: {e}"}

@app.post("/api/zalo/send-test-all-groups")
async def api_ufm_send_test_all_groups(req: Request):
    \"\"\"Gửi tin nhắn test tới tất cả các nhóm Zalo đang BẬT của UFM.\"\"\"
    try:
        from zalo_sender import ZaloDispatcher
        dispatcher = ZaloDispatcher(CONFIG_FILE, db_file=database.UFM_DB_FILE)
        dispatcher.bot_name = "Bot 4 - UFM (Yuki 4 ĐRL)"
        now_vn = datetime.now(timezone(timedelta(hours=7))).strftime('%H:%M:%S %d/%m/%Y')
        test_msg = f"🧪 [TEST TOÀN BỘ NHÓM ZALO - UFM]\\n━━━━━━━━━━━━━━━━━━━━\\nBot 4 (UFM) kiểm tra kết nối tới các nhóm đang BẬT.\\n⏰ Thời gian: {now_vn}"
        ok, msg = dispatcher.send_test_alert(test_message=test_msg)
        return {"status": "ok" if ok else "error", "success": ok, "message": msg}
    except Exception as e:
        return {"status": "error", "success": False, "message": f"Lỗi gửi tin tới tất cả nhóm: {e}"}

@app.get("/api/zalo/quad-target-groups")
async def api_ufm_quad_target_groups():
    \"\"\"Trả về danh sách nhóm mục tiêu của UFM.\"\"\"
    cfg = get_config()
    groups = cfg.get("zalo", {}).get("target_groups", [])
    return {"status": "ok", "groups": groups}
"""

if '@app.post("/api/zalo/send-test-target")' not in content:
    # Insert before @app.post("/api/zalo/send-demo-alert")
    anchor = '@app.post("/api/zalo/send-demo-alert")'
    if anchor in content:
        content = content.replace(anchor, zalo_routes + "\n" + anchor, 1)

# 2. Fix the interceptor in the template
old_interceptor = '''    (function() {
      if (window.location.pathname.startsWith('/ufm')) {
        const origFetch = window.fetch;
        window.fetch = function(url, options) {
          if (typeof url === 'string' && url.startsWith('/api/')) {
            url = '/ufm' + url;
          }
          return origFetch(url, options);
        };
      }
    })();'''

new_interceptor = '''    (function() {
      const isUfm = window.location.pathname.startsWith('/ufm');
      if (isUfm) {
        const origFetch = window.fetch;
        window.fetch = function(url, options) {
          if (typeof url === 'string') {
            // Danh sách các endpoint toàn cục của hệ thống (port 8000 root)
            const rootApis = ['/api/all-logs'];
            const isRootApi = rootApis.some(ep => url.startsWith(ep));
            if (url.startsWith('/api/') && !isRootApi) {
              url = '/ufm' + url;
            }
          }
          return origFetch(url, options);
        };
      }
    })();'''

if old_interceptor in content:
    content = content.replace(old_interceptor, new_interceptor)

# 3. Fix fetchLogs in vaa/ufm/web_app.py
old_ufm_fetchlogs = '''    async function fetchLogs() {
      try {
        const url = (currentLogUfmScope === 'ALL') ? '/api/all-logs?limit=80' : '/api/logs?limit=80';
        const res = await fetch(url);
        const data = await res.json();
        const term = document.getElementById('terminalLog');
        if (!data.logs || data.logs.length === 0) {
          term.innerHTML = '<div class="text-gray-500">Chưa có nhật ký nào.</div>';
          return;
        }

        let html = '';
        for (const log of data.logs) {
          let lvlColor = 'text-blue-400';
          if (log.level === 'WARN') lvlColor = 'text-amber-400';
          if (log.level === 'ERROR') lvlColor = 'text-rose-400';
          if (log.level === 'ZALO') lvlColor = 'text-emerald-400';
          if (log.level === 'ACTIVITY') lvlColor = 'text-indigo-400';
          if (log.level === 'SNIPER') lvlColor = 'text-red-400 font-bold';
          if (log.level === 'STUDENT') lvlColor = 'text-cyan-400';
          if (log.level === 'SCAN') lvlColor = 'text-teal-400';

          const timeStr = log.created_at || '';
          const botBadge = (currentLogUfmScope === 'ALL' && log.bot) ? `<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-gray-800 text-blue-300 border border-gray-700 shrink-0">[${log.bot}]</span> ` : '';

          html += `<div class="flex items-start gap-1.5 py-0.5"><span class="text-gray-500 shrink-0 font-mono">[${timeStr}]</span> ${botBadge}<span class="${lvlColor} shrink-0">[${log.level}]</span> <span class="break-all">${log.message}</span></div>`;
        }
        term.innerHTML = html;
      } catch (e) {
        console.error(e);
      }
    }'''

new_ufm_fetchlogs = '''    let ufmLogSortAsc = false; // Mặc định: Mới nhất ở trên cùng

    async function fetchLogs() {
      try {
        const prefix = window.location.pathname.startsWith('/ufm') ? '/ufm' : '';
        const url = (currentLogUfmScope === 'ALL') ? '/api/all-logs?limit=80' : (prefix + '/api/logs?limit=80');
        const res = await fetch(url);
        const data = await res.json();
        const term = document.getElementById('terminalLog');
        if (!data.logs || data.logs.length === 0) {
          term.innerHTML = '<div class="text-gray-500">Chưa có nhật ký nào.</div>';
          return;
        }

        // Mới nhất ở trên cùng (false), hoặc cũ nhất ở trên cùng (true)
        const displayLogs = ufmLogSortAsc ? [...data.logs].reverse() : [...data.logs];

        let html = '';
        for (const log of displayLogs) {
          let lvlColor = 'text-blue-400';
          if (log.level === 'WARN') lvlColor = 'text-amber-400';
          if (log.level === 'ERROR') lvlColor = 'text-rose-400';
          if (log.level === 'ZALO') lvlColor = 'text-emerald-400';
          if (log.level === 'ACTIVITY') lvlColor = 'text-indigo-400';
          if (log.level === 'SNIPER') lvlColor = 'text-red-400 font-bold';
          if (log.level === 'STUDENT') lvlColor = 'text-cyan-400';
          if (log.level === 'SCAN') lvlColor = 'text-teal-400';

          const timeStr = log.created_at || '';
          const botBadge = (currentLogUfmScope === 'ALL' && log.bot) ? `<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-gray-800 text-blue-300 border border-gray-700 shrink-0">[${log.bot}]</span> ` : '';

          // Làm sạch timestamp lặp lại bên trong message để dễ nhìn
          const cleanMsg = (log.message || '').replace(/^([🔄✅⚠️❌🚨💡📌⚡🔥]?\s*)\[\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\]\s*/, '$1');

          html += `<div class="flex items-start gap-1.5 py-0.5 border-b border-gray-800/30"><span class="text-gray-400 shrink-0 font-mono select-none">[${timeStr}]</span> ${botBadge}<span class="${lvlColor} shrink-0">[${log.level}]</span> <span class="break-all text-gray-200">${cleanMsg}</span></div>`;
        }
        term.innerHTML = html;
      } catch (e) {
        console.error(e);
      }
    }'''

if old_ufm_fetchlogs in content:
    content = content.replace(old_ufm_fetchlogs, new_ufm_fetchlogs, 1)

with open(ufm_app_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Patched vaa/ufm/web_app.py successfully!")
