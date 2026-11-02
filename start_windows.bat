@echo off
chcp 65001 >nul
title HUIT Social Crawler & Zalo Bot Monitor

echo ==============================================================
echo 🚀 ĐANG KHỞI ĐỘNG HỆ THỐNG CÀO FACEBOOK & BẮN ZALO 24/7
echo ==============================================================

:: Khởi chạy Web Dashboard ở cửa sổ nền
start "Web Dashboard (Port 8000)" cmd /k "python -m uvicorn web_app:app --host 0.0.0.0 --port 8000"

:: Đợi 2 giây cho web server sẵn sàng rồi tự mở trình duyệt
timeout /t 2 >nul
start http://localhost:8000

:: Khởi chạy cả 4 Bot (HUIT, VAA, IUH, UFM ĐRL) quét và bắn Zalo
echo.
echo 🔄 Đang khởi động đồng thời cả 4 Bot (HUIT + VAA + IUH + UFM ĐRL)...
python -u run_all.py


pause
