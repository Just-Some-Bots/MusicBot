---
title: Updating
position: 3
---

![GitHub release](https://img.shields.io/github/release/Just-Some-Bots/MusicBot.svg?style=flat-square)

To update the bot, open the **console** (Linux)/**Terminal** (OSX)/**Git Bash** (Windows) and run the following command:

    git pull

Make sure you run the command in the folder you have the bot installed to. Afterwards, update your dependencies by running the correct file for your system.

If you get an error similar to `Your local changes to the following files would be overwritten by merge`, backup your `autoplaylist.txt` file to another location, then run `git reset --hard` and then `git pull` again. Be aware that `git reset --hard` discards your local changes to the bot's files, so if you modified the bot, it will undo those changes. If you have made changes to the code, consider stashing them or performing a merge. We don't help with modified versions of the bot, so lookup how to work with stashes and merges on Google if this is an issue.
{: .warning }

**Important:** If you **did not** originally follow our guides and instead downloaded the bot manually, this command will not work for you. Instead, reinstall the bot properly using the appropriate guide for your operating system on this wiki.
{: .error }