// HUIT Auto Form & Zalo Bot - Frontend Application Controller
let pagesChartInstance = null;
let formRateChartInstance = null;
let autoScroll = true;
let currentConfig = null;

// ==================== KHỞI TẠO HỆ THỐNG ====================
document.addEventListener('DOMContentLoaded', () => {
  lucide.createIcons();
  initCharts();
  refreshAllData();
  initWebSocketLogs();

  // Tự động làm mới số liệu mỗi 6 giây
  setInterval(fetchStats, 6000);
});

function refreshAllData() {
  fetchStats();
  fetchConfig();
  fetchRegistrations();
  fetchRecentPosts();
  fetchNotificationHistory();
  fetchVaaStats();
}

function showToast(message, type = 'info') {
  const toast = document.getElementById('toast');
  const msgElem = document.getElementById('toast-msg');
  msgElem.innerText = message;
  toast.classList.remove('hidden');
  setTimeout(() => {
    toast.classList.add('hidden');
  }, 3500);
}

// ==================== ĐIỀU HƯỚNG TABS ====================
function switchTab(tabId) {
  document.querySelectorAll('.tab-content').forEach(tab => tab.classList.add('hidden'));
  document.querySelectorAll('.nav-item').forEach(btn => {
    btn.classList.remove('text-cyan-400', 'bg-cyan-500/10', 'border', 'border-cyan-500/20', 'text-amber-300', 'bg-amber-500/10', 'border-amber-500/20');
    btn.classList.add('text-slate-300');
  });

  const targetTab = document.getElementById(tabId);
  const targetNav = document.getElementById(`nav-${tabId}`);
  if (targetTab) targetTab.classList.remove('hidden');
  if (targetNav) {
    targetNav.classList.remove('text-slate-300');
    if (tabId === 'tab-vaa') {
      targetNav.classList.add('text-amber-300', 'bg-amber-500/10', 'border', 'border-amber-500/20');
    } else {
      targetNav.classList.add('text-cyan-400', 'bg-cyan-500/10', 'border', 'border-cyan-500/20');
    }
  }

  // Cập nhật tiêu đề Topbar
  const titles = {
    'tab-overview': 'Tổng Quan Số Liệu (HUIT)',
    'tab-zalo': 'Quản Lý Nhóm & Cá Nhân Zalo (HUIT)',
    'tab-fanpages': 'Danh Sách Mục Tiêu Fanpage (HUIT)',
    'tab-profile': 'Hồ Sơ Sinh Viên & Cấu Hình Gemini AI',
    'tab-registrations': 'Lịch Sử Nộp Google Form',
    'tab-history': 'Lịch Sử Thông Báo & Hoạt Động (HUIT)',
    'tab-terminal': 'Live Console Streaming',
    'tab-supabase': 'Đồng Bộ Supabase Cloud',
    'tab-vaa': '✈️ Bot VAA - Học Viện Hàng Không Việt Nam'
  };
  document.getElementById('topbar-title').innerText = titles[tabId] || 'Hệ Thống Quản Trị';
  if (tabId === 'tab-history') {
    fetchNotificationHistory();
  } else if (tabId === 'tab-vaa') {
    fetchVaaStats();
    fetchVaaConfig();
    fetchVaaHistory();
  }
  lucide.createIcons();
}

