---
title: 26th May 2024
type: major
---

**Noticable Changes**

This covers major changes in the newly added `dev` branch as well as the `review` branch. The entire player backend has had a major overhaul, courtesy of [ItsTheFae](https://github.com/itsTheFae) many bugs have been squashed, new features, commands, and options have been added. The last changelog update was 3 years ago. For an entire list of changes it's best to [view the commits.](https://github.com/Just-Some-Bots/MusicBot/commits/dev/)

 **Options:**
   * The bot being deafened in a VC has been made optional.
   * Adds the option to have the bot leave for various situations: after x time, when queue is empty, and if the bot is paused for x time.
   * Adds an option to set a default playback speed.
   * Storage options:
      - Adds the option to limit storage by size. (eg: 8GB)
      - Adds the option to only keep files that have been used in the last x amount of time.
      - Adds the option to keep autoplaylist files in cache while other storage options are set.
   * Adds the option to use commands by mentions (eg: @bot play song)
   * Adds the option to set a custom status message, and provides variables to use dynamically. 
   * Adds the option to set a prefix per guild. 
   * Adds a round robin option. 
   * Adds the option to enable or disable user block list.
   * Adds the option to enable or disable song block list.
   * Adds the option to enable a network checker. Mostly used for bots being ran 24/7. 
   * Adds the option to save all songs played with the bot to a global playlist, history.txt
      - Adds an option to save this per guild, history-{Guild_ID}.txt.
   * Adds an option to play local media from the local MediaFileDirectory path. 
      - `play file://path/to/file.ext`
   * Adds the option to automatically unpause the bot when play commands are used. 
   **Files:**
   * Adds an option to keep a max amount of logs. 
   * Adds an option to set the format used for logs. 
   * Adds an option to set a folder path for audio_cache.
   * Adds an option to set a file path for user block list and song block list.
   * Adds an option to set a directory path for the auto playlist.
   * Adds an option to set a directory path for local media. 

   **New commands:**
   * Loop commands. 
      - Loop the current song or the entire playlist.
   * Move command.
      - Move a song from a spot in the queue to a new spot in queue. (eg: `move 5 2`)
   * Autoplaylist command.
      - Adds a command for autoplaylist manipulation. You can add songs to the autoplaylist, remove songs, show a list of avaiable playlist, or 
      set a playlist for a guild. 
   * Shuffeplay command.
      - Adds a command to playback a playlist shuffled. Like turning shuffle on spotify and then pressing play. 
   * Blockuser command.
      - Adds a user to the block list.
   * Blocksong command.
      - Adds a song to the block list.
   * Botlatency command.
      - Display current latency between bot and discord. Will also show voice latencies.
   * Latency command.
      - User version of botlatency. 
   * Cache command.
      - Show current cache storage info.
      - Clear cache.
   * Checkupdates command.
      - Shows current bot version and updates available to the bot or packages.
   * Config command.
      - Change config options on the fly.
   * Permissions command.
      - Change config permissions on the fly.
   * Follow command. 
      - Will follow the command issuer around a guild when moving channels.
      - Owner can specify who to follow. 
   * Resetplaylist command.
      - Resets all songs in guilds autoplaylist file.
   * Restart sub commands.
      - Adds new sub commands to restart.
      - soft will reload the config without reloading the source code.
      - fill will restart and reload configs and source code.
      - uppip will attempt to update pip packages and then fully restart.
      - upgit will attempt to upgrade the bot and then fully restart.
      - upgrade will attempt to upgrade the bot and packages then fully restart. 
   * Setprefix command.
      - Set the prefix for the guild.
   * Seek command.
      - Seek to a certain spot in the song
   * Speed command.
      - Adjust the current playback speed. 
   * Uptime command.
      - Display how long the bot has been actively connected to discord session. 
        This is per startup so a restart full will reset this.
   * Setperms command. 
      - setperms list
         show loaded groups and list permission options.

      - setperms reload
         reloads permissions from the permissions.ini file.

      - setperms add [GroupName]
         add new group with defaults.

      - setperms remove [GroupName]
         remove existing group.

      - setperms help [PermName]
         show help text for the permission option.

      - setperms show [GroupName] [PermName]
         show permission value for given group and permission.

      - setperms save [GroupName]
         save permissions group to file.

      - setperms set [GroupName] [PermName] [Value]
         set permission value for the group.

   **Bug fixes:**
   * Fixed a bug where the summon message would display even if the bot was already in a vc.
   * Fixed the restart command.
   * Fixed Spotify not being able to use credentials. 
   * Fixed bot crashing on restart when using spotify secret and ID. 
   * Fixed permissions not being disabled when leaving GrantToRoles or UserList empty.
   * Fixed spelling mistakes in en.json.
   * Fixed a bug where when using the option command to enable autoplaylist the currently playing song would get skipped. 
   * Fixed a bug where messages would get deleted even when set not to.
   * Fixed a bug where invoking commands would get deleted even when set not to. 
   * Fixed a bug where stage channels where being recoginized as text channels. 
      - Also adds support for playing musing in stage channels.
   * Remove checks for request package. 
      - These checks where causing an issue due to the request package being used internally in one of the other packages. Leaving the bot unusable. 
   * Fixed a bug where now playing messages weren't respecting the `DeleteNowPlaying` option. 
   * Automatic fix using certifi when local SSL store is missing certs.
   * Fixed an error when timer options are missing and default int is used. 
   * Fixed file section not being validated. 
   * Fixed a bug where missing logs would halt startup. 
   * Fixed a index bug with new round robin option.
   * Fixed skip command not tallying votes properly.
   
   **Overhauls:**
   * The player has been overhauled to be easier to read, and be more effectient. The changes are massive. 
      - The player will now make less calls to extract_info. 
      - Autoplaylist songs are now skipped when a user queues a song. 
   * Complete overhaul of ytdl information extraction and several player commands, performance focused. 
      - Updates `shuffleplay` to shuffle playlist entries before they are queued. 
      - Adds playlist name and other details to pldump generated files. 
      - Enable pldump command to send file to invoking channel if DM fails. 
      - Updates Now Playing Status to use custom status and activity (experimental). 
      - Adds stream support to autoplaylist entries, if they are detected as a stream. 
      - Adds stream support to regular play command, if input is detected as a stream. 
      - Adds playlist link support to autoplaylist entries. (experimental) 
      - Asks if user wants to queue the playlist when using links with playlist and video IDs. 
      - Include thumbnail in now-playing for any tracks that have it. 
      - Remove all extraneous calls to extract_info, and carry extracted info with entries. 
      - Rebuild of Spotify API to make it faster to enqueue Spotify playlists and albums. 
   * Restart and shutdown has been cleaned up to properly clean pending task. 
   * Autopause logic has been cleaned up to make it easier to read. 
   * Removes shlex from the search command, search engines now handle quotes directly.
   * Fixes possible issues with counting members in channel not respecting bot exceptions.
   * Updates ConfigParser to provide extra parser methods rather than relying on validation later.
   * Updates Permissions to also use extended ConfigParser methods, for consistency.
   * Refactored the decorator methods to live in utils.py or be removed.
   * Majority of function definitions now have some kind of docstring.
   * Playing compound links now works better and does not double-queue the carrier video.
   * Add actual command-line arguments to control logging, show version, and skip startup checks. 
      - Supported CLI flags:
         -V to print version and exit.
         --help or -h for standard help / usage.
         --no-checks Legacy option to skip startup checks.
         --logs-kept Set the number of logs to keep when rotating logs.
         --log-level Set an override to DebugLevel in config/options.ini file.
         --log-rotate-fmt Set a filename component using strftime() compatible string.
   * Update the `queue` command to add pagination by both command arg and reactions.
   * Allow `listids` and `perms` commands to fall back to sending in public if DM fails.
   * Improved security of subprocess command execution, to reduce command/shell injection risks.
   * Adds logic to check for updates to MusicBot via git and for dependencies via pip.
      - Adds new command checkupdates to print status about available updates.
      - Adds new command botversion to print bot current version, as reported by git.
      - Adds new CLI flag --no-update-check to disable checking for updates on startup.
      - Adds new CLI flag --no-install-deps to disable automatic install of dependencies when ImportError happens.
   * Further updates to start-up to (hopefully) gracefully fail and install dependencies.
   * Changes on_ready event to call status update and join channels after the event.
   * Changes to player/voice handling to (hopefully) prevent dead players.
   * Adds re-try logic to get_player to (hopefully) deal with initial connection failures.
   * Auto playlist had some refinements in entry extraction and error handling.
   * All launcher files run.sh and run.bat now pass CLI arguments to python. 
   * Adds bootleg Voice connection resume from network outages.
      - Uses discord.py library reconnect logic for back-off retry, can be slow after long outages.
      - Uses custom retry logic to attempt connection multiple times before failing.
      - Detects network outage and automatically pauses or resumes player.
   * Fix logging on Windows so module names are not <string> placeholder.
   * Adds an offline status update to logout/shutdown process.
   * Adds playback progress to saved queue, and starts playback at the saved position.
   * Update run.sh python detection to account for name conventions between distros.
   * Update update.sh python detection to the same as in run.sh. 
   * Improve and test various aspects of Install and Update scripts.
      - All installers now ask before proceeding to install packages.
      - Linux install.sh now supports --list flag to show possible supported distros.
      - Linux install.sh improved detection of python with correct version.
      - Linux install.sh now requires User and Group to set up system service.
      - Windows installer adds FFmpeg install step to install.ps1 via winget tool.
      - Linux distro support updates:
      - Drop support of CentOS 6 as end-of-life.
      - Adds support for CentOS Stream 8.
      - Adds CentOS 7, tested despite EOL date being June 2024.
      - Drop support of Ubuntu versions before 18.04.
      - Tested Ubuntu 18.04, 20.04, and 22.04 installer.
      - Adds support for Pop! OS, tested with 22.04 (20.04 is not tested but may work)
      - Tested Arch Linux (2024.03.01), with venv install.
      - Adds support for Debian 12, with venv install.
      - Tested Debian 11.3 installation.
      - Tested Raspberry Pi OS (Desktop i386, reported as Debian 11).
   * Added new `install.ps1` script. 
   
   **Final Notes:**
   All changes may not be documented here and it's in your best interest to look at [commits](https://github.com/Just-Some-Bots/MusicBot/commits/dev/) on the repo if you want more in depth explanation of the changes made recently. 