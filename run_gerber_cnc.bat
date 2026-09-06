@echo off
REM Lanzador simple para gerber_cnc.exe
set SCRIPT_DIR=%~dp0
"%SCRIPT_DIR%\dist\gerber_cnc.exe"
pause
