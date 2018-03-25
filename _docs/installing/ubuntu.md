---
title: Ubuntu
category: Installing the bot
order: 1
---

<img class="doc-img" src="{{ site.baseurl }}/images/ubuntu.png" alt="Ubuntu" style="width: 75px; float: right;"/>

Installing MusicBot on Ubuntu via the command line is the **recommended way to install the bot**, though the system dependencies differ depending on what version of Ubuntu you are using. Firstly, lets install the dependencies required for your system:

## Ubuntu 14.04
~~~ bash
# Install build tools
sudo apt-get install build-essential unzip -y
sudo apt-get install software-properties-common -y

# Add external repositories
sudo add-apt-repository ppa:deadsnakes -y
sudo add-apt-repository ppa:mc3man/trusty-media -y
sudo add-apt-repository ppa:chris-lea/libsodium -y

# Install system dependencies
sudo apt-get update -y
sudo apt-get install git python python3.5-dev libav-tools libopus-dev libffi-dev libsodium-dev python3-pip -y
sudo apt-get upgrade -y

# Clone the MusicBot to your home directory
git clone https://github.com/Just-Some-Bots/MusicBot.git ~/MusicBot -b master
cd ~/MusicBot

# Install Python dependencies
sudo python3.5 -m pip install -U pip
sudo python3.5 -m pip install -U -r requirements.txt 
~~~

## Ubuntu 16.04
~~~ bash
# Install build tools
sudo apt-get install build-essential unzip -y
sudo apt-get install software-properties-common -y

# Add external repositories
sudo add-apt-repository ppa:mc3man/xerus-media -y

# Install system dependencies
sudo apt-get update -y
sudo apt-get install git ffmpeg libopus-dev libffi-dev libsodium-dev python3-pip python3-dev -y
sudo apt-get upgrade -y

# Clone the MusicBot to your home directory
git clone https://github.com/Just-Some-Bots/MusicBot.git ~/MusicBot -b master
cd ~/MusicBot

# Install Python dependencies
sudo python3 -m pip install -U pip
sudo python3 -m pip install -U -r requirements.txt 
~~~

After doing those commands, you can [configure](#guidesconfiguration) the bot and then run it using `sudo ./run.sh`.