// ==================== BIỂU ĐỒ CHART.JS ====================
function initCharts() {
  const ctxPages = document.getElementById('chart-pages').getContext('2d');
  pagesChartInstance = new Chart(ctxPages, {
    type: 'bar',
    data: {
      labels: ['Đang tải...'],
      datasets: [{
        label: 'Số bài phát hiện',
        data: [0],
        backgroundColor: 'rgba(6, 182, 212, 0.6)',
        borderColor: '#06b6d4',
        borderWidth: 1,
        borderRadius: 6
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94a3b8', font: { size: 10 } } },
        y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#94a3b8', stepSize: 1 } }
      }
    }
  });

  const ctxForm = document.getElementById('chart-form-rate').getContext('2d');
  formRateChartInstance = new Chart(ctxForm, {
    type: 'doughnut',
    data: {
      labels: ['Thành công', 'Thất bại'],
      datasets: [{
        data: [1, 0],
        backgroundColor: ['#10b981', '#f43f5e'],
        borderWidth: 0
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: 'bottom', labels: { color: '#cbd5e1', font: { size: 11 } } } },
      cutout: '70%'
    }
  });
}

// ==================== LẤY DỮ LIỆU THỐNG KÊ ====================
async function fetchStats() {
  try {
    const res = await fetch('/api/stats');
    if (!res.ok) return;
    const data = await res.json();

    // 1. Cập nhật trạng thái Bot & Uptime
    const bot = data.bot || {};
    const badge = document.getElementById('sidebar-bot-badge');
    const topUptime = document.getElementById('topbar-uptime');
    const btnStart = document.getElementById('btn-start');
    const btnStop = document.getElementById('btn-stop');

    if (bot.running) {
      badge.innerText = 'ĐANG CHẠY';
      badge.className = 'px-2 py-0.5 rounded-full font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 animate-pulse';
      topUptime.innerText = `Thời gian chạy: ${bot.uptime_human} (PID: ${bot.pid})`;
      btnStart.classList.add('opacity-50', 'pointer-events-none');
      btnStop.classList.remove('opacity-50', 'pointer-events-none');
    } else {
      badge.innerText = 'ĐÃ DỪNG';
      badge.className = 'px-2 py-0.5 rounded-full font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20';
      topUptime.innerText = 'Thời gian chạy: Đang dừng';
      btnStart.classList.remove('opacity-50', 'pointer-events-none');
      btnStop.classList.add('opacity-50', 'pointer-events-none');
    }

    // 2. Cập nhật thẻ KPI
    document.getElementById('stat-total-posts').innerText = data.total_posts_scanned || 0;
    document.getElementById('stat-sent-group').innerText = data.total_sent_group || 0;
    document.getElementById('stat-form-success').innerText = data.total_registered_success || 0;
    document.getElementById('stat-sent-admin').innerText = data.total_sent_admin || 0;

    // 3. Cập nhật biểu đồ Fanpage
    if (pagesChartInstance && data.pages_breakdown && data.pages_breakdown.length > 0) {
      pagesChartInstance.data.labels = data.pages_breakdown.map(p => p.name.length > 18 ? p.name.substring(0, 18) + '...' : p.name);
      pagesChartInstance.data.datasets[0].data = data.pages_breakdown.map(p => p.count);
      pagesChartInstance.update();
    }

    // 4. Cập nhật biểu đồ Form
    const successCount = data.total_registered_success || 0;
    const failedCount = data.total_registered_failed || 0;
    document.getElementById('rate-success').innerText = successCount;
    document.getElementById('rate-failed').innerText = failedCount;
    if (formRateChartInstance) {
      formRateChartInstance.data.datasets[0].data = [successCount || (failedCount ? 0 : 1), failedCount];
      formRateChartInstance.update();
    }

    // 5. Cập nhật badge Supabase
    const sb = data.supabase || {};
    const sbBadge = document.getElementById('sidebar-supabase-badge');
    if (sb.connected) {
      sbBadge.innerText = 'ONLINE';
      sbBadge.className = 'px-2 py-0.5 rounded-full font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20';
    } else {
      sbBadge.innerText = 'OFFLINE';
      sbBadge.className = 'px-2 py-0.5 rounded-full font-semibold bg-slate-500/10 text-slate-400 border border-slate-500/20';
    }

  } catch (err) {
    console.error('Lỗi khi fetchStats:', err);
  }
}

// ==================== LẤY & HIỂN THỊ CẤU HÌNH ====================
async function fetchConfig() {
  try {
    const res = await fetch('/api/config');
    if (!res.ok) return;
    currentConfig = await res.json();

    // 1. Nhóm Zalo & Cá nhân Zalo
    renderZaloGroups(currentConfig.zalo?.target_groups || []);
    renderZaloUsers(currentConfig.zalo?.target_users || []);

    // 2. Fanpages mục tiêu
    renderFanpages(currentConfig.targets || []);

    // 3. Profile sinh viên & Session Gmail
    const prof = currentConfig.auto_form_registration?.student_profile || {};
    document.getElementById('prof-fullname').value = prof.fullname || 'Trần Lê Phát';
    document.getElementById('prof-student-id').value = prof.student_id || '2040260270';
    document.getElementById('prof-class-name').value = prof.class_name || '26QHQTMK02';
    document.getElementById('prof-email').value = prof.email || 'yukilegit10@gmail.com';
    document.getElementById('prof-phone').value = prof.phone || '03843465437';
    document.getElementById('prof-faculty').value = prof.faculty || 'Khoa Thương mại';
    document.getElementById('prof-gender').value = prof.gender || 'Nam';
    if (document.getElementById('prof-google-session')) {
      document.getElementById('prof-google-session').value = prof.google_session_file || 'clone_01.json';
    }
    checkGoogleSessions();

    // 4. Cấu hình AI & Form
    const autoCfg = currentConfig.auto_form_registration || {};
    document.getElementById('cfg-gemini-key').value = autoCfg.gemini_api_key || '';
    document.getElementById('cfg-auto-form-enabled').checked = Boolean(autoCfg.enabled);
    document.getElementById('cfg-headless').checked = !Boolean(autoCfg.headless);

  } catch (err) {
    console.error('Lỗi khi fetchConfig:', err);
  }
}

async function checkGoogleSessions() {
  try {
    const res = await fetch('/api/google/sessions');
    if (res.ok) {
      const data = await res.json();
      const sessions = data.sessions || [];
      const badge = document.getElementById('session-badge');
      if (badge) {
        if (sessions.length > 0) {
          badge.innerText = `✅ ĐÃ ĐĂNG NHẬP GMAIL (${sessions[0].filename})`;
          badge.className = 'text-[10px] px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-mono';
        } else {
          badge.innerText = '⚠️ CHƯA CÓ FILE PHIÊN';
          badge.className = 'text-[10px] px-2 py-0.5 rounded bg-amber-500/20 text-amber-400 font-mono';
        }
      }
    }
  } catch (err) {
    console.error('Lỗi checkGoogleSessions:', err);
  }
}

function renderZaloGroups(groups) {
  const container = document.getElementById('zalo-groups-list');
  if (!container) return;
  if (!groups || groups.length === 0) {
    container.innerHTML = '<p class="text-xs text-slate-500 py-3 col-span-2">Chưa có nhóm Zalo nào. Bấm nút "+ Thêm Nhóm Zalo" ở trên để nhận tin.</p>';
    return;
  }

  container.innerHTML = groups.map(g => `
    <div class="p-4 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-between">
      <div class="flex items-center gap-3 overflow-hidden">
        <div class="w-9 h-9 rounded-lg bg-blue-500/10 text-blue-400 flex items-center justify-center flex-shrink-0">
          <i data-lucide="users" class="w-4 h-4"></i>
        </div>
        <div class="truncate">
          <h4 class="text-sm font-semibold text-white truncate">${g.name}</h4>
          <p class="text-xs text-slate-400 font-mono">ID: ${g.id}</p>
        </div>
      </div>
      <div class="flex items-center gap-3 flex-shrink-0">
        <label class="relative inline-flex items-center cursor-pointer">
          <input type="checkbox" ${g.enabled ? 'checked' : ''} onchange="toggleRecipient('GROUP', '${g.id}', this.checked)" class="sr-only peer">
          <div class="w-11 h-6 bg-slate-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-cyan-600"></div>
        </label>
        <button onclick="deleteRecipient('GROUP', '${g.id}', '${g.name}')" title="Xóa nhóm này" class="p-1.5 rounded-lg text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 transition">
          <i data-lucide="trash-2" class="w-4 h-4"></i>
        </button>
      </div>
    </div>
  `).join('');
  lucide.createIcons();
}

function renderZaloUsers(users) {
  const container = document.getElementById('zalo-users-list');
  if (!container) return;
  if (!users || users.length === 0) {
    container.innerHTML = '<p class="text-xs text-slate-500 py-3 col-span-2">Chưa có cá nhân Zalo nào. Bấm nút "+ Thêm Cá Nhân Zalo" ở trên để gửi riêng.</p>';
    return;
  }

  container.innerHTML = users.map(u => `
    <div class="p-4 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-between">
      <div class="flex items-center gap-3 overflow-hidden">
        <div class="w-9 h-9 rounded-lg bg-purple-500/10 text-purple-400 flex items-center justify-center flex-shrink-0">
          <i data-lucide="user" class="w-4 h-4"></i>
        </div>
        <div class="truncate">
          <h4 class="text-sm font-semibold text-white truncate">${u.name}</h4>
          <p class="text-xs text-slate-400 font-mono">UID: ${u.id}</p>
        </div>
      </div>
      <div class="flex items-center gap-3 flex-shrink-0">
        <label class="relative inline-flex items-center cursor-pointer">
          <input type="checkbox" ${u.enabled ? 'checked' : ''} onchange="toggleRecipient('USER', '${u.id}', this.checked)" class="sr-only peer">
          <div class="w-11 h-6 bg-slate-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-purple-600"></div>
        </label>
        <button onclick="deleteRecipient('USER', '${u.id}', '${u.name}')" title="Xóa cá nhân này" class="p-1.5 rounded-lg text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 transition">
          <i data-lucide="trash-2" class="w-4 h-4"></i>
        </button>
      </div>
    </div>
  `).join('');
  lucide.createIcons();
}

function openAddRecipientModal(type = 'GROUP') {
  document.getElementById('recipient-type').value = type;
  const select = document.getElementById('recipient-type-select');
  if (select) select.value = type;
  const title = document.getElementById('modal-recipient-title');
  if (title) {
    title.innerHTML = type === 'GROUP' 
      ? '<i data-lucide="users" class="w-4 h-4 text-cyan-400"></i><span>Thêm Nhóm Zalo Nhận Tin</span>'
      : '<i data-lucide="user-plus" class="w-4 h-4 text-purple-400"></i><span>Thêm Cá Nhân Zalo Nhận Tin</span>';
  }
  document.getElementById('recipient-name').value = '';
  document.getElementById('recipient-id').value = '';
  document.getElementById('modal-add-recipient').classList.remove('hidden');
  lucide.createIcons();
}

function closeAddRecipientModal() {
  document.getElementById('modal-add-recipient').classList.add('hidden');
}

async function submitAddRecipient(e) {
  e.preventDefault();
  const type = document.getElementById('recipient-type').value;
  const name = document.getElementById('recipient-name').value.trim();
  const id = document.getElementById('recipient-id').value.trim();

  if (!id) {
    showToast('Vui lòng nhập ID Zalo!', 'error');
    return;
  }

  try {
    const res = await fetch('/api/zalo/recipient/add', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type, id, name })
    });
    const data = await res.json();
    if (res.ok) {
      showToast(data.message || 'Thêm người nhận thành công!');
      closeAddRecipientModal();
      fetchConfig();
      fetchStats();
    } else {
      showToast(data.detail || 'Có lỗi xảy ra', 'error');
    }
  } catch (err) {
    showToast('Lỗi gửi yêu cầu: ' + err, 'error');
  }
}

