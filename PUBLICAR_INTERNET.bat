@echo off
chcp 65001 >nul
title Publicar CHAMAS FLAMEJANTES na Internet
cd /d "%~dp0"

if not exist "cloudflared.exe" (
    echo Coloque o arquivo cloudflared.exe nesta mesma pasta.
    echo Depois inicie primeiro o INICIAR.bat e execute este arquivo.
    pause
    exit /b 1
)

echo.
echo Gerando um endereco publico temporario...
echo Copie o endereco https://...trycloudflare.com que aparecer abaixo.
echo.
cloudflared.exe tunnel --url http://127.0.0.1:5000
pause
