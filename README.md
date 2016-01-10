# RhinoBot: The music bot for Discord.

# :exclamation::exclamation: This is the old version of RhinoBot! :exclamation::exclamation:

The up-to-date rewrite is in the [develop branch](https://github.com/SexualRhinoceros/MusicBot/tree/develop). You should use the `develop` branch version, not the `master` branch version.

### What is this and what does it do?

RhinoBot is a very nifty Discord music bot written in [Python](https://www.python.org "Python homepage"). It plays requested songs and if the queue becomes empty it will play through a list of existing songs.

### How do I set it up?

**DO NOT FOLLOW THESE INSTRUCTIONS! INSTALL THE [DEVELOP BRANCH](https://github.com/SexualRhinoceros/MusicBot/tree/develop) VERSION.** Installation instructions will remain in this README.md file for history purposes:

1. Install [Python 3.5.1](https://www.python.org/downloads/)
    - Make sure you select this option in the Python install: ![Python install](https://camo.githubusercontent.com/72c0076cde5aa62745595fd6f3113ef0156ca5a2/687474703a2f2f692e696d6775722e636f6d2f3438716d524a302e706e67)
2. Install [Git](https://git-scm.com/download/win)
    - Make sure you select this option in the Git install: ![Git install](https://cdn.discordapp.com/attachments/129489631539494912/129505383223001088/pic.png)
3. Download the bot and [configure](#configuration-file) it in `options.txt`.
4. Install dependencies by running `fixnupdate.bat`.
5. Run bot with `runbot.bat`.

Once started, its good to go. If you have any errors, report them here or on my Discord and then restart the bot.

Discord help channel: [https://discord.gg/0iqN3da4zqrSz036](https://discord.gg/0iqN3da4zqrSz036)

### Configuration File

- **Line 1:** Email address of bot for Discord.
- **Line 2:** Password of bot for Discord.
- **Line 3:** Accepts "0" or "1", enables or disables the whitelist. 0 turning it off, 1 turning it on.
- **Line 4:** The number of days until a person can freely interact with the bot and not be on the whitelist.
- **Line 5:** The Owner's Discord user ID.
- **Line 6:** The number of votes to skip for it to actually skip.

### What are it's commands?

- `!whatismyuserid` will tell you your user ID.
- `!whitelist @username` will whitelist people (and you if the server is new!) so they can play music.
- `!blacklist @username` will disallow a person from interacting with the bot.
- `!play help` will summon a list of commands accepted by the bot.
- `!play url` will allow me to play a new song or add it to the queue.
- `!play playlist` will print out all links to youtube videos currently in the queue.
- `!play pause` will pause the playing of music! Will NOT pause the song but rather the playing of songs. Only usable by the bot's owner.
- `!play resume` will resume the playing of songs! Only usable by the bot's owner.
- `!play shuffle` will shuffle the songs in the playlist! Only usable by the bot's owner.
- `!play skip` will make it skip to the next song after 2 people vote! Instant skip though if used by the Bot's Owner.
- `!play volume level` will change the volume level! Default is 0.15 (15%). **MUST BE A NUMBER FROM 0-1.**

### FAQ

The FAQ can be accessed at [this wiki article](https://github.com/SexualRhinoceros/MusicBot/wiki/FAQ).
