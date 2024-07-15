---
title: Configuration
category: Using the bot
order: 1
---

Configuring MusicBot is relatively straight forward. All configuration files are stored within the `config` directory of MusicBot and can be edited with any line-ending-aware text editor (like Notepad++, Sublime text, Atom, or VS Code to name a few.)

> **Warning:** Do not use Notepad or Wordpad to edit the config files, these editors will break the config files.

A general breakdown of the config directory is as follows:  

-  `example_options.ini` --- A complete options file with comments explaining each config option.  This file gets updated when new options are added or changed.  This file may be used as a template by some setup logic.
- `example_permissions.ini` --- A complete permissions file with comments explaining the permissions system.  This file gets updated when new permissions are added or changed.  This file is automatically copied if `permissions.ini` is missing.
- `example_aliases.json` --- An example of command aliases.  This file gets updated with MusicBot, though aliases are optional. 
- `options.ini` --- The primary config file for MusicBot.
- `permissions.ini` --- The permissions that control user access to MusicBot.
- `aliases.json` --- The command aliases MusicBot will allow, if aliases are enabled.
- `blocklist_songs.txt` --- A list of song URLs or titles that should not be allowed to play.
- `blocklist_users.txt` --- A list of user IDs that should not be allowed to use the MusicBot.
- `playlists/` --- A folder full of playlist text files, used by the auto-playlist option or the play-history options.
- `playlists/default.txt` --- A bundled playlist (typically URLs) which is updated with MusicBot.  This file gets copied if auto-playlist is enabled but no `autoplaylist.txt` playlist file is available.
- `playlists/autoplaylist.txt` --- A list of URLs or track titles to automatically play when auto-playlist options are enabled.
- `i18n/` --- A folder full of localization files, for MusicBot translations.  ***Notice:** The current translation system does not provide full translation of MusicBot.  Current translations are provided by community members and may be out-of-date with current code. *

## First time setup
Before you can run MusicBot, you must configure MusicBot. To do this takes a few steps:   
1.) Create a Discord API Token.  
2.) Configure your MusicBot.  
3.) Connect your MusicBot.

### 1. Create a Discord API Token
To create a Discord Bot, and get your API Token, visit the [Official Discord Developer Portal](https://discord.com/developers/applications/me) and log in to your discord account.   
Once logged in, follow the instructions in this [10 second video](https://drive.google.com/file/d/1wZG_TBVfjQfj0CEYaRTzS60D-cbfeeYZ/view). If you followed it entirely, you should have revealed your token and can now copy it into the config file in the next step. 

<img class="doc-img" src="{{ site.baseurl }}/images/token.png" alt="Token example" style="width: 500px;"/>

Please note that MusicBot also requires privileged intents to function. You need to enable each of the Gateway Intents on your [Discord Application](https://discord.com/developers/applications)'s 'Bot' page.

<img class="doc-img" src="{{ site.baseurl }}/images/intents.png" alt="Intents" style="width: 500px;"/>

### 2. Configure your MusicBot
Basic configuration is very simple. Just follow these steps:  
1.) Open your bot folder and then the `config` folder.  
2.) Copy `example_options.ini` and rename it to `options.ini`.  
3.) Open `options.ini` with a code editor like Notepad++ or Atom.  
4.) Update the `Token` option with your Discord API Token.  
5.) Update the other options as you see fit and save the file.

> **Warning:** Do not use Notepad or WordPad to edit the config files.  They do not preserve line endings and will break your config files.

There are other configurations you can set up, such as the permissions, command aliases, and auto-playlists. But as long as you have `[Credentials] > Token` configured with a valid API token in `options.ini` file, the MusicBot should be ready to run.

### 3. Connect your MusicBot
Once you have minimally configured MusicBot, the next step is adding it to your discord server(s).  
  
If MusicBot is not already joined to a discord server, it will print out an OAuth Invite URL when it starts up. This URL can be copied and used in your web browser or discord client to add the bot to discord servers.[TODO: Verify this is true]  

Alternatively, you can generate an invite URL by using the Discord Developer Portal and clicking the 'Generate OAuth2 URL' button on the application page.

## Configure via command

MusicBot supports managing some configurations via commands. Notably, much of `options.ini` and `permissions.ini` can be managed by their own commands `config` and `setperms` respectively.  
These commands can be used to list available options with their descriptions and default values.  They can also be used to manipulate the configuration in real-time.  

To learn more about these commands, visit the commands page.

## All available options
This section describes the contents of the primary config file, `options.ini`. Each sub-heading in this section corresponds to a section name within the options file. The child headings of each section are option names and describe each option, accepted values and default values for the option.  

---

### [Credentials]
#### Token
Discord bot authentication token for your Bot.  
Visit Discord Developer Portal to create a bot App and generate your Token.  
Never publish your bot token!  
**Default Value:** *empty*    

