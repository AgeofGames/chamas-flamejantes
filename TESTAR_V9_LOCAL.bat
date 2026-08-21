@echo off
title CHAMAS FLAMEJANTES V9 - TESTE LOCAL
cd /d "%~dp0"
echo ============================================================
echo  CHAMAS FLAMEJANTES V9 - TESTE LOCAL
echo ============================================================
echo.
if not exist ".venv\Scripts\python.exe" (
  echo Ambiente virtual nao encontrado.
  echo Execute INSTALAR.bat primeiro.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" app.py
pause
