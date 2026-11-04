#!/bin/sh

# Lấy cổng do Render cấp phát (mặc định 8000 nếu chạy local)
PORT=${PORT:-8000}

# Múi giờ chuẩn Việt Nam GMT+7
export TZ="Asia/Ho_Chi_Minh"

echo "=========================================================="
echo "🚀 ĐANG KHỞI ĐỘNG HỆ THỐNG HUIT SOCIAL BOT 24/7"
echo "🌐 Web Dashboard Port: $PORT"
echo "=========================================================="

# 1. Khởi chạy Web Dashboard ở chế độ nền
uvicorn web_app:app --host 0.0.0.0 --port $PORT &

# Nếu môi trường đặt DISABLE_BOTS=true (ví dụ Render chỉ dùng làm Web UI, còn Bot chạy trên Cloud VPS)
if [ "$DISABLE_BOTS" = "true" ]; then
    echo "⏸️ DISABLE_BOTS=true: Chỉ duy trì Web Dashboard, toàn bộ 5 Bot đã được chuyển giao cho Cloud VPS vận hành độc lập."
    wait
else
    # 2. Khởi chạy đồng thời toàn bộ 5 Bot (HUIT + VAA + IUH + UFM + OU ĐRL) liên tục 24/7 ở foreground
    python -u run_all.py
fi
