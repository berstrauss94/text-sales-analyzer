@echo off
cd /d "%~dp0"
echo Iniciando servidor...
start /min "" pythonw web_app.py
timeout /t 2 /nobreak >nul
echo Servidor iniciado. Abre tu navegador en: http://localhost:5000
start http://localhost:5000
