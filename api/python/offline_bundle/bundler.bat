@echo off
rem SPDX-License-Identifier: Apache-2.0
rem Copyright (C) 2026 SOLIDKOSMOS S.A.
rem
rem Make an offline installation bundle of the SK-RAFT Python client.
rem Run this script on a computer that has internet access.
rem
rem Usage: bundler.bat [options of make_bundle.py]
rem
rem Without options, the bundle is for Linux x86_64 and Windows amd64, and
rem for the Python version that runs the bundler. With options, the script
rem gives them to make_bundle.py as they are. For the options, run:
rem bundler.bat --help
rem
rem bundler.sh is the same script for Linux.
rem
rem The script uses the first Python that it finds:
rem   1. the Python that the PYTHON variable gives,
rem   2. the Python of the active virtual environment,
rem   3. the Python of .venv in this repository,
rem   4. the py launcher (py -3),
rem   5. python.
rem If that Python has no pip, the script creates a temporary virtual
rem environment and deletes it at the end.

setlocal EnableExtensions
set "HERE=%~dp0"
set "ROOT=%HERE%..\..\.."
set "BUNDLER=%HERE%make_bundle.py"
set "PY="
set "PYARGS="
set "TMPVENV="

if defined PYTHON set "PY=%PYTHON%"
if not defined PY if defined VIRTUAL_ENV (
    if exist "%VIRTUAL_ENV%\Scripts\python.exe" (
        set "PY=%VIRTUAL_ENV%\Scripts\python.exe"
    )
)
if not defined PY if exist "%ROOT%\.venv\Scripts\python.exe" (
    set "PY=%ROOT%\.venv\Scripts\python.exe"
)
if not defined PY (
    where py >nul 2>nul && set "PY=py" && set "PYARGS=-3"
)
if not defined PY (
    where python >nul 2>nul && set "PY=python"
)
if not defined PY (
    echo Cannot make the bundle: Python 3 is not installed. 1>&2
    exit /b 1
)

"%PY%" %PYARGS% -m pip --version >nul 2>nul
if not errorlevel 1 goto :run

set "TMPVENV=%TEMP%\skraft-bundler-%RANDOM%%RANDOM%"
echo %PY% has no pip. Create a temporary virtual environment.
"%PY%" %PYARGS% -m venv "%TMPVENV%"
if not errorlevel 1 goto :venv_ok
echo Cannot make the bundle: cannot create a virtual environment 1>&2
echo with %PY%. 1>&2
set "CODE=1"
goto :end

:venv_ok
set "PY=%TMPVENV%\Scripts\python.exe"
set "PYARGS="

:run
if "%~1"=="" (
    "%PY%" %PYARGS% "%BUNDLER%" --target linux-x86_64 --target windows-amd64
) else (
    "%PY%" %PYARGS% "%BUNDLER%" %*
)
set "CODE=%ERRORLEVEL%"

:end
if defined TMPVENV if exist "%TMPVENV%" rmdir /s /q "%TMPVENV%"
exit /b %CODE%
