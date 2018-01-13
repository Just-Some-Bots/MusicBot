---
title: Installing on Raspbian
position: 5
---

<img class="doc-img" src="images/raspbian.png" alt="Raspbian" style="width: 75px;"/>

Installing MusicBot on Raspbian for use with a Raspberry Pi 2 or 3B is a long-winded process and may take a while to complete. If you're willing to try it, you can run the following commands in order to install it:

```bash
# Install dependencies
apt-get install sudo
apt-get install git
sudo apt-get update -y
sudo apt-get upgrade -y
sudo apt-get dist-upgrade
sudo apt-get install build-essential libncursesw5-dev libgdbm-dev libc6-dev
sudo apt-get install zlib1g-dev libsqlite3-dev tk-dev
sudo apt-get install libssl-dev openssl
sudo apt-get install build-essential unzip -y
sudo apt-get install software-properties-common -y
sudo add-apt-repository ppa:deadsnakes -y
sudo add-apt-repository ppa:mc3man/trusty-media -y
sudo add-apt-repository ppa:chris-lea/libsodium -y
sudo apt-get install libopus-dev libffi-dev libsodium-dev

# Build Python from scratch
cd ~
wget https://www.python.org/ftp/python/3.5.4/Python-3.5.4.tgz
tar -zxvf Python-3.5.4.tgz
cd Python-3.5.4
./configure
sudo make  # add -j4 to the end of this if you have a quad-core Raspberry Pi
sudo make install

# Install pip
cd ~
wget https://bootstrap.pypa.io/get-pip.py
sudo python3.5 get-pip.py

# Install H264 support
cd /usr/src
sudo git clone git://git.videolan.org/x264
cd x264
sudo ./configure --host=arm-unknown-linux-gnueabi --enable-static --disable-opencl
sudo make
sudo make install

# Install FFmpeg
cd /usr/src
sudo git clone https://github.com/FFmpeg/FFmpeg.git
cd FFmpeg
sudo ./configure --arch=armel --target-os=linux --enable-gpl --enable-libx264 --enable-nonfree

sudo make  # add -j4 to the end of this if you have a quad-core Raspberry Pi
sudo make install

# Clone the MusicBot
cd ~
git clone https://github.com/Just-Some-Bots/MusicBot.git MusicBot -b master
cd MusicBot
sudo -H pip3.5 install --upgrade -r requirements.txt
```

After this, you can find a folder called `MusicBot` inside your home directory. [Configure](#guidesconfiguration) it, and then run `./runbot-linux-mac.sh` to start the bot.