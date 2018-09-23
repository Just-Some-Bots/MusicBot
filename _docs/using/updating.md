---
title: Updating
category: Using the bot
order: 4
---

![GitHub release](https://img.shields.io/github/release/Just-Some-Bots/MusicBot.svg?style=flat-square)

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

#### fetal: unable to access 'https://github.com/Just-Some-Bots/MusicBot.git' SSL certificate problem: self signed certificate in certificate chain
try disabling your antivirus. Some antivirus (such as Kaspersky Internet Security) is known to interfere with git.
