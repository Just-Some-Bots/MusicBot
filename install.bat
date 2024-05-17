@ECHO off

CHCP 65001 > NUL

REM --> The install.bat script only exists to easily launch the PowerShell script.
REM --> By default powershell might error about running unsigned scripts...

CD "%~dp0"

SET InstFile="%~dp0%\install.ps1"
IF exist %InstFile% (
    powershell.exe -noprofile -executionpolicy bypass -file "%InstFile%"
) ELSE (
    echo Could not locate install.ps1
    echo Please ensure it is available to continue the automatic install.
)
