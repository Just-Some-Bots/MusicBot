# Table of Contents

2. [Step 1: Installing Python](#step-1-installing-python-351)
    - [1.a Download Python installer](#1a-downloading-python-installer)
    - [1.b: Install Python](#1b-install-python-351)
3. [Step 2: Install and configure MusicBot](#step-2-install-and-configure-musicbot)
    - [2.a: Download MusicBot](#2a-download-musicbot)
    - [2.b: Change configuration file](#2b-change-configuration-file)
    - [2.c: Start the bot!](#2c-start-the-bot)

## Step 1: Installing Python 3.5.1

Python 3.5+ is required to run musicbot.

### 1.a: Downloading Python installer

You can find the Windows installer for Python 3.5.1 at [Python's website](https://www.python.org/ftp/python/3.5.1/python-3.5.1.exe "Download Python 3.5.1 for windows"). Just open the page and let it download.

### 1.b: Install Python 3.5.1

Open the installer you downloaded in step 1.a. When the installer opens, ensure that the checkboxes *'Install launcher for all users (recommended)'* and '*Add Python 3.5 to PATH*' are both **checked** and then click the big *Install Now* button.

![Python installer initial screen](http://i.imgur.com/48qmRJ0.png)

**If a UAC prompt appears, click *'yes'* to start installation.**

Python should begin to install and you should see the progress bar slowly fill as the installation takes place.

![Python installer progress bar](http://i.imgur.com/bSUIO10.png)

Once that is done, click the button labeled *Close* to finish installation.

![Python installer completion screen](http://i.imgur.com/zb9s0gA.png)

You have now successfully installed Python onto your machine! :smile:

## Step 2: Install and configure MusicBot

### 2.a: Download MusicBot

##### Latest Version: [v1.9.5 RC7](https://github.com/SexualRhinoceros/MusicBot/releases/tag/v1.9.5rc7)

Download the bot and extract the .zip file into a convenient location (your Desktop, for example).

![Extracting .zip file](http://i.imgur.com/PDTvnEu.png)

### 2.b: Change configuration file

When the extraction finishes, a new window should appear with the following contents:

![MusicBot contents](http://i.imgur.com/Tm0NEoW.png)

In the `config` folder, if there isn't a file called `options.ini`, copy `example_options.ini` and rename the copy to `options.ini`.  Then, open `options.ini` in a text editor OTHER than Windows Notepad, otherwise you'll see a single line full of stuff. I suggest [Notepad++](https://notepad-plus-plus.org "Notepad++").  Editing the options file with windows notepad will mangle the content and the bot won't be able to read it.

Configure the file however you want, it should explain everything you need.  The three things you MUST change are the bot's email, password and your OwnerID. If you have any further questions, you can ask on the help server.

### 2.c: Start the bot!

**If you haven't already done so, create a COMPLETELY NEW Discord account for your bot.** You cannot share accounts with your bot.  Discord doesn't allow multiple voice connections from one account (you won't be able to listen to your own bot :cry:).

Log into the bot's account in your browser (you can use a private tab so you don't need to log out of yours) and join the server you want your bot to live on. Then, log out of the bot's account (or just close the tab if its a private tab).

Go back to the main MusicBot directory and double click `runbot.bat`. If you don't see any errors, that means everything is good and running correctly! You don't need to do anything else! :smile: You can check out the [wiki articles](https://github.com/SexualRhinoceros/MusicBot/wiki/Commands-list "Commands list") to find out how to use your bot.  If you see an error and you don't know what it means, ask about it on the help server.

**NOTE:** By default, the `AutoSummon` option is enabled.  This means the bot will automatically join the owner's voice channel. If the owner isn't in a voice channel, join one and use the command `!summon` to bring the bot into your channel.