---
title: MacOS
category: Installing the bot
order: 3
---

<img class="doc-img" src="{{ site.baseurl }}/images/mac.png" alt="Mac" style="width: 75px; float: right;"/>

Installing MusicBot on Mac is quite simple.

> **The steps below are for macOS Catalina and above. They may not work on older versions of macOS.**

You will need to open Terminal and run the following commands:

```bash
# Install Homebrew and Xcode command line tools
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew update
xcode-select --install

# Install dependencies
brew install git ffmpeg opus libffi libsodium

# Clone the MusicBot
cd desktop
git clone https://github.com/Just-Some-Bots/MusicBot.git MusicBot -b master 

# Install Python dependencies
cd MusicBot
python3 -m pip install -U pip
python3 -m pip install -U -r requirements.txt
```

After this, you can find a folder called `MusicBot` on your Desktop. You can then open it, [configure]({{ site.baseurl }}/using/configuration) your bot, and then run the bot by double-clicking the `run.sh` file.

If you can't run this, you may have to open Terminal, cd to the folder, and use `chmod +x run.sh` to give the file executable permissions.
