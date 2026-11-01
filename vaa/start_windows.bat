@echo off
chcp 65001 > nul
title [YUKI 2] VAA BOT & DASHBOARD 24/7 (HỌC VIỆN HÀNG KHÔNG)

echo ======================================================================
echo 🚀 KHỞI ĐỘNG HỆ THỐNG YUKI 2 - VAA BOT (HỌC VIỆN HÀNG KHÔNG VIỆT NAM)
echo 👤 Quản trị viên: Trần Lê Phát (@yukilegit11-creator)
echo 🌐 Web Dashboard: http://localhost:5002
echo ======================================================================

start "YUKI 2 - VAA Web Dashboard (Port 5002)" cmd /k "python -u web_app.py"
timeout /t 2 > nul
start "YUKI 2 - VAA 24/7 Crawler & Zalo Alert" cmd /k "python -u bot.py"

echo.
echo ✅ Đã khởi chạy thành công cả Web Dashboard và Bot quét VAA!
echo Bạn có thể quản trị bot tại: http://localhost:5002
