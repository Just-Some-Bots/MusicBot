---
title: Updating
category: Using the bot
order: 4
---

![GitHub release](https://img.shields.io/github/release/Just-Some-Bots/MusicBot.svg?style=flat-square)

> As of 1.9.8, the bot no longer supports Python 3.5.2 and below due to some dependency depended on newer version of python. If you are updating the bot from version below than 1.9.8 then you need to update your python to the following version
> - Windows: Python 3.5.3 upward [[Download](https://www.python.org/ftp/python/3.7.0/python-3.7.0.exe)]
> - Mac: Python 3.6 [[Download](https://www.python.org/ftp/python/3.6.6/python-3.6.6-macosx10.6.pkg)]
> - Linux: Python 3.6 (do not forget to get pip)
>
> and then, follow instructions in the 'Manual update' section

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