#### Spotify_ClientID
An optional Spotify Client ID to enable MusicBot to interact with Spotify API.  See the [Spotify integration]({{ site.baseurl }}/using/spotify) page for more info.  
**Default Value:** *empty*  

#### Spotify_ClientSecret
Provide an optional Spotify Client Secret to enable MusicBot to interact with Spotify API.  See the [Spotify integration]({{ site.baseurl }}/using/spotify) page for more info.  
**Default Value:** *empty*  

---

### [Permissions]
#### OwnerID
Provide a Discord User ID number or the word `auto` to set the owner of this bot.  
Only one user can be set here, and they will be granted full permissions.  
When set to `auto` the ID will be set to the user which created the bot token.   
**Default Value:** `auto`  

#### DevIDs
A list of Discord User ID numbers who can use the dev-only commands.  
**Warning** these commands are dangerous and allow arbitrary code execution.    
**Default Value:** *empty*  

#### BotExceptionIDs
Discord Member IDs for other bots that MusicBot should not ignore.  
All bots are ignored by default.  
**Default Value:** *empty*  

---

### [Chat]
#### CommandPrefix
Command prefix is how all MusicBot commands must be started.  
Excluding literal empty spaces, it can be set to almost any arbitrary character(s).  
For example, if set to `!` then the play command is `!play`.  
**Default Value:** `!`  

#### CommandsByMention
Enable using commands with `@[YourBotNameHere]`  
The CommandPrefix is still available, but can be replaced with @ mention.  
**Default Value:** `yes`  

#### BindToChannels
Discord Channel ID numbers for text channels that MusicBot should exclusively use for listening and responding to commands.  
All channels are used if this is not set.  
This is useful to keep bot commands in one or few channels of a server.  
**Default Value:** *empty*  

#### AllowUnboundServers
A multi-server option to allow MusicBot to respond in all text channels of a server, when that server does not have channel IDs configured in `BindToChannels` option.  
If `BindToChannels` is left empty, this option has no impact.  
**Default Value:** `no`  

#### AutojoinChannels
A list of Voice Channel IDs that MusicBot should automatically join on start up.  
**Default Value:** *empty*  

#### DMNowPlaying
MusicBot will try to send Now Playing notices directly to the member who requested the song instead of posting in server channel.  
**Default Value:** `no`  

#### DisableNowPlayingAutomatic
Disable now playing messages for songs played via auto playlist.  
**Default Value:** `no`  

#### NowPlayingChannels
Forces MusicBot to use a specific channel to send now playing messages. One text channel ID per server.  
**Default Value:** *empty*  

#### DeleteNowPlaying
MusicBot will automatically delete Now Playing messages.  
**Default Value:** `yes`  

---

### [MusicBot]
#### DebugLevel
Set the log verbosity of MusicBot. Normally this should be set to `INFO`.  
It can be set to one of the following:  
 `CRITICAL`, `ERROR`, `WARNING`, `INFO`, `DEBUG`, `VOICEDEBUG`, `FFMPEG`, `NOISY`, or `EVERYTHING`  
Levels are listed in highest to lowest priority. Where lower priority means more log output.  
**Default Value:** `INFO`  

#### DefaultVolume
Sets the default volume level MusicBot will play songs at. Must be a value from `0.0` to `1.0`, inclusive.  
**Default Value:** `0.15`  

#### DefaultSpeed
Sets the default speed MusicBot will play songs at.  
Must be a value from `0.5` to `100.0` for ffmpeg to use it.  
**Default Value:** `1.0`  

#### SkipsRequired
Number of member votes required to skip a song.  
Acts as a minimum when `SkipRatio` would require more votes.  
If you set this to `1` it will disable voting, and each skip command will immediately skip.  
Alternatively use Permissions to enable force-skip / vote-bypass for specific users or groups.  
**Default Value:** `4`  

#### SkipRatio
This percent of listeners must vote for skip to pass a skip vote.  
The listener count excludes deafened users from the vote tally.  
If `SkipsRequired` is lower than the calculated number of listener votes, it will be used instead.  
For example:  
11 members in a channel with MusicBot, 1 is deafened, and 1 votes to skip.  
MusicBot counts 10 listeners, and 1 vote to skip.  
If `SkipRatio` is set to `0.7`, then 7 votes are needed to skip.  
If `SkipsRequired` is set to `4` only 4 votes are needed.  
If `SkipsRequired` was `9` instead, the ratio dictates 7 votes are needed.  
**Default Value:** `0.5`  

#### SaveVideos
Allow MusicBot to keep downloaded media, or disable to delete downloads right away.  
**Default Value:** `yes`  