async function toggleRecipient(type, id, enabled) {
  try {
    try { localStorage.removeItem('huit_recipient_overrides'); } catch(e){}

    const res = await fetch('/api/zalo/recipient/toggle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type, id, enabled })
    });
    const data = await res.json();
    showToast(data.message || 'Đã cập nhật trạng thái!');
    fetchConfig();
  } catch (err) {
    showToast('Lỗi cập nhật: ' + err, 'error');
  }
}

async function deleteRecipient(type, id, name) {
  const typeName = type === 'GROUP' ? 'nhóm' : 'cá nhân';
  if (!confirm(`Bạn có chắc muốn xóa ${typeName} "${name}" (${id}) khỏi danh sách nhận tin?`)) {
    return;
  }
  try {
    const res = await fetch('/api/zalo/recipient/delete', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type, id })
    });
    const data = await res.json();
    showToast(data.message || 'Đã xóa thành công!');
    fetchConfig();
    fetchStats();
  } catch (err) {
    showToast('Lỗi khi xóa: ' + err, 'error');
  }
}

function renderFanpages(targets) {
  const container = document.getElementById('fanpages-list');
  if (!targets || targets.length === 0) {
    container.innerHTML = '<p class="text-xs text-slate-500">Không có fanpage nào.</p>';
    return;
  }

  container.innerHTML = targets.map((t, idx) => `
    <div class="p-4 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-between">
      <div class="flex items-center gap-3 overflow-hidden">
        <div class="w-9 h-9 rounded-lg bg-purple-500/10 text-purple-400 flex items-center justify-center flex-shrink-0">
          <i data-lucide="globe" class="w-4 h-4"></i>
        </div>
        <div class="truncate">
          <h4 class="text-sm font-semibold text-white truncate">${t.name}</h4>
          <a href="${t.url}" target="_blank" class="text-xs text-cyan-400 hover:underline truncate block">${t.url}</a>
        </div>
      </div>
      <span class="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">Theo dõi</span>
    </div>
  `).join('');
  lucide.createIcons();
}

async function toggleGroup(id, enabled) {
  return toggleRecipient('GROUP', id, enabled);
}

async function saveStudentProfile(e) {
  e.preventDefault();
  if (!currentConfig) return;

  const prof = {
    fullname: document.getElementById('prof-fullname').value.trim(),
    student_id: document.getElementById('prof-student-id').value.trim(),
    class_name: document.getElementById('prof-class-name').value.trim(),
    email: document.getElementById('prof-email').value.trim(),
    phone: document.getElementById('prof-phone').value.trim(),
    faculty: document.getElementById('prof-faculty').value.trim(),
    gender: document.getElementById('prof-gender').value,
    google_session_file: document.getElementById('prof-google-session')?.value.trim() || 'clone_01.json'
  };

  currentConfig.auto_form_registration.student_profile = prof;
  currentConfig.auto_form_registration.google_session_file = prof.google_session_file;
  
  if (!currentConfig.auto_form_registration.students) {
    currentConfig.auto_form_registration.students = [];
  }
  if (currentConfig.auto_form_registration.students.length > 0) {
    currentConfig.auto_form_registration.students[0] = { ...prof, enabled: true };
  } else {
    currentConfig.auto_form_registration.students.push({ ...prof, enabled: true });
  }

  try {
    const res = await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(currentConfig)
    });
    if (res.ok) {
      showToast('🎉 Đã lưu thông tin sinh viên & phiên Gmail tương ứng!');
      fetchConfig();
    }
  } catch (err) {
    showToast('Lỗi lưu thông tin: ' + err, 'error');
  }
}

