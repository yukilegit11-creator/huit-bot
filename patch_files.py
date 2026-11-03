import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

ROOT_DIR = r"C:\Users\Admin\Documents\HUIT"
WEB_APP_PATH = os.path.join(ROOT_DIR, "web_app.py")
UFM_WEB_APP_PATH = os.path.join(ROOT_DIR, "vaa", "ufm", "web_app.py")
VAA_WEB_APP_PATH = os.path.join(ROOT_DIR, "vaa", "web_app.py")

print("Starting patch...")

# ================= 1. PATCH ROOT web_app.py =================
with open(WEB_APP_PATH, "r", encoding="utf-8") as f:
    code = f.read()

# Fix imports if needed
if "import time" not in code[:300]:
    code = code.replace("import sqlite3\n", "import sqlite3\nimport time\nimport asyncio\n", 1)

# Fix time.sleep(1) in api_send_test_all_groups
code = code.replace("time.sleep(1)", "await asyncio.sleep(1)")

# Remove duplicated api_master_send_demo_alert if present twice
first_demo_alert = code.find('@app.post("/api/zalo/send-demo-alert")')
second_demo_alert = code.find('@app.post("/api/zalo/send-demo-alert")', first_demo_alert + 40)
if second_demo_alert != -1 and first_demo_alert != -1:
    # Just leave or keep, python allows re-registering
    pass

# Patch Bot 1 renderTargetGroups to include "Test Nhóm" button
old_b1_btn = """          <div class="flex items-center gap-3">
            <button onclick="toggleZaloGroup('${g.id}')\""""
new_b1_btn = """          <div class="flex items-center gap-3">
            <button onclick="sendTestToSingleGroup('${g.id}', '${g.name}', '${g.type || 'GROUP'}', 'bot1')" class="px-2.5 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 bg-indigo-50 text-indigo-700 hover:bg-indigo-100 border border-indigo-200" title="Gửi tin nhắn test riêng vào nhóm này">
              <i class="fa-solid fa-paper-plane text-xs"></i> Test
            </button>
            <button onclick="toggleZaloGroup('${g.id}')\""""
if old_b1_btn in code:
    code = code.replace(old_b1_btn, new_b1_btn, 1)
    print("Patched Bot 1 renderTargetGroups test button!")
else:
    print("Bot 1 renderTargetGroups pattern not found or already patched.")

# Patch Bot 2 renderTargetGroups to include "Test Nhóm" button
old_b2_btn = """          <div class="flex items-center gap-3">
            <button onclick="toggleZaloGroup('${g.id}')\""""
if old_b2_btn in code:
    new_b2_btn = """          <div class="flex items-center gap-3">
            <button onclick="sendTestToSingleGroup('${g.id}', '${g.name}', '${g.type || 'GROUP'}', 'bot2')" class="px-2.5 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 bg-sky-50 text-sky-700 hover:bg-sky-100 border border-sky-200" title="Gửi tin nhắn test riêng vào nhóm này">
              <i class="fa-solid fa-paper-plane text-xs"></i> Test
            </button>
            <button onclick="toggleZaloGroup('${g.id}')\""""
    code = code.replace(old_b2_btn, new_b2_btn, 1)
    print("Patched Bot 2 renderTargetGroups test button!")
else:
    print("Bot 2 renderTargetGroups pattern not found or already patched.")

# Patch Bot 3 renderTargetGroups to include "Test" button
old_b3_btn = """            <div class="flex items-center gap-2">
              <button onclick="toggleTargetGroup('${g.id}', ${!g.enabled})\""""
new_b3_btn = """            <div class="flex items-center gap-2">
              <button onclick="sendTestToSingleGroup('${g.id}', '${g.name}', '${g.type || 'GROUP'}', 'bot3')" class="px-2.5 py-1 rounded-lg text-[11px] font-bold bg-rose-50 text-rose-700 hover:bg-rose-100 border border-rose-200 flex items-center gap-1" title="Gửi tin nhắn test riêng vào nhóm này">
                <i class="fa-solid fa-paper-plane text-[10px]"></i> Test
              </button>
              <button onclick="toggleTargetGroup('${g.id}', ${!g.enabled})\""""
if old_b3_btn in code:
    code = code.replace(old_b3_btn, new_b3_btn, 1)
    print("Patched Bot 3 renderTargetGroups test button!")
