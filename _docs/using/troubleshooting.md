---
title: Troubleshooting
category: Using the bot
order: 6
---

This is a table of common issues and solutions for the bot. Please check here before leaving an issue on GitHub or asking for help in our [support server](https://discord.gg/bots).

---

## MusicBot was not installed using Git.  

This can happen if you did not use `git clone ...` to download MusicBot.  
The fix in this case is simply follow one of the guides or use the install scripts to get set up.  

This may also happen if you mess up file permissions in some way.  
The fix for this depends on the system you use, but typically you want to examine ownership and read/write access permissions and make sure they don't deny access from the user who launches MusicBot.  

---

## Failed environment check, ...  

These checks may fail if you have moved files around, broken file permissions, or have tried to start the bot outside of its cloned directory.  
It is recommended to use the bundled `run.bat` or `run.sh` as these will automatically change directory.  
Double check your file permissions are correct and if all else fails, re-install using a guide on this site.  

---

## Lagging while playing music  

This can happen for a number of reasons, usually involving network quality and/or CPU load.  
Newer versions of MusicBot make use of newer methods in discord.py which should help reduce CPU load.  
If your version is new enough, you can use the options `UseOpusProbe` or `UseOpusAudio` to adjust how audio is processed and reduce CPU load.  

---

## Bot can't login, bad credentials  

Check you copied the correct token from your [bot application page](https://discordapp.com/developers/applications/me) into your config file. It is called **Token**, not Client Secret.

---

## WebSocket connection is closed  

The bot tries to handle websocket disconnects, but sometimes there can be a problem, for example if Discord's voice servers go down. Try restarting the bot or switching server region if this error is persistent.

---

## ./run.sh: command not found  

While Git *should* preserve file permissions, you may need to set `run.sh` to be executable by running `chmod a+x run.sh`.

---

## Your config file is missing some options.  

This typically shows up after you update the bot.  
The warning just indicates your current options file is missing newly available options. 
Default settings are used for all missing options.  

Updates will usually include changes in `example_options.ini` file, so you can copy 
the new options from that file.  Alternatively, in newer versions, you can use the `config` command to manage missing options.  

---

## NameError: name 'everything' is not defined

Caused by using Python 3.13 with older versions of MusicBot. 
To fix this you can either downgrade Python, or upgrade MusicBot.
At time of writing this issue is resolved in the `dev` branch.  
Please note Python 3.13 "free-threaded" is not currently supported.

---

## Download failed due to ...  

As MusicBot depends almost entirely on yt-dlp, these errors can cover a broad range of causes.  
To deal with these, you'll want to make sure you have yt-dlp up-to-date, first and foremost.  

If the service you are using requires authorization of some sort, be sure to set 
that up or update it following the guides/docs provided by yt-dlp.  
In some cases, modifications to MusicBot may be required to enable new or existing 
options in yt-dlp. Feel free to bring those to our attention or contribute your changes to add the option for everyone.  

