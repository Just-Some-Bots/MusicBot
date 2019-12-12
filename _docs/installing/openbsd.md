---
title: OpenBSD
category: Installing the bot
order: 8
---

MusicBot can run on OpenBSD systems as well by installing missing dependencies via `pip` in a virtual environment. Note that the X11 sets must be installed, and `csh`  must be used to activate the virtualenv and execute the bot. `bash` works too, but `csh` already comes with every OpenBSD installation.

## OpenBSD 6.6

~~~ bash
# Install Python and native libraries
doas pkg_add python # select version 3.7.4
doas pkg_add ffmpeg
doas pkg_add libsodium
doas pkg_add git

# Ensure pip is set up
python3 -m ensurepip

# Create virtual environment
python3 -m venv musicbot_virtualenv
cd musicbot_virtualenv

# Activate the virtual environment
csh # if you aren't already running csh
source bin/activate.csh

# Clone the MusicBot
git clone https://github.com/Just-Some-Bots/MusicBot.git -b master
cd MusicBot

# Install Python dependencies
pip3 install -U pip
pip3 install -U -r requirements.txt
~~~

After doing those commands, you can [configure]({{ site.baseurl }}/using/configuration) the bot and then run it using `./run.py`.

In accordance with OpenBSD conventions, you are recommended to create a dedicated user for the bot in order to keep it privilege-separated from the rest of your system. Refer to the `useradd(1)` [manual page](https://man.openbsd.org/useradd) for more details. Refer to the `rc.d(8)` [manual page](https://man.openbsd.org/rc.d) for details on how to start the bot automatically on system startup.