#### StorageLimitBytes
If `SaveVideos` is enabled, this sets a limit on how much storage space should be used.  
Downloaded media is deleted based on least recent use, or oldest first.  
Shorthand notations like `20 MB` or `0.75GB` are accepted by this option.  
Setting this to `0` will remove storage limits.  
**Default Value:** `0`  

#### StorageLimitDays
If `SaveVideos` is enabled, this sets a time limit on how long files should be kept in days.  
Windows uses file creation time for this while other OS use last file access time.  
This should be a positive, whole number.  
**Default Value:** `0`  

#### StorageRetainAutoPlay
If `SaveVideos` is enabled, never purge media downloaded for auto playlist songs from the cache.  
This option ignores any storage limits set above.  
**Default Value:** `yes`  

#### NowPlayingMentions
Mention the user who added the song when it is played.  
This will @ the user.  
**Default Value:** `no`  

#### AutoSummon
Automatically join the owner if they are in an accessible voice channel when bot starts.  
**Default Value:** `yes`  

#### UseAutoPlaylist
Enable MusicBot to automatically play music from the `autoplaylist.txt` file.  
If it does not exist it will be created using a bundled default list.  
**Default Value:** `yes`  

#### AutoPlaylistRandom
Shuffles the auto-playlist tracks before playing them.  
**Default Value:** `yes`  

#### AutoPlaylistAutoSkip
Enable automatic skip of auto-playlist songs when a user plays a new song.  
This only applies to the current playing song if it was added by the auto-playlist.  
**Default Value:** `no`  

#### AutoPlaylistRemoveBlocked
Remove songs from the auto-playlist if they are found in the song blocklist.  
This will update the playlist file and create an audit file with the removed entries.  
**Default Value:** `no`  

#### AutoPause
MusicBot will automatically pause playback when no users are actively listening.  
Deafened users are not considered active listeners.  
**Default Value:** `yes`  

#### DeleteMessages
Allow MusicBot to automatically delete messages it sends, after a short delay.  
**Default Value:** `yes`  

#### DeleteInvoking
Allow MusicBot to auto delete valid commands after a short delay.  
**Default Value:** `no`  

#### PersistentQueue
Allow MusicBot to save the song queue, so they will survive restarts.  
**Default Value:** `yes`  

#### StatusMessage
Specify a custom message to use as the bot's status.  
If left empty, the bot will display dynamic info about music currently being played in its status instead.  
Custom status messages may also use the following variables:  
 `{n_playing}` = Number of currently Playing music players.  
 `{n_paused}`  = Number of currently Paused music players.  
 `{n_connected}` = Number of connected music players, in any player state.  
  
The following variables give access to information about the player and track.  
These variables may not be accurate in multi-guild bots:  
 `{p0_length}`   = The total duration of the track, if available. Ex: [2:34]  
 `{p0_title}`    = The track title for the currently playing track.  
 `{p0_url}`      = The track url for the currently playing track.  

**Default Value:** *empty*  

#### WriteCurrentSong
If enabled, MusicBot will save the current playing track title to:  `data/{server_ID}/current.txt`  
**Default Value:** `no`  

#### AllowAuthorSkip
Allow the member who requested the song to skip it, bypassing votes and permissions.  
**Default Value:** `yes`  

#### UseExperimentalEqualization
Uses ffmpeg to pre-process media and get volume normalizing options for use in playback.  
This can improve volume fluctuation in playback and potentially make playback volume more consistent between tracks.  
However, it can also cause delays in starting playback that increases with the size/duration of the media.  
**Default Value:** `no`  

#### UseEmbeds
Allow MusicBot to format it's messages as embeds instead of plain text / markdown.  
**Default Value:** `yes`  

#### QueueLength
The number of entries to show per-page when using q command to list the queue.  
**Default Value:** `10`  

#### RemoveFromAPOnError
Enable MusicBot to automatically remove unplayable entries from the auto playlist.  
**Default Value:** `yes`  

#### ShowConfigOnLaunch
Display MusicBot config settings in the logs at startup.  
**Default Value:** `no`  

#### LegacySkip
Enable users with the InstaSkip permission to bypass skip voting and force skips.  
**Default Value:** `no`  

#### LeaveServersWithoutOwner
If enabled, MusicBot will leave servers if the owner is not in their member list.  
**Default Value:** `no`  

#### UseAlias
If enabled, MusicBot will allow commands to have multiple names using aliases stored in:  `config/aliases.json`  
**Default Value:** `yes`  

#### CustomEmbedFooter
Replace MusicBot name/version in embed footer with custom text.  
Only applied when `UseEmbeds` is enabled and it is not blank.  
**Default Value:** `Just-Some-Bots/MusicBot (release-250723-148-gde021b5c-dirty)`  

