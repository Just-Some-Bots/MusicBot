# MusicBot JP

[![GitHub tag](https://img.shields.io/github/tag/kosugikun/MusicBot_JP.svg)]()
[![Python](https://img.shields.io/badge/python-3.5%2C%203.6-blue.svg?style=flat-square)](https://www.python.org/downloads/)
[![Discord](https://img.shields.io/discord/414411462207995904.svg?style=flat-square)](https://discord.gg/DuN7jvh)
[![GitHub license](https://img.shields.io/github/license/kosugikun/MusicBot_JP.svg)](https://github.com/kosugikun/MusicBot_JP/blob/master/LICENSE)

MusicBot JPは、[discord.py](https://github.com/Rapptz/discord)を使って[Python](https://www.python.org "Python homepage")3.5+用に書かれたオリジナルのDiscord音楽ボットです。ライブラリー。それは、YouTubeや他のサービスから、要求された曲をDiscordサーバー（または複数のサーバー）に再生し、キューが空になると、既存の曲のリストを再生するように構成されています。ボットは所有者がコマンドを特定の人に制限できるように権限システムを備えています。 MusicBotJPは、曲を再生するだけでなく、ライブメディアを音声チャンネルにストリーミングすることができます（実験的）。

![Main](https://i.imgur.com/EZljY52.png)

##セットアップ
MusicBotの設定は比較的簡単です。作成した[ガイド](https://github.com/Just-Some-Bots/MusicBot/wiki)に従ってください。その後、ボットがDiscordに接続できるようにボットを設定することができます。

The main configuration file is `config/options.ini`, but is not included. Simply make a copy of `example_options.ini` and rename to `options.ini`. See `example_options.ini` for more information on how to configure it.

### Commands

There are many commands that can be used with the bot. Most notably, the `play <url>` command (preceded by your command prefix) will download, process, and play a song from YouTube or a similar site. A full list of commands are available [here](https://github.com/Just-Some-Bots/MusicBot/wiki/Commands "Commands").

### Further reading

* [Project license](LICENSE)
