---
title: Debian
category: Installing the bot
order: 5
---

<img class="doc-img" src="{{ site.baseurl }}/images/debian.png" alt="debian" style="width: 75px; float: right;"/>

Installing the bot on Debian is similar to [Ubuntu](/installing/ubuntu), but requires some additional system dependencies obtained through `apt`.

~~~ bash
# Update system repositories
sudo apt-get update -y
sudo apt-get upgrade -y

# Install dependencies
sudo apt-get install git libopus-dev libffi-dev libsodium-dev ffmpeg -y
sudo apt-get install build-essential libncursesw5-dev libgdbm-dev libc6-dev zlib1g-dev libsqlite3-dev tk-dev libssl-dev openssl -y

# If using Debian Stretch or lower, you need to install Python too using...
sudo apt-get install python3.5 -y

# Clone the MusicBot to your home directory
cd ~
git clone https://github.com/Just-Some-Bots/MusicBot.git MusicBot -b master
cd MusicBot

# Install dependencies
sudo -H python3.5 -m pip install --upgrade pip
sudo -H python3.5 -m pip install --upgrade -r requirements.txt
~~~

After this, you can find a folder called `MusicBot` inside your home directory. [Configure]({{ site.baseurl }}/using/configuration) it, and then run `./run.sh` to start the bot.
