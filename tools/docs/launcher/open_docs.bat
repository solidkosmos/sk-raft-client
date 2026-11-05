@echo off
rem SPDX-License-Identifier: Apache-2.0
rem Copyright (C) 2026 SOLIDKOSMOS S.A.
rem
rem Open the SK-RAFT documentation in the web browser, through a server
rem on this computer only. See README.txt. Stop it with Ctrl+C.
rem
rem Usage: open_docs.bat [--port PORT] [--no-browser]

setlocal
set "HERE=%~dp0"

where py >/dev/null 2>nul
if not errorlevel 1 (
    py -3 "%HERE%open_docs.py" %*
    goto :end
)
where python >/dev/null 2>nul
if not errorlevel 1 (
    python "%HERE%open_docs.py" %*
    goto :end
)
echo Cannot open the documentation: Python 3 is not installed.
echo Open index.html in the browser instead. See README.txt.
pause
exit /b 1

:end
set "CODE=%ERRORLEVEL%"
if not "%CODE%"=="0" pause
exit /b %CODE%
