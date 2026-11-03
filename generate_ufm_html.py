# -*- coding: utf-8 -*-
import os

templates_dir = r"c:\Users\Admin\Documents\HUIT\vaa\ufm\templates"
os.makedirs(templates_dir, exist_ok=True)
index_html_path = os.path.join(templates_dir, "index.html")

html_content = r'''<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>UFM Portal Feed & Bot Monitor 24/7 (Yuki 4)</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');
    body { font-family: 'Plus Jakarta Sans', sans-serif; }
    .font-mono { font-family: 'JetBrains Mono', monospace; }
    .glass { background: rgba(255, 255, 255, 0.94); backdrop-filter: blur(12px); }
    #console-stream::-webkit-scrollbar { width: 6px; }
    #console-stream::-webkit-scrollbar-track { background: #0f172a; }
    #console-stream::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }
    #console-stream::-webkit-scrollbar-thumb:hover { background: #475569; }
  </style>
  <script>
    (function() {
      const isUfm = window.location.pathname.startsWith('/ufm');
      if (isUfm) {
        const origFetch = window.fetch;
        window.fetch = function(url, options) {
          if (typeof url === 'string') {
            const rootApis = ['/api/all-logs', '/api/zalo/quad-target-groups'];
            const isRootApi = rootApis.some(ep => url.startsWith(ep));
            if (url.startsWith('/api/') && !isRootApi) {
              url = '/ufm' + url;
            }
          }
          return origFetch(url, options);
        };
      }
    })();
  </script>
</head>
<body class="bg-slate-50 text-slate-800 min-h-screen flex flex-col">

  <!-- TOP NAVBAR -->
  <header class="glass sticky top-0 z-50 border-b border-slate-200">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
      <div class="flex items-center space-x-5">
        <div class="flex items-center space-x-3">
          <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-600 to-teal-700 flex items-center justify-center text-white shadow-md shadow-emerald-500/20">
            <i class="fa-solid fa-building-columns text-lg"></i>
          </div>
          <div>
            <h1 class="font-bold text-lg leading-tight text-slate-900">UFM Portal Feed & Bot (Yuki 4)</h1>
            <p class="text-xs text-slate-500 font-medium">Cổng hoatdong.ufm.edu.vn & Săn Điểm Rèn Luyện 24/7</p>
          </div>
        </div>

        <!-- 4-BOT SWITCHER PILL -->
        <div class="hidden sm:flex items-center bg-slate-100 p-1 rounded-xl border border-slate-200 text-xs font-bold">
          <a href="/" class="px-3 py-1.5 rounded-lg text-slate-600 hover:text-slate-900 transition">
            🎓 Bot 1: HUIT (Yuki 1)
          </a>
          <a href="/bot2" class="px-3 py-1.5 rounded-lg text-slate-600 hover:text-slate-900 transition">
            ✈️ Bot 2: VAA (Yuki 2)
          </a>
          <a href="/bot3" class="px-3 py-1.5 rounded-lg text-rose-700 hover:text-rose-900 transition">
            🔴 Bot 3: IUH (Yuki 3)
          </a>
          <a href="/ufm" class="px-3 py-1.5 rounded-lg bg-white text-emerald-700 shadow-xs">
            🏛️ Bot 4: UFM (Yuki 4)
          </a>
        </div>
      </div>

      <div class="flex items-center space-x-3">
        <!-- ADMIN PROFILE: TRẦN LÊ PHÁT -->
        <div class="hidden md:flex items-center gap-2.5 px-3 py-1.5 bg-slate-100 hover:bg-slate-200/80 rounded-xl border border-slate-200 transition">
          <img src="https://avatars.githubusercontent.com/u/349174043?v=4" class="w-8 h-8 rounded-xl object-cover ring-2 ring-emerald-500/50 shadow-xs" alt="Admin Avatar">
          <div class="text-left">
            <div class="flex items-center gap-1.5 leading-none">
              <span class="text-xs font-bold text-slate-900">Yuki</span>
              <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" title="Admin Active"></span>
            </div>
            <a href="https://github.com/yukilegit11-creator" target="_blank" class="text-[10px] text-slate-500 hover:text-emerald-600 flex items-center gap-1 font-mono leading-tight mt-1">
              <i class="fa-brands fa-github text-slate-700"></i> yukilegit11-creator
            </a>
          </div>
        </div>

        <!-- ACTION BUTTONS IN NAVBAR -->
        <button onclick="openQuadTestModal('bot4')" class="px-3.5 py-2 rounded-xl text-xs font-bold bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white shadow-xs transition flex items-center gap-1.5" title="Mở bảng kiểm tra & bắn tin nhắn test cho 4 Bot">
          <i class="fa-solid fa-vial-circle-check"></i>
          <span>Test Nhóm Zalo (4 Bot)</span>
        </button>

        <button onclick="triggerTestZalo()" class="hidden lg:flex px-3.5 py-2 rounded-xl text-xs font-bold bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 transition items-center gap-1.5" title="Gửi tin nhắn thử nghiệm Zalo">
          <i class="fa-solid fa-paper-plane text-xs"></i>
          <span>Bắn tin thử</span>
        </button>

        <button onclick="triggerSendDemoAlert()" class="hidden lg:flex px-3.5 py-2 rounded-xl text-xs font-bold bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border border-emerald-200 transition items-center gap-1.5" title="Gửi thông báo mới nhất vào nhóm demo">
          <i class="fa-solid fa-bullhorn text-xs"></i>
          <span>Gửi nhóm demo</span>
        </button>

        <!-- BOT POWER TOGGLE BUTTON -->
        <button id="bot-toggle-btn-bot4" onclick="toggleBot()" class="px-4 py-2 rounded-xl text-xs font-bold shadow-md transition flex items-center gap-2 bg-emerald-500 hover:bg-emerald-600 text-white shadow-emerald-500/20">
          <span id="bot-toggle-icon-bot4" class="w-2.5 h-2.5 rounded-full bg-white"></span>
          <span id="bot-toggle-text-bot4">🟢 BOT ĐANG CHẠY (BẬT)</span>
        </button>
      </div>
    </div>
  </header>

  <!-- MAIN CONTENT CONTAINER -->
  <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 flex-1 w-full space-y-6">

    <!-- COOKIE ALERT BANNER (IF INVALID OR EXPIRED) -->
    <div id="zaloCookieAlertBanner" class="hidden bg-gradient-to-r from-rose-600 to-red-600 rounded-2xl p-4 text-white shadow-lg shadow-rose-600/30 flex flex-wrap items-center justify-between gap-4 animate-pulse">
      <div class="flex items-center gap-3.5">
        <div class="w-11 h-11 rounded-xl bg-white/20 flex items-center justify-center text-xl">
          <i class="fa-solid fa-triangle-exclamation"></i>
        </div>
        <div>
          <h4 class="font-extrabold text-sm tracking-wide">⚠️ CẢNH BÁO: COOKIE ZALO CỦA BOT 4 ĐÃ HẾT HẠN HOẶC BỊ HỦY!</h4>
          <p class="text-xs text-rose-100 mt-0.5">Không thể gửi thông báo sự kiện UFM vào Zalo. Hãy cập nhật cookie mới ngay!</p>
        </div>
      </div>
      <button onclick="openZaloCookieModal()" class="px-4 py-2 bg-slate-900 hover:bg-black text-white text-xs font-bold rounded-xl transition whitespace-nowrap shadow-xs">
        <i class="fa-solid fa-key mr-1.5"></i> Cập Nhật Cookie Zalo Ngay
      </button>
    </div>

    <!-- 5 KPI STAT CARDS (EXACT MATCH BOT 1 / 2 / 3 STYLE) -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
      <!-- Card 1: Hoạt động CSDL -->
      <div class="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs flex items-center justify-between">
        <div>
          <p class="text-xs font-bold text-slate-500 uppercase tracking-wider">Hoạt Động CSDL</p>
          <h3 id="stat-total-activities" class="text-2xl font-extrabold text-slate-900 mt-1">0</h3>
          <p class="text-[11px] text-slate-400 mt-0.5">Cổng hoatdong.ufm.edu.vn</p>
        </div>
        <div class="w-12 h-12 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center text-xl">
          <i class="fa-solid fa-calendar-check"></i>
        </div>
      </div>

      <!-- Card 2: Tin Đã Bắn Zalo -->
      <div class="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs flex items-center justify-between">
        <div>
          <p class="text-xs font-bold text-slate-500 uppercase tracking-wider">Tin Đã Bắn Zalo</p>
          <h3 id="stat-total-zalo" class="text-2xl font-extrabold text-indigo-600 mt-1">0</h3>
          <p class="text-[11px] text-slate-400 mt-0.5">Các nhóm đang BẬT</p>
        </div>
        <div class="w-12 h-12 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center text-xl">
          <i class="fa-solid fa-paper-plane"></i>
        </div>
      </div>

      <!-- Card 3: Sinh Viên Đã Nạp -->
      <div class="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs flex items-center justify-between">
        <div>
          <p class="text-xs font-bold text-slate-500 uppercase tracking-wider">Sinh Viên Đã Nạp</p>
          <h3 id="stat-total-students" class="text-2xl font-extrabold text-blue-600 mt-1">0</h3>
          <p id="stat-student-valid-count" class="text-[11px] text-slate-400 mt-0.5">0 phiên hợp lệ</p>
        </div>
        <div class="w-12 h-12 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center text-xl">
          <i class="fa-solid fa-user-graduate"></i>
        </div>
      </div>

      <!-- Card 4: Cổng UFM & Auto-Login -->
      <div class="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs flex items-center justify-between">
        <div>
          <p class="text-xs font-bold text-slate-500 uppercase tracking-wider">Cổng UFM Scraper</p>
          <div id="stat-portal-status" class="mt-2 text-xs font-bold text-emerald-600 flex items-center gap-1.5">
            <span class="w-2 h-2 rounded-full bg-emerald-500"></span> Tự đăng nhập 24/7
          </div>
          <p class="text-[11px] text-slate-400 mt-1 font-mono">2621008460</p>
        </div>
        <div class="w-12 h-12 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center text-xl">
          <i class="fa-solid fa-shield-halved"></i>
        </div>
      </div>

      <!-- Card 5: Chu Kỳ Quét -->
      <div class="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs flex items-center justify-between">
        <div>
          <p class="text-xs font-bold text-slate-500 uppercase tracking-wider">Lần Quét Cuối</p>
          <h3 id="stat-last-scan" class="text-sm font-bold text-slate-800 mt-2 font-mono">Chưa quét</h3>
          <p id="stat-scan-cycle" class="text-[11px] text-slate-400 mt-0.5">Chu kỳ: #0</p>
        </div>
        <div class="w-12 h-12 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center text-xl">
          <i class="fa-solid fa-clock-rotate-left"></i>
        </div>
      </div>
    </div>

    <!-- QUICK ACTION BAR -->
    <div class="bg-white p-4 rounded-2xl border border-slate-200/80 shadow-xs flex flex-wrap items-center justify-between gap-3">
      <div class="flex flex-wrap items-center gap-2.5">
        <button onclick="triggerScanNow()" class="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold shadow-xs transition flex items-center gap-1.5">
          <i class="fa-solid fa-rotate"></i>
          <span>Quét Ngay Lập Tức</span>
        </button>

        <button onclick="openQuadTestModal('bot4')" class="px-3.5 py-2 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 text-white rounded-xl text-xs font-bold shadow-xs transition flex items-center gap-1.5">
          <i class="fa-solid fa-vial-circle-check"></i>
          <span>Bắn Tin Test Zalo</span>
        </button>

        <button onclick="triggerSendDemoAlert()" class="px-3.5 py-2 bg-slate-800 hover:bg-slate-900 text-white rounded-xl text-xs font-bold shadow-xs transition flex items-center gap-1.5">
          <i class="fa-solid fa-bullhorn"></i>
          <span>Gửi Nhóm Demo</span>
        </button>

        <button onclick="reloginUFM()" class="px-3.5 py-2 bg-amber-50 hover:bg-amber-100 text-amber-800 border border-amber-200 rounded-xl text-xs font-bold transition flex items-center gap-1.5">
          <i class="fa-solid fa-arrow-right-to-bracket"></i>
          <span>Đăng Nhập Lại Cổng UFM</span>
        </button>
      </div>

      <div class="flex items-center gap-2">
        <a href="/ufm/submit-cookie" target="_blank" class="px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200 rounded-xl text-xs font-bold transition flex items-center gap-1.5">
          <i class="fa-solid fa-arrow-up-right-from-square"></i>
          <span>Mở Form Nạp Sinh Viên</span>
        </a>
        <button onclick="copyStudentSubmitLink()" class="px-3 py-2 bg-white hover:bg-slate-100 text-emerald-700 border border-emerald-200 rounded-xl text-xs font-bold transition flex items-center gap-1.5" title="Sao chép link gửi sinh viên">
          <i class="fa-solid fa-copy"></i>
          <span>Sao chép Link</span>
        </button>
      </div>
    </div>

    <!-- NAVIGATION TABS -->
    <div class="flex items-center gap-2 overflow-x-auto border-b border-slate-200 pb-2">
      <button id="tabBtnActivities" onclick="switchTab('activities')" class="px-4 py-2 rounded-xl text-xs font-bold bg-emerald-600 text-white shadow-xs transition flex items-center gap-2 whitespace-nowrap">
        <i class="fa-solid fa-list-check"></i>
        <span>Hoạt Động & ĐRL UFM</span>
      </button>

      <button id="tabBtnStudents" onclick="switchTab('students')" class="px-4 py-2 rounded-xl text-xs font-bold text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition flex items-center gap-2 whitespace-nowrap">
        <i class="fa-solid fa-user-graduate"></i>
        <span>Sinh Viên & Săn Slot (<span id="tab-student-badge">0</span>)</span>
      </button>

      <button id="tabBtnLogs" onclick="switchTab('logs')" class="px-4 py-2 rounded-xl text-xs font-bold text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition flex items-center gap-2 whitespace-nowrap">
        <i class="fa-solid fa-terminal"></i>
        <span>Live Terminal Log</span>
      </button>

      <button id="tabBtnChannels" onclick="switchTab('channels')" class="px-4 py-2 rounded-xl text-xs font-bold text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition flex items-center gap-2 whitespace-nowrap">
        <i class="fa-solid fa-comments"></i>
        <span>Kênh Nhận Tin (Zalo / FB)</span>
      </button>

      <button id="tabBtnHistory" onclick="switchTab('history')" class="px-4 py-2 rounded-xl text-xs font-bold text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition flex items-center gap-2 whitespace-nowrap">
        <i class="fa-solid fa-clock-rotate-left"></i>
        <span>Lịch Sử Phát Tin</span>
      </button>

      <button id="tabBtnConfig" onclick="switchTab('config')" class="px-4 py-2 rounded-xl text-xs font-bold text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition flex items-center gap-2 whitespace-nowrap">
        <i class="fa-solid fa-gear"></i>
        <span>Cấu Hình Cổng & Bot</span>
      </button>
    </div>

    <!-- TAB 1: DANH SÁCH HOẠT ĐỘNG UFM -->
    <div id="tabActivities" class="space-y-4">
      <div class="bg-white p-4 rounded-2xl border border-slate-200/80 shadow-xs flex flex-wrap items-center justify-between gap-4">
        <div class="flex items-center gap-2.5 flex-1 min-w-[280px]">
          <div class="relative w-full max-w-md">
            <i class="fa-solid fa-magnifying-glass absolute left-3.5 top-3 text-slate-400 text-xs"></i>
            <input type="text" id="activitySearch" oninput="filterActivities()" placeholder="Tìm theo tên hoạt động, đơn vị, mã..." class="w-full pl-9 pr-4 py-2 text-xs border border-slate-300 rounded-xl focus:outline-emerald-500">
          </div>
        </div>

        <div class="flex items-center gap-1.5 text-xs">
          <button onclick="setActivityFilter('all')" id="filter-act-all" class="px-3 py-1.5 rounded-lg font-bold bg-emerald-600 text-white shadow-xs">Tất cả</button>
          <button onclick="setActivityFilter('open')" id="filter-act-open" class="px-3 py-1.5 rounded-lg font-medium text-slate-600 hover:bg-slate-100">Đang mở</button>
          <button onclick="setActivityFilter('full')" id="filter-act-full" class="px-3 py-1.5 rounded-lg font-medium text-slate-600 hover:bg-slate-100">Đã đủ slot</button>
        </div>
      </div>

      <!-- Activities List Container -->
      <div id="activitiesList" class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div class="col-span-full py-12 text-center text-slate-400">
          <i class="fa-solid fa-spinner fa-spin text-3xl mb-3 text-emerald-600"></i>
          <p class="font-medium text-sm">Đang tải danh sách hoạt động từ Cổng UFM...</p>
        </div>
      </div>
    </div>

    <!-- TAB 2: QUẢN LÝ SINH VIÊN & AUTO-ĐĂNG KÝ -->
    <div id="tabStudents" class="hidden space-y-4">
      <div class="bg-white p-4 rounded-2xl border border-slate-200/80 shadow-xs flex flex-wrap items-center justify-between gap-3">
        <div class="flex flex-wrap items-center gap-2">
          <button onclick="openAddStudentModal()" class="px-3.5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold shadow-xs transition flex items-center gap-1.5">
            <i class="fa-solid fa-user-plus"></i>
            <span>+ Nạp Sinh Viên Mới</span>
          </button>
          <button onclick="openBulkImportModal()" class="px-3.5 py-2 bg-slate-800 hover:bg-slate-900 text-white rounded-xl text-xs font-bold shadow-xs transition flex items-center gap-1.5">
            <i class="fa-solid fa-file-import"></i>
            <span>Import Hàng Loạt</span>
          </button>
          <button onclick="checkAllStudentsCookie()" class="px-3.5 py-2 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 rounded-xl text-xs font-bold transition flex items-center gap-1.5">
            <i class="fa-solid fa-shield-halved"></i>
            <span>Kiểm Tra Phiên Tất Cả</span>
          </button>
          <button onclick="reloginAllStudents()" class="px-3.5 py-2 bg-amber-50 hover:bg-amber-100 text-amber-800 border border-amber-200 rounded-xl text-xs font-bold transition flex items-center gap-1.5">
            <i class="fa-solid fa-arrows-rotate"></i>
            <span>Tự Đăng Nhập Lại Tất Cả</span>
          </button>
          <button onclick="triggerBatchRegister()" class="px-3.5 py-2 bg-gradient-to-r from-rose-600 to-red-600 hover:from-rose-700 text-white rounded-xl text-xs font-bold shadow-xs transition flex items-center gap-1.5">
            <i class="fa-solid fa-bolt"></i>
            <span>Thực Hiện Auto-Đăng Ký</span>
          </button>
        </div>

        <div class="w-full sm:w-64">
          <input type="text" id="studentSearch" oninput="filterStudents()" placeholder="Tìm theo MSSV, họ tên..." class="w-full px-3.5 py-2 text-xs border border-slate-300 rounded-xl focus:outline-emerald-500 font-mono">
        </div>
      </div>

      <!-- Students Table -->
      <div class="bg-white rounded-2xl border border-slate-200/80 shadow-xs overflow-hidden">
        <div class="overflow-x-auto">
          <table class="w-full text-left text-xs text-slate-600">
            <thead class="bg-slate-100/80 text-slate-700 font-bold uppercase text-[10px] border-b border-slate-200">
              <tr>
                <th class="px-4 py-3">MSSV</th>
                <th class="px-4 py-3">Họ và Tên</th>
                <th class="px-4 py-3">Lớp</th>
                <th class="px-4 py-3">Mật Khẩu (24/7)</th>
                <th class="px-4 py-3">Phiên Cổng</th>
                <th class="px-4 py-3">Auto-Apply</th>
                <th class="px-4 py-3 text-right">Hành Động</th>
              </tr>
            </thead>
            <tbody id="studentsTableBody" class="divide-y divide-slate-100">
              <tr>
                <td colspan="7" class="px-4 py-10 text-center text-slate-400">Đang tải danh sách sinh viên...</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- TAB 3: LIVE TERMINAL CONSOLE LOG (EXACT SAME CONTROLS AS BOT 1, 2, 3) -->
    <div id="tabLogs" class="hidden space-y-4">
      <div class="bg-white rounded-2xl border border-slate-200/80 shadow-xs overflow-hidden flex flex-col">
        <div class="p-4 border-b border-slate-200 flex flex-wrap items-center justify-between gap-3 bg-slate-50/80">
          <div class="flex items-center space-x-2">
            <div class="w-7 h-7 rounded-lg bg-emerald-100 text-emerald-700 flex items-center justify-center text-xs">
              <i class="fa-solid fa-terminal"></i>
            </div>
            <div>
              <h3 class="font-bold text-xs text-slate-900 leading-none">Live Console Log (UFM Bot 4)</h3>
              <p class="text-[10px] text-slate-500 mt-0.5">Nhật ký tiến trình quét hoạt động Cổng UFM & Bắn Zalo 24/7</p>
            </div>
          </div>

          <div class="flex flex-wrap items-center gap-2">
            <!-- SCOPE SELECTOR -->
            <div class="inline-flex rounded-lg bg-slate-200/80 p-0.5 text-[11px] font-bold">
              <button id="btn-log-scope-ufm" onclick="setLogUfmScope('UFM')" class="px-2.5 py-1 rounded bg-white text-emerald-700 shadow-xs">
                UFM Bot
              </button>
              <button id="btn-log-scope-all" onclick="setLogUfmScope('ALL')" class="px-2.5 py-1 rounded text-slate-600 hover:text-slate-900 transition">
                Hợp Nhất 4 Bot
              </button>
            </div>

            <!-- SORT BUTTON (TOGGLE DESC / ASC) -->
            <button onclick="toggleBot4LogSort()" id="bot4-sort-btn" class="px-2.5 py-1 text-xs text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-md transition flex items-center gap-1.5" title="Đổi thứ tự log: Mới nhất trên cùng hoặc cũ nhất trên cùng">
              <i class="fa-solid fa-arrow-down-short-wide text-cyan-400"></i>
              <span id="bot4-sort-text">Mới nhất trên</span>
            </button>

            <!-- AUTO SCROLL CHECKBOX -->
            <label class="text-xs text-slate-600 flex items-center gap-1.5 cursor-pointer select-none">
              <input type="checkbox" id="console-autoscroll" class="rounded text-emerald-600">
              <span>Auto Scroll</span>
            </label>

            <!-- CLEAR VIEW -->
            <button onclick="clearTerminalViewUFM()" class="px-2.5 py-1 text-xs text-slate-600 hover:text-slate-900 bg-slate-100 hover:bg-slate-200 rounded-md transition border border-slate-300 flex items-center gap-1">
              <i class="fa-solid fa-broom"></i>
              <span>Xóa</span>
            </button>

            <!-- REFRESH -->
            <button onclick="fetchLogs()" class="px-2.5 py-1 text-xs text-emerald-700 hover:text-emerald-800 bg-emerald-50 border border-emerald-200 rounded-md transition" title="Làm mới">
              <i class="fa-solid fa-rotate"></i>
            </button>
          </div>
        </div>

        <!-- DARK STREAM TERMINAL BOX -->
        <div id="console-stream" class="p-4 font-mono text-xs text-slate-300 h-[520px] overflow-y-auto space-y-1.5 bg-[#0b0f19]">
          <div class="text-slate-500 italic">Đang kết nối luồng nhật ký thời gian thực...</div>
        </div>
      </div>
    </div>

    <!-- TAB 4: KÊNH NHẬN TIN (ZALO & MESSENGER) -->
    <div id="tabChannels" class="hidden space-y-6">
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <!-- Zalo Session Card -->
        <div class="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs space-y-4">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center text-lg font-bold">
                Z
              </div>
              <div>
                <h4 class="font-bold text-slate-900 text-sm">Tài Khoản Zalo Bot 4</h4>
                <p id="zalo-uid-text" class="text-xs text-slate-500 font-mono">UID: Đang kiểm tra...</p>
              </div>
            </div>
            <span id="zalo-status-badge" class="px-2.5 py-1 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">Hợp Lệ</span>
          </div>

          <div class="flex items-center gap-2 pt-2 border-t border-slate-100">
            <button onclick="checkZaloSessionNow()" class="px-3.5 py-2 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 rounded-xl text-xs font-bold transition flex items-center gap-1.5">
              <i class="fa-solid fa-shield-halved"></i>
              <span>Kiểm Tra Phiên</span>
            </button>
            <button onclick="openZaloCookieModal()" class="px-3.5 py-2 bg-slate-800 hover:bg-slate-900 text-white rounded-xl text-xs font-bold transition flex items-center gap-1.5">
              <i class="fa-solid fa-key"></i>
              <span>Cập Nhật Cookie Zalo</span>
            </button>
          </div>
        </div>

        <!-- Messenger Session Card -->
        <div class="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs space-y-4">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center text-lg">
                <i class="fa-brands fa-facebook-messenger"></i>
              </div>
              <div>
                <h4 class="font-bold text-slate-900 text-sm">Facebook Messenger</h4>
                <p id="msger-uid-text" class="text-xs text-slate-500 font-mono">Chưa kích hoạt</p>
              </div>
            </div>
            <button id="msger-toggle-btn" onclick="toggleMessengerChannel()" class="px-3 py-1 rounded-lg text-xs font-bold bg-slate-100 text-slate-600 border border-slate-200">
              TẮT
            </button>
          </div>

          <div class="flex items-center gap-2 pt-2 border-t border-slate-100">
            <button onclick="checkMessengerSessionNow()" class="px-3.5 py-2 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 rounded-xl text-xs font-bold transition flex items-center gap-1.5">
              <i class="fa-solid fa-shield-halved"></i>
              <span>Kiểm Tra Phiên</span>
            </button>
            <button onclick="openMessengerCookieModal()" class="px-3.5 py-2 bg-slate-800 hover:bg-slate-900 text-white rounded-xl text-xs font-bold transition flex items-center gap-1.5">
              <i class="fa-solid fa-key"></i>
              <span>Cập Nhật Cookie Messenger</span>
            </button>
          </div>
        </div>
      </div>

      <!-- Target Groups Table -->
      <div class="bg-white rounded-2xl border border-slate-200/80 shadow-xs overflow-hidden space-y-4 p-5">
        <div class="flex items-center justify-between">
          <div>
            <h4 class="font-bold text-slate-900 text-sm">Danh Sách Nhóm Zalo Nhận Tin Tức Thì</h4>
            <p class="text-xs text-slate-500">Khi có hoạt động UFM mới hoặc mở thêm slot, bot sẽ tự động phát tin vào các nhóm này</p>
          </div>
          <div class="flex items-center gap-2">
            <button onclick="fetchZaloGroupsFromClient()" class="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-bold border border-slate-200 transition">
              <i class="fa-solid fa-arrows-rotate mr-1"></i> Đồng bộ từ Zalo
            </button>
            <button onclick="openAddTargetGroupModal()" class="px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold transition">
              <i class="fa-solid fa-plus mr-1"></i> Thêm Nhóm
            </button>
          </div>
        </div>

        <div id="targetGroupsEditor" class="space-y-2">
          <!-- Rendered in JS -->
        </div>
      </div>
    </div>

    <!-- TAB 5: LỊCH SỬ PHÁT TIN -->
    <div id="tabHistory" class="hidden space-y-4">
      <div class="bg-white rounded-2xl border border-slate-200/80 shadow-xs overflow-hidden">
        <div class="p-4 border-b border-slate-100 flex items-center justify-between">
          <h3 class="font-bold text-xs text-slate-900 uppercase tracking-wider">Lịch Sử Gửi Thông Báo Vào Zalo</h3>
          <button onclick="fetchHistory()" class="px-2.5 py-1 text-xs text-emerald-700 hover:text-emerald-800 bg-emerald-50 border border-emerald-200 rounded-md transition">
            <i class="fa-solid fa-rotate mr-1"></i> Tải lại
          </button>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-left text-xs text-slate-600">
            <thead class="bg-slate-100/80 text-slate-700 font-bold uppercase text-[10px] border-b border-slate-200">
              <tr>
                <th class="px-4 py-3">Thời Gian</th>
                <th class="px-4 py-3">Hoạt Động / Tiêu Đề</th>
                <th class="px-4 py-3">Loại Tin</th>
                <th class="px-4 py-3">Kênh Đích</th>
                <th class="px-4 py-3">Trạng Thái</th>
              </tr>
            </thead>
            <tbody id="historyTableBody" class="divide-y divide-slate-100">
              <tr>
                <td colspan="5" class="px-4 py-8 text-center text-slate-400">Đang tải lịch sử phát tin...</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- TAB 6: CẤU HÌNH CỔNG & HỆ THỐNG -->
    <div id="tabConfig" class="hidden space-y-4">
      <div class="max-w-2xl bg-white p-6 rounded-2xl border border-slate-200/80 shadow-xs space-y-5">
        <div>
          <h3 class="font-bold text-sm text-slate-900">Cấu Hình Tài Khoản Cổng UFM (Scraper)</h3>
          <p class="text-xs text-slate-500">Tài khoản sinh viên dùng để tự động cào dữ liệu hoạt động 24/7 từ hoatdong.ufm.edu.vn</p>
        </div>

        <div class="space-y-4">
          <div>
            <label class="block text-xs font-bold text-slate-700 mb-1">Mã Số Sinh Viên (MSSV / Username)</label>
            <input type="text" id="cfg-portal-user" class="w-full px-3.5 py-2 text-xs border border-slate-300 rounded-xl focus:outline-emerald-500 font-mono">
          </div>
          <div>
            <label class="block text-xs font-bold text-slate-700 mb-1">Mật Khẩu Cổng UFM</label>
            <input type="password" id="cfg-portal-pass" class="w-full px-3.5 py-2 text-xs border border-slate-300 rounded-xl focus:outline-emerald-500">
          </div>
          <div>
            <label class="block text-xs font-bold text-slate-700 mb-1">Chu Kỳ Quét (Giây)</label>
            <input type="number" id="cfg-scan-interval" class="w-full px-3.5 py-2 text-xs border border-slate-300 rounded-xl focus:outline-emerald-500 font-mono">
          </div>

          <div class="pt-3 border-t border-slate-100 flex items-center gap-3">
            <button onclick="savePortalConfig()" class="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold shadow-xs transition">
              <i class="fa-solid fa-floppy-disk mr-1.5"></i> Lưu Cấu Hình
            </button>
            <button onclick="reloginUFM()" class="px-4 py-2.5 bg-slate-800 hover:bg-slate-900 text-white rounded-xl text-xs font-bold shadow-xs transition">
              <i class="fa-solid fa-right-to-bracket mr-1.5"></i> Đăng Nhập Lại Ngay
            </button>
          </div>
        </div>
      </div>
    </div>
  </main>

  <!-- MODAL: TEST NHÓM ZALO CHO CẢ 4 BOT (QUAD TEST MODAL) -->
  <div id="quad-test-modal" class="hidden fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
    <div class="bg-white rounded-3xl border border-slate-200/80 shadow-2xl max-w-2xl w-full p-6 space-y-5 animate-scale-in">
      <div class="flex items-center justify-between pb-3 border-b border-slate-100">
        <div class="flex items-center gap-2.5">
          <div class="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-600 to-purple-600 text-white flex items-center justify-center text-sm shadow-md shadow-indigo-500/20">
            <i class="fa-solid fa-vial-circle-check"></i>
          </div>
          <div>
            <h3 class="font-bold text-sm text-slate-900">Bảng Kiểm Tra Tín Hiệu Zalo (Cả 4 Bot)</h3>
            <p class="text-[11px] text-slate-500">Bắn tin nhắn thử nghiệm vào từng nhóm cụ thể để xác nhận kết nối</p>
          </div>
        </div>
        <button onclick="closeQuadTestModal()" class="w-8 h-8 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-700 transition flex items-center justify-center">
          <i class="fa-solid fa-xmark text-base"></i>
        </button>
      </div>

      <!-- BOT TABS -->
      <div class="flex items-center gap-1.5 bg-slate-100 p-1 rounded-xl text-xs font-bold">
        <button id="quad-tab-bot1" onclick="switchQuadTestBot('bot1')" class="px-3 py-1.5 rounded-lg text-slate-600 hover:text-slate-900 transition flex-1">
          Bot 1 (HUIT)
        </button>
        <button id="quad-tab-bot2" onclick="switchQuadTestBot('bot2')" class="px-3 py-1.5 rounded-lg text-slate-600 hover:text-slate-900 transition flex-1">
          Bot 2 (VAA)
        </button>
        <button id="quad-tab-bot3" onclick="switchQuadTestBot('bot3')" class="px-3 py-1.5 rounded-lg text-slate-600 hover:text-slate-900 transition flex-1">
          Bot 3 (IUH)
        </button>
        <button id="quad-tab-bot4" onclick="switchQuadTestBot('bot4')" class="px-3 py-1.5 rounded-lg bg-white text-emerald-700 shadow-xs flex-1">
          Bot 4 (UFM)
        </button>
      </div>

      <!-- Status banner inside modal -->
      <div id="quad-test-status" class="hidden p-3 rounded-xl text-xs font-medium border"></div>

      <!-- Optional custom text -->
      <div>
        <label class="block text-xs font-bold text-slate-700 mb-1">Nội Dung Tin Nhắn Tùy Chọn (Để trống nếu muốn dùng tin mặc định):</label>
        <input type="text" id="quad-custom-msg" placeholder="Ví dụ: Yuki Bot kiểm tra đường truyền tín hiệu nhóm..." class="w-full px-3.5 py-2 text-xs border border-slate-300 rounded-xl focus:outline-indigo-500">
      </div>

      <!-- Action: Test all groups -->
      <div class="flex items-center justify-between bg-slate-50 p-3 rounded-xl border border-slate-200">
        <div class="text-xs text-slate-600">
          <span class="font-bold text-slate-800">Bắn tin thử toàn bộ:</span> Gửi tin kiểm tra lần lượt tới tất cả nhóm đang BẬT
        </div>
        <button onclick="triggerTestAllForCurrentBot()" class="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-bold transition flex items-center gap-1 shadow-xs">
          <i class="fa-solid fa-paper-plane text-xs"></i> Test Tất Cả
        </button>
      </div>

      <!-- Groups List in Quad Modal -->
      <div class="space-y-2 max-h-64 overflow-y-auto pr-1" id="quad-groups-list">
        <div class="text-center py-6 text-slate-400 text-xs">Đang nạp danh sách nhóm...</div>
      </div>
    </div>
  </div>

  <!-- MODAL: THÊM SINH VIÊN MỚI -->
  <div id="add-student-modal" class="hidden fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
    <div class="bg-white rounded-3xl border border-slate-200/80 shadow-2xl max-w-md w-full p-6 space-y-4">
      <div class="flex items-center justify-between pb-2 border-b border-slate-100">
        <h3 class="font-bold text-sm text-slate-900">Thêm Sinh Viên Mới</h3>
        <button onclick="closeAddStudentModal()" class="w-7 h-7 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-700 flex items-center justify-center">
          <i class="fa-solid fa-xmark"></i>
        </button>
      </div>

      <div class="space-y-3">
        <div>
          <label class="block text-xs font-bold text-slate-700 mb-1">Mã Số Sinh Viên (MSSV) *</label>
          <input type="text" id="modal-st-mssv" placeholder="2621008460" class="w-full px-3.5 py-2 text-xs border border-slate-300 rounded-xl focus:outline-emerald-500 font-mono">
        </div>
        <div>
          <label class="block text-xs font-bold text-slate-700 mb-1">Mật Khẩu Cổng UFM (Để tự đăng nhập 24/7)</label>
          <input type="password" id="modal-st-pwd" placeholder="Mật khẩu cổng hoatdong.ufm.edu.vn" class="w-full px-3.5 py-2 text-xs border border-slate-300 rounded-xl focus:outline-emerald-500">
        </div>
        <div>
          <label class="block text-xs font-bold text-slate-700 mb-1">Họ Và Tên</label>
          <input type="text" id="modal-st-name" placeholder="Nguyễn Văn A" class="w-full px-3.5 py-2 text-xs border border-slate-300 rounded-xl focus:outline-emerald-500">
        </div>
        <div>
          <label class="block text-xs font-bold text-slate-700 mb-1">Lớp Sinh Hoạt</label>
          <input type="text" id="modal-st-class" placeholder="22DTA01" class="w-full px-3.5 py-2 text-xs border border-slate-300 rounded-xl focus:outline-emerald-500 font-mono">
        </div>

        <button onclick="saveNewStudentFromModal()" class="w-full py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold shadow-xs transition mt-2">
          Xác Thực & Lưu Sinh Viên
        </button>
      </div>
    </div>
  </div>

  <!-- MODAL: IMPORT HÀNG LOẠT -->
  <div id="bulk-import-modal" class="hidden fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
    <div class="bg-white rounded-3xl border border-slate-200/80 shadow-2xl max-w-lg w-full p-6 space-y-4">
      <div class="flex items-center justify-between pb-2 border-b border-slate-100">
        <h3 class="font-bold text-sm text-slate-900">Import Danh Sách Sinh Viên Hàng Loạt</h3>
        <button onclick="closeBulkImportModal()" class="w-7 h-7 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-700 flex items-center justify-center">
          <i class="fa-solid fa-xmark"></i>
        </button>
      </div>

      <div class="space-y-3">
        <p class="text-xs text-slate-500">Mỗi dòng một sinh viên theo định dạng: <code class="bg-slate-100 px-1 py-0.5 rounded text-emerald-700 font-mono">MSSV | Mật khẩu | Họ tên</code></p>
        <textarea id="bulk-import-text" rows="7" placeholder="2621008460 | focusoncareer2111!!! | Đàm Anh Duy&#10;2621008461 | pass123 | Nguyễn Văn B" class="w-full p-3 text-xs border border-slate-300 rounded-xl focus:outline-emerald-500 font-mono"></textarea>
        
        <button onclick="submitBulkImport()" class="w-full py-2.5 rounded-xl bg-slate-800 hover:bg-slate-900 text-white text-xs font-bold shadow-xs transition">
          Bắt Đầu Import & Xác Thực
        </button>
      </div>
    </div>
  </div>

  <!-- MODAL: CẬP NHẬT COOKIE ZALO -->
  <div id="zalo-cookie-modal" class="hidden fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
    <div class="bg-white rounded-3xl border border-slate-200/80 shadow-2xl max-w-lg w-full p-6 space-y-4">
      <div class="flex items-center justify-between pb-2 border-b border-slate-100">
        <h3 class="font-bold text-sm text-slate-900">Cập Nhật Cookie Zalo Bot 4</h3>
        <button onclick="closeZaloCookieModal()" class="w-7 h-7 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-700 flex items-center justify-center">
          <i class="fa-solid fa-xmark"></i>
        </button>
      </div>

      <div class="space-y-3">
        <p class="text-xs text-slate-500">Dán mảng JSON cookie xuất từ tiện ích J2Team Cookies hoặc EditThisCookie:</p>
        <textarea id="modal-zalo-cookies" rows="6" placeholder="[ { &quot;name&quot;: &quot;zpw_sek&quot;, &quot;value&quot;: &quot;...&quot; }, ... ]" class="w-full p-3 text-xs border border-slate-300 rounded-xl focus:outline-emerald-500 font-mono"></textarea>
        
        <button onclick="submitZaloCookies()" class="w-full py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold shadow-xs transition">
          Kiểm Tra & Lưu Cookie Zalo
        </button>
      </div>
    </div>
  </div>

  <!-- JAVASCRIPT LOGIC -->
  <script>
    let allActivities = [];
    let allStudents = [];
    let currentConfig = {};
    let currentLogUfmScope = 'UFM';
    let currentQuadBot = 'bot4';
    let quadBotsData = {};
    let bot4LogSortAsc = false; // Mặc định: Mới nhất trên (DESC)

    // ================= TAB SWITCHER =================
    function switchTab(tab) {
      const tabs = ['activities', 'students', 'logs', 'channels', 'history', 'config'];
      tabs.forEach(t => {
        const el = document.getElementById('tab' + t.charAt(0).toUpperCase() + t.slice(1));
        const btn = document.getElementById('tabBtn' + t.charAt(0).toUpperCase() + t.slice(1));
        if (el) el.classList.add('hidden');
        if (btn) btn.className = "px-4 py-2 rounded-xl text-xs font-bold text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition flex items-center gap-2 whitespace-nowrap";
      });

      const activeEl = document.getElementById('tab' + tab.charAt(0).toUpperCase() + tab.slice(1));
      const activeBtn = document.getElementById('tabBtn' + tab.charAt(0).toUpperCase() + tab.slice(1));
      if (activeEl) activeEl.classList.remove('hidden');
      if (activeBtn) activeBtn.className = "px-4 py-2 rounded-xl text-xs font-bold bg-emerald-600 text-white shadow-xs transition flex items-center gap-2 whitespace-nowrap";

      if (tab === 'activities') fetchActivities();
      else if (tab === 'students') fetchStudents();
      else if (tab === 'logs') fetchLogs();
      else if (tab === 'channels') renderAllActiveChannels();
      else if (tab === 'history') fetchHistory();
      else if (tab === 'config') loadConfigForm();
    }

    // ================= STATUS & BOT TOGGLE =================
    async function fetchStatus() {
      try {
        const res = await fetch('/api/status');
        const data = await res.json();
        
        document.getElementById('stat-total-activities').innerText = data.stats.total_activities || 0;
        document.getElementById('stat-total-zalo').innerText = data.stats.total_zalo_sent || 0;
        document.getElementById('stat-total-students').innerText = data.student_stats.total_students || 0;
        document.getElementById('tab-student-badge').innerText = data.student_stats.total_students || 0;
        document.getElementById('stat-student-valid-count').innerText = (data.student_stats.valid_sessions || 0) + ' phiên hợp lệ';
        document.getElementById('stat-last-scan').innerText = data.last_scan_time || 'Chưa quét';
        document.getElementById('stat-scan-cycle').innerText = 'Chu kỳ: #' + (data.total_scans || 0);

        // Bot toggle button UI
        const btn = document.getElementById('bot-toggle-btn-bot4');
        const txt = document.getElementById('bot-toggle-text-bot4');
        if (data.is_active) {
          btn.className = "px-4 py-2 rounded-xl text-xs font-bold shadow-md transition flex items-center gap-2 bg-emerald-500 hover:bg-emerald-600 text-white shadow-emerald-500/20";
          txt.innerText = "🟢 BOT ĐANG CHẠY (BẬT)";
        } else {
          btn.className = "px-4 py-2 rounded-xl text-xs font-bold shadow-md transition flex items-center gap-2 bg-rose-500 hover:bg-rose-600 text-white shadow-rose-500/20";
          txt.innerText = "🔴 BOT ĐÃ TẮT (TẠM DỪNG)";
        }

        // Cookie alert
        const banner = document.getElementById('zaloCookieAlertBanner');
        if (data.zalo_cookie_status === 'expired' || data.zalo_cookie_status === 'missing') {
          banner.classList.remove('hidden');
        } else {
          banner.classList.add('hidden');
        }

        // Zalo UID
        if (data.zalo_account_uid) {
          document.getElementById('zalo-uid-text').innerText = 'UID: ' + data.zalo_account_uid;
        }
      } catch (e) {
        console.error('Lỗi tải status:', e);
      }
    }

    async function toggleBot() {
      try {
        const res = await fetch('/api/bot/toggle', { method: 'POST' });
        const data = await res.json();
        Swal.fire('Thông báo', data.message, 'info');
        fetchStatus();
      } catch (e) {
        Swal.fire('Lỗi', e.message, 'error');
      }
    }

    async function triggerScanNow() {
      Swal.fire({
        title: 'Đang quét Cổng UFM...',
        text: 'Bot đang kết nối Cổng UFM và bóc tách hoạt động mới...',
        allowOutsideClick: false,
        didOpen: () => { Swal.showLoading(); }
      });
      try {
        const res = await fetch('/api/bot/scan-now', { method: 'POST' });
        const data = await res.json();
        if (data.success) {
          Swal.fire('Hoàn tất!', data.message, 'success');
        } else {
          Swal.fire('Chưa hoàn tất', data.message, 'warning');
        }
        fetchStatus();
        fetchActivities();
        fetchLogs();
      } catch (e) {
        Swal.fire('Lỗi', e.message, 'error');
      }
    }

    // ================= TEST ZALO & DEMO =================
    async function triggerTestZalo(targetId = null, targetName = '', targetType = 'GROUP') {
      if (targetId) {
        const ans = await Swal.fire({
          title: '🧪 Gửi tin TEST?',
          text: `Gửi tin nhắn thử nghiệm tới: "${targetName || targetId}" (${targetId})`,
          icon: 'question',
          showCancelButton: true,
          confirmButtonText: 'Gửi Ngay',
          cancelButtonText: 'Hủy'
        });
        if (!ans.isConfirmed) return;
      }

      Swal.fire({
        title: 'Đang gửi tin test vào Zalo...',
        allowOutsideClick: false,
        didOpen: () => { Swal.showLoading(); }
      });

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
        if (data.success || data.status === 'ok') {
          Swal.fire('Thành công!', data.message, 'success');
        } else {
          Swal.fire('Lỗi gửi tin', data.detail || data.message || 'Chưa gửi được tin', 'error');
        }
        fetchLogs();
      } catch (e) {
        Swal.fire('Lỗi', e.message, 'error');
      }
    }

    async function triggerSendDemoAlert() {
      const confirmRes = await Swal.fire({
        title: '📢 Gửi thông báo vào nhóm demo?',
        text: 'Bot sẽ gửi hoạt động UFM mới nhất vào nhóm demo (ID: 7456361874031804652) kèm tag @All.',
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: '🚀 Bắn Ngay',
        cancelButtonText: 'Hủy'
      });
      if (!confirmRes.isConfirmed) return;

      Swal.fire({
        title: 'Đang phát tin vào nhóm demo...',
        allowOutsideClick: false,
        didOpen: () => { Swal.showLoading(); }
      });

      try {
        const res = await fetch('/api/zalo/send-demo-alert', { method: 'POST' });
        const data = await res.json();
        if (data.success || data.status === 'ok') {
          Swal.fire('Thành công!', data.message, 'success');
        } else {
          Swal.fire('Thất bại', data.message || 'Chưa gửi được tin!', 'error');
        }
        fetchLogs();
      } catch (e) {
        Swal.fire('Lỗi', e.message, 'error');
      }
    }

    // ================= ACTIVITIES TAB =================
    let actFilterMode = 'all';

    function setActivityFilter(mode) {
      actFilterMode = mode;
      ['all', 'open', 'full'].forEach(m => {
        const b = document.getElementById('filter-act-' + m);
        if (b) {
          b.className = (m === mode) ? 'px-3 py-1.5 rounded-lg font-bold bg-emerald-600 text-white shadow-xs' : 'px-3 py-1.5 rounded-lg font-medium text-slate-600 hover:bg-slate-100';
        }
      });
      filterActivities();
    }

    async function fetchActivities() {
      try {
        const res = await fetch('/api/activities?limit=100');
        const data = await res.json();
        allActivities = data.activities || [];
        filterActivities();
      } catch (e) {
        console.error('Lỗi tải hoạt động:', e);
      }
    }

    function filterActivities() {
      const query = (document.getElementById('activitySearch')?.value || '').toLowerCase().trim();
      let list = allActivities;

      if (query) {
        list = list.filter(a => (a.title || '').toLowerCase().includes(query) || (a.unit || '').toLowerCase().includes(query) || (a.activity_id || '').toLowerCase().includes(query));
      }

      if (actFilterMode === 'open') {
        list = list.filter(a => !a.is_full && (a.status || '').toLowerCase().includes('mở'));
      } else if (actFilterMode === 'full') {
        list = list.filter(a => a.is_full || (a.status || '').toLowerCase().includes('đủ'));
      }

      renderActivities(list);
    }

    function renderActivities(acts) {
      const container = document.getElementById('activitiesList');
      if (!acts || acts.length === 0) {
        container.innerHTML = `
          <div class="col-span-full py-16 text-center text-slate-400 bg-white rounded-2xl border border-slate-200/80 p-6">
            <i class="fa-solid fa-inbox text-4xl mb-3 text-slate-300"></i>
            <p class="font-medium text-sm">Chưa có hoạt động nào trong cơ sở dữ liệu.</p>
            <p class="text-xs text-slate-400 mt-1">Nhấn "Quét Ngay Lập Tức" để cào dữ liệu từ Cổng UFM!</p>
          </div>
        `;
        return;
      }

      container.innerHTML = acts.map(a => {
        const isOpen = !a.is_full && (a.status || '').toLowerCase().includes('mở');
        const statusBadge = isOpen ?
          `<span class="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center gap-1"><span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span> ${a.status || 'Đang mở'}</span>` :
          `<span class="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-slate-100 text-slate-600 border border-slate-200">${a.status || 'Đã đủ'}</span>`;

        let pointsBadge = '';
        if (a.points > 0) pointsBadge += `<span class="px-2 py-0.5 rounded-md text-[10px] font-bold bg-amber-50 text-amber-700 border border-amber-200">+${a.points} ĐRL</span> `;
        if (a.ctxh > 0) pointsBadge += `<span class="px-2 py-0.5 rounded-md text-[10px] font-bold bg-purple-50 text-purple-700 border border-purple-200">+${a.ctxh} CTXH</span>`;

        return `
          <div class="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-xs hover:shadow-md transition flex flex-col justify-between space-y-3">
            <div class="space-y-2">
              <div class="flex items-center justify-between gap-2">
                <span class="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-slate-100 text-slate-700 border border-slate-200">ID: ${a.activity_id}</span>
                <div class="flex items-center gap-1.5">
                  ${pointsBadge}
                  ${statusBadge}
                </div>
              </div>

              <h4 class="font-bold text-sm text-slate-900 leading-snug line-clamp-2">${a.title || 'Không có tiêu đề'}</h4>
              
              <div class="space-y-1 text-xs text-slate-500">
                <div class="flex items-center gap-2"><i class="fa-solid fa-building text-slate-400 text-xs w-3.5"></i> <span class="truncate">${a.unit || 'Chưa rõ đơn vị'}</span></div>
                <div class="flex items-center gap-2"><i class="fa-regular fa-clock text-slate-400 text-xs w-3.5"></i> <span>${a.event_time || 'Xem chi tiết'}</span></div>
                <div class="flex items-center gap-2"><i class="fa-solid fa-location-dot text-slate-400 text-xs w-3.5"></i> <span class="truncate">${a.location || 'Tại cơ sở'}</span></div>
              </div>
            </div>

            <div class="pt-3 border-t border-slate-100 flex items-center justify-between gap-2">
              <a href="${a.register_url || 'https://hoatdong.ufm.edu.vn/DangKy'}" target="_blank" class="px-3 py-1.5 rounded-lg text-xs font-bold text-emerald-700 hover:bg-emerald-50 transition flex items-center gap-1">
                <span>Vào Cổng</span> <i class="fa-solid fa-arrow-up-right-from-square text-[10px]"></i>
              </a>

              <div class="flex items-center gap-1.5">
                <button onclick="quickBatchRegister('${a.activity_id}')" class="px-2.5 py-1.5 bg-rose-50 hover:bg-rose-100 text-rose-700 rounded-lg text-xs font-bold transition flex items-center gap-1" title="Tự đăng ký hoạt động này cho toàn bộ sinh viên đã nạp">
                  <i class="fa-solid fa-bolt text-xs"></i> <span>Auto-Apply</span>
                </button>
              </div>
            </div>
          </div>
        `;
      }).join('');
    }

    // ================= STUDENTS TAB =================
    async function fetchStudents() {
      try {
        const res = await fetch('/api/students');
        const data = await res.json();
        allStudents = data.students || [];
        document.getElementById('tab-student-badge').innerText = allStudents.length;
        filterStudents();
      } catch (e) {
        console.error('Lỗi tải sinh viên:', e);
      }
    }

    function filterStudents() {
      const query = (document.getElementById('studentSearch')?.value || '').toLowerCase().trim();
      let list = allStudents;
      if (query) {
        list = list.filter(s => (s.mssv || '').toLowerCase().includes(query) || (s.full_name || '').toLowerCase().includes(query));
      }
      renderStudents(list);
    }

    function renderStudents(students) {
      const tbody = document.getElementById('studentsTableBody');
      if (!students || students.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" class="px-4 py-8 text-center text-slate-400">Chưa có sinh viên nào trong danh sách. Hãy nhấn "+ Nạp Sinh Viên Mới" hoặc "Import Hàng Loạt".</td></tr>`;
        return;
      }

      tbody.innerHTML = students.map(st => {
        const isValid = st.session_status === 'valid';
        const sessionBadge = isValid ?
          `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">Hợp Lệ</span>` :
          `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-50 text-rose-700 border border-rose-200">Cần Sửa</span>`;

        const hasPwd = Boolean(st.password);
        const pwdBadge = hasPwd ?
          `<span class="text-emerald-600 font-bold flex items-center gap-1"><i class="fa-solid fa-circle-check"></i> Đã lưu</span>` :
          `<span class="text-slate-400 italic">Chưa có</span>`;

        return `
          <tr class="hover:bg-slate-50 transition">
            <td class="px-4 py-3 font-mono font-bold text-slate-900">${st.mssv}</td>
            <td class="px-4 py-3 font-medium text-slate-800">${st.full_name || st.mssv}</td>
            <td class="px-4 py-3 font-mono text-slate-500">${st.class_name || '-'}</td>
            <td class="px-4 py-3">${pwdBadge}</td>
            <td class="px-4 py-3">${sessionBadge}</td>
            <td class="px-4 py-3">
              <label class="relative inline-flex items-center cursor-pointer">
                <input type="checkbox" ${st.is_active ? 'checked' : ''} onchange="toggleStudentActive('${st.mssv}', this.checked)" class="sr-only peer">
                <div class="w-8 h-4.5 bg-slate-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-3.5 after:w-3.5 after:transition-all peer-checked:bg-emerald-600"></div>
              </label>
            </td>
            <td class="px-4 py-3 text-right space-x-1">
              <button onclick="deleteStudent('${st.mssv}')" class="px-2 py-1 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded transition" title="Xóa sinh viên">
                <i class="fa-regular fa-trash-can"></i>
              </button>
            </td>
          </tr>
        `;
      }).join('');
    }

    async function toggleStudentActive(mssv, active) {
      try {
        await fetch('/api/student/toggle', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ mssv: mssv, is_active: active })
        });
      } catch (e) {
        console.error(e);
      }
    }

    async function deleteStudent(mssv) {
      const ans = await Swal.fire({
        title: 'Xóa sinh viên?',
        text: `Bạn có chắc muốn xóa sinh viên MSSV ${mssv} khỏi hệ thống?`,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#e11d48',
        confirmButtonText: 'Xóa Ngay',
        cancelButtonText: 'Hủy'
      });
      if (!ans.isConfirmed) return;

      try {
        const res = await fetch('/api/student/delete', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ mssv: mssv })
        });
        const data = await res.json();
        Swal.fire('Đã xóa!', data.message, 'success');
        fetchStudents();
        fetchStatus();
      } catch (e) {
        Swal.fire('Lỗi', e.message, 'error');
      }
    }

    async function checkAllStudentsCookie() {
      Swal.fire({
        title: 'Đang kiểm tra phiên tất cả sinh viên...',
        allowOutsideClick: false,
        didOpen: () => { Swal.showLoading(); }
      });
      try {
        const res = await fetch('/api/students/check-all', { method: 'POST' });
        const data = await res.json();
        Swal.fire('Hoàn tất!', data.message, 'info');
        fetchStudents();
        fetchStatus();
      } catch (e) {
        Swal.fire('Lỗi', e.message, 'error');
      }
    }

    async function reloginAllStudents() {
      Swal.fire({
        title: 'Đang tự động đăng nhập lại tất cả sinh viên...',
        text: 'Hệ thống dùng mật khẩu đã lưu để cấp lại phiên cookie mới...',
        allowOutsideClick: false,
        didOpen: () => { Swal.showLoading(); }
      });
      try {
        const res = await fetch('/api/students/relogin-all', { method: 'POST' });
        const data = await res.json();
        Swal.fire('Hoàn tất!', data.message, 'success');
        fetchStudents();
        fetchStatus();
      } catch (e) {
        Swal.fire('Lỗi', e.message, 'error');
      }
    }

    async function quickBatchRegister(actId) {
      const ans = await Swal.fire({
        title: '⚡ Auto-Đăng Ký Hoạt Động?',
        text: `Tự động đăng ký Hoạt động #${actId} cho tất cả các sinh viên đang BẬT?`,
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: '🚀 Bắt Đầu Đăng Ký',
        cancelButtonText: 'Hủy'
      });
      if (!ans.isConfirmed) return;

      try {
        const res = await fetch('/api/students/batch-register', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ activity_id: actId })
        });
        const data = await res.json();
        Swal.fire('Thông báo', data.message, 'info');
        switchTab('logs');
      } catch (e) {
        Swal.fire('Lỗi', e.message, 'error');
      }
    }

    async function triggerBatchRegister() {
      const { value: actId } = await Swal.fire({
        title: '⚡ Nhập Mã Hoạt Động Cần Đăng Ký',
        input: 'text',
        inputLabel: 'Activity ID (Ví dụ: 1245 hoặc lấy từ bảng hoạt động)',
        inputPlaceholder: 'Nhập ID hoạt động...',
        showCancelButton: true,
        confirmButtonText: 'Bắt Đầu Đăng Ký'
      });
      if (actId) {
        quickBatchRegister(actId);
      }
    }

    function copyStudentSubmitLink() {
      const url = window.location.origin + '/ufm/submit-cookie';
      navigator.clipboard.writeText(url).then(() => {
        Swal.fire({
          toast: true,
          position: 'top-end',
          icon: 'success',
          title: 'Đã sao chép link nạp sinh viên!',
          showConfirmButton: false,
          timer: 2500
        });
      });
    }

    // ================= TERMINAL CONSOLE LOG (EXACT SAME AS BOT 1, 2, 3) =================
    function setLogUfmScope(scope) {
      currentLogUfmScope = scope;
      const btnUfm = document.getElementById('btn-log-scope-ufm');
      const btnAll = document.getElementById('btn-log-scope-all');
      if (scope === 'UFM') {
        btnUfm.className = 'px-2.5 py-1 rounded bg-white text-emerald-700 shadow-xs';
        btnAll.className = 'px-2.5 py-1 rounded text-slate-600 hover:text-slate-900 transition';
      } else {
        btnAll.className = 'px-2.5 py-1 rounded bg-white text-emerald-700 shadow-xs';
        btnUfm.className = 'px-2.5 py-1 rounded text-slate-600 hover:text-slate-900 transition';
      }
      fetchLogs();
    }

    function toggleBot4LogSort() {
      bot4LogSortAsc = !bot4LogSortAsc;
      const btnText = document.getElementById('bot4-sort-text');
      const btnIcon = document.querySelector('#bot4-sort-btn i');
      if (bot4LogSortAsc) {
        if (btnText) btnText.innerText = 'Cũ nhất trên';
        if (btnIcon) btnIcon.className = 'fa-solid fa-arrow-up-short-wide text-amber-400';
      } else {
        if (btnText) btnText.innerText = 'Mới nhất trên';
        if (btnIcon) btnIcon.className = 'fa-solid fa-arrow-down-short-wide text-cyan-400';
      }
      fetchLogs();
    }

    async function fetchLogs() {
      try {
        const url = (currentLogUfmScope === 'ALL') ? '/api/all-logs?limit=80' : '/api/logs?limit=80';
        const res = await fetch(url);
        const data = await res.json();
        if (data.status === 'ok') {
          renderLogs(data.logs || []);
        }
      } catch (err) {
        console.error('Lỗi tải logs:', err);
      }
    }

    function renderLogs(logs) {
      const container = document.getElementById('console-stream');
      if (!logs || logs.length === 0) {
        container.innerHTML = '<div class="text-slate-500">Chưa có nhật ký ghi nhận...</div>';
        return;
      }

      // Sắp xếp: bot4LogSortAsc = true (Cũ nhất trên) -> reverse; ngược lại giữ nguyên DESC (Mới nhất trên)
      const sortedLogs = bot4LogSortAsc ? [...logs].reverse() : [...logs];

      container.innerHTML = sortedLogs.map(l => {
        let badgeColor = 'bg-blue-900/60 text-blue-400 border-blue-800';
        if (l.level === 'SCAN') badgeColor = 'bg-cyan-950 text-cyan-400 border-cyan-800';
        else if (l.level === 'STUDENT' || l.level === 'ACTIVITY') badgeColor = 'bg-emerald-950 text-emerald-400 border-emerald-800';
        else if (l.level === 'WARN') badgeColor = 'bg-amber-950 text-amber-300 border-amber-800';
        else if (l.level === 'ZALO') badgeColor = 'bg-indigo-950 text-indigo-300 border-indigo-800';
        else if (l.level === 'MESSENGER') badgeColor = 'bg-purple-950 text-purple-300 border-purple-800';
        else if (l.level === 'ERROR') badgeColor = 'bg-rose-950 text-rose-400 border-rose-800';

        const timeStr = l.created_at || '';
        const botBadge = (currentLogUfmScope === 'ALL' && l.bot) ? `<span class="px-1.5 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-emerald-300 border border-slate-700 shrink-0">[${l.bot}]</span>` : '';

        // Dọn dẹp timestamp thừa trong nội dung tin nhắn
        let cleanMsg = String(l.message || '');
        cleanMsg = cleanMsg.replace(/^(\S+\s*)?\[\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\]\s*/, '$1');
        cleanMsg = cleanMsg.replace(/^\[\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\]\s*/, '');

        return `
          <div class="flex items-start gap-2 hover:bg-slate-800/40 px-2 py-1 rounded transition">
            <span class="text-slate-500 shrink-0 text-[11px] font-mono">${timeStr}</span>
            ${botBadge}
            <span class="px-1.5 py-0.5 rounded text-[10px] font-bold border ${badgeColor} shrink-0">${l.level}</span>
            <span class="text-slate-200 leading-relaxed break-all">${cleanMsg}</span>
          </div>
        `;
      }).join('');

      if (bot4LogSortAsc && document.getElementById('console-autoscroll') && document.getElementById('console-autoscroll').checked) {
        container.scrollTop = container.scrollHeight;
      }
    }

    function clearTerminalViewUFM() {
      document.getElementById('console-stream').innerHTML = '<div class="text-slate-500">Màn hình đã xóa. Đang chờ log tiếp theo...</div>';
    }

    // ================= CHANNELS & TARGET GROUPS =================
    async function renderAllActiveChannels() {
      try {
        const res = await fetch('/api/config');
        const data = await res.json();
        currentConfig = data.config || {};
        renderTargetGroupsEditor(currentConfig.zalo?.target_groups || []);
        
        // Messenger toggle status
        const isMsgerEnabled = currentConfig.messenger?.enabled || false;
        const mBtn = document.getElementById('msger-toggle-btn');
        if (mBtn) {
          mBtn.className = isMsgerEnabled ? 'px-3 py-1 rounded-lg text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-200' : 'px-3 py-1 rounded-lg text-xs font-bold bg-slate-100 text-slate-600 border border-slate-200';
          mBtn.innerText = isMsgerEnabled ? 'BẬT' : 'TẮT';
        }
      } catch (e) {
        console.error(e);
      }
    }

    function renderTargetGroupsEditor(groups) {
      const container = document.getElementById('targetGroupsEditor');
      if (!groups || groups.length === 0) {
        container.innerHTML = `<div class="p-4 text-center text-slate-400 text-xs">Chưa có nhóm Zalo nào. Hãy nhấn "+ Thêm Nhóm" hoặc "Đồng bộ từ Zalo".</div>`;
        return;
      }

      container.innerHTML = groups.map((g, idx) => `
        <div class="flex items-center justify-between p-3.5 bg-slate-50 border border-slate-200 rounded-xl hover:bg-slate-100/80 transition">
          <div class="flex items-center gap-3">
            <span class="w-6 h-6 rounded-lg bg-emerald-100 text-emerald-800 flex items-center justify-center text-xs font-bold font-mono">${idx+1}</span>
            <div>
              <div class="font-bold text-xs text-slate-900">${g.name || 'Nhóm ' + g.id}</div>
              <div class="text-[11px] text-slate-400 font-mono">ID: ${g.id} (${g.type || 'GROUP'})</div>
            </div>
          </div>

          <div class="flex items-center gap-2">
            <label class="relative inline-flex items-center cursor-pointer">
              <input type="checkbox" ${g.enabled !== false ? 'checked' : ''} onchange="toggleGroupEnabled(${idx}, this.checked)" class="sr-only peer">
              <div class="w-8 h-4.5 bg-slate-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-3.5 after:w-3.5 after:transition-all peer-checked:bg-emerald-600"></div>
            </label>
            <button onclick="triggerTestZalo('${g.id}', '${g.name}', '${g.type || 'GROUP'}')" class="px-2.5 py-1 text-xs font-bold text-indigo-700 bg-indigo-50 hover:bg-indigo-100 border border-indigo-200 rounded-lg transition" title="Bắn tin test thử vào nhóm này">
              Thử tin
            </button>
            <button onclick="deleteTargetGroup(${idx})" class="p-1 text-slate-400 hover:text-rose-600 transition" title="Xóa nhóm">
              <i class="fa-regular fa-trash-can"></i>
            </button>
          </div>
        </div>
      `).join('');
    }

    function toggleGroupEnabled(idx, val) {
      if (currentConfig.zalo?.target_groups?.[idx]) {
        currentConfig.zalo.target_groups[idx].enabled = val;
        saveZaloGroupsConfig();
      }
    }

    function deleteTargetGroup(idx) {
      if (currentConfig.zalo?.target_groups?.[idx]) {
        currentConfig.zalo.target_groups.splice(idx, 1);
        saveZaloGroupsConfig();
        renderTargetGroupsEditor(currentConfig.zalo.target_groups);
      }
    }

    async function saveZaloGroupsConfig() {
      try {
        await fetch('/api/config/save', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(currentConfig)
        });
      } catch (e) {
        console.error(e);
      }
    }

    async function openAddTargetGroupModal() {
      const { value: formValues } = await Swal.fire({
        title: 'Thêm Nhóm Zalo Mới',
        html:
          '<input id="swal-gid" class="swal2-input text-xs" placeholder="Nhập ID Nhóm (Thread ID)">' +
          '<input id="swal-gname" class="swal2-input text-xs" placeholder="Tên Nhóm Gợi Nhớ">',
        focusConfirm: false,
        showCancelButton: true,
        confirmButtonText: 'Thêm Ngay',
        preConfirm: () => {
          return [
            document.getElementById('swal-gid').value.trim(),
            document.getElementById('swal-gname').value.trim()
          ]
        }
      });

      if (formValues && formValues[0]) {
        if (!currentConfig.zalo) currentConfig.zalo = {};
        if (!currentConfig.zalo.target_groups) currentConfig.zalo.target_groups = [];
        currentConfig.zalo.target_groups.push({
          id: formValues[0],
          name: formValues[1] || ('Nhóm ' + formValues[0]),
          type: 'GROUP',
          enabled: true
        });
        saveZaloGroupsConfig();
        renderTargetGroupsEditor(currentConfig.zalo.target_groups);
      }
    }

    async function checkZaloSessionNow() {
      Swal.fire({
        title: 'Đang kiểm tra phiên Zalo...',
        allowOutsideClick: false,
        didOpen: () => { Swal.showLoading(); }
      });
      try {
        const res = await fetch('/api/zalo/check-status', { method: 'POST' });
        const data = await res.json();
        if (data.success) {
          Swal.fire('Hợp lệ!', data.message, 'success');
        } else {
          Swal.fire('Lỗi phiên', data.message, 'error');
        }
        fetchStatus();
      } catch (e) {
        Swal.fire('Lỗi', e.message, 'error');
      }
    }

    async function fetchZaloGroupsFromClient() {
      Swal.fire({
        title: 'Đang tải danh sách nhóm từ Zalo...',
        allowOutsideClick: false,
        didOpen: () => { Swal.showLoading(); }
      });
      try {
        const res = await fetch('/api/zalo/fetch-groups');
        const data = await res.json();
        if (data.success && data.groups && data.groups.length > 0) {
          if (!currentConfig.zalo) currentConfig.zalo = {};
          currentConfig.zalo.target_groups = data.groups;
          saveZaloGroupsConfig();
          renderTargetGroupsEditor(data.groups);
          Swal.fire('Đã đồng bộ!', `Tìm thấy và lưu ${data.groups.length} nhóm từ Zalo!`, 'success');
        } else {
          Swal.fire('Thông báo', data.message || 'Không tìm thấy nhóm nào.', 'info');
        }
      } catch (e) {
        Swal.fire('Lỗi', e.message, 'error');
      }
    }

    // ================= MESSENGER HANDLERS =================
    async function toggleMessengerChannel() {
      const isEnabled = currentConfig.messenger?.enabled || false;
      const newState = !isEnabled;
      try {
        const res = await fetch('/api/messenger/toggle', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ enabled: newState })
        });
        const data = await res.json();
        Swal.fire('Messenger', data.message, 'info');
        renderAllActiveChannels();
      } catch (e) {
        Swal.fire('Lỗi', e.message, 'error');
      }
    }

    async function checkMessengerSessionNow() {
      Swal.fire({
        title: 'Đang kiểm tra kết nối Messenger...',
        allowOutsideClick: false,
        didOpen: () => { Swal.showLoading(); }
      });
      try {
        const res = await fetch('/api/messenger/check-connection', { method: 'POST' });
        const data = await res.json();
        if (data.status === 'ok') {
          Swal.fire('Hợp lệ!', data.message, 'success');
        } else {
          Swal.fire('Lỗi phiên', data.message, 'error');
        }
      } catch (e) {
        Swal.fire('Lỗi', e.message, 'error');
      }
    }

    // ================= HISTORY TAB =================
    async function fetchHistory() {
      try {
        const res = await fetch('/api/delivery-history?limit=100');
        const data = await res.json();
        const tbody = document.getElementById('historyTableBody');
        const history = data.history || [];
        if (history.length === 0) {
          tbody.innerHTML = `<tr><td colspan="5" class="px-4 py-8 text-center text-slate-400">Chưa có lịch sử phát tin nào.</td></tr>`;
          return;
        }

        tbody.innerHTML = history.map(h => `
          <tr class="hover:bg-slate-50 transition">
            <td class="px-4 py-3 font-mono text-[11px] text-slate-500">${h.sent_time || '-'}</td>
            <td class="px-4 py-3 font-medium text-slate-900">${h.title || h.activity_id}</td>
            <td class="px-4 py-3"><span class="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-100 text-slate-700 font-mono">${h.action_type || 'NEW'}</span></td>
            <td class="px-4 py-3 font-mono text-[11px] text-slate-600">${h.target_name || h.target_id || 'Zalo Target'}</td>
            <td class="px-4 py-3"><span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">Thành Công</span></td>
          </tr>
        `).join('');
      } catch (e) {
        console.error(e);
      }
    }

    // ================= CONFIG TAB =================
    async function loadConfigForm() {
      try {
        const res = await fetch('/api/config');
        const data = await res.json();
        currentConfig = data.config || {};
        const p = currentConfig.ufm_portal || {};
        document.getElementById('cfg-portal-user').value = p.username || '';
        document.getElementById('cfg-portal-pass').value = p.password || '';
        document.getElementById('cfg-scan-interval').value = p.check_interval_seconds || 20;
      } catch (e) {
        console.error(e);
      }
    }

    async function savePortalConfig() {
      if (!currentConfig.ufm_portal) currentConfig.ufm_portal = {};
      currentConfig.ufm_portal.username = document.getElementById('cfg-portal-user').value.trim();
      currentConfig.ufm_portal.password = document.getElementById('cfg-portal-pass').value.trim();
      currentConfig.ufm_portal.check_interval_seconds = parseInt(document.getElementById('cfg-scan-interval').value) || 20;

      try {
        const res = await fetch('/api/config/save', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(currentConfig)
        });
        const data = await res.json();
        Swal.fire('Thành công', data.message, 'success');
      } catch (e) {
        Swal.fire('Lỗi', e.message, 'error');
      }
    }

    async function reloginUFM() {
      Swal.fire({
        title: 'Đang kết nối Cổng UFM...',
        text: 'Hệ thống đang tự giải mã ASP.NET Token và đăng nhập...',
        allowOutsideClick: false,
        didOpen: () => { Swal.showLoading(); }
      });
      try {
        const res = await fetch('/api/portal/login', { method: 'POST' });
        const data = await res.json();
        if (data.success) {
          Swal.fire('Thành công!', data.message, 'success');
        } else {
          Swal.fire('Thất bại', data.message, 'error');
        }
        fetchStatus();
      } catch (e) {
        Swal.fire('Lỗi', e.message, 'error');
      }
    }

    // ================= QUAD TEST MODAL HANDLERS =================
    async function openQuadTestModal(botId = 'bot4') {
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
        if (data.status === 'ok' && data.bots) {
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
          tab.className = (b === botId) ?
            "px-3 py-1.5 rounded-lg bg-white text-emerald-700 shadow-xs flex-1 text-center font-bold" :
            "px-3 py-1.5 rounded-lg text-slate-600 hover:text-slate-900 transition flex-1 text-center font-bold";
        }
      });
      renderQuadGroupsList(botId);
    }

    function renderQuadGroupsList(botId) {
      const container = document.getElementById('quad-groups-list');
      const botData = quadBotsData[botId];
      if (!botData || !botData.groups || botData.groups.length === 0) {
        container.innerHTML = `<div class="p-6 text-center text-slate-400 text-xs">Bot này chưa có nhóm mục tiêu nào trong cấu hình.</div>`;
        return;
      }

      container.innerHTML = botData.groups.map(g => `
        <div class="flex items-center justify-between p-3 bg-slate-50 border border-slate-200 rounded-xl hover:bg-slate-100 transition">
          <div class="flex items-center gap-2.5">
            <div class="w-7 h-7 rounded-lg bg-indigo-100 text-indigo-700 flex items-center justify-center text-xs font-bold font-mono">
              <i class="fa-solid fa-users"></i>
            </div>
            <div>
              <div class="font-bold text-xs text-slate-900">${g.name || 'Nhóm ' + g.id}</div>
              <div class="text-[11px] text-slate-400 font-mono">ID: ${g.id} (${g.type || 'GROUP'})</div>
            </div>
          </div>
          <button onclick="sendTestFromQuadModal('${g.id}', '${g.name}', '${g.type || 'GROUP'}', '${botId}')" class="px-3 py-1.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 rounded-lg text-xs font-bold transition flex items-center gap-1.5">
            <i class="fa-solid fa-paper-plane text-xs"></i> Gửi Test
          </button>
        </div>
      `).join('');
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
        if (res.ok && (data.success || data.status === 'ok')) {
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
        if (res.ok && (data.success || data.status === 'ok')) {
          if (statusDiv) {
            statusDiv.className = 'p-3 rounded-xl text-xs font-medium border bg-emerald-50 border-emerald-200 text-emerald-800 block';
            statusDiv.innerHTML = `✅ <b>Hoàn tất!</b> ${data.message}`;
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

    // ================= MODAL HANDLERS =================
    function openAddStudentModal() {
      document.getElementById('add-student-modal').classList.remove('hidden');
    }
    function closeAddStudentModal() {
      document.getElementById('add-student-modal').classList.add('hidden');
    }
    async function saveNewStudentFromModal() {
      const mssv = document.getElementById('modal-st-mssv').value.trim();
      const pwd = document.getElementById('modal-st-pwd').value.trim();
      const name = document.getElementById('modal-st-name').value.trim();
      const cls = document.getElementById('modal-st-class').value.trim();

      if (!mssv) {
        Swal.fire('Lưu ý', 'Vui lòng nhập MSSV!', 'warning');
        return;
      }

      Swal.fire({ title: 'Đang xác thực...', didOpen: () => { Swal.showLoading(); } });
      try {
        const res = await fetch('/api/student/submit', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ mssv: mssv, password: pwd, full_name: name, class_name: cls })
        });
        const data = await res.json();
        closeAddStudentModal();
        if (data.success) {
          Swal.fire('Thành công!', data.message, 'success');
        } else {
          Swal.fire('Chưa hoàn tất', data.message, 'warning');
        }
        fetchStudents();
        fetchStatus();
      } catch (e) {
        Swal.fire('Lỗi', e.message, 'error');
      }
    }

    function openBulkImportModal() {
      document.getElementById('bulk-import-modal').classList.remove('hidden');
    }
    function closeBulkImportModal() {
      document.getElementById('bulk-import-modal').classList.add('hidden');
    }
    async function submitBulkImport() {
      const text = document.getElementById('bulk-import-text').value.trim();
      if (!text) {
        Swal.fire('Lưu ý', 'Vui lòng dán danh sách tài khoản!', 'warning');
        return;
      }

      Swal.fire({ title: 'Đang xử lý import...', didOpen: () => { Swal.showLoading(); } });
      try {
        const res = await fetch('/api/students/bulk-import', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text_data: text })
        });
        const data = await res.json();
        closeBulkImportModal();
        if (data.success) {
          Swal.fire('Hoàn tất!', data.message, 'success');
        } else {
          Swal.fire('Chưa hoàn tất', data.message, 'warning');
        }
        fetchStudents();
        fetchStatus();
      } catch (e) {
        Swal.fire('Lỗi', e.message, 'error');
      }
    }

    function openZaloCookieModal() {
      document.getElementById('zalo-cookie-modal').classList.remove('hidden');
    }
    function closeZaloCookieModal() {
      document.getElementById('zalo-cookie-modal').classList.add('hidden');
    }
    async function submitZaloCookies() {
      const c = document.getElementById('modal-zalo-cookies').value.trim();
      if (!c) {
        Swal.fire('Lưu ý', 'Vui lòng dán JSON Cookies!', 'warning');
        return;
      }

      Swal.fire({ title: 'Đang lưu & xác thực...', didOpen: () => { Swal.showLoading(); } });
      try {
        const res = await fetch('/api/zalo/update-cookies', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ cookies: c })
        });
        const data = await res.json();
        closeZaloCookieModal();
        if (data.success) {
          Swal.fire('Thành công!', data.message, 'success');
        } else {
          Swal.fire('Thất bại', data.message, 'error');
        }
        fetchStatus();
      } catch (e) {
        Swal.fire('Lỗi', e.message, 'error');
      }
    }

    function openMessengerCookieModal() {
      Swal.fire({
        title: 'Cập nhật Cookie Messenger',
        input: 'textarea',
        inputPlaceholder: 'Dán JSON Cookies Messenger vào đây...',
        showCancelButton: true,
        confirmButtonText: 'Lưu Cookie'
      }).then(async (result) => {
        if (result.value) {
          try {
            const res = await fetch('/api/messenger/update-cookies', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ cookies: result.value })
            });
            const data = await res.json();
            Swal.fire('Messenger', data.message, data.status === 'ok' ? 'success' : 'error');
          } catch (e) {
            Swal.fire('Lỗi', e.message, 'error');
          }
        }
      });
    }

    // ================= INITIAL LOAD =================
    document.addEventListener('DOMContentLoaded', () => {
      fetchStatus();
      fetchActivities();
      fetchStudents();
      fetchLogs();
      setInterval(fetchStatus, 5000);
      setInterval(fetchLogs, 3000);
    });
  </script>
</body>
</html>'''

with open(index_html_path, "w", encoding="utf-8") as f:
    f.write(html_content)

print("Created vaa/ufm/templates/index.html successfully!")
