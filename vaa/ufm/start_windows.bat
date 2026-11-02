@echo off
chcp 65001 >nul
title Yuki 4 - UFM Bot Dashboard (Đại học Tài chính - Marketing)
color 0b

echo =================================================================
echo   [YUKI 4] BOT TU DONG CAO HOAT DONG & BAN ZALO TRUONG UFM
echo   Don vi: Truong Dai hoc Tai chinh - Marketing (UFM)
echo   Quan tri vien: Tran Le Phat (@yukilegit11-creator)
echo =================================================================
echo.
echo [1/2] Dang kiem tra moi truong Python...
python --version
if errorlevel 1 (
    echo [LOI] Khong tim thay Python! Vui long cai dat Python 3.10 tro len.
    pause
    exit /b
)

echo.
echo [2/2] Dang khoi dong Web Dashboard va Bot UFM 24/7...
python -u run_all.py

pause
