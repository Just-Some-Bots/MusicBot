@ECHO off

CD /d "%~dp0"

IF EXIST %SYSTEMROOT%\py.exe (
    CMD /k C:\Windows\py.exe -3.5 -m pip install --upgrade -r requirements.txt
    EXIT
)

python --version > NUL 2>&1
IF %ERRORLEVEL% NEQ 0 GOTO nopython

CMD /k python -m pip install --upgrade -r requirements.txt
GOTO end

:nopython
ECHO ERROR: Python has either not been installed or not added to your PATH.

:end
PAUSE
