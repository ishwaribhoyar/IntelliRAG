@echo off
echo ==============================================
echo   Starting IntelliRAG Application Preview
echo ==============================================
cd /d "%~dp0"
call backend\venv\Scripts\activate.bat
set PYTHONPATH=backend
echo IntelliRAG is starting at http://localhost:8000
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir backend --reload
pause
