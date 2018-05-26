---
title: Raspbian
category: Installing the bot
order: 4
---

<img class="doc-img" src="{{ site.baseurl }}/images/raspbian.png" alt="Raspbian" style="width: 75px; float: right;"/>

Installing MusicBot on Raspbian for use with a Raspberry Pi 2 or 3B is a **long-winded process and may take a while to complete**. If you're willing to try it, you can run the following commands in order to install it:

```bash
# Install dependencies
sudo apt-get update -y
sudo apt-get upgrade -y
sudo apt-get install git build-essential libncursesw5-dev libgdbm-dev libc6-dev zlib1g-dev libsqlite3-dev tk-dev libssl-dev openssl unzip software-properties-common libopus-dev libffi-dev libsodium-dev -y

# Build Python from scratch
cd ~
wget https://www.python.org/ftp/python/3.5.4/Python-3.5.4.tgz
tar -zxvf Python-3.5.4.tgz
cd Python-3.5.4
./configure
sudo make  # add -j4 to the end of this if you have a quad-core Raspberry Pi (2B, 3B[+])
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
sudo make # add -j4 to the end of this if you have a quad-core Raspberry Pi (2B, 3B[+])
sudo make install

# Install FFmpeg
cd /usr/src
sudo git clone https://github.com/FFmpeg/FFmpeg.git
cd FFmpeg
sudo ./configure --arch=armel --target-os=linux --enable-gpl --enable-libx264 --enable-nonfree
sudo make  # add -j4 to the end of this if you have a quad-core Raspberry Pi (2B, 3B[+])
sudo make install

# Clone the MusicBot
cd ~
git clone https://github.com/Just-Some-Bots/MusicBot.git MusicBot -b master
cd MusicBot
sudo -H pip3.5 install --upgrade -r requirements.txt
```

After this, you can find a folder called `MusicBot` inside your home directory. [Configure]({{ site.baseurl }}/using/configuration) it, and then run `./run.sh` to start the bot.
