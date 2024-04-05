@ECHO off

CHCP 65001 > NUL

REM --> This script only exists to easily launch the PowerShell script.
REM --> By default powershell might error about running unsigned scripts...

powershell.exe -noprofile -executionpolicy bypass -file install.ps1
