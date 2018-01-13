---
title: Installing on Debian
position: 6
---

<img class="doc-img" src="images/debian.png" alt="debian" style="width: 75px;"/>

You can install MusicBot on your Debian Jessie or Stretch machine, by running these commands in order:

If you are using Debian Jessie, you need to follow [this guide](https://gist.github.com/jaydenkieran/75b2bbc32b5b70c4fdfb161ecdb6daa2) for installing Python before running the commands below. For an explanation of why this is necessary, see Debian's [wiki page](https://wiki.debian.org/DontBreakDebian).
{: .warning }

~~~ bash
# Install dependencies
sudo apt-get install git libopus-dev libffi-dev libsodium-dev -y
sudo apt-get install build-essential libncursesw5-dev libgdbm-dev libc6-dev zlib1g-dev libsqlite3-dev tk-dev libssl-dev openssl -y

# Install Python
sudo apt-get install python3.5 -y

# Clone the MusicBot to your home directory
cd ~
git clone https://github.com/Just-Some-Bots/MusicBot.git MusicBot -b master
cd MusicBot

# Install dependencies
sudo -H python3.5 -m pip install --upgrade pip
sudo -H python3.5 -m pip install --upgrade -r requirements.txt
~~~
{: title="Stretch" }

~~~ bash
# Install dependencies
sudo apt-get install git libopus-dev libffi-dev libsodium-dev -y
sudo apt-get install build-essential libncursesw5-dev libgdbm-dev libc6-dev zlib1g-dev libsqlite3-dev tk-dev libssl-dev openssl -y

# Clone the MusicBot to your home directory
cd ~
git clone https://github.com/Just-Some-Bots/MusicBot.git MusicBot -b master
cd MusicBot

# Install dependencies
sudo -H python3.5 -m pip install --upgrade pip
sudo -H python3.5 -m pip install --upgrade -r requirements.txt
~~~
{: title="Jessie" }

After this, you can find a folder called `MusicBot` inside your home directory. [Configure](#guidesconfiguration) it, and then run `./runbot-linux-mac.sh` to start the bot.