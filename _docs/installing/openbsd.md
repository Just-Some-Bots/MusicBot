---
title: OpenBSD
category: Installing the bot
order: 8
---
MusicBot can run on OpenBSD systems as well. Note that the X11 sets must be installed, due to the `ffmpeg` dependency.

## OpenBSD 6.6

~~~bash
# Install Python and libraries available as packages
doas pkg_add python # select version 3.8 or above
doas pkg_add py3-aiohttp youtube-dl ffmpeg libsodium git

# Ensure pip is set up
python3 -m ensurepip

# Clone the MusicBot
git clone https://github.com/Just-Some-Bots/MusicBot.git -b review
cd MusicBot

# Install remaining dependencies
doas pip3 install -U pip
doas pip3 install -U -r requirements.txt
~~~

After doing those commands, you can [configure]({{ site.baseurl }}/using/configuration) the bot and then run it using `./run.py`.

In accordance with OpenBSD conventions, you are recommended to create a dedicated user for the bot in order to keep it privilege-separated from the rest of your system. Refer to the `useradd(1)` [manual page](https://man.openbsd.org/useradd) for more details. Refer to the `rc.d(8)` [manual page](https://man.openbsd.org/rc.d) for details on how to start the bot automatically on system startup.
