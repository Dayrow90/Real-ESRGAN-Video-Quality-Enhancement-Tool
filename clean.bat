@echo off
REM Clean Script for Video Enhancement Frames
REM This script directly deletes contents of output\frames_extract and output\frames_enhance folders

title Cleaning Frames

echo Cleaning output\frames_extract folder...
if exist "output\frames_extract\" (
    del /q "output\frames_extract\*" >nul 2>&1
    for /d %%i in ("output\frames_extract\*") do rmdir /q "%%i" >nul 2>&1
    echo Done.
) else (
    echo output\frames_extract folder does not exist.
)

echo Cleaning output\frames_enhance folder...
if exist "output\frames_enhance\" (
    del /q "output\frames_enhance\*" >nul 2>&1
    for /d %%i in ("output\frames_enhance\*") do rmdir /q "%%i" >nul 2>&1
    echo Done.
) else (
    echo output\frames_enhance folder does not exist.
)

echo.
echo Cleanup completed!