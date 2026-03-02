@echo off
REM Video Quality Enhancement Tool Startup Script

REM Set title
title Video Quality Enhancement Tool

REM Get current directory
set PROJECT_ROOT=%~dp0

REM Add ffmpeg.exe to system PATH temporarily
set PATH=%PROJECT_ROOT%;%PATH%

REM Launch the main program directly
echo Starting Video Quality Enhancement Tool...
"%PROJECT_ROOT%python\python.exe" "%PROJECT_ROOT%video_enhancer.py"

REM pause
pause