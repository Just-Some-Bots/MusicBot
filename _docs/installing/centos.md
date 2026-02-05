---
title: CentOS
category: Installing the bot
order: 8
---
<img class="os-icon" src="{{ site.baseurl }}/images/centos-stream.svg" alt="CentOS Stream logo"/>
Installation on CentOS Stream is supported on versions 9 and 10.  
Other RHEL or CentOS-like distros may also work with these steps, but you may need to adjust or add commands.  


## CentOS Stream 10  

The following steps will minimally set up MusicBot.

```bash
# Install extra repos, needed for ffmpeg.
sudo dnf config-manager --set-enabled crb
sudo dnf install --nogpgcheck https://dl.fedoraproject.org/pub/epel/epel-release-latest-10.noarch.rpm
sudo dnf install --nogpgcheck https://mirrors.rpmfusion.org/free/el/rpmfusion-free-release-10.noarch.rpm

# Install available packages.
sudo yum -y install opus-devel libffi-devel git curl jq ffmpeg python3 python3-pip python3-devel unzip

# Install deno JS runtime needed for yt-dlp.
curl -fsSL https://deno.land/install.sh | sh

# NOTE: Restart your user session or terminal to ensure PATH updates are loaded.

# Clone the MusicBot
git clone https://github.com/Just-Some-Bots/MusicBot.git MusicBot -b dev
cd MusicBot

# Install bot requirements
python3 -m pip install -U -r requirements.txt

```

Once everything has been completed, you can go ahead and [configure]({{ site.baseurl }}/using/configuration) the bot and then run the bot with the `./run.sh` script.



## CentOS Stream 9

These steps should get everything set up on CentOS Stream 9.  

```bash

# Add extra repositories to system package manager, needed for ffmpeg.
sudo dnf config-manager --set-enabled crb
sudo dnf install --nogpgcheck https://dl.fedoraproject.org/pub/epel/epel{,-next}-release-latest-9.noarch.rpm
sudo dnf install --nogpgcheck https://mirrors.rpmfusion.org/free/el/rpmfusion-free-release-9.noarch.rpm

# Install dependency packages.
sudo yum -y install opus-devel libffi-devel git curl jq ffmpeg unzip \
    yum-utils make gcc openssl-devel bzip2-devel libffi-devel zlib-devel 

# Download and build Python 3.10
curl https://www.python.org/ftp/python/3.10.14/Python-3.10.14.tar.xz -o "Python-3.10.14.tar.xz"

# Extract the downloaded archive and change into it.
tar -xf Python-3.10.14.tar.xz
cd Python-3.10.14

# Configure Python 3.10.14 build options.
./configure --enable-optimizations

# Compile the source code.
# Note: add `-j N` where N is the number of CPU cores, for faster builds.
make

# Install Python to the system using alternate install location to avoid conflicts with older system python
sudo make altinstall

# Leave the source directory
cd ..

# Install deno JS runtime needed for yt-dlp.
curl -fsSL https://deno.land/install.sh | sh

# NOTE: Restart your user session or terminal to ensure PATH updates are loaded.

# Clone the MusicBot
git clone https://github.com/Just-Some-Bots/MusicBot.git MusicBot -b dev
cd MusicBot

# Install bot requirements
python3 -m pip install -U -r requirements.txt

```

Next [configure]({{ site.baseurl }}/using/configuration) the bot and then run the bot with the `./run.sh` script.  