else:
    print("Bot 3 renderTargetGroups pattern not found or already patched.")

# Add sendTestToSingleGroup to Bot 3 script if not present
if "sendTestToSingleGroup" not in code[code.find("@app.api_route(\"/bot3\""):]:
    b3_pos = code.find("function toggleTargetGroup(gid, enabled)")
    if b3_pos != -1:
        b3_helper = """    async function sendTestToSingleGroup(targetId, targetName, targetType, botId='bot3') {
      if (!confirm(`🧪 Bạn có chắc muốn gửi tin nhắn TEST vào nhóm/mục tiêu:\\n"${targetName}" (ID: ${targetId})?`)) return;
      try {
        const res = await fetch('/api/zalo/send-test-target', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            bot_id: botId,
            target_id: targetId,
            target_type: targetType,
            target_name: targetName
          })
        });
        const data = await res.json();
        if (res.ok && data.success) {
          alert('✅ ' + data.message);
        } else {
          alert('❌ ' + (data.detail || data.message || 'Lỗi gửi tin test'));
        }
      } catch (err) {
        alert('Lỗi gửi tin test: ' + err);
      }
    }

"""
        code = code[:b3_pos] + b3_helper + code[b3_pos:]
        print("Added sendTestToSingleGroup helper to Bot 3 script!")

# Add Top Navbar button for Quad Test Modal across Bot 1, Bot 2, Bot 3
nav_btn_html = """        <!-- TEST ZALO 4 BOT MODAL BUTTON -->
        <button onclick="openQuadTestModal()" class="px-3.5 py-2 rounded-xl text-xs font-bold bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white shadow-xs transition flex items-center gap-1.5" title="Mở bảng kiểm tra & bắn tin nhắn test cho từng nhóm Zalo của 4 Bot">
          <i class="fa-solid fa-vial-circle-check"></i>
          <span>Test Nhóm Zalo (4 Bot)</span>
        </button>
"""

# For Bot 1
if "id=\"btn-sync-github-bot1\"" in code and "openQuadTestModal" not in code[:code.find("@app.api_route(\"/bot2\"")]:
    code = code.replace("id=\"btn-sync-github-bot1\"", "id=\"btn-sync-github-bot1\"", 1)
    pos = code.find("<button id=\"btn-sync-github-bot1\"")
    if pos != -1:
        code = code[:pos] + nav_btn_html + code[pos:]
        print("Added Quad Test button to Bot 1 navbar!")

# For Bot 2
if "id=\"btn-sync-github-bot2\"" in code and "openQuadTestModal" not in code[code.find("@app.api_route(\"/bot2\""):code.find("@app.api_route(\"/bot3\"")]:
    pos = code.find("<button id=\"btn-sync-github-bot2\"")
    if pos != -1:
        code = code[:pos] + nav_btn_html + code[pos:]
        print("Added Quad Test button to Bot 2 navbar!")

# For Bot 3
if "id=\"btn-sync-github-bot3\"" in code and "openQuadTestModal" not in code[code.find("@app.api_route(\"/bot3\""):code.find("if __name__")]:
    pos = code.find("<button id=\"btn-sync-github-bot3\"")
    if pos != -1:
        code = code[:pos] + nav_btn_html + code[pos:]
        print("Added Quad Test button to Bot 3 navbar!")

