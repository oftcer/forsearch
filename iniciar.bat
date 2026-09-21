@echo off
title ForSearch
cd /d "%~dp0"

where python >nul 2>&1
if %errorlevel%==0 (
    start "" pythonw "%~dp0search_app.py"
    if errorlevel 1 python "%~dp0search_app.py"
    exit /b
)

where py >nul 2>&1
if %errorlevel%==0 (
    start "" py -3 "%~dp0search_app.py"
    exit /b
)

echo Python nao encontrado. Instale Python 3 e marque "Add to PATH".
pause
