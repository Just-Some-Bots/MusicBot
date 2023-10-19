---
title: Raspbian
category: Installing the bot
order: 4
---

<img class="doc-img" src="{{ site.baseurl }}/images/raspbian.png" alt="Raspbian" style="width: 75px; float: right;"/>

Installing MusicBot on Raspbian may take a while to complete.
If you're willing to try it, you can run the following commands in order to install it:

```bash
# Update system packages
sudo apt-get update -y
sudo apt-get upgrade -y


wget https://www.python.org/ftp/python/3.10.13/Python-3.10.13.tar.xz # Download the Python files.
tar -xf Python-3.10.13.tar.xz # Unarchive the files.
cd Python-3.10.13 # Move to the unarchived files.
./configure --enable-optimizations 
make -j
sudo make altinstall # This can take some time.
cd .. 
wget https://bootstrap.pypa.io/get-pip.py # Install pip.
python3 get-pip.py
rm get-pip.py # Cleanup.
rm Python-3.10.13.tar.xz # Cleanup.
sudo rm -rf Python-3.10.13 #Cleanup

# Install dependencies
sudo apt install git
sudo apt install libopus-dev
sudo apt install ffmpeg
sudo apt-get install -y build-essential tk-dev libncurses5-dev \
libncursesw5-dev libreadline6-dev libdb5.3-dev libgdbm-dev libsqlite3-dev \
libssl-dev libbz2-dev libexpat1-dev liblzma-dev zlib1g-dev libffi-dev

# Install Python 3.10
mkdir pytemp
cd pytemp
wget https://www.python.org/ftp/python/3.10.13/Python-3.10.13.tgz
tar zxf Python-3.10.13.tgz
cd Python-3.10.13
./configure --enable-optimizations
make -j4
sudo make altinstall
cd ..

# Install pip
curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
python3 get-pip.py

# Remove temporary python directory
cd ..
rm -r pytemp

# Clone the MusicBot
cd ~
git clone https://github.com/Just-Some-Bots/MusicBot.git MusicBot -b master
cd MusicBot
python3 -m pip install --upgrade -r requirements.txt
python3 -m pip install --upgrade -r requirements.txt
```

After this, you can find a folder called `MusicBot` inside your home directory. [Configure]({{ site.baseurl }}/using/configuration) it, and then run `bash ./run.sh` to start the bot.
