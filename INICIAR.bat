@echo off
chcp 65001 >nul
title CHAMAS FLAMEJANTES V5 - Age of Mythology Retold
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Primeira execucao: instalando o ambiente...
    call INSTALAR.bat
)

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo Nao foi possivel criar o ambiente Python.
    pause
    exit /b 1
)

start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:5000'"
echo.
echo ============================================================
echo   CHAMAS FLAMEJANTES
echo   Site:   http://127.0.0.1:5000
echo   Admin:  http://127.0.0.1:5000/admin
echo ============================================================
echo.
echo Nao feche esta janela enquanto o site estiver sendo usado.
echo.
".venv\Scripts\python.exe" app.py
pause
