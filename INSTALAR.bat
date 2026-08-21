@echo off
chcp 65001 >nul
title Instalador - CHAMAS FLAMEJANTES
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 -m venv .venv
) else (
    where python >nul 2>nul
    if not %errorlevel%==0 (
        echo.
        echo Python nao encontrado.
        echo Instale o Python 3.11 ou superior e marque "Add Python to PATH".
        echo Depois execute este arquivo novamente.
        pause
        exit /b 1
    )
    python -m venv .venv
)

call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
pip install -r requirements.txt
echo.
echo Instalacao concluida.
echo Agora execute INICIAR.bat
pause
