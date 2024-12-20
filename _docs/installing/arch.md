---
title: Arch
category: Installing the bot
order: 7
---

<img class="doc-img" src="{{ site.baseurl }}/images/arch.png" alt="centos" style="width: 75px; float: right;"/>
Installation on Arch Linux is like many other Linux distributions, however these steps may be out-of-date at any moment due to Arch being a rolling distribution, which tends to provide very new versions of packages.  
Please keep this in mind when seeking support.  

On the most recent versions of Arch, Python's pip packages are now managed by the system package manager.  To get around this and avoid causing issues with the system Python libraries, MusicBot should be installed using Python's Venv tool.  
Follow these steps to install MusicBot with Venv:  


~~~ bash
# Update system packages
sudo pacman -Syu

# Install system packaged dependencies
sudo pacman -S git curl python python-pip ffmpeg

# Create a Virtual environment for MusicBot in your Home directory.
cd ~
python -m venv ./MusicBotVenv

# Enter the new Venv directory.
cd ./MusicBotVenv

# Activate the Venv wrapper.
source ./bin/activate

# Clone MusicBot source code with git.
# You can change '-b master` to use dev or review branch as desired.
git clone https://github.com/Just-Some-Bots/MusicBot.git MusicBot -b master

# Enter the cloned MusicBot directory.
cd MusicBot

# Install MusicBot python dependencies.
pip install -U -r requirements.txt

# Deactivate Venv wrapper.
deactivate

~~~

Once everything has been completed, you can go ahead and [configure]({{ site.baseurl }}/using/configuration) the bot and then run with the `run.sh` script.  

As long as MusicBot source directory is contained within a Venv directory, the start and update scripts will look for and automatically activate the Venv.  

