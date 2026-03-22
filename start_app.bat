@echo off
title HomeNAS Launcher
echo ==========================================
echo Starting HomeNAS Zuin Stack
echo ==========================================

set "ACTIVATE_CMD="
set "PY_PREFIX="

if exist ".venv\Scripts\activate.bat" set "ACTIVATE_CMD=.venv\Scripts\activate.bat"
if defined ACTIVATE_CMD goto :FoundVenv

if exist "venv\Scripts\activate.bat" set "ACTIVATE_CMD=venv\Scripts\activate.bat"
if defined ACTIVATE_CMD goto :FoundVenv

echo No virtual environment found. Using system Python.
goto :StartServices

:FoundVenv
echo Found virtual environment: %ACTIVATE_CMD%
call %ACTIVATE_CMD%
set "PY_PREFIX=call %ACTIVATE_CMD% & "

:StartServices

:: 0. Prepare Environment
echo Running migrations...
%PY_PREFIX% python manage.py migrate --noinput
echo Collecting static files...
%PY_PREFIX% python manage.py collectstatic --noinput

:: 1. Start Redis check
echo Attempting to start Redis...
start "Redis Server" cmd /k "redis-server || echo Redis not found in PATH!"

timeout /t 3 /nobreak >nul

:: 2. Start Celery Worker
echo Starting Celery Worker...
start "Celery Worker" cmd /k "%PY_PREFIX% celery -A home_nas worker -l info -P solo"

:: 3. Start Celery Beat
echo Starting Celery Beat...
start "Celery Beat" cmd /k "%PY_PREFIX% celery -A home_nas beat -l info"

:: 4. Start Django Backend
echo Starting Django Server...
start "Django Server" cmd /k "%PY_PREFIX% python manage.py run_waitress"

:: 5. Start Django Backend
echo Starting SFTP Server...
start "SFTP Server" cmd /k "%PY_PREFIX% python manage.py run_sftp --port 2222"

:: 6. Start Frontend
echo Starting Frontend...
cd frontend
start "Frontend (Vite)" cmd /k "npm run dev"
cd ..

echo ==========================================
echo All services launched.
echo Backend:   http://localhost:8000
echo Frontend:  http://localhost:5173
echo ==========================================
echo If any window closes immediately, check for errors.
pause