async function saveAiKey() {
  if (!currentConfig) return;
  const key = document.getElementById('cfg-gemini-key').value.trim();
  currentConfig.auto_form_registration.gemini_api_key = key;

  try {
    const res = await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(currentConfig)
    });
    if (res.ok) {
      showToast('✨ Đã cập nhật Gemini API Key!');
    }
  } catch (err) {
    showToast('Lỗi lưu key: ' + err, 'error');
  }
}

async function toggleFormSetting(field, value) {
  if (!currentConfig) return;
  currentConfig.auto_form_registration[field] = value;
  try {
    await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(currentConfig)
    });
    showToast(`Đã ${value ? 'bật' : 'tắt'} ${field}!`);
  } catch (err) {
    showToast('Lỗi cập nhật: ' + err, 'error');
  }
}

// ==================== BÀI VIẾT & LỊCH SỬ NỘP FORM ====================
async function fetchRecentPosts() {
  try {
    const res = await fetch('/api/posts?limit=15');
    if (!res.ok) return;
    const posts = await res.json();
    const tbody = document.getElementById('table-recent-posts');
    if (!posts || posts.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" class="px-5 py-6 text-center text-slate-500">Chưa có bài viết nào được quét.</td></tr>';
      return;
    }

    tbody.innerHTML = posts.map(p => `
      <tr class="hover:bg-slate-800/30 transition">
        <td class="px-5 py-3 font-medium text-white">${p.page_name}</td>
        <td class="px-5 py-3">
          <span class="px-2 py-0.5 rounded text-xs bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">${p.matched_keywords || 'Tất cả'}</span>
        </td>
        <td class="px-5 py-3">
          ${p.form_url ? `<a href="${p.form_url}" target="_blank" class="text-xs text-brand-500 hover:underline flex items-center gap-1"><i data-lucide="external-link" class="w-3 h-3"></i> Link Form</a>` : '<span class="text-slate-500 text-xs">-</span>'}
        </td>
        <td class="px-5 py-3">
          ${p.sent_group ? '<span class="text-xs px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">Đã bắn Nhóm</span>' : '<span class="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-500">Chưa bắn</span>'}
        </td>
        <td class="px-5 py-3 text-xs text-slate-400">${p.created_at}</td>
      </tr>
    `).join('');
    lucide.createIcons();
  } catch (err) {
    console.error('Lỗi khi fetchRecentPosts:', err);
  }
}

async function fetchRegistrations() {
  try {
    const res = await fetch('/api/registrations?limit=50');
    if (!res.ok) return;
    const regs = await res.json();
    const tbody = document.getElementById('table-registrations-body');
    if (!regs || regs.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" class="px-5 py-6 text-center text-slate-500">Chưa có lượt nộp form tự động nào.</td></tr>';
      return;
    }

    tbody.innerHTML = regs.map(r => {
      // 1. Thời gian nộp form
      const timeStr = r.created_at || 'Vừa xong';

      // 2. Thông tin đã điền
      let filledHtml = '';
      let items = [];
      if (r.filled_fields && Array.isArray(r.filled_fields) && r.filled_fields.length > 0) {
        items = r.filled_fields;
      } else if (r.message) {
        items = r.message.split(/[,|;]/).map(s => s.trim()).filter(Boolean);
      }
      if (items.length > 0) {
        filledHtml = `<div class="flex flex-wrap gap-1.5 max-w-sm">` + items.map(it => 
          `<span class="px-2 py-0.5 rounded text-[11px] bg-slate-800 text-cyan-300 border border-slate-700 font-mono">${it}</span>`
        ).join('') + `</div>`;
      } else {
        filledHtml = `<span class="text-xs text-slate-400">${r.message || 'Họ tên, MSSV, Lớp, SĐT, Email'}</span>`;
      }

      // 3. Ảnh đã nộp form
      let imgHtml = '';
      const rawPath = r.screenshot_path || '';
      const shotFilename = rawPath ? rawPath.split(/[\\/]/).pop() : '';
      const imgSrc = r.screenshot_base64 || (shotFilename ? `/screenshots/${shotFilename}` : '');
      if (imgSrc) {
        imgHtml = `
          <div class="flex items-center gap-2">
            <img src="${imgSrc}" onclick="openModalScreenshot(this.src)" class="w-14 h-9 object-cover rounded-md border border-cyan-500/40 cursor-pointer hover:border-cyan-400 hover:scale-105 transition shadow-sm" title="Click để phóng to ảnh nộp form" onerror="this.onerror=null; this.src='https://placehold.co/100x60/0f172a/38bdf8?text=Anh+Nop'">
            <button onclick="openModalScreenshot('${imgSrc}')" class="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-[11px] text-cyan-300 border border-slate-700 transition flex items-center gap-1">
              <i data-lucide="zoom-in" class="w-3 h-3"></i> Xem Ảnh
            </button>
          </div>
        `;
      } else {
        imgHtml = '<span class="text-xs text-slate-500">Chưa có ảnh</span>';
      }

      return `
        <tr class="hover:bg-slate-800/30 transition">
          <td class="px-5 py-3 text-xs text-cyan-400 font-mono whitespace-nowrap">
            <i data-lucide="clock" class="w-3.5 h-3.5 inline mr-1 text-slate-400"></i>${timeStr}
          </td>
          <td class="px-5 py-3 font-medium text-white">${r.page_name}</td>
          <td class="px-5 py-3">
            <div class="font-medium text-white text-xs">${r.student_name}</div>
            <div class="text-[11px] text-slate-400 font-mono">${r.student_id}</div>
          </td>
          <td class="px-5 py-3">
            <a href="${r.form_url}" target="_blank" class="text-xs text-brand-500 hover:underline truncate max-w-[150px] block flex items-center gap-1" title="${r.form_url}">
              <i data-lucide="external-link" class="w-3 h-3 flex-shrink-0"></i> Mở Form
            </a>
          </td>
          <td class="px-5 py-3">
            ${filledHtml}
          </td>
          <td class="px-5 py-3">
            ${imgHtml}
          </td>
          <td class="px-5 py-3">
            ${r.status === 'SUCCESS' ? 
              '<span class="px-2.5 py-1 rounded-full text-[11px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 whitespace-nowrap">THÀNH CÔNG</span>' : 
              '<span class="px-2.5 py-1 rounded-full text-[11px] font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20 whitespace-nowrap">LỖI / CHÚ Ý</span>'}
          </td>
        </tr>
      `;
    }).join('');
    lucide.createIcons();
  } catch (err) {
    console.error('Lỗi khi fetchRegistrations:', err);
  }
}

