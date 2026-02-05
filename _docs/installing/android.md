---
title: Android
category: Installing the bot
order: 9
---

Installing MusicBot on Android requires manual setup, some technical knowledge, and of course time.  
***Android is not officially supported*** primarilly due to lack of contributors who use the environment.  
The following steps may be completely incorrect or wildly out-of-date!  


## Install Steps

First, install [Termux](https://play.google.com/store/apps/details?id=com.termux) on your device.  

After your terminal is installed, you can run the following commands to start getting setup:

```bash

# Update system packages first.
pkg update
pkg upgrade

# Install system dependencies.
pkg install glib libffi cmake python git ffmpeg deno

# Switch to your home directory.
cd ~

# Clone the dev branch of MusicBot into a folder called 'MusicBot'.
git clone https://github.com/Just-Some-Bots/Musicbot.git MusicBot -b dev

# Now enter the MusicBot directory.
cd MusicBot

# Install python dependencies for MusicBot.
python -m pip install -U -r requirements.txt

```

Following this setup, you can <a href="{{ site.baseurl }}/using/configuration">configure the bot</a> and 
then run the bot with <code>./run.sh</code>  

Since Termux and Android are not officially supported, it is recommended to cofigure 
your `DebugLevel` option to `EVERYTHING` while getting set up and troubleshooting.  
