@ECHO off
SETLOCAL EnableDelayedExpansion

CD /d "%~dp0"

SET version=1
FOR /F "tokens=* USEBACKQ" %%H IN (`git --version`) DO SET gvar=%%F
IF /I NOT %gvar:~0,6% == git ve GOTO nogit
CLS

IF EXIST C:\Windows\py.exe (
	CMD /k C:\Windows\py.exe -3.5 -m pip install --upgrade -r requirements.txt
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

IF /I NOT %version:~0,3% == 3.5 GOTO errorhandler
CMD /k %pypath% -m pip install --upgrade -r requirements.txt
GOTO end

:errorhandlerpy
IF /I %version% == 0 GOTO nopython
ECHO ERROR: Bad version detected at %var%, please install Python 3.5+
GOTO end

:nogit
ECHO ERROR: Git Installation not detected. Git is required to install dependencies.
GOTO end

:nopython
ECHO ERROR: No install of Python has been detected. Python 3.5+ is required.

:end
PAUSE
