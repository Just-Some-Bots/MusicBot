---
title: Raspbian
category: Installing the bot
order: 4
---

<img class="doc-img" src="{{ site.baseurl }}/images/raspbian.png" alt="Raspbian" style="width: 75px; float: right;"/>

Installing MusicBot on Raspbian for use with a Raspberry Pi 2 or 3B **may take a while to complete and may have poor performance**. 
If you're willing to try it, you can run the following commands in order to install it:

```bash
# Install dependencies
sudo apt install python3-pip
sudo apt install git
sudo apt install libopus-dev
sudo apt install ffmpeg

# Clone the MusicBot
cd ~
git clone https://github.com/Just-Some-Bots/MusicBot.git MusicBot -b master
cd MusicBot
sudo python3 -m pip install --upgrade -r requirements.txt
```

After this, you can find a folder called `MusicBot` inside your home directory. [Configure]({{ site.baseurl }}/using/configuration) it, and then run `./run.sh` to start the bot.
