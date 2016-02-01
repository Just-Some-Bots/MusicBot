@ECHO off
SETLOCAL EnableDelayedExpansion
CHCP 65001

CD /d "%~dp0"

SET version=1
FOR /F "tokens=* USEBACKQ" %%H IN (`git --version`) DO SET gvar=%%F
IF /I NOT %gvar:~0,6% == git ve GOTO nogit
CLS

IF EXIST C:\Windows\py.exe (
	CMD /k C:\Windows\py.exe -3 run.py
    GOTO end
)

FOR /f "delims=" %%a IN ('C:\Windows\System32\where.exe python') DO (
    FOR /F "tokens=* USEBACKQ" %%F IN (`"%%a" -V`) DO (
	    CLS
        SET var=%%F
    )
    SET var=!var:~7,5!
    IF !var! GTR !version! (
        SET version=!var!
        SET pypath="%%a"
    )
)

IF /I NOT %version:~0,3% == 3.5 GOTO errorhandlerpy
CMD /k %pypath% run.py
GOTO end

:errorhandlerpy
IF /I %version% == 0 GOTO nopython
ECHO ERROR: Bad version detected at %var%, please install Python 3.5.1
GOTO end

:nogit
ECHO ERROR: Git Installation not detected. Please review the README for more information
GOTO end

:nopython
ECHO ERROR: No install of Python has been detected. Please review the README for more information

:end
PAUSE