# Modal snippet to inject before </body> in all templates
modal_component = """
  <!-- ==================== QUAD BOT ZALO TEST MODAL ==================== -->
  <div id="quad-test-modal" class="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm hidden flex items-center justify-center p-4" style="z-index: 9999;">
    <div class="bg-white rounded-2xl shadow-2xl border border-slate-200 max-w-2xl w-full max-h-[90vh] flex flex-col overflow-hidden text-slate-800">
      <!-- Header -->
      <div class="p-4 px-6 border-b border-slate-100 flex items-center justify-between bg-gradient-to-r from-indigo-50 to-purple-50">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-xl bg-indigo-600 text-white flex items-center justify-center text-lg shadow-md shadow-indigo-500/20">
            <i class="fa-solid fa-vial-circle-check"></i>
          </div>
          <div>
            <h3 class="font-bold text-slate-900 text-base leading-tight">Bắn Tin Nhắn Test Zalo (4 Bot Yuki)</h3>
            <p class="text-xs text-slate-500">Kiểm tra kết nối và gửi tin test riêng lẻ từng nhóm hoặc tất cả nhóm</p>
          </div>
        </div>
        <button onclick="closeQuadTestModal()" class="w-8 h-8 rounded-lg bg-white/80 hover:bg-slate-200 text-slate-500 flex items-center justify-center transition font-bold text-lg">
          ✕
        </button>
      </div>

      <!-- Body -->
      <div class="p-5 overflow-y-auto space-y-4 flex-1">
        <!-- 4 Bot Selector Tabs -->
        <div class="grid grid-cols-4 gap-2 bg-slate-100 p-1.5 rounded-xl text-xs font-bold text-center">
          <button id="quad-tab-bot1" onclick="switchQuadTestBot('bot1')" class="py-2 rounded-lg bg-white text-indigo-700 shadow-xs transition">
            🎓 Bot 1 (HUIT)
          </button>
          <button id="quad-tab-bot2" onclick="switchQuadTestBot('bot2')" class="py-2 rounded-lg text-slate-600 hover:text-slate-900 transition">
            ✈️ Bot 2 (VAA)
          </button>
          <button id="quad-tab-bot3" onclick="switchQuadTestBot('bot3')" class="py-2 rounded-lg text-slate-600 hover:text-slate-900 transition">
            🔴 Bot 3 (IUH)
          </button>
          <button id="quad-tab-bot4" onclick="switchQuadTestBot('bot4')" class="py-2 rounded-lg text-slate-600 hover:text-slate-900 transition">
            🏛️ Bot 4 (UFM)
          </button>
        </div>

        <!-- Custom message input -->
        <div>
          <label class="block text-xs font-bold text-slate-700 mb-1">Nội dung tin nhắn test (Để trống để dùng mẫu chuẩn @All):</label>
          <input type="text" id="quad-custom-msg" placeholder="Ví dụ: 🔔 Bot test tín hiệu Zalo hoạt động tốt..." class="w-full px-3 py-2 text-xs rounded-xl border border-slate-200 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500">
        </div>

        <!-- Action bar for selected bot -->
        <div class="flex items-center justify-between bg-slate-50 p-3 rounded-xl border border-slate-200">
          <div>
            <span id="quad-bot-title" class="text-xs font-bold text-slate-800">Bot 1 - HUIT</span>
            <span id="quad-groups-summary" class="text-[11px] text-slate-500 ml-2">Đang tải...</span>
          </div>
          <button id="btn-test-all-quad" onclick="triggerTestAllForCurrentBot()" class="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-bold shadow-xs transition flex items-center gap-1.5">
            <i class="fa-solid fa-paper-plane"></i> Gửi Test Tất Cả Nhóm
          </button>
        </div>

        <!-- Target Groups List -->
        <div class="space-y-2">
          <label class="block text-xs font-bold text-slate-700">Danh sách nhóm mục tiêu của Bot này (Bấm "Gửi Test" từng nhóm):</label>
          <div id="quad-groups-list" class="space-y-2 max-h-64 overflow-y-auto pr-1">
            <!-- Rendered dynamically -->
          </div>
        </div>

        <!-- Live status / log output -->
        <div id="quad-test-status" class="hidden p-3 rounded-xl text-xs font-medium border"></div>
      </div>

      <!-- Footer -->
      <div class="p-3 px-6 border-t border-slate-100 bg-slate-50 flex items-center justify-between text-xs text-slate-500">
        <span>💡 Lệnh trong Zalo: <code class="bg-white px-1.5 py-0.5 rounded border font-mono text-indigo-600">/test &lt;tên nhóm&gt;</code> hoặc <code class="bg-white px-1.5 py-0.5 rounded border font-mono text-indigo-600">/testall</code></span>
        <button onclick="closeQuadTestModal()" class="px-4 py-1.5 bg-slate-200 hover:bg-slate-300 text-slate-700 font-bold rounded-xl transition">
          Đóng
        </button>
      </div>
    </div>
  </div>

  <script>
    let currentQuadBot = 'bot1';
    let quadBotsData = {};

    async function openQuadTestModal(botId = 'bot1') {
      const modal = document.getElementById('quad-test-modal');
      if (modal) modal.classList.remove('hidden');
      await loadQuadTargetGroups();
      switchQuadTestBot(botId);
    }

    function closeQuadTestModal() {
      const modal = document.getElementById('quad-test-modal');
      if (modal) modal.classList.add('hidden');
    }

    async function loadQuadTargetGroups() {
      try {
        const res = await fetch('/api/zalo/quad-target-groups');
        const data = await res.json();
        if (data.status === 'ok') {
          data.bots.forEach(b => {
            quadBotsData[b.bot_id] = b;
          });
        }
      } catch (err) {
        console.error('Lỗi tải danh sách nhóm quad:', err);
      }
    }

    function switchQuadTestBot(botId) {
      currentQuadBot = botId;
      ['bot1', 'bot2', 'bot3', 'bot4'].forEach(b => {
        const tab = document.getElementById(`quad-tab-${b}`);
        if (tab) {
          if (b === botId) {
            tab.className = 'py-2 rounded-lg bg-white text-indigo-700 shadow-xs transition';
          } else {
            tab.className = 'py-2 rounded-lg text-slate-600 hover:text-slate-900 transition';
          }
        }
      });

      const botData = quadBotsData[botId];
      if (!botData) return;

      const titleEl = document.getElementById('quad-bot-title');
      if (titleEl) titleEl.innerText = botData.bot_name;

      const groups = botData.groups || [];
      const enabledCount = groups.filter(g => g.enabled).length;
      const summaryEl = document.getElementById('quad-groups-summary');
      if (summaryEl) summaryEl.innerText = `(${enabledCount}/${groups.length} nhóm đang bật)`;

      const container = document.getElementById('quad-groups-list');
      if (!container) return;

      if (groups.length === 0) {
        container.innerHTML = '<div class="p-4 text-center text-slate-400 text-xs bg-slate-50 rounded-xl">Chưa cấu hình nhóm Zalo nào cho Bot này.</div>';
        return;
      }

      container.innerHTML = groups.map(g => {
        const isUser = (g.type || '').toUpperCase() === 'USER';
        const typeBadge = isUser ? '<span class="text-[10px] bg-purple-100 text-purple-700 font-bold px-2 py-0.5 rounded-full">Cá nhân</span>' : '<span class="text-[10px] bg-blue-100 text-blue-700 font-bold px-2 py-0.5 rounded-full">Nhóm</span>';
        const statusBadge = g.enabled ? '<span class="text-[10px] bg-emerald-100 text-emerald-800 font-semibold px-2 py-0.5 rounded-full">Đang nhận tin</span>' : '<span class="text-[10px] bg-slate-200 text-slate-600 font-semibold px-2 py-0.5 rounded-full">Đã tắt</span>';

        return `
          <div class="p-3 bg-white hover:bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-between transition">
            <div class="flex items-center gap-3">
              <div class="w-9 h-9 rounded-xl ${g.enabled ? 'bg-indigo-100 text-indigo-700' : 'bg-slate-100 text-slate-400'} flex items-center justify-center font-bold text-sm">
                <i class="fa-solid ${isUser ? 'fa-user' : 'fa-users'}"></i>
              </div>
              <div>
                <div class="flex items-center gap-2">
                  <span class="text-xs font-bold text-slate-900">${g.name}</span>
                  ${typeBadge}
                  ${statusBadge}
                </div>
                <div class="text-[11px] text-slate-400 font-mono mt-0.5">ID: ${g.id}</div>
              </div>
            </div>

            <button onclick="sendTestFromQuadModal('${g.id}', '${g.name}', '${g.type || 'GROUP'}', '${botId}')" class="px-3 py-1.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 rounded-lg text-xs font-bold transition flex items-center gap-1.5">
              <i class="fa-solid fa-paper-plane text-xs"></i> Gửi Test
            </button>
          </div>
        `;
      }).join('');
    }

    async function sendTestFromQuadModal(targetId, targetName, targetType, botId) {
      const statusDiv = document.getElementById('quad-test-status');
      if (statusDiv) {
        statusDiv.className = 'p-3 rounded-xl text-xs font-medium border bg-amber-50 border-amber-200 text-amber-800 block';
        statusDiv.innerHTML = `<i class="fa-solid fa-spinner fa-spin mr-1"></i> Đang gửi tin nhắn test tới "${targetName}" (${targetId})...`;
      }

      const customMsg = document.getElementById('quad-custom-msg')?.value.trim() || '';

      try {
        const res = await fetch('/api/zalo/send-test-target', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            bot_id: botId,
            target_id: targetId,
            target_type: targetType,
            target_name: targetName,
            custom_message: customMsg || null
          })
        });
        const data = await res.json();
        if (res.ok && data.success) {
          if (statusDiv) {
            statusDiv.className = 'p-3 rounded-xl text-xs font-medium border bg-emerald-50 border-emerald-200 text-emerald-800 block';
            statusDiv.innerHTML = `✅ <b>Thành công!</b> ${data.message}`;
          }
        } else {
          if (statusDiv) {
            statusDiv.className = 'p-3 rounded-xl text-xs font-medium border bg-rose-50 border-rose-200 text-rose-800 block';
            statusDiv.innerHTML = `❌ <b>Lỗi:</b> ${data.detail || data.message || 'Không thể gửi tin'}`;
          }
        }
      } catch (err) {
        if (statusDiv) {
          statusDiv.className = 'p-3 rounded-xl text-xs font-medium border bg-rose-50 border-rose-200 text-rose-800 block';
          statusDiv.innerHTML = `❌ <b>Lỗi kết nối:</b> ${err}`;
        }
      }
    }

    async function triggerTestAllForCurrentBot() {
      const botName = quadBotsData[currentQuadBot]?.bot_name || currentQuadBot;
      if (!confirm(`Bạn có chắc muốn gửi tin nhắn TEST tới TẤT CẢ các nhóm đang bật của ${botName}?`)) return;

      const statusDiv = document.getElementById('quad-test-status');
      if (statusDiv) {
        statusDiv.className = 'p-3 rounded-xl text-xs font-medium border bg-amber-50 border-amber-200 text-amber-800 block';
        statusDiv.innerHTML = `<i class="fa-solid fa-spinner fa-spin mr-1"></i> Đang gửi tin nhắn test lần lượt tới các nhóm...`;
      }

      try {
        const res = await fetch('/api/zalo/send-test-all-groups', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ bot_id: currentQuadBot })
        });
        const data = await res.json();
        if (res.ok && data.status === 'ok') {
          if (statusDiv) {
            statusDiv.className = 'p-3 rounded-xl text-xs font-medium border bg-emerald-50 border-emerald-200 text-emerald-800 block';
            statusDiv.innerHTML = `✅ <b>Hoàn tất!</b> Đã gửi thành công ${data.success_count}/${data.total} nhóm của ${data.bot_name}.`;
          }
        } else {
          if (statusDiv) {
            statusDiv.className = 'p-3 rounded-xl text-xs font-medium border bg-rose-50 border-rose-200 text-rose-800 block';
            statusDiv.innerHTML = `❌ <b>Lỗi:</b> ${data.detail || 'Không thể gửi test tất cả'}`;
          }
        }
      } catch (err) {
        if (statusDiv) {
          statusDiv.className = 'p-3 rounded-xl text-xs font-medium border bg-rose-50 border-rose-200 text-rose-800 block';
          statusDiv.innerHTML = `❌ <b>Lỗi kết nối:</b> ${err}`;
        }
      }
    }
  </script>
"""

