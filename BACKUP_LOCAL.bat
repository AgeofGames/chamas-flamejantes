@echo off
chcp 65001 >nul
cd /d "%~dp0"
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HH-mm-ss"') do set stamp=%%i
set destino=backups\%stamp%
mkdir "%destino%" >nul 2>nul
copy /Y "data\tournament.sqlite" "%destino%\tournament.sqlite" >nul
if exist "static\uploads" xcopy /E /I /Y "static\uploads" "%destino%\uploads" >nul
copy /Y "VERSAO.txt" "%destino%\VERSAO.txt" >nul
echo.
echo Backup criado em: %destino%
pause
