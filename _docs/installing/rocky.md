---
title: Rocky
category: Installing the bot
order: 11
---

<img class="doc-img" src="{{ site.baseurl }}/images/rocky.png" alt="rocky" style="width: 75px; float: right;"/>

Installing the bot on Rocky is similar to [Ubuntu](/installing/ubuntu), but requires a different package manager.

# Rocky 9
~~~bash
# Update system repositories
sudo dnf -y update 

# Install dependencies
sudo dnf -y install epel-release
sudo dnf -y groupinstall "Development Tools"
sudo dnf -y install git openssl-devel bzip2-devel libffi-devel xz-devel

sudo dnf -y install https://mirrors.rpmfusion.org/free/el/rpmfusion-free-release-9.noarch.rpm
sudo dnf  config-manager --set-enabled crb
sudo dnf -y install ffmpeg


# Install Python (skip this if `python3 --version` shows python 3.8.18 or newer is installed)
sudo dnf install -y python3 

# Install pip
curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
python3 get-pip.py

# Clone the MusicBot to your home directory
cd ~
git clone https://github.com/Just-Some-Bots/MusicBot.git MusicBot -b master
cd MusicBot

# Install dependencies
python3 -m pip install --upgrade pip
python3 -m pip install --upgrade -r requirements.txt
~~~

After this, you can find a folder called `MusicBot` inside your home directory. [Configure]({{ site.baseurl }}/using/configuration) it, and then run `bash ./run.sh` to start the bot.