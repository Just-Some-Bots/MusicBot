---
title: Running MusicBot
category: Using the bot
order: 13
---

## How to Run

First, make sure you have properly installed MusicBot by following one of the install 
guides appropriate for your OS and version.  
Next, read the [configuration page]({{ site.baseurl }}/using/configuration/) to 
set up a Discord App and configure MusicBot.  
Finally, MusicBot can be started by using `run.bat` on Windows and `run.sh` on most 
Linux and Unix-like OS, such as macOS or BSD.  

Generally speaking the two scripts attempt to find an installed python interpreter 
and then use it to run the `run.py` file, with any arguments passed on the command 
line being passed to python.  

If you have more than one version of Python, these scripts might fail to use the 
correct version of Python.  Just the nature of the beast, as we support multiple 
versions of Python but dependencies need to be installed on a per-version basis.  
If you're not used to working with Python, this can cause you some confusion.  
You can either remove un-needed versions or simply copy, edit, and rename 
the `run.bat` or `run.sh` scripts to make use of a specific python version.  

Ultimately, the simplest way to run MusicBot is to change directory to the MusicBot 
folder where `run.py` file is, and then run `python run.py` replacing "python" as needed 
for your OS or specific version / python install.  
On Windows this might be `py.exe -3.X` (replace "3.x" with a real version like 3.10) 
or simply `python.exe` on the command line.  
On Linux / Unix-likes this is typically something like `python3`.  

> **Notice:** MusicBot is provided under an [MIT License](https://github.com/Just-Some-Bots/MusicBot/blob/master/LICENSE). By using the software you agree to the terms of the License. 

## How to Auto Start

MusicBot can be made into a "service" by using a number of different methods.  
For Windows, the [Non-Sucking Service Manager]({{ site.baseurl }}/using/nssm/) application is recommended.  
For macOS, newer versions may be able to use [SystemD]({{ site.baseurl }}/using/systemd/) while older versions might use `launchd` or install and use `pm2` instead.  
For Linux-like OS, the automation of choice depends on your distribution, but currently we have guides for `SystemD` and `pm2` which you can use or take inspiration from.

## CLI Flags <a name="flags"></a>  

This section describes the command line arguments (aka flags) available to use with 
any of the bundled run scripts (`run.sh`, `run.bat`, and `run.py`) provided by MusicBot.  

> Note: These docs may not contain details for features in the `dev` or `review` branches.  Use the `--help` flag for details on options not listed here.

These are the options available for use:
```text

  -h, --help            show this help message and exit.

  -V, --version         Print the MusicBot version information and exit.

  --lang LANG_BOTH      Override the default / system detected language for all text in MusicBot.

  --log_lang LANG_LOGS  Use this language for all server-side log messages from MusicBot.

  --msg_lang LANG_MSGS  Use this language for all messages sent to discord from MusicBot.
                        This does not prevent per-guild language selection.

  --no-checks           Skip all optional startup checks, including the update check.

  --no-disk-check       Skip only the disk space check at startup.

  --no-update-check     Skip only the update check at startup.

  --no-install-deps     Disable MusicBot from trying to install dependencies when it cannot import them.

  --logs-kept KEEP_N_LOGS
                        Specify how many log files to keep, between 0 and 100 inclusive. (Default: 0)

  --log-level LOG_LEVEL
                        Override the log level settings set in config. Must be one of: 
                        CRITICAL, ERROR, WARNING, INFO, DEBUG, VOICEDEBUG, FFMPEG, NOISY, EVERYTHING

  --log-rotate-fmt OLD_LOG_FMT
                        Override the default date format used when rotating log files. 
                        This should contain values compatible with strftime().
                        Default: .ended-%Y-%j-%H%m%S 

  --write-dir GLOBAL_WRITES_BASEDIR
                        Supply a directory under which MusicBot will store all mutable files.  
                        Essentially treats the install directory as read-only.  
                        MusicBot must have permission to create this directory and files within it.

```
