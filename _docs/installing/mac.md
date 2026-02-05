---
title: MacOS
category: Installing the bot
order: 4
---
<img class="os-icon" src="{{ site.baseurl }}/images/mac.png" alt="mac OS Logo"/>

Installing MusicBot on Mac is simple using homebrew and xcode.  

> Note: On ARM-based mac (M1, M4, etc.) you may encounter an issue with Opus not loading. 
You can bypass this by enabling `UseOpusAudio` in your options.ini file.  


### Catalina & above
These steps were made for macOS Catalina and above.

To install, you will need to open Terminal and use the following commands (adjust them as needed for your system):  

```bash
# Install Homebrew and Xcode command line tools.
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
echo; echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> /Users/$(id -un)/.zprofile \
eval "$(/opt/homebrew/bin/brew shellenv)" # To fix "zsh: command not found: brew"

# set up xcode.
xcode-select --install

# update brew package index.
brew update

# Install system dependencies
brew install libsodium libffi ffmpeg git opus-tools deno

# Install python using version 3.10, or any version from 3.10 to 3.13
brew install python@3.10

# Clone the MusicBot using master branch, you may also use review or dev.
cd desktop
git clone https://github.com/Just-Some-Bots/MusicBot.git MusicBot -b master

# Install Python dependencies
cd MusicBot
python3 -m pip install -U -r requirements.txt
```

After this, you can find a folder called `MusicBot` on your Desktop. You can then open it, [configure]({{ site.baseurl }}/using/configuration) your bot, and then run the bot by double-clicking the `run.sh` file.

If you can't run this, you may have to open Terminal, cd to the folder, and use `chmod +x run.sh` to give the file executable permissions.