# Replace all </body> tags in web_app.py with modal_component + </body>
if "id=\"quad-test-modal\"" not in code:
    code = code.replace("</body>", modal_component + "\n</body>")
    print("Injected quad-test-modal into all HTML views in web_app.py!")

with open(WEB_APP_PATH, "w", encoding="utf-8") as f:
    f.write(code)
print("Saved C:\\Users\\Admin\\Documents\\HUIT\\web_app.py successfully!")

# ================= 2. PATCH vaa/ufm/web_app.py =================
with open(UFM_WEB_APP_PATH, "r", encoding="utf-8") as f:
    ufm_code = f.read()

# Update triggerTestZalo in UFM to support targetId, targetName, targetType
old_trigger_test = """    async function triggerTestZalo(targetId = null) {
      Swal.fire({ title: 'Đang gửi thông báo thử nghiệm vào Zalo...', allowOutsideClick: false, didOpen: () => { Swal.showLoading(); } });
      const url = targetId ? `/api/test-zalo?target_id=${targetId}` : '/api/test-zalo';
      const res = await fetch(url, { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        Swal.fire('Đã gửi!', data.message, 'success');
      } else {
        Swal.fire('Lỗi', data.message, 'error');
      }
      fetchStatus();
      fetchLogs();
    }"""

