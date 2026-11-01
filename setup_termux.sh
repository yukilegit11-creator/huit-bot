#!/data/data/com.termux/files/usr/bin/bash

echo "=========================================================="
echo "🚀 CÀI ĐẶT HỆ THỐNG BOT CÀO HUIT & BẮN ZALO 24/7 TRÊN TERMUX"
echo "=========================================================="

# 1. Cập nhật gói phần mềm Termux
pkg update -y && pkg install -y python git termux-api

# 2. Cài đặt các thư viện Python cần thiết
pip install --upgrade pip
pip install requests beautifulsoup4 zlapi fastapi uvicorn python-multipart

# 3. Kích hoạt chế độ chống ngủ khi tắt màn hình (Termux Wake Lock)
echo "🔒 Kích hoạt chế độ chạy nền không tắt (Wake Lock)..."
termux-wake-lock

# 4. Khởi động Bot chạy ngầm liên tục 24/24
echo "🚀 Đang khởi động Bot quét Facebook và Web Dashboard..."
nohup python -u bot.py > bot.log 2>&1 &
nohup uvicorn web_app:app --host 0.0.0.0 --port 8000 > web.log 2>&1 &

echo ""
echo "✅ BOT ĐÃ ĐƯỢC TREO THÀNH CÔNG VÀ ĐANG CHẠY 24/24!"
echo "👉 Để xem nhật ký cào bài & gửi Zalo: tail -f bot.log"
echo "👉 Truy cập Web Dashboard từ máy khác cùng mạng WiFi: http://$(ifconfig 2>/dev/null | grep 'inet ' | grep -v '127.0.0.1' | awk '{print $2}' | head -n 1):8000"
echo "=========================================================="
