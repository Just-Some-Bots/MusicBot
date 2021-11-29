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


wget https://www.python.org/ftp/python/3.8.12/Python-3.8.12.tar.xz # Download the Python files.
tar -xf Python-3.8.12.tar.xz # Unarchive the files.
cd Python-3.8.12 # Move to the unarchived files.
./configure --enable-optimizations 
make -j
sudo make altinstall # This can take some time.
cd .. 
wget https://bootstrap.pypa.io/get-pip.py # Install pip.
python3.8 get-pip.py
rm get-pip.py # Cleanup.
rm Python-3.8.12.tar.xz # Cleanup.
sudo rm -rf Python-3.8.12 #Cleanup

# Install dependencies
sudo apt -y install git
sudo apt -y install libopus-dev
sudo apt -y install ffmpeg

# Clone the MusicBot
cd ~
git clone https://github.com/Just-Some-Bots/MusicBot.git MusicBot -b review
cd MusicBot
sudo python3.8 -m pip install --upgrade -r requirements.txt
```

After this, you can find a folder called `MusicBot` inside your home directory. [Configure]({{ site.baseurl }}/using/configuration) it, and then run `./run.sh` to start the bot.
