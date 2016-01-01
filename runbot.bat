@echo off
SETLOCAL EnableDelayedExpansion
SET version=1
FOR /F "tokens=* USEBACKQ" %%H IN (`git --version`) DO SET gvar=%%F
IF /I NOT %gvar:~0,6% == git ve GOTO nogit
cls
FOR /f "delims=" %%a IN ('where python') DO (
    FOR /F "tokens=* USEBACKQ" %%F IN (`"%%a" -V`) DO (
	    cls
        SET var=%%F
    )
    SET var=!var:~7,5!
    IF !var! GTR !version! (
        SET version=!var!
        SET pypath="%%a"
    )
)
IF /I NOT %version:~0,3% == 3.5 GOTO errorhandler
%pypath% run.py
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
pause
