# MusicBot

## What does it do?

It plays music in a plug.dj "request" style and if nothing is left it will play through a list of existing songs!

## Setup and Installation

Currently, you will need these things to run the bot:

  - [Python 3.5+](https://www.python.org/downloads/) (**not python 2.7**)
  - [Git](https://git-scm.com/download/win)

Ensure the following options are checked during installation:

#### Python
![python options](https://i.gyazo.com/2c06a7ee35afda3383185916fd2a94d3.png)


#### Git
![git options](https://cdn.discordapp.com/attachments/129489631539494912/129505383223001088/pic.png)

After python and git have been installed:
  - Make sure you have a Discord account ready for your bot.

## Configuration options

The options.txt file is in `.ini` format.  Example text:

```ini
[Credentials]
Username = musicbot
Password = honk

[Permissions]
OwnerID = 123456789123456789

[Chat]
CommandPrefix = $

[MusicBot]
DaysActive = 3
WhiteListCheck = no
SkipsRequired = 6
SkipRatio = 0.5
SaveVideos = yes
```

## Commands

The command character here is set to `!` for example purposes, but can be set to almost anything in the config.

`!whitelist @username` Adds the user to the whitelist to bypass the DaysActive check.

`!blacklist @username` Disallows the user from interacting with the bot.

`!help` Prints a list commands in chat.

`!joinserver invite_url_or_code` Tells the bot to join the linked server. Valid types:
  - `!joinserver https://discord.gg/0cDvIgU2voWAPofv`
  - `!joinserver https://discordapp.com/invite/0cDvIgU2voWAPofv`
  - `!joinserver 0cDvIgU2voWAPofv`

`!summon` Calls the bot to join whatever voice channel you're in.

`!play url` Adds the linked media to the queue.  [[Supported sites]](https://rg3.github.io/youtube-dl/supportedsites.html)
  - **Note:** While technically supported by youtube_dl, twitch.tv and other streaming sites will not work, due to the bot predownloading the content before it's played.

`!queue` Lists all the songs in queue, along with who added them.

`!pause` Pauses playback of the currently playing song.

`!resume` Resumes playback of the currently paused song.

`!shuffle` Mixes the playlist up.

`!skip` Vote to skip the current song.  The owner can skip at any time.

`!volume [ 1 - 100 | +X | -X ]` Sets the playback volume of the bot.  Don't type the brackets though.  Examples:
  - `!volume 20` Set the volume to 20.
  - `!volume +5` Increase the volume by 5.
  - `!volume -5` Decrease the volume by 5.

## Sounds cool, How do I use it?
Simply download the bot, set the dependencies up, then run `runbot.bat`! (or `runbot.sh` on mac/linux)

It'll let you know if it's connected and what channels are connected.

Once started, it's good to go. If you have any errors, report them here or on my discord and then restart the bot

Rhino Bot Help Discord - https://discord.gg/0iqN3da4zqrSz036

#FAQ

Q:`'pip' is not recognized as an internal or external command`

A: http://stackoverflow.com/questions/23708898/pip-is-not-recognized-as-an-internal-or-external-command

Q:`Bot prints 'no, not whitelisted and new' when I try to play something`

A: Add yourself to the whitelist!

Q:`I'm getting this error!` http://puu.sh/m6hkf/40eec0910c.png

A: The bot needs permission to delete messages. An option to toggle this behavior will be added eventually.

Q:`I'm having other errors with the bot, it has to be broken`

A: If Rhinobot is running in my discord, the bot isn't broken. I keep everything as updated as possible!

