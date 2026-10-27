@echo off
REM Luminaz - start the app on this computer, then open http://127.0.0.1:5000 in your browser.
cd /d "%~dp0"
where py >nul 2>nul && set PY=py -3 || set PY=python
%PY% -c "import flask" 2>nul || %PY% -m pip install --user flask
if not exist instance\luminaz.sqlite (
  echo First run: loading sample data so there is something to look at.
  %PY% manage.py demo
)
start "" http://127.0.0.1:5000
%PY% run.py
pause
