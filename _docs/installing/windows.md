---
title: Windows
category: Installing the bot
order: 2
---

<img class="doc-img" src="{{ site.baseurl }}/images/windows.png" alt="Windows" style="width: 75px; float: right;"/>

> If you do not clone the bot using Git, and instead download the ZIP file from GitHub and attempt to run it, you will receive an error.

MusicBot can be installed on Windows 7, 8, and 10 too, though it requires installing some programs on your computer first.

1. Install [Python 3.7](https://www.python.org/ftp/python/3.7.0/python-3.7.0.exe).
2. During the setup, tick `Install launcher for all users (recommended)` and `Add Python 3.7 to PATH` when prompted.
3. Install [Git for Windows](http://gitforwindows.org/).
4. During the setup, tick `Git from the command line and also 3rd-party software`, `Checkout Windows-style, commit Unix-style endings`, and `Use MinTTY (the default terminal MSYS2)`.
5. Open Git Bash by right-clicking an empty space inside of a folder (e.g My Documents) and clicking `Git Bash here`.
6. Run `git clone https://github.com/Just-Some-Bots/MusicBot.git MusicBot -b master` in the command window that opens.


After doing that, a folder called `MusicBot` will appear in the folder you opened Git Bash in. [Configure]({{ site.baseurl }}/using/configuration) your bot, then run `update.bat` to update your dependencies, then `run.bat` to start the MusicBot.