// ==================== ĐIỀU KHIỂN TIẾN TRÌNH BOT ====================
async function botAction(action) {
  try {
    const res = await fetch(`/api/bot/${action}`, { method: 'POST' });
    const data = await res.json();
    showToast(data.message || `Đã thực hiện lệnh: ${action.toUpperCase()}!`);
    fetchStats();
  } catch (err) {
    showToast('Lỗi thực hiện lệnh bot: ' + err, 'error');
  }
}

// ==================== LIVE WEBSOCKET LOGS ====================
function initWebSocketLogs() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws/logs`;
  const terminal = document.getElementById('terminal-screen');

  try {
    const socket = new WebSocket(wsUrl);

    socket.onopen = () => {
      appendTerminal('✅ [WebSocket] Đã kết nối luồng logs thời gian thực từ Bot.');
    };

    socket.onmessage = (event) => {
      appendTerminal(event.data);
    };

    socket.onclose = () => {
      appendTerminal('⚠️ [WebSocket] Đã ngắt kết nối. Thử kết nối lại sau 4s...');
      setTimeout(initWebSocketLogs, 4000);
    };

    socket.onerror = () => {
      socket.close();
    };
  } catch (err) {
    console.error('WebSocket Error:', err);
  }
}

function appendTerminal(text) {
  const screen = document.getElementById('terminal-screen');
  const line = document.createElement('div');
  line.innerText = text;
  screen.appendChild(line);

  if (autoScroll) {
    screen.scrollTop = screen.scrollHeight;
  }
}

function clearTerminal() {
  document.getElementById('terminal-screen').innerHTML = '';
}

function toggleAutoScroll() {
  autoScroll = !autoScroll;
  const btn = document.getElementById('btn-autoscroll');
  btn.innerText = `Tự cuộn: ${autoScroll ? 'BẬT' : 'TẮT'}`;
  btn.className = autoScroll ? 
    'px-3 py-1 rounded bg-cyan-600/30 text-cyan-400 border border-cyan-500/30 text-xs' : 
    'px-3 py-1 rounded bg-slate-800 text-slate-400 text-xs';
}

function togglePasswordVisibility(id) {
  const el = document.getElementById(id);
  el.type = el.type === 'password' ? 'text' : 'password';
}

function openModalScreenshot(src) {
  const modalImg = document.getElementById('modal-img');
  if (modalImg) {
    modalImg.onerror = function() {
      this.onerror = null;
      this.src = 'https://placehold.co/600x400/0f172a/38bdf8?text=B%E1%BA%B1ng+Ch%E1%BB%A9ng+%C4%90ang+%C4%90%E1%BB%93ng+B%E1%BB%99';
    };
    modalImg.src = src;
  }
  document.getElementById('modal-screenshot').classList.remove('hidden');
}

function closeModalScreenshot() {
  document.getElementById('modal-screenshot').classList.add('hidden');
}

// ==================== LỊCH SỬ THÔNG BÁO & HOẠT ĐỘNG ====================
let currentHistoryFilter = 'ALL';
let historyDataCache = [];

async function fetchNotificationHistory() {
  try {
    const url = currentHistoryFilter === 'ALL' ? '/api/notifications/history' : `/api/notifications/history?category=${currentHistoryFilter}`;
    const res = await fetch(url);
    if (!res.ok) return;
    const data = await res.json();
    historyDataCache = data.history || [];
    renderNotificationHistory(historyDataCache);
    if (data.summary) {
      renderHistorySummary(data.summary);
    }
  } catch (err) {
    console.error('Lỗi tải lịch sử thông báo:', err);
  }
}

function renderHistorySummary(sum) {
  const lastStartElem = document.getElementById('hist-stat-last-start');
  const uptimeElem = document.getElementById('hist-stat-uptime');
  const totalSentElem = document.getElementById('hist-stat-total-sent');
  const totalFormsElem = document.getElementById('hist-stat-total-forms');
  const lastStopElem = document.getElementById('hist-stat-last-stop');

  if (lastStartElem) {
    lastStartElem.innerText = sum.last_start || 'Chưa ghi nhận';
  }
  if (uptimeElem) {
    uptimeElem.innerText = sum.is_running ? `Đang chạy (${sum.uptime_human})` : 'Đang dừng';
    uptimeElem.className = sum.is_running ? 'text-[11px] text-emerald-400 mt-1 font-semibold' : 'text-[11px] text-slate-400 mt-1';
  }
  if (totalSentElem) {
    totalSentElem.innerText = sum.total_notifications || 0;
  }
  if (totalFormsElem) {
    totalFormsElem.innerText = sum.total_forms || 0;
  }
  if (lastStopElem) {
    lastStopElem.innerText = sum.last_stop || 'Chưa có';
  }
}

function filterHistoryCategory(cat) {
  currentHistoryFilter = cat;
  document.querySelectorAll('.hist-filter-btn').forEach(btn => {
    btn.classList.remove('bg-cyan-600', 'text-white');
    btn.classList.add('bg-slate-800', 'text-slate-300');
  });
  const activeBtn = document.getElementById(`filter-hist-${cat.toLowerCase()}`);
  if (activeBtn) {
    activeBtn.classList.remove('bg-slate-800', 'text-slate-300');
    activeBtn.classList.add('bg-cyan-600', 'text-white');
  }
  fetchNotificationHistory();
}

function renderNotificationHistory(items) {
  const tbody = document.getElementById('table-history-body');
  if (!tbody) return;

  if (!items || items.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="px-5 py-8 text-center text-slate-500">Chưa có thông báo hoặc hoạt động nào trong danh mục này.</td></tr>`;
    return;
  }

  tbody.innerHTML = items.map((it, idx) => {
    let catBadge = '';
    const cat = (it.category || '').toUpperCase();
    const title = (it.title || '').toUpperCase();

    if (cat === 'GROUP') {
      catBadge = '<span class="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">Nhóm Zalo</span>';
    } else if (cat === 'USER') {
      catBadge = '<span class="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">Cá Nhân</span>';
    } else if (cat === 'ADMIN') {
      catBadge = '<span class="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-purple-500/10 text-purple-400 border border-purple-500/20">Admin</span>';
    } else if (cat === 'FORM') {
      catBadge = '<span class="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">Điền Form</span>';
    } else if (cat === 'SYSTEM') {
      if (title.includes('KHỞI ĐỘNG') || title.includes('BẬT')) {
        catBadge = '<span class="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">Bật Bot</span>';
      } else if (title.includes('DỪNG')) {
        catBadge = '<span class="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-rose-500/20 text-rose-300 border border-rose-500/30">Dừng Bot</span>';
      } else {
        catBadge = '<span class="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">Hệ Thống</span>';
      }
    } else {
      catBadge = `<span class="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-slate-800 text-slate-300 border border-slate-700">${cat || 'HỆ THỐNG'}</span>`;
    }

    const st = (it.status || 'SUCCESS').toUpperCase();
    let statusBadge = '';
    if (st === 'SUCCESS') {
      statusBadge = '<span class="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">THÀNH CÔNG</span>';
    } else if (st === 'RUNNING') {
      statusBadge = '<span class="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">ĐANG CHẠY</span>';
    } else if (st === 'STOPPED') {
      statusBadge = '<span class="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-slate-700 text-slate-300 border border-slate-600">ĐÃ DỪNG</span>';
    } else {
      statusBadge = `<span class="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20" title="${it.status}">THẤT BẠI</span>`;
    }

    const cleanContent = (it.content || '').replace(/\n/g, ' ').slice(0, 75);

    return `
      <tr class="hover:bg-slate-800/30 transition">
        <td class="px-5 py-3 text-xs text-slate-400 font-mono whitespace-nowrap">${it.created_at || '-'}</td>
        <td class="px-5 py-3 whitespace-nowrap">${catBadge}</td>
        <td class="px-5 py-3 text-xs font-medium text-white max-w-[180px] truncate" title="${it.recipient_name || ''} (${it.recipient_id || ''})">
          ${it.recipient_name || 'Hệ thống'}
          <span class="block text-[11px] text-slate-500 font-mono">${it.recipient_id || ''}</span>
        </td>
        <td class="px-5 py-3 text-xs text-slate-300 font-medium max-w-[200px] truncate" title="${it.title || ''}">${it.title || 'Thông báo'}</td>
        <td class="px-5 py-3 text-xs text-slate-400 max-w-[280px] truncate">${cleanContent}...</td>
        <td class="px-5 py-3 whitespace-nowrap">${statusBadge}</td>
        <td class="px-5 py-3 text-right whitespace-nowrap">
          <button onclick="openHistoryDetailModal(${idx})" class="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-cyan-400 text-xs transition">
            Xem Chi Tiết
          </button>
        </td>
      </tr>
    `;
  }).join('');
  lucide.createIcons();
}