new_trigger_test = """    async function triggerTestZalo(targetId = null, targetName = '', targetType = 'GROUP') {
      if (targetId) {
        const ans = await Swal.fire({
          title: '🧪 Xác nhận gửi tin TEST?',
          text: `Gửi tin nhắn test vào: "${targetName || targetId}" (ID: ${targetId})`,
          icon: 'question',
          showCancelButton: true,
          confirmButtonText: 'Gửi ngay',
          cancelButtonText: 'Hủy'
        });
        if (!ans.isConfirmed) return;
      }
      Swal.fire({ title: 'Đang gửi thông báo thử nghiệm vào Zalo...', allowOutsideClick: false, didOpen: () => { Swal.showLoading(); } });
      try {
        const res = await fetch('/api/zalo/send-test-target', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            bot_id: 'bot4',
            target_id: targetId || '7456361874031804652',
            target_type: targetType,
            target_name: targetName || 'demo'
          })
        });
        const data = await res.json();
        if (res.ok && data.success) {
          Swal.fire('Đã gửi!', data.message, 'success');
        } else {
          Swal.fire('Lỗi', data.detail || data.message || 'Lỗi gửi tin', 'error');
        }
      } catch (err) {
        Swal.fire('Lỗi', String(err), 'error');
      }
      fetchStatus();
      fetchLogs();
    }"""

