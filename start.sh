#!/bin/sh

# Lấy cổng do Render cấp phát (mặc định 8000 nếu chạy local)
PORT=${PORT:-8000}

# Múi giờ chuẩn Việt Nam GMT+7
export TZ="Asia/Ho_Chi_Minh"

echo "=========================================================="
echo "🚀 ĐANG KHỞI ĐỘNG HỆ THỐNG TRÊN RENDER CLOUD 24/7"
echo "🌐 Web Dashboard Port: $PORT"
echo "=========================================================="

# 1. Khởi chạy Web Dashboard ở chế độ nền
uvicorn web_app:app --host 0.0.0.0 --port $PORT &

# 2. Khởi chạy đồng thời cả 4 Bot (HUIT + VAA + IUH + UFM ĐRL) liên tục 24/7 ở chế độ chính (foreground)
python -u run_all.py

