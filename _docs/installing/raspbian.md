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

# Installer for python 3.8
wget https://cdn.discordapp.com/attachments/157598062020132865/804093346007482418/installer.sh # change this later to another link
# Make it executable
sudo chmod +x installer.sh
# Run the script
./installer.sh




# Install dependencies
sudo apt -y install python3-dev
sudo apt -y install python3-pip
sudo apt -y install git
sudo apt -y install libopus-dev
sudo apt -y install ffmpeg

# Clone the MusicBot
cd ~
git clone https://github.com/Just-Some-Bots/MusicBot.git MusicBot -b master
cd MusicBot
sudo python3.8 -m pip install --upgrade -r requirements.txt
```

After this, you can find a folder called `MusicBot` inside your home directory. [Configure]({{ site.baseurl }}/using/configuration) it, and then run `./run.sh` to start the bot.