if old_trigger_test in ufm_code:
    ufm_code = ufm_code.replace(old_trigger_test, new_trigger_test)
    print("Patched triggerTestZalo in UFM web_app.py!")

# Update button in UFM renderZaloGroupsConfig
old_ufm_row_btn = """            <button onclick="triggerTestZalo('${g.id}')" class="px-2 py-1 rounded bg-indigo-600/30 hover:bg-indigo-600 text-indigo-300 hover:text-white border border-indigo-500/30 text-[11px] font-medium transition">
              Thử tin
            </button>"""

new_ufm_row_btn = """            <button onclick="triggerTestZalo('${g.id}', '${g.name}', '${g.type || 'GROUP'}')" class="px-2.5 py-1.5 rounded bg-indigo-600/30 hover:bg-indigo-600 text-indigo-300 hover:text-white border border-indigo-500/30 text-[11px] font-medium transition flex items-center gap-1" title="Gửi tin nhắn test riêng vào nhóm này">
              <i class="bi bi-send-fill text-[10px]"></i> Thử tin
            </button>"""

if old_ufm_row_btn in ufm_code:
    ufm_code = ufm_code.replace(old_ufm_row_btn, new_ufm_row_btn)
    print("Patched UFM row button in renderZaloGroupsConfig!")

# Add top button in UFM navbar
ufm_top_btn = """        <!-- Test Zalo 4 Bot Button -->
        <button onclick="openQuadTestModal('bot4')" class="px-3.5 py-1.5 rounded-lg bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white text-xs font-semibold flex items-center gap-1.5 transition shadow-lg shadow-indigo-600/30">
          <i class="bi bi-shield-check text-xs"></i>
          <span>Test Nhóm Zalo (4 Bot)</span>
        </button>
"""
if "triggerSendDemoAlert()" in ufm_code and "openQuadTestModal" not in ufm_code:
    pos = ufm_code.find("<!-- Send Demo Group Alert Button -->")
    if pos != -1:
        ufm_code = ufm_code[:pos] + ufm_top_btn + "\n        " + ufm_code[pos:]
        print("Added Quad Test button to UFM top bar!")

# Add modal to UFM
if "id=\"quad-test-modal\"" not in ufm_code:
    ufm_code = ufm_code.replace("</body>", modal_component + "\n</body>")
    print("Injected quad-test-modal into UFM web_app.py!")

with open(UFM_WEB_APP_PATH, "w", encoding="utf-8") as f:
    f.write(ufm_code)
print("Saved vaa/ufm/web_app.py successfully!")

# Also sync vaa/web_app.py with ROOT web_app.py if needed
if os.path.exists(VAA_WEB_APP_PATH):
    with open(VAA_WEB_APP_PATH, "w", encoding="utf-8") as f:
        f.write(code)
    print("Synchronized vaa/web_app.py successfully!")

print("All patches completed successfully!")
