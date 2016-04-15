# Table of Contents

[Introduction](#introduction)

1. [Step 1: Preparation](#step-1-preparation)
    - [1.a: Install XCode and Homebrew](#1a-install-xcode-and-homebrew)
    - [1.b: Installing dependencies](#1b-installing-dependencies)
2. [Step 2: Download and setup MusicBot](#2-download-and-setup-musicbot)
    - [2.a: Install python dependencies](#2a-install-python-dependencies)
    - [2.b: Change configuration file](#2b-change-configuration-files)
3. [Step 3: Start the bot](#3-start-the-bot)
    - [3.a: Test the bot (non permanent)](#3a-test-the-bot-non-permanent)
    - [3.b: Start the bot (permanent with screen)](#3b-start-the-bot-permanent-with-screen)

# Introduction

Installing the bot on OSX requires the downloading of several libraries. These libraries are best managed with [Homebrew](http://brew.sh/). Homebrew requires XCode to function.

# Step 1: Preparation

Let's get everything ready to install.

### 1.a: Install XCode and Homebrew

If you do not have XCode, download it from the Mac App Store and install it. Following that, go to [Homebrew](http://brew.sh/) and download Homebrew. Run `brew update` to fetch the latest package data.

### 1.b: Installing dependencies

To install dependencies, enter the following command **without sudo**

    brew install git
    brew install python3
    brew install ffmpeg
    brew install opus
    brew install libffi
    brew install libsodium

## 2: Download and setup MusicBot

Run the following commands to download MusicBot:

    git clone https://github.com/SexualRhinoceros/MusicBot.git MusicBot
    cd MusicBot
    git checkout review

### 2.a: Install python dependencies

This next step is somewhat optional, as MusicBot will attempt to do this for you if you haven't. On OSX, you should run these commands **without root**, since Homebrew does not clobber your system Python.

    pip3.5 install --upgrade -r requirements.txt
    
This installs the various python dependencies used by the bot.

### 2.b: Change configuration files

The configuration files are located in the `config/` directory. There are two files, `example_options.ini` and `example_permissions.ini` that tell you how to configure the bot. You should copy these files to `options.ini` and `permissions.ini` respectively.

## 3: Start the bot 

**If you haven't already done so, create a COMPLETELY NEW Discord account for your bot.** You cannot share accounts with your bot - Discord doesn't allow multiple voice connections from one account (you won't be able to listen to your own bot :cry:).

Log into the bot's account on your Discord client and join the server you want your bot to live on. Then, log out of the bot's account on your Discord client.

### 3.a Test the bot (non permanent)
Go back to the SSH for your server and make sure you're in the `MusicBot` folder (you should see `username@host:~/MusicBot$` or something similar in front of the cursor).

Run this:

    python3.5 run.py

If you see this:

    Connected!

    Username: [Bot Username]
    ID: [Bot User ID]
    --Server List--
    [Server Name(s)]

that means everything is good and running correctly!

### 3.b: Start the bot (permanent with screen)

Close the test bot first by hitting `Ctrl+C` in the SSH window while the bot is running.  You may need to press it a few times.

Run this to make a `screen` console:

    screen -S bot

This creates a `screen` console with the name 'bot' so you can easily come back later if there are any problems. Don't be alarmed that the SSH window became empty.

To start the bot in this screen, run:

    python3.5 run.py

Once that's online and good, press `Ctrl+a` then `d` separately to 'detach' from the screen. Your music bot should still be online on your server.

Now you can close your SSH window or terminal and play with your bot!

If you ever want to have a look at the bot's console logs, SSH back into the machine and run:

    screen -r bot

That should bring everything back up.

You don't need to do anything else! :smile: You can check out the [wiki articles](https://github.com/SexualRhinoceros/MusicBot/wiki/Commands-list "Commands list") to find out how to use your bot. :grin: