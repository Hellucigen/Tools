@echo off
title Mimesis Video Recompress
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0recompress_mimesis.ps1"
echo.
pause
