---
title: Breaking Changes for 2026
type: major
---

In this years changelog update, a new set of dependencies!  
To keep YouTube working, yt-dlp needs some extra bits now.  They're "optional" but also required, for youtube at least... 

Here is the summary of changes since our last changelog:  

**Python support changes**  

After this update, MusicBot requires python 3.10 or higher.  
Being that 3.10 is End-of-Life soon, maybe go for 3.11 or 3.12. 


**Dependency changes**

With the latest changes in yt-dlp, we have changed requirements.txt to use `yt-dlp[default]` which will include `yt-dlp-ejs` that enables the JS runtime support.  
Additionally, the `polib` python package was added to auto-compile i18n files, which should make translating or customizing text a bit easier.  

The "EJS" package needs a JavaScript runtime, like deno or node. Since yt-dlp recommended deno, and it appears to be easiest to manage, we've added it to our installers and guides.  

Lastly, `discord.py` library has been locked to version 2.6.4 for now, and the optional speed components have been removed as a default. Users may still add the speed components.  


**Feature changes**

Here is a short list of changes that were more than just bugs:

 - Removed Spotify Guest Mode, meaning Spotify support now requires you to provide API credentials.  
 - Updated `remove` command also allows range of songs or all songs from a mentioned user.  
 - Updated local media support to allow spaces in file names. (oops!)  
 - Added option `YtdlpConcurrentFrags` to allow multi-threaded download. That is, the number of child-threads each download thread is allowed to create.  
 - Save the last "now playing" channel between sessions. Also uses bound channels for auto now playing when possible.  


**General changes**  

Other noteworthy changes in this update include:  

 - Fixed bug in `play` with single-word searches.  
 - Fixed some error messages not properly formatting.  
 - Fixed file name too long errors.  
 - Try to fix queue message output being too large.  
 - Fix response sometimes showing "None" in markdown mode.  
 - Prevent bash scripts from being used on windows.  
 - Fix play by search not showing track info.  
 - Updated the `i18n/lang.py` tool, adding `--new` option.  
 - Add URL field to automatic now-playing messages.  
 - Fixed some language errors and updated translation data.  

