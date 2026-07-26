@echo off
setlocal
cd /d "%~dp0"
title MARK Installer
echo.
echo MARK installer for Windows
echo ==========================
echo.
where py >nul 2>nul
if errorlevel 1 (
  where python >nul 2>nul
  if errorlevel 1 (
    echo Python 3 was not found.
    echo.
    echo Please install Python 3 from https://www.python.org/downloads/windows/
    echo During installation, check the box labelled "Add Python to PATH".
    echo Then run this installer again.
    echo.
    pause
    exit /b 1
  )
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-chp-alerter.ps1"
if errorlevel 1 (
  echo.
  echo MARK could not start. Review runtime\mark-gui-error.log for details.
  pause
)
