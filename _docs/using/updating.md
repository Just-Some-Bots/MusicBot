---
title: Updating
category: Using the bot
order: 5
---

[![GitHub stars](https://img.shields.io/github/stars/Just-Some-Bots/MusicBot.svg)](https://github.com/Just-Some-Bots/MusicBot/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/Just-Some-Bots/MusicBot.svg)](https://github.com/Just-Some-Bots/MusicBot/network)
[![Python version](https://img.shields.io/badge/python-3.8%20to%203.13-blue.svg)](https://python.org)


> MucicBot requires Python 3.8 or higher.   

Before updating, make sure to read the [latest changes](/MusicBot/changelog), as some behaviour may have changed significantly.

## Automatic update script  

With any luck, in most cases you can update using the bundled update script.  
On Windows, the update script will attempt to update FFmpeg.  This is optional and can be skipped.    

* **Linux/MacOS**: `./update.sh` (for Mac users: run this in a Terminal)
* **Windows**: Open `update.bat`.
* **Other**: Run `python update.py` on the command line.

## Manual update steps.  

Use the following steps to manually update the MusicBot.  

> **Note:** You can use git to stash or create a local branch if you want to save your changes. 
We do not provide support for custom modifications.  If your modification solves an issue, please contribute your fix or report the issue with your findings.  


```sh

# Reset all changes you've made to musicbot.
git reset --hard

# Pull the latest changes from GitHub.
git pull

# Update the bot's Python dependencies.
python -m pip install -U -r requirements.txt

```

For other dependencies like FFmpeg or git, you'll need to use other tools specific to your OS.  
On Windows you may be able to use `WinGet` or find and use an installer package to update these applications.  
On mac OS you likely want to use `homebrew` or some modern package manager.  
On Linux and Unix-likes you will of course use your system package manager for these.  

> **Note:**  Updating ffmpeg and git is optional!  You should only update these if you need to, like if something is broken, vulnerable, or would perform better with a newer version. 
MusicBot does not have recommendations for specific versions, and leaves system administration up to the user.  


### Common problems
#### error: Your local changes to the following files would be overwritten by merge
This indicates that you are trying to pull the latest updates from Git, but you've made changes to the bot's source files yourself. As a result, Git struggles to merge your changes with the bot's changes. To fix this, stash your changes first by running `git stash`, then run `git stash pop` after pulling.

Alternatively, discard your local changes by running `git reset --hard`.

> We do not support modification. If you are having issues updating because you have edited the bot's files, this is the most guidance you will get.

#### fatal: Not a git repository
This indicates that you have not installed the bot using Git. To be able to update, you need to install the bot using Git by following the guides on this site.

#### fatal: unable to access 'https://github.com/Just-Some-Bots/MusicBot.git' SSL certificate problem: self signed certificate in certificate chain
Try disabling your antivirus. Some antivirus software (such as Kaspersky Internet Security) is known to interfere with git.
