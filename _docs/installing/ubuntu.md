---
title: Ubuntu
category: Installing the bot
order: 3
---

<img class="doc-img" src="{{ site.baseurl }}/images/ubuntu.png" alt="Ubuntu" style="width: 75px; float: right;"/>

Installing MusicBot on Ubuntu is simple, and we have steps for several LTS versions.  
While this guide leaves out non-LTS versions of Ubuntu, the steps here are a good place to start for interim versions.  
If you're unsure which version you have, you can find out by using the following command:  
`lsb_release -s -d`  
It should output something similar to the following:  
`Ubuntu 20.04.2 LTS`  
We can ignore the Patch version. As long as your Major and Minor versions match, the steps here should work.  

---

<a class="expand-all-details">Show/Hide All</a>

## Ubuntu 18.04  
<details>
  <summary>Install steps.</summary>

On Ubuntu 18.04 and lower the system packaged Python is too old for MusicBot.<br>  
So we install packages for MusicBot as well as those needed to compile Python from source.<br>  

{% highlight bash %}
# Update system packages.
sudo apt-get update -y
sudo apt-get upgrade -y

# Install required packages for Python and MusicBot.
sudo apt-get install -y build-essential libopus-dev libffi-dev \
    libsodium-dev libssl-dev zlib1g-dev libncurses5-dev \
    libgdbm-dev libnss3-dev libreadline-dev libsqlite3-dev \
    libbz2-dev liblzma-dev lzma-dev uuid-dev \
    unzip curl git jq ffmpeg

# Download and build Python 3.10
wget https://www.python.org/ftp/python/3.10.14/Python-3.10.14.tar.xz

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

# Clone MusicBot
git clone https://github.com/Just-Some-Bots/MusicBot/ -b dev ./MusicBot

# Change into the cloned directory
cd ./MusicBot

# Now install the pip libraries
python -m pip install -U -r ./requirements.txt

{% endhighlight %}

When install is finished you need to <a href="{{ site.baseurl }}/using/configuration">Configure</a> MusicBot.<br>  
After configuring you can use the command <code>./run.sh</code> to start the bot.


</details>

---

## Ubuntu 20.04 & 22.04  
<details>
  <summary>Install steps.</summary>

For Ubuntu 20.04 and 22.04, the Python 3 packages should be 3.8 or newer which makes install pretty simple.

{% highlight bash %}
# Update system packages first
sudo apt-get update -y
sudo apt-get upgrade -y

# Install dependency packages
sudo apt-get install -y build-essential software-properties-common \
    unzip curl git ffmpeg libopus-dev libffi-dev libsodium-dev \
    python3-pip python3-dev jq
    
# Clone the MusicBot repository targeting the latest dev branch
git clone https://github.com/Just-Some-Bots/MusicBot.git -b dev ./MusicBot

# Change directory into the cloned repo
cd ./MusicBot/

# Now install the pip libraries
python -m pip install -U -r ./requirements.txt
{% endhighlight %}

Once finished, you need to <a href="{{ site.baseurl }}/using/configuration">Configure</a> MusicBot.<br>  
After configuring you can use the command <code>./run.sh</code> to start the bot.


</details>

---

## Ubuntu 24.04 and higher  
<details>
  <summary>Install steps.</summary>

On Ubuntu 24.04 and up, Python is system-managed. This means we need to install a Venv.<br>  
So an additional package and some steps to set up Venv are required.<br>  

{% highlight bash %}

sudo apt-get update -y
sudo apt-get upgrade -y
sudo apt-get install build-essential software-properties-common \
    unzip curl git ffmpeg libopus-dev libffi-dev libsodium-dev \
    python3-full python3-pip python3-venv python3-dev jq -y

# Set up the venv directory as ./MusicBotVenv
python -m venv ./MusicBotVenv

# Change into the venv directory and activate venv
cd ./MusicBotVenv
source ./bin/activate

# Clone the MusicBot repository targeting the latest dev branch
git clone https://github.com/Just-Some-Bots/MusicBot.git -b dev ./MusicBot

# Change directory into the cloned repo
cd ./MusicBot/

# Now install the pip libraries
python -m pip install -U -r ./requirements.txt

# lastly, exit the virtual environment
deactivate
{% endhighlight %}

After these steps, MusicBot will be installed within <code>./MusicBotVenv/MusicBot/</code> and will need to be configured. Follow the <a href="{{ site.baseurl }}/using/configuration">Configuration</a> guide before starting the MusicBot.  <br>
<br>
<b>Note:</b> As long as the MusicBot cloned directory is inside the Venv directory, the <code>run.sh</code> and <code>update.sh</code> scripts should find and load the Venv automatically.<br>  
If you need to manually update python libraries for MusicBot, you will need to activate the venv before you can do so.  

</details>

---

<a class="expand-all-details">Show/Hide All</a>
