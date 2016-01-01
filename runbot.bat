@echo off
SETLOCAL EnableDelayedExpansion
SET version=1
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

:errorhandler
IF /I %version% == 0 GOTO nopython
ECHO ERROR: Bad version detected at %var%, please install Python 3.5.1
GOTO end

:nopython
ECHO ERROR: No install of Python has been detected. Please review the README for more information

:end
pause