function openHistoryDetailModal(index) {
  const item = historyDataCache[index];
  if (!item) return;

  document.getElementById('modal-hist-title').innerHTML = `
    <i data-lucide="bell" class="w-4 h-4 text-cyan-400"></i>
    <span>${item.title || 'Chi Tiết Thông Báo'}</span>
  `;
  document.getElementById('modal-hist-meta').innerText = `Đối tượng: ${item.recipient_name || 'N/A'} (${item.recipient_id || ''}) | Lúc: ${item.created_at || 'N/A'} | Loại: ${item.category || 'N/A'}`;
  document.getElementById('modal-hist-content').innerText = item.content || '(Nội dung trống)';
  document.getElementById('modal-history-detail').classList.remove('hidden');
  lucide.createIcons();
}

function closeHistoryDetailModal() {
  document.getElementById('modal-history-detail').classList.add('hidden');
}

async function clearNotificationHistory() {
  if (!confirm('Bạn có chắc chắn muốn xóa toàn bộ lịch sử thông báo và hoạt động không?')) {
    return;
  }
  try {
    const res = await fetch('/api/notifications/history/clear', { method: 'DELETE' });
    const data = await res.json();
    showToast(data.message || 'Đã xóa lịch sử thông báo!');
    fetchNotificationHistory();
  } catch (err) {
    showToast('Lỗi khi xóa lịch sử: ' + err, 'error');
  }
}

// ==================== QUẢN LÝ BOT VAA (HỌC VIỆN HÀNG KHÔNG) ====================
let currentVaaConfig = null;
let vaaHistoryList = [];

