---
title: Arch
category: Installing the bot
order: 7
---

<img class="doc-img" src="{{ site.baseurl }}/images/arch.png" alt="arch" style="width: 75px; float: right;"/>
Installation on Arch is **majorly untested and is not officially supported.** Please keep this in mind when seeking support.

~~~ bash
# Update system repositories
sudo pacman -Sy

# Install dependencies
sudo pacman -S base-devel git opus libffi libsodium ncurses gdbm glibc zlib sqlite tk openssl ffmpeg

# Install Python 3.6 from the AUR
git clone https://aur.archlinux.org/python36.git
cd python36
makepkg -sic

# Install pip to Python 3.6
curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
sudo python3.6 get-pip.py

# Clone the MusicBot to your home directory
cd ~
git clone https://github.com/Just-Some-Bots/MusicBot.git MusicBot -b master
cd MusicBot

# Install dependencies
sudo python3.6 -m pip install --upgrade pip
sudo python3.6 -m pip install --upgrade -r requirements.txt
~~~

Once everything has been completed, you can go ahead and [configure]({{ site.baseurl }}/using/configuration) the bot and then run with `sh ./run.sh`.
