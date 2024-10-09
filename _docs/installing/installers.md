---
title: Auto Installer
category: Installing the bot
order: 1
---

MusicBot has an automatic installer script for Windows and various Linux OS.  
These script can be used as stand-alone installers which will download MusicBot to a default location.  
Or you can call the script within an existing clone to install the clone.  
The installer scripts will prompt you before making any changes.  

The scripts are provided by contributors like you, and may not always work.  
Please consider contributing corrections and improvements to the installers or these guides to help keep them current.  

### Windows

For Windows you need to download `install.bat` and `install.ps1` into the same directory.  
The `install.bat` file will set a temporary execution profile and execute the `install.ps1` file.  
If you are familiar with PowerShell and execution profiles / restrictions, feel free to skip the bat-file.  
The installer may request administrative access in order to install winget, git, python, and ffmpeg before it downloads the MusicBot files.  
Both install files can be located in the Github repository.  

For users familiar with Command Prompt, these commands will quickly do the job.  
Do NOT start Command Prompt in admin mode, it will only cause trouble here.  

```bat
curl https://raw.githubusercontent.com/just-some-bots/musicbot/dev/install.bat > install.bat

curl https://raw.githubusercontent.com/just-some-bots/musicbot/dev/install.ps1 > install.ps1

install.bat
```

The above will download both the latest .bat and .ps1 from the dev branch, then execute the .bat file.  
The files should be in your `C:\User\<user>\` folder or whatever directory the prompt displays.  


### Linux 

For Linux you only need to download one script from the Github repository.  
The `install.sh` script attempts to provide automatic install for a variety of distros.  
To see a list of potentially supported versions, use `install.sh --list`  

Here are some quick commands to get the script:
```bash
# Download with wget
wget https://raw.githubusercontent.com/just-some-bots/musicbot/dev/install.sh

# Or use curl to download
curl https://raw.githubusercontent.com/just-some-bots/musicbot/dev/install.sh -o install.sh

# mark as executable.
chmod +x ./install.sh

# see if you're supported.
./install.sh --list

# run installer.
./install.sh
```

The above is the recommended way to go about it, so you can double check things.  

Or if you're in a serious hurry:  
```bash
# download with curl and execute immediately.
bash <(curl -s https://raw.githubusercontent.com/just-some-bots/musicbot/dev/install.sh)

# download with wget and execute immediately.
bash <(wget -q https://raw.githubusercontent.com/just-some-bots/musicbot/dev/install.sh -O -)
```

---