async function fetchVaaStats() {
  try {
    const res = await fetch('/api/vaa/stats');
    if (!res.ok) return;
    const data = await res.json();

    const bot = data.bot || {};
    const badgeStatus = document.getElementById('stat-vaa-status-text');
    const badgeUptime = document.getElementById('stat-vaa-uptime');
    const btnStart = document.getElementById('btn-vaa-start');
    const btnStop = document.getElementById('btn-vaa-stop');

    if (badgeStatus) {
      if (bot.running) {
        badgeStatus.innerText = 'ĐANG CHẠY';
        badgeStatus.className = 'text-xl font-extrabold text-emerald-400 animate-pulse';
        if (badgeUptime) badgeUptime.innerText = `Thời gian chạy: ${bot.uptime_human} (PID: ${bot.pid || 'N/A'})`;
        if (btnStart) btnStart.classList.add('opacity-50', 'pointer-events-none');
        if (btnStop) btnStop.classList.remove('opacity-50', 'pointer-events-none');
      } else {
        badgeStatus.innerText = 'ĐÃ DỪNG';
        badgeStatus.className = 'text-xl font-extrabold text-rose-400';
        if (badgeUptime) badgeUptime.innerText = 'Trạng thái: Đang dừng';
        if (btnStart) btnStart.classList.remove('opacity-50', 'pointer-events-none');
        if (btnStop) btnStop.classList.add('opacity-50', 'pointer-events-none');
      }
    }

    const statPosts = document.getElementById('stat-vaa-total-posts');
    if (statPosts) statPosts.innerText = data.total_posts_scanned || 0;

    const statSent = document.getElementById('stat-vaa-sent-group');
    if (statSent) statSent.innerText = data.total_sent_group || 0;

    const statTargets = document.getElementById('stat-vaa-targets-count');
    if (statTargets) statTargets.innerText = data.total_targets || 11;

    const tagAllChk = document.getElementById('vaa-tag-all-checkbox');
    if (tagAllChk) tagAllChk.checked = Boolean(data.auto_tag_all);

  } catch (err) {
    console.error('Lỗi fetchVaaStats:', err);
  }
}

async function fetchVaaConfig() {
  try {
    const res = await fetch('/api/vaa/config');
    if (!res.ok) return;
    currentVaaConfig = await res.json();

    renderVaaTargets(currentVaaConfig.targets || []);
    renderVaaZaloGroups(currentVaaConfig.zalo?.target_groups || []);
  } catch (err) {
    console.error('Lỗi fetchVaaConfig:', err);
  }
}

function renderVaaTargets(targets) {
  const container = document.getElementById('vaa-targets-list');
  if (!container) return;

  if (!targets || targets.length === 0) {
    container.innerHTML = '<p class="text-xs text-slate-500 py-3 col-span-3">Chưa có nguồn Fanpage nào cho VAA.</p>';
    return;
  }

  container.innerHTML = targets.map((t, idx) => {
    const isEnabled = t.enabled !== false;
    return `
      <div class="p-4 rounded-xl glass border ${isEnabled ? 'border-amber-500/30 bg-amber-500/5' : 'border-slate-800 bg-slate-900/40 opacity-70'} flex flex-col justify-between transition hover:border-amber-500/50">
        <div>
          <div class="flex items-center justify-between gap-2 mb-2">
            <span class="text-xs font-bold text-amber-400">#${idx + 1}</span>
            <span class="px-2 py-0.5 rounded text-[10px] font-semibold ${isEnabled ? 'bg-emerald-500/20 text-emerald-400' : 'bg-slate-800 text-slate-400'}">
              ${isEnabled ? 'ĐANG QUÉT' : 'TẠM TẮT'}
            </span>
          </div>
          <h4 class="text-xs font-semibold text-white line-clamp-2 mb-1.5" title="${t.name}">${t.name}</h4>
          <a href="${t.url}" target="_blank" rel="noopener noreferrer" class="text-[11px] text-sky-400 hover:text-sky-300 flex items-center gap-1 truncate mb-3">
            <i data-lucide="external-link" class="w-3 h-3 flex-shrink-0"></i>
            <span class="truncate">${t.url}</span>
          </a>
        </div>
        <div class="pt-2 border-t border-slate-800/80 flex items-center justify-between">
          <span class="text-[11px] text-slate-400">Trạng thái</span>
          <label class="relative inline-flex items-center cursor-pointer">
            <input type="checkbox" ${isEnabled ? 'checked' : ''} onchange="toggleVaaTarget('${t.id}', this.checked)" class="sr-only peer">
            <div class="w-9 h-5 bg-slate-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-amber-500"></div>
          </label>
        </div>
      </div>
    `;
  }).join('');
  lucide.createIcons();
}

function renderVaaZaloGroups(groups) {
  const container = document.getElementById('vaa-zalo-groups-list');
  if (!container) return;

  if (!groups || groups.length === 0) {
    container.innerHTML = '<p class="text-xs text-slate-500 py-3 col-span-3">Chưa có nhóm Zalo VAA nào.</p>';
    return;
  }

  container.innerHTML = groups.map(g => {
    const isDemo = String(g.id) === '475259879796859360';
    const isEnabled = Boolean(g.enabled);
    return `
      <div class="p-4 rounded-xl glass border ${isDemo ? 'border-emerald-500/40 bg-emerald-500/10 shadow-lg shadow-emerald-500/5' : (isEnabled ? 'border-amber-500/30' : 'border-slate-800 bg-slate-900/40 opacity-75')} transition">
        <div class="flex items-start justify-between gap-3 mb-2">
          <div>
            <div class="flex items-center gap-1.5 flex-wrap">
              <span class="text-xs font-bold text-white">${g.name || 'Nhóm Zalo'}</span>
              ${isDemo ? '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500 text-slate-950">NHẬN TIN CHÍNH</span>' : ''}
            </div>
            <p class="text-[11px] text-slate-400 font-mono mt-0.5">ID: ${g.id}</p>
          </div>
          <label class="relative inline-flex items-center cursor-pointer flex-shrink-0">
            <input type="checkbox" ${isEnabled ? 'checked' : ''} onchange="toggleVaaGroup('${g.id}', this.checked)" class="sr-only peer">
            <div class="w-9 h-5 bg-slate-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-emerald-500"></div>
          </label>
        </div>
        <div class="text-[11px] text-slate-400 pt-2 border-t border-slate-800/60 flex items-center justify-between">
          <span>Loại: ${g.type || 'GROUP'}</span>
          <span class="${isEnabled ? 'text-emerald-400 font-semibold' : 'text-slate-500'}">${isEnabled ? '🟢 Đang Nhận Tin' : '⚪ Đã Tắt'}</span>
        </div>
      </div>
    `;
  }).join('');
  lucide.createIcons();
}

