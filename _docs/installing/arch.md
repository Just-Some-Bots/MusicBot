---
title: Arch
category: Installing the bot
order: 7
---

<img class="doc-img" src="{{ site.baseurl }}/images/arch.png" alt="centos" style="width: 75px; float: right;"/>
Installation on Arch is **majorly untested and is not officially supported** due to issues. Please keep this in mind when seeking support.

~~~# Update system packages
sudo pacman -Syu

# Install dependencies
sudo pacman -S git python python-pip opus libffi libsodium ncurses gdbm glibc zlib sqlite tk openssl

# Clone the MusicBot to your home directory
cd ~
git clone https://github.com/Just-Some-Bots/MusicBot.git MusicBot -b master
cd MusicBot

# Install dependencies
sudo pip install --upgrade pip
sudo pip install --upgrade -r requirements.txt
~~~

Once everything has been completed, you can go ahead and [configure]({{ site.baseurl }}/using/configuration) the bot and then run with `sudo ./run.sh`.
