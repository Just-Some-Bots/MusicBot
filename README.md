# MusicBot

[![GitHub release](https://img.shields.io/github/release/Just-Some-Bots/MusicBot.svg?style=flat-square)](https://github.com/Just-Some-Bots/MusicBot/wiki)
[![Python](https://img.shields.io/badge/python-3.5%2C%203.6-blue.svg?style=flat-square)](https://www.python.org/downloads/)
[![Discord](https://img.shields.io/discord/129489631539494912.svg?style=flat-square)](https://discord.gg/bots)

MusicBot is the original Discord music bot written for [Python](https://www.python.org "Python homepage") 3.5+, using the [discord.py](https://github.com/Rapptz/discord.py) library. It plays requested songs, from YouTube and other services, into a Discord server (or multiple servers) and if the queue becomes empty it will play through a list of existing songs, if configured to do so. The bot features a permissions system allowing owners to restrict commands to certain people. As well as playing songs, MusicBot is capable of streaming live media into a voice channel (experimental).

## Setup
Setting up the MusicBot is relatively painless - just follow one of the [guides](https://github.com/Just-Some-Bots/MusicBot/wiki) we have created for you. After that, you can begin to configure your bot to ensure that it can connect to Discord.

The main configuration file is `config/options.ini`, but is not included. Simply make a copy of `example_options.ini` and rename to `options.ini`. See `example_options.ini` for more information on how to configure it.

### Commands

There are many commands that can be used with the bot. Most notably, the `play <url>` command (preceded by your command prefix) will download, process, and play a song from YouTube or a similar site. A full list of commands are available [here](https://github.com/SexualRhinoceros/MusicBot/wiki/Commands-list "Commands list").

### Further reading

* [Support Discord server](https://discord.gg/bots)
* [Project license](LICENSE)