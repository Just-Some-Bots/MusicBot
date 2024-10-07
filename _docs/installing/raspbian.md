---
title: Raspbian
category: Installing the bot
order: 4
---

<img class="doc-img" src="{{ site.baseurl }}/images/raspbian.png" alt="Raspbian" style="width: 75px; float: right;"/>

MusicBot can be installed on Raspbian and Raspberry Pi OS. Older versions of Pi OS (known as Raspbian) may require some manual install steps.
This guide is broken into three sections depending on your version of Raspberry Pi OS or Raspbian.  
If you're unsure which version you can run the following command:
`lsb_release -s -d`
You should see an output similar to the one of the following:
`Debian GNU/Linux 12 (bookworm)`  or `Raspbian GNU/Linux 10 (buster)`
We're most interested in the last two bits of info, the number and code-name.  

Installing MusicBot on Raspbian may take a while to complete.
If you're willing to try it, you can run the following commands in order to install it:

---

## Bullseye and higher.

<details>
  <summary>Bullseye install steps.</summary>

For **Bullseye** or later versions, Python 3.9+ is already installed and system-managed.
```bash
# Update system packages.
sudo apt-get update -y
sudo apt-get upgrade -y

# Install dependencies.
sudo apt install git libopus-dev ffmpeg -y

# Clone the MusicBot repository targeting the latest dev branch.
git clone https://github.com/Just-Some-Bots/MusicBot.git MusicBot -b dev
cd ./MusicBot/

# Make install script executable and run it
chmod +x ./install.sh
./install.sh
```

</details>

---

## Buster and earlier.

We will need to build python3.10 manually.

```bash
# Update system packages.
sudo apt-get update -y
sudo apt-get upgrade -y

# Install dependencies required to build Python.
sudo apt-get install -y build-essential zlib1g-dev uuid-dev liblzma-dev \
lzma-dev libncurses5-dev libgdbm-dev libnss3-dev libssl-dev \
libreadline-dev libffi-dev libsqlite3-dev libbz2-dev

# Download and build Python 3.10
wget https://www.python.org/ftp/python/3.10.13/Python-3.10.13.tar.xz
tar -xf Python-3.10.13.tar.xz
cd Python-3.10.13
./configure --enable-optimizations
make -j4 # Compile the source code using 4 parallel jobs for faster build times.
sudo make altinstall
cd ..
```

### Installing pip
When it comes to installing pip, you have a couple options based on your system version.

1.
```bash
# Install pip using the get-pip.py script for Debian 10 or less
curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
python3.10 get-pip.py
```

2.
```bash
# Install pip using apt for 11
sudo apt install python3-pip -y
```

3.
```bash
# Use a virtual enviroment for 12+

# change to home directory
cd ~

# set up venv in MusicBotVenv
python -m venv MusicBotVenv

# move cloned directory inside venv, so MusicBot can see the venv
mv ./MusicBot ./MusicBotVenv/MusicBot

# activate venv
source ./MusicBotVenv/bin/activate

# install pip libs inside venv
pip install -U -r ./MusicBotVenv/MusicBot/requirements.txt

# leave venv when done with
deactivate
```

4.
```bash
# Install with the -break-system-packages 12+
# NOT RECOMMENED
# If you plan to use the Pi for more than just MusicBot this could have side effects on your system.
# There is software in modern Debian based Linux distros that is built out of python, so to keep it all stable they force pip to obey rules of the system package manager instead.

pip install --break-system-packages -U -r ./MusicBot/requirements.txt
```


```bash
# Cleanup (only need if you had to manually build python 3.10)
rm -r Python-3.10.13  # Remove the source directory; it's no longer needed to run Python.
rm Python-3.10.13.tar.xz # Remove the archive; it's no longer needed after extraction.
rm get-pip.py # Remove the installation script; pip is now installed.

# Install additional dependencies
sudo apt install git libopus-dev ffmpeg -y

# Clone the MusicBot repository targeting the latest dev branch.
git clone https://github.com/Just-Some-Bots/MusicBot.git MusicBot -b dev
cd ./MusicBot/

# Make install script executable and run it
chmod +x ./install.sh
./install.sh
```

---

After this, you can find a folder called `MusicBot` inside your home directory. [Configure]({{ site.baseurl }}/using/configuration) it, and then run `./run.sh` to start the bot.
