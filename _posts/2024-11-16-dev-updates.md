---
title: Is this 3.0?
type: major
---

Many additions and changes have been made since the last change log entry in May.  
This post will list a summary of important changes per month since the last post.  

**November 2024**

- Refactor of discord message handling to make behaviour of commands consistent with options.  
- Refactor i18n with Gettext and bundled tools to enable translation and customization of MusicBot text.  
  Please see the [`./i18n/readme.md`](https://github.com/Just-Some-Bots/MusicBot/i18n/readme.md) file for more info on how translations work and how to use them.  
- Updates to many parts of the guides and documentation.
- Adds `setalias` command.  
- Adds several dev-only commands for project maintenance.  
- Adds option for Opus audio, for reduced CPU usage.  
- Adds option to remove embed footer.  
- Adds options to control message delete delay, with a short and long times.  
- Adds sub-command syntax for permissions.
- Adds optional new command permissions mode to allow more complicated permissions.
- Enables MusicBot to generate example options & perms files.
- Enables MusicBot to generate missing options & perms files.
- Enables MusicBot to move all writable directories using `--write-dir` CLI flag.
- Rename oauth2 username to avoid conflict with yt-dlp.
- Replace docstring help with @command_helper decorator.
- Extend python logger class rather than virtually construct it.
- Fix CLI arg parsing logic to allow Python 3.13 to launch MusicBot.

**October 2024**  

- Improved Stage Channel handling with request to speak logic.  

**September 2024**  

- Update `install.sh` for Linux/Unix-like OS to add various command line options.
  Use `install.sh --help` to see those.
- Update `install.ps1` and `install.bat` for Windows to attempt auto-install of WinGet tool.
- Fixed some issues with updating ffmpeg via winget on windows.
- Added `autoplaylist add all` sub-command to add all of the queue to the autoplaylist.
- Added async lock to summon command.
- Bug fix for status message player total counting logic.
- Bug fixes for `playnext` and `seek` command.  

**August 2024**  

- Adds integrated OAuth2 support for yt-dlp, and several options to configure it.
- Updated example_options.ini file.
- Fix bug with playback speed.
- Changed discord.py for windows to fix issue with speed option.

**July 2024**  

- Adds an owner-only command `setcookies` to allow managing cookies remotely.  
- Continue to download songs when the header check request hits a timeout.  
- Changes downloader to randomize UA strings for each extraction when UA is not static via config.  
- Added support for `cookies.txt` file passed to yt-dlp by adding the file to the data folder to enable cookies. Must not be empty!  
- Add option to allow changing yt-dlp UA strings from dynamic to static / custom UA.  
- Add option to enable HTTP/HTTPS proxy for yt-dlp and media checking only. (APIs and ffmpeg will not use this proxy.)  
- Add option to count paused players, off by default to restore historic behavior of status message.  
- Add support for complex aliases, with arguments.  
- Re-enables pre-download for next track in the queue. (still no support for auto playlist tracks and the new-song edge case.)  
- Better handling of player inactivity checks to prevent premature disconnects.  
- Better handling of start-up failures to trigger installing dependencies.  
- Adds a check for ffmpeg being executable to start-up.  
- Windows will now prefer system-installed ffmpeg over using bundled bin/ exes.  
- Improved debug command flexibility.  
- Added dev-only command to generate markdown from config and permissions code. A step to generating documentations from the source.  
- General code clean up.  

**May 31st 2024**  

- Addressed an infinite loop bug.
- Improved error handling.
- Improved internal task management.

