---
title: 26th April 2019
type: minor
---

**New versioning approach:**

From now on, MusicBot versions will use the date of the release to the `master` branch (shown as `release-DDMMYY` when running the bot), and not an arbitrary version number. This change is because it makes it easier to see how old the version is that a user is using, and because the old versioning was fairly nonsensical.

**Changes:**

* Add Taiwan (tradiitonal Chinese) translation file
* Change discord.py definition in requirements.txt to use PyPI version
* Stop the bot from throwing summon error on voice state update
* Fix "module 'aiohttp' has no attribute 'Timeout'" raised when queueing unrecognized source using the play command
* Add Spanish translation file
* Add Swedish translation file
* Added now playing message for automatic entries
* Fix Bandcamp album issue
* Fix an issue where the now playing message was not deleted after a song ended