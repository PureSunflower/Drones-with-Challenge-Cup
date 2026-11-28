@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m dashboard.main_window
    goto :done
)
if exist ".gui-deps\PySide6" set "PYTHONPATH=%~dp0.deps;%~dp0.gui-deps;%PYTHONPATH%"
for /d %%P in ("%LocalAppData%\Programs\Python\Python3*") do (
    if exist "%%~fP\python.exe" set "DRONES_PYTHON=%%~fP\python.exe"
)
if defined DRONES_PYTHON (
    "%DRONES_PYTHON%" -m dashboard.main_window
) else (
    python -m dashboard.main_window
)
:done
if errorlevel 1 pause
