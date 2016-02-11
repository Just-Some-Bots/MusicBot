@ECHO off

CHCP 65001 > NUL
CD /d "%~dp0"

IF EXIST %SYSTEMROOT%\py.exe (
    CMD /k py.exe -3.5 run.py
    EXIT
)

rem git --version > NUL 2>&1
rem IF %ERRORLEVEL% NEQ 0 GOTO nogit

python --version > NUL 2>&1
IF %ERRORLEVEL% NEQ 0 GOTO nopython

CMD /k python run.py
GOTO end

rem :nogit
rem ECHO ERROR: Git has either not been installed or not added to your PATH.
rem GOTO end

:nopython
ECHO ERROR: Git has either not been installed or not added to your PATH.

:end
PAUSE
