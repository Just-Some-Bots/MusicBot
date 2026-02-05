---
title: Windows
category: Installing the bot
order: 2
---
<img class="os-icon" src="{{ site.baseurl }}/images/windows.png" alt="Windows Logo"/>

> If you do not clone the bot using Git, and instead download the ZIP file from GitHub and attempt to run it, you will receive an error.

MusicBot can be installed on Windows 7 through 11, though it requires installing some programs on your computer first.

## Manual Install with WinGet

These steps can be used to install on Windows 10 and 11, using mainly the WinGet tool.  
This is roughly the same process `install.ps1` follows, without some tweaks and fall-back methods.  

1. Download and install WinGet from this URL: [https://aka.ms/getwinget](https://aka.ms/getwinget)  
2. After installing winget, open PowerShell and run these commands:  
   ```bat
   winget install Git.Git
   winget install Python.Python.3.11 --custom "/passive Include_launcher=1"
   winget install ffmpeg
   winget install --id=DenoLand.Deno
```  
3. Close and re-open PowerShell. This reloads environment variables that changed from the earlier commands.  
4. Use the `cd` command to change to a suitable location for the install. Example: `cd C:\Users\Adam\`  
5. Run the following commands to download the bot code into a folder named "MusicBot" and then install python packages:
   ```bat
   git clone https://github.com/Just-Some-Bots/MusicBot.git -b dev "MusicBot"
   cd MusicBot
   py.exe -3.11 -m pip install -U -r requirements.txt
```  
6. Now you can [configure]({{ site.baseurl }}/using/configuration) your bot.  
7. Lastly run `run.bat` to start the MusicBot.  


## Manual Step-by-Step Install

These are older steps used to install MusicBot manually on Windows.  They may no longer be accurate, and are here mostly as a reference.  

1. Install [Python 3.10](https://www.python.org/ftp/python/3.10.13/python-3.10.13-amd64.exe).  
2. During the setup, tick `Install launcher for all users (recommended)` and `Add Python 3.10 to PATH` when prompted.  
3. Install [Git for Windows](http://gitforwindows.org/).  
4. During the setup, tick `Git from the command line and also 3rd-party software`, `Checkout Windows-style, commit Unix-style endings`, and `Use MinTTY (the default terminal MSYS2)`.  
5. Open Git Bash by right-clicking an empty space inside of a folder (e.g My Documents) and clicking `Git Bash here`.  
6. Run `git clone https://github.com/Just-Some-Bots/MusicBot.git MusicBot -b dev` in the command window that opens.  
7. Find a suitable way to install deno from: https://github.com/denoland/deno/  

After doing that, a folder called `MusicBot` will appear in the folder you opened Git Bash in. [Configure]({{ site.baseurl }}/using/configuration) your bot, then run `update.bat` to update your dependencies, then `run.bat` to start the MusicBot.
