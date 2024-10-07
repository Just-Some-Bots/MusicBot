---
title: Raspbian / Pi OS
category: Installing the bot
order: 4
---

<img class="doc-img" src="{{ site.baseurl }}/images/raspbian.png" alt="Raspbian" style="width: 75px; float: right;"/>

MusicBot can be installed on Raspbian and Raspberry Pi OS. Older versions of Pi OS (known as Raspbian) may require some manual steps.  
This guide is broken into three sections depending on your version of Raspberry Pi OS or Raspbian.  
If you're unsure which version you have, you can find out by using the following command:  
`lsb_release -s -d`  
It should output something similar to the one of the following:  
`Debian GNU/Linux 12 (bookworm)`  *or* `Raspbian GNU/Linux 10 (buster)`  
We're interested in the last two bits of info, the number and code-name.  

---

## Version 12 (bookworm) and up
<details>
  <summary>Raspbery Pi OS 12 (bookworm) install steps.</summary>  

For Pi OS version 12 (bookworm) or later, Python 3 is system-managed.<br />  
This means MusicBot must be installed in a Python Venv (Virtual Environment) to avoid complications between system python libraries and libraries that MusicBot depends on.<br />  
In practice, there are only a few extra commands to follow:<br />  

{% highlight bash %}
# Update system packages.
sudo apt-get update -y
sudo apt-get upgrade -y

# Install dependencies.
sudo apt install -y jq git curl ffmpeg build-essential \
   libopus-dev libffi-dev libsodium-dev \
   python3-full python3-dev python3-venv python3-pip

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

After these steps, MusicBot will be installed within <code>./MusicBotVenv/MusicBot/</code> and will need to be configured. Follow the <a href="{{ site.baseurl }}/using/configuration">Configuration</a> guide before starting the MusicBot.  

<b>Note:</b> As long as the MusicBot cloned directory is inside the Venv directory, the <code>run.sh</code> and <code>update.sh</code> scripts should find and load the Venv automatically.  
If you need to manually update python libraries for MusicBot, you will need to activate the venv before you can do so.  

</details>  

---

## Version 11 (bullseye)
<details>
  <summary>Raspberry Pi OS 11 (bullseye) install steps.</summary>  

For Pi OS version 11 (bullseye), the Python 3.8+ is available as a system package, so installing is pretty simple. Just follow these commands:  

{% highlight bash %}
# Update system packages.
sudo apt-get update -y
sudo apt-get upgrade -y

# Install dependencies.
sudo apt install -y git curl ffmpeg python3 python3-pip

# Clone the MusicBot repository targeting the latest dev branch
git clone https://github.com/Just-Some-Bots/MusicBot.git -b dev ./MusicBot

# Change directory into the cloned repo
cd ./MusicBot/

# Now install the pip libraries
python -m pip install -U -r ./requirements.txt
{% endhighlight %}

Once finished, you need to <a href="{{ site.baseurl }}/using/configuration">Configure</a> MusicBot. After configuring you can use the command <code>./run.sh</code> to start the bot.

</details>

---

## Version 10 (buster) and earlier.
<details>
  <summary>Raspbian 10 (buster) install steps.</summary>

For Raspbian version 10 (buster) and earlier versions, you will need to manually build/compile an appropriate version of Python 3.8 or higher as well as installing pip.  
This can take a bit of time to complete and may require a little troubleshooting know-how if these steps are out-of-date or incomplete in some way.  

If you're willing to carefully follow along, these steps *should* get MusicBot working:

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
wget https://www.python.org/ftp/python/3.10.13/Python-3.10.14.tar.xz

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

When install is finished you need to <a href="{{ site.baseurl }}/using/configuration">Configure</a> MusicBot.  
After configuring you can use the command <code>./run.sh</code> to start the bot.

</details>

---