#### SelfDeafen
MusicBot will automatically deafen itself when entering a voice channel.  
MusicBot doesn't use incoming voice data, but this signals to the API that we don't want to receive audio and displays the deafen icon which some users prefer.  
**Default Value:** `yes`  

#### LeaveInactiveVC
If enabled, MusicBot will leave a voice channel when no users are actively listening, after waiting for a period set in `LeaveInactiveVCTimeOut`.  
**Default Value:** `no`  

#### LeaveInactiveVCTimeOut
Set a period of time to wait before leaving an inactive voice channel.  
Only applies when `LeaveInactiveVC` is enabled.  
Time can be set in seconds or as a duration phrase containing any of: day, hour, minute, second  
Example values:   `.5 hours`,  `1 day`,  `77min`  
**Default Value:** `300`  

#### LeaveAfterQueueEmpty
If enabled, MusicBot will leave the channel immediately when the song queue is empty.  
**Default Value:** `no`  

#### LeavePlayerInactiveFor
Set a period of seconds that a player can be paused or not playing before it will disconnect.  
This setting is independent of `LeaveAfterQueueEmpty`.  
Time can be set in seconds or using duration phrase as described in `LeaveInactiveVCTimeOut`  
Set to `0` to disable.  
**Default Value:** `0`  

#### SearchList
If enabled, users must indicate search result choices by sending a message instead of using reactions.  
**Default Value:** `no`  

#### DefaultSearchResults
Sets the default number of search results to fetch when using search command without a specific number.  
**Default Value:** `3`  

#### EnablePrefixPerGuild
Allow MusicBot to save a per-server command prefix, and enables `setprefix` command.  
**Default Value:** `no`  

#### RoundRobinQueue
If enabled and multiple members are adding songs, MusicBot will organize playback for one song per member.  
**Default Value:** `no`  

#### EnableNetworkChecker
Allow MusicBot to use system ping command to detect network outage and availability.  
This is useful if you keep the bot joined to a channel or playing music 24/7.  
MusicBot must be restarted to enable network testing.  
By default this is disabled.  
**Default Value:** `no`  

#### SavePlayedHistoryGlobal
Enable saving all songs played by MusicBot to a global playlist, `history.txt`  
**Default Value:** `no`  

#### SavePlayedHistoryGuilds
Enable saving songs played per-guild/server to a playlist, `history-{guild_id}.txt`  
**Default Value:** `no`  

#### EnableLocalMedia
Enable playback of local media files using the play command.  
When enabled, users can use:  `play file://path/to/file.ext`
to play files from the local `MediaFileDirectory` path.  
**Default Value:** `no`  

#### UnpausePlayerOnPlay
Allow MusicBot to automatically unpause when play commands are used.  
**Default Value:** `no`  

#### EnableUserBlocklist
Enable the user block list feature, without emptying the block list.  
**Default Value:** `yes`  

#### EnableSongBlocklist
Enable the song block list feature, without emptying the block list.  
**Default Value:** `no`  

---

### [Files]
#### UserBlocklistFile
An optional file path to a text file listing Discord User IDs, one per line.  
**Default Value:** `config/blocklist_users.txt`  

#### SongBlocklistFile
An optional file path to a text file that lists URLs, words, or phrases one per line.
Any song title or URL that contains any line in the list will be blocked.  
**Default Value:** `config/blocklist_songs.txt`  

#### AutoPlaylistDirectory
An optional path to a directory containing auto playlist files.  
Each file should contain a list of playable URLs or terms, one track per line.  
**Default Value:** `config/playlists`  

#### MediaFileDirectory
An optional directory path where playable media files can be stored.  
All files and sub-directories can then be accessed by using 'file://' as a protocol.  
Example:  file://some/folder/name/file.ext  
Maps to:  ./media/some/folder/name/file.ext  
**Default Value:** `media`  

#### i18nFile
An optional file path to an i18n language file.  
This option may be removed or replaced in the future!  
**Default Value:** `config/i18n/en.json`  

#### AudioCachePath
An optional directory path where MusicBot will store long and short-term cache for playback.  
**Default Value:** `/home/main/git-repos/MusicBot/audio_cache`  

#### LogsMaxKept
Configure automatic log file rotation at restart, and limit the number of files kept.  
When disabled, only one log is kept and its contents are replaced each run.  
Default is `0`, for disabled.  
Maximum allowed number is `100`.  
**Default Value:** `0`  

#### LogsDateFormat
Configure the log file date format used when LogsMaxKept is enabled.  
If left blank, a warning is logged and the default will be used instead.  
Learn more about time format codes from the tables and data here:  
    https://docs.python.org/3/library/datetime.html#strftime-strptime-behavior  
**Default Value:** `.ended-%Y-%j-%H%m%S`  

