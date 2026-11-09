@echo off
rem SPDX-License-Identifier: Apache-2.0
rem Copyright (C) 2026 SOLIDKOSMOS S.A.
rem
rem Install the SK-RAFT Python client from this offline bundle.
rem Usage: install.bat [--venv PATH]
rem Set PYTHON to use a specific interpreter, for example
rem set PYTHON=C:\Python311\python.exe

setlocal
set "HERE=%~dp0"

if defined PYTHON (
    "%PYTHON%" "%HERE%install.py" %*
    goto :end
)
if defined VIRTUAL_ENV (
    python "%HERE%install.py" %*
    goto :end
)
where py >nul 2>nul
if not errorlevel 1 (
    py -3 "%HERE%install.py" %*
    goto :end
)
where python >nul 2>nul
if not errorlevel 1 (
    python "%HERE%install.py" %*
    goto :end
)
echo Cannot install: Python 3 is not installed. 1>&2
exit /b 1

:end
set "CODE=%ERRORLEVEL%"
if not defined SKRAFT_NO_PAUSE pause
exit /b %CODE%