async function fetchVaaHistory() {
  try {
    const res = await fetch('/api/vaa/history?limit=50');
    if (!res.ok) return;
    vaaHistoryList = await res.json();

    const tbody = document.getElementById('table-vaa-history-body');
    if (!tbody) return;

    if (!vaaHistoryList || vaaHistoryList.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6" class="px-5 py-8 text-center text-slate-500">Chưa có thông báo VAA nào được lưu. Bấm "Quét Thử Ngay" để bắt đầu!</td></tr>';
      return;
    }

    tbody.innerHTML = vaaHistoryList.map(item => {
      const isTagAll = item.status && item.status.includes('TAG_ALL');
      return `
        <tr class="hover:bg-slate-800/40 transition">
          <td class="px-5 py-3.5 text-xs text-slate-400 whitespace-nowrap">${item.created_at || 'Vừa xong'}</td>
          <td class="px-5 py-3.5 text-xs font-medium text-white">${item.title || 'Thông báo VAA'}</td>
          <td class="px-5 py-3.5 text-xs font-mono text-emerald-400">${item.recipient_name || 'demo'}</td>
          <td class="px-5 py-3.5 text-xs text-slate-300 max-w-md truncate" title="${item.content || ''}">${item.content || 'N/A'}</td>
          <td class="px-5 py-3.5 text-xs">
            <span class="px-2 py-0.5 rounded text-[10px] font-semibold ${isTagAll ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30' : 'bg-emerald-500/20 text-emerald-300'}">
              ${isTagAll ? '🏷️ ĐÃ GỬI + @ALL' : '✅ ĐÃ GỬI'}
            </span>
          </td>
          <td class="px-5 py-3.5 text-xs text-right whitespace-nowrap">
            <button onclick="openVaaHistoryDetail(${item.id})" class="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs transition">
              Xem chi tiết
            </button>
          </td>
        </tr>
      `;
    }).join('');
    lucide.createIcons();
  } catch (err) {
    console.error('Lỗi fetchVaaHistory:', err);
  }
}

function openVaaHistoryDetail(id) {
  const item = vaaHistoryList.find(x => x.id === id);
  if (!item) return;

  const modal = document.getElementById('modal-vaa-history-detail');
  if (!modal) return;

  document.getElementById('modal-vaa-hist-title').innerHTML = `
    <i data-lucide="plane" class="w-4 h-4 text-amber-400"></i>
    <span>${item.title || 'Thông Báo VAA'}</span>
  `;
  document.getElementById('modal-vaa-hist-meta').innerText = `Đối tượng nhận: ${item.recipient_name || 'demo'} (${item.recipient_id || ''}) | Lúc: ${item.created_at || 'N/A'}`;
  document.getElementById('modal-vaa-hist-content').innerText = item.content || '(Nội dung trống)';
  modal.classList.remove('hidden');
  lucide.createIcons();
}

function closeVaaHistoryDetailModal() {
  const modal = document.getElementById('modal-vaa-history-detail');
  if (modal) modal.classList.add('hidden');
}

async function vaaBotAction(action) {
  try {
    const res = await fetch(`/api/vaa/bot/${action}`, { method: 'POST' });
    const data = await res.json();
    showToast(`Bot VAA: ${data.message || data.status || 'Thao tác thành công!'}`);
    setTimeout(fetchVaaStats, 1000);
  } catch (err) {
    showToast('Lỗi thao tác Bot VAA: ' + err, 'error');
  }
}

async function triggerVaaScanNow() {
  const btn = document.getElementById('btn-vaa-scan');
  if (btn) {
    btn.classList.add('opacity-50', 'pointer-events-none');
    btn.innerHTML = '<i data-lucide="loader-2" class="w-3.5 h-3.5 animate-spin"></i><span>Đang Quét...</span>';
    lucide.createIcons();
  }
  showToast('✈️ Đang quét 11 trang Fanpage Học Viện Hàng Không...');
  try {
    const res = await fetch('/api/vaa/scan_now', { method: 'POST' });
    const data = await res.json();
    if (data.status === 'success') {
      showToast(`✅ Quét VAA hoàn tất! Quét: ${data.result?.scanned || 0} bài, Mới: ${data.result?.new_posts || 0} bài`);
    } else {
      showToast(`⚠️ Quét VAA: ${data.message || 'Không có kết quả'}`);
    }
    fetchVaaStats();
    fetchVaaHistory();
  } catch (err) {
    showToast('Lỗi quét VAA: ' + err, 'error');
  } finally {
    if (btn) {
      btn.classList.remove('opacity-50', 'pointer-events-none');
      btn.innerHTML = '<i data-lucide="refresh-cw" class="w-3.5 h-3.5"></i><span>Quét Thử Ngay</span>';
      lucide.createIcons();
    }
  }
}

async function toggleVaaTarget(id, enabled) {
  try {
    const res = await fetch('/api/vaa/targets/toggle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id, enabled })
    });
    const data = await res.json();
    showToast(data.message || 'Đã đổi trạng thái nguồn VAA!');
    fetchVaaStats();
  } catch (err) {
    showToast('Lỗi cập nhật nguồn VAA: ' + err, 'error');
  }
}

async function toggleVaaGroup(id, enabled) {
  try {
    const res = await fetch('/api/vaa/groups/toggle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id, enabled })
    });
    const data = await res.json();
    showToast(data.message || 'Đã cập nhật nhóm Zalo VAA!');
    fetchVaaStats();
  } catch (err) {
    showToast('Lỗi cập nhật nhóm VAA: ' + err, 'error');
  }
}

async function toggleVaaTagAll() {
  try {
    const res = await fetch('/api/vaa/groups/toggle_tag_all', { method: 'POST' });
    const data = await res.json();
    showToast(`Đã ${data.auto_tag_all ? 'BẬT' : 'TẮT'} tự động Tag @All cho VAA!`);
  } catch (err) {
    showToast('Lỗi cập nhật Tag @All: ' + err, 'error');
  }
}

