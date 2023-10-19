---
title: Android
category: Installing the bot
order: 9
---

Installing MusicBot on Android is simple, just time consuming.

Firstly, ensure you install [Termux](https://play.google.com/store/apps/details?id=com.termux) on your device.

After your terminal is installed, you can run the following commands to start getting setup:

```bash
# Update system packages
apt update -y
apt upgrade -y
```
```bash
# Install dependencies
pkg install glib libffi cmake
pkg install python git ffmpeg
```
```bash
# Clone MusicBot
cd ~
git clone https://github.com/Just-Some-Bots/Musicbot.git MusicBot -b master
cd MusicBot
python -m pip install -U -r requirements.txt
```

Following this setup, you can configure the bot and run the bot with

<pre class="code">./run.sh</pre>
