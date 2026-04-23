@echo off
echo Deteniendo servidor...
taskkill /f /im pythonw.exe >nul 2>&1
taskkill /f /im python.exe /fi "WINDOWTITLE eq web_app*" >nul 2>&1
echo Servidor detenido.
