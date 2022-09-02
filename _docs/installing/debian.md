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

# Install Python 3.8
mkdir pytemp
cd pytemp
wget https://www.python.org/ftp/python/3.8.7/Python-3.8.7.tgz
tar zxf Python-3.8.7.tgz
cd Python-3.8.7
./configure --enable-optimizations
make -j4
sudo make altinstall
cd ..

# Install pip
curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
python3.8 get-pip.py

# Remove temporary python directory
cd ..
rm -r pytemp

# Clone the MusicBot to your home directory
cd ~
git clone https://github.com/Just-Some-Bots/MusicBot.git MusicBot -b master
cd MusicBot

# Install dependencies
sudo -H python3.8 -m pip install --upgrade pip
sudo -H python3.8 -m pip install --upgrade -r requirements.txt
~~~

After this, you can find a folder called `MusicBot` inside your home directory. [Configure]({{ site.baseurl }}/using/configuration) it, and then run `bash ./run.sh` to start the bot.
