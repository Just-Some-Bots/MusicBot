---
title: 1.9.6
type: major
---

This is a courtesy release to merge commits from the review branch into master that have been on that branch for a long time. There are a lot of things that have changed code-wise, but the end user functionality generally remains the same.

### Notable changes
For a definitive list of changes, [view the commits](https://github.com/Just-Some-Bots/MusicBot/commits/1.9.6).

* Support for streaming (`!stream`) has been added, but may be buggy - use at your own risk
* The bot allows Python 3.6 and later versions to run it - not guaranteed to work
* A lot of code has been cleaned up and/or rewritten
* Additional sanity checks have been added
* The bot now uses the `logging` module rather than printing to stdout normally, also uses `colorlog`
* Voice code has been improved
* Autopausing has been improved
* Dev commands have been added, dev IDs can be added in config
* Fixed several issues, including one when trying to run the bot using recent discord.py versions

### Notes
With this release, a LICENSE file has been added to the repo. While we've always stated that this bot as being under the MIT license, we've now made this known properly.

**Please avoid downloading the ZIP of this release unless absolutely necessary.** Follow the [guides](https://github.com/Just-Some-Bots/MusicBot/wiki) on the wiki to learn how to install the bot instead, or if you've already installed it, [update the bot](https://github.com/Just-Some-Bots/MusicBot/wiki/Updating).