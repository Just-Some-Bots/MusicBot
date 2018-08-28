---
title: 1.9.8
type: major
---

**discord.py rewrite**

Starting from version 1.9.8, MusicBot requires the rewrite version of discord.py. It can be installed using the update files included, or by running `python3 -m pip install -U -r requirements.txt`.

Non-extensive list of changes:

* A fallback will be used if an i18n file cannot be parsed
* The save command now allows passing a custom URL
* Additional error handling has been added for experimental EQ
* Allow skipping bot update (but updating dependencies) when running the update script
* `LegacySkip` has been added as an option for those who prefer old skip behaviour
* Experimental EQ handling will now happen asynchronously
* Experimental EQ handling will take place after a track is downloaded, rather than before playing, to allow processing while the bot is playing other media
* A max search limit has been added to permissions
* Additional error handling has been added for Spotify
* `open.spotify.com` URLs are now supported
* Experimental EQ will no longer be enabled by default
* Changes have been made to the Dockerfile to allow it to work again
* discord.py now handles websocket reconnects and other issues, hopefully reducing the bot's random disconnects
* Fixed streams using the wrong options for ffmpeg
* Large Spotify playlists will now be handled properly
* Fix an issue with setting the bot's avatar

Translations have been contributed (thanks!):

* Japanese
* Korean