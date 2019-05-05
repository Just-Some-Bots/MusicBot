---
title: Updating
category: Using the bot
order: 4
---

[![GitHub stars](https://img.shields.io/github/stars/Just-Some-Bots/MusicBot.svg)](https://github.com/Just-Some-Bots/MusicBot/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/Just-Some-Bots/MusicBot.svg)](https://github.com/Just-Some-Bots/MusicBot/network)
[![Python version](https://img.shields.io/badge/python-3.5%2C%203.6%2C%203.7-blue.svg)](https://python.org)

> MucicBot version 1.9.8 requires Python 3.5.3 or higher. If you are updating the MusicBot with version below than 1.9.8, reinstall Python with the following version.
> - Windows: [[Download](https://www.python.org/ftp/python/3.7.0/python-3.7.0.exe)]
> - Mac: [[Download](https://www.python.org/ftp/python/3.6.6/python-3.6.6-macosx10.6.pkg)]
> - Linux: Install Python 3.6 and pip using your package manager
>
> If you are updating the MusicBot with version below than 1.9.7-rc2. Please follow instructions in the `Manual update` section.

Before updating, make sure to read the [latest changes](/changelog), as some behaviour may have changed significantly.

* **Linux/MacOS**: `./update.sh` (for Mac users: run this in a Terminal)
* **Windows**: Open `update.bat`.
* **Other**: Run `python update.py` on the command line.

## Manual update

```sh
git reset --hard  # Reset your current working directory
git pull  # Pull the latest changes from Git
python -m pip install -U -r requirements.txt  # Update the dependencies
```

### Common problems
#### error: Your local changes to the following files would be overwritten by merge
This indicates that you are trying to pull the latest updates from Git, but you've made changes to the bot's source files yourself. As a result, Git struggles to merge your changes with the bot's changes. To fix this, stash your changes first by running `git stash`, then run `git stash pop` after pulling.

Alternatively, discard your local changes by running `git reset --hard`.

> We do not support modification. If you are having issues updating because you have edited the bot's files, this is the most guidance you will get.

#### fatal: Not a git repository
This indicates that you have not installed the bot using Git. To be able to update, you need to install the bot using Git by following the guides on this site.

#### fatal: unable to access 'https://github.com/Just-Some-Bots/MusicBot.git' SSL certificate problem: self signed certificate in certificate chain
Try disabling your antivirus. Some antivirus software (such as Kaspersky Internet Security) is known to interfere with git.
