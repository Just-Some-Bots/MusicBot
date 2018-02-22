# MusicBot JP

[![GitHub tag](https://img.shields.io/github/tag/expressjs/express.svg?style=flat-square)]()
[![Python](https://img.shields.io/badge/python-3.5%2C%203.6-blue.svg?style=flat-square)](https://www.python.org/downloads/)

MusicBot JPは、[discord.py](https://github.com/Rapptz/discord)を使って[Python](https://www.python.org "Python homepage")3.5+用に書かれたオリジナルのDiscord音楽ボットです。ライブラリー。それは、YouTubeや他のサービスから、要求された曲をDiscordサーバー（または複数のサーバー）に再生し、キューが空になると、既存の曲のリストを再生するように構成されています。ボットは所有者がコマンドを特定の人に制限できるように権限システムを備えています。 MusicBotJPは、曲を再生するだけでなく、ライブメディアを音声チャンネルにストリーミングすることができます（実験的）。

![Main](https://i.imgur.com/EZljY52.png)

##セットアップo
MusicBotの設定は比較的簡単です。作成した[ガイド](https://github.com/Just-Some-Bots/MusicBot/wiki)に従ってください。その後、ボットがDiscordに接続できるようにボットを設定することができます。

メインの設定ファイルは `config / options.ini`ですが、含まれていません。 `example_options.ini`のコピーを作り、` options.ini`に名前を変更するだけです。それを設定する方法の詳細については、 `example_options.ini`を参照してください。

### コマンド

ボットで使用できる多くのコマンドがあります。特に、コマンドプレフィックスの前にある `play <url>`コマンドは、YouTubeや類似のサイトから曲をダウンロード、処理、再生します。コマンドの完全なリストが利用可能です[ここ](https://github.com/Just-Some-Bots/MusicBot/wiki/Commands "Commands")。

### 参考文献

* [プロジェクトライセンス]（LICENSE）
