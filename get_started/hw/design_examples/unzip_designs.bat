@echo off
rem SPDX-License-Identifier: Apache-2.0
rem Copyright (C) 2026 SOLIDKOSMOS S.A.
rem
rem Unpack the prebuilt design files (bitstream, EBD, LL and XDC files).
rem The ZIP file must be in the same directory as this script.
rem The result is basys3\<top>\ and zedboard\<top>\ in this directory.
setlocal

cd /d "%~dp0"
set "ZIP=design_examples.zip"

if not exist "%ZIP%" (
    echo Error: %ZIP% not found in %CD%
    exit /b 1
)

where tar >nul 2>&1
if %errorlevel%==0 (
    tar -xf "%ZIP%"
) else (
    powershell -NoProfile -Command "Expand-Archive -Force -LiteralPath '%ZIP%' -DestinationPath '.'"
)
if errorlevel 1 (
    echo Error: could not extract %ZIP%
    exit /b 1
)

echo Design files extracted to %CD%
