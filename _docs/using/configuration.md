---
title: Configuration
category: Using the bot
order: 1
---

This page describes MusicBot's primary configuration file.  
The main configuration file is `config/options.ini`, which is typically copied from `config/example_options.ini` file.  

> Editing your configuration file using Notepad or WordPad may result in broken config files.  
  An editor that is aware of encoding and line-endings is recommended. (Notepad++, VS Code, etc.)  


## First Time Setup

Before you can configure MusicBot, you need to set up a Bot application on the Discord Developer Portal.  
This section will guide you through all those steps:  

<details>
  <summary>How to make a Discord Bot and Configure MusicBot.</summary>

<h3>Make a new Bot and Token</h3>

First, log in to the official Discord Developer Portal and access the <a href="https://discord.com/developers/applications/me">Applications page</a>.<br>  
<ul>
<li>Create a new application, then open the "Bot" page from the menu.</li>  
<li>Find the Token section to reveal and copy your new Bot Token.<br>  
  <strong style="color:#7d6f00;">Notice:</strong> If you have 2FA enabled, you may need to "Reset Token" before you can see it.<br>
  <strong style="color:#ff7373;">Warning:</strong> Keep the Token safe! Don't share it or lose it or you'll need to regenerate it!<br></li>  

<li>Next set the privileged intents. You need to enable each of the Gateway Intents.<br>  
  - Enable Presence Intent<br>
  - Enable Server Members Intent<br>
  - Enable Message Content Intent<br></li>
</ul>

<h3>Configure MusicBot</h3>

You should now have your token and can now copy it into your config file.<br>  
To finish setting up:<br>  
<ul>
<li>Open your bot folder and then the <code>config</code> folder within it.</li>  
<li>Copy <code>example_options.ini</code> and rename it to <code>options.ini</code>.</li>  
<li>Open <code>options.ini</code> then find the "Token" option under <code>[Credentials]</code>.</li>  
<li>Update the value of "Token" with the token you copied from Discord Applications.</li>  
<li>Save, close, and try running MusicBot!</li>
</ul>

If everything is working, make sure to review the rest of the options and make changes as needed.<br>

<h3>How to Run MusicBot</h3>

MusicBot provides a collection of scripts to start the bot.<br>  
For Windows you'll usually use <code>run.bat</code> to start the bot.<br>  
For various Linux-like OS, use <code>run.sh</code> instead.<br>  
You may also launch <code>run.py</code> by passing it to python directly.<br>
All of these scripts support the same <a href="{{ site.baseurl }}/using/running/#flags">command line arguments</a>.<br>  

</details>

---

## Documentation for options.ini  

The options listed here may be older or newer than your installed version of MusicBot.  
For a version-specific documentation, please read the `example_options.ini` file included with your version of MusicBot.    

<p><a class="expand-all-details">Show/Hide All</a></p>

#### [Credentials]

<details>
  <summary>Token</summary>

Discord bot authentication token for your Bot.<br>
Visit Discord Developer Portal to create a bot App and generate your Token.<br>
Never publish your bot token!<br>  
<strong>Default Value:</strong> <i>*empty*</i>  
</details>  
<details>
  <summary>Spotify_ClientID</summary>

Provide your own Spotify Client ID to enable MusicBot to interact with Spotify API.<br>
MusicBot will try to use the web player API (guest mode) if nothing is set here.<br>
Using your own API credentials grants higher usage limits than guest mode.<br>  
<strong>Default Value:</strong> <i>*empty*</i>  
</details>  
<details>
  <summary>Spotify_ClientSecret</summary>

Provide your Spotify Client Secret to enable MusicBot to interact with Spotify API.<br>
This is required if you set the Spotify_ClientID option above.<br>  
<strong>Default Value:</strong> <i>*empty*</i>  
</details>  


#### [Permissions]

<details>
  <summary>OwnerID</summary>

Provide a Discord User ID number to set the owner of this bot.<br>
The word 'auto' or number 0 will set the owner based on App information.<br>
Only one owner ID can be set here. Generally, setting 'auto' is recommended.<br>  
<strong>Default Value:</strong> <code>0</code>  
</details>  
<details>
  <summary>DevIDs</summary>

A list of Discord User IDs who can use the dev-only commands.<br>
Warning: dev-only commands can allow arbitrary remote code execution.<br>
Use spaces to separate multiple IDs.<br>
Most users should leave this setting blank.<br>  
<strong>Default Value:</strong> <i>*empty*</i>  
</details>  
<details>
  <summary>BotExceptionIDs</summary>

Discord Member IDs for other bots that MusicBot should not ignore.<br>
Use spaces to separate multiple IDs.<br>
All bots are ignored by default.<br>  
<strong>Default Value:</strong> <i>*empty*</i>  
</details>  


#### [ChatCommands]

<details>
  <summary>CommandPrefix</summary>

Command prefix is how all MusicBot commands must be started in Discord messages.<br>
E.g., if you set this to * the play command is trigger by *play ...<br>  
<strong>Default Value:</strong> <code>!</code>  
</details>  
<details>
  <summary>CommandsByMention</summary>

Enable using commands with @[YourBotNameHere]<br>
The CommandPrefix is still available, but can be replaced with @ mention.<br>  
<strong>Default Value:</strong> <code>yes</code>  
</details>  
<details>
  <summary>BindToChannels</summary>

ID numbers for text channels that MusicBot should exclusively use for commands.<br>
This can contain IDs for channels in multiple servers.<br>
Use spaces to separate multiple IDs.<br>
All channels are used if this is not set.<br>  
<strong>Default Value:</strong> <i>*empty*</i>  
</details>  
<details>
  <summary>AllowUnboundServers</summary>

Allow responses in all channels while no specific channel is set for a server.<br>
Only used when BindToChannels is missing an ID for a server.<br>  
<strong>Default Value:</strong> <code>yes</code>  
</details>  
<details>
  <summary>UseAlias</summary>

If enabled, MusicBot will allow commands to have multiple names using data in:  config/aliases.json<br>  
<strong>Default Value:</strong> <code>yes</code>  
</details>  
<details>
  <summary>EnablePrefixPerGuild</summary>

Allow MusicBot to save a per-server command prefix, and enables the setprefix command.<br>  
<strong>Default Value:</strong> <code>no</code>  
</details>  


#### [ChatResponses]

<details>
  <summary>DMNowPlaying</summary>

MusicBot will try to send Now Playing notices directly to the member who requested the song instead of posting in a server channel.<br>  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>DisableNowPlayingAutomatic</summary>

Disable now playing messages for songs played via auto playlist.<br>  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>NowPlayingChannels</summary>

Forces MusicBot to use a specific channel to send now playing messages.<br>
Only one text channel ID can be used per server.<br>  
<strong>Default Value:</strong> <i>*empty*</i>  
</details>  
<details>
  <summary>DeleteNowPlaying</summary>

MusicBot will automatically delete Now Playing messages.<br>  
<strong>Default Value:</strong> <code>yes</code>  
</details>  
<details>
  <summary>NowPlayingMentions</summary>

Mention the user who added the song when it is played.<br>  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>DeleteMessages</summary>

Allow MusicBot to automatically delete messages it sends, after a delay.<br>
Delay period is controlled by DeleteDelayShort and DeleteDelayLong.<br>  
<strong>Default Value:</strong> <code>yes</code>  
</details>  
<details>
  <summary>DeleteInvoking</summary>

Auto delete valid commands after a delay.<br>  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>DeleteDelayShort</summary>

Sets the short period of seconds before deleting messages.<br>
This period is used by messages that require no further interaction.<br>  
<strong>Default Value:</strong> <code>0:00:30</code>  
</details>  
<details>
  <summary>DeleteDelayLong</summary>

Sets the long delay period before deleting messages.<br>
This period is used by interactive or long-winded messages, like search and help.<br>  
<strong>Default Value:</strong> <code>0:01:00</code>  
</details>  
<details>
  <summary>UseEmbeds</summary>

Allow MusicBot to format its messages as embeds.<br>  
<strong>Default Value:</strong> <code>yes</code>  
</details>  
<details>
  <summary>CustomEmbedFooter</summary>

Replace MusicBot name/version in embed footer with custom text.<br>
Only applied when UseEmbeds is enabled and it is not blank.<br>  
<strong>Default Value:</strong> <code>Just-Some-Bots/MusicBot (alpha-050125-18-g1ef01294-config-cli-tool)</code>  
</details>  
<details>
  <summary>RemoveEmbedFooter</summary>

Completely remove the footer from embeds.<br>  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>SearchList</summary>

If enabled, users must indicate search result choices by sending a message instead of using reactions.<br>  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>DefaultSearchResults</summary>

Sets the default number of search results to fetch when using the search command without a specific number.<br>  
<strong>Default Value:</strong> <code>3</code>  
</details>  
<details>
  <summary>QueueLength</summary>

The number of entries to show per-page when using q command to list the queue.<br>  
<strong>Default Value:</strong> <code>10</code>  
</details>  
<details>
  <summary>ReplyAndMention</summary>

Command responses will also mention or notify the user.<br>  
<strong>Default Value:</strong> <code>yes</code>  
</details>  


#### [Playback]

<details>
  <summary>DefaultVolume</summary>

Sets the default volume level MusicBot will play songs at.<br>
You can use any value from 0 to 1, or 0% to 100% volume.<br>  
<strong>Default Value:</strong> <code>0.15</code>  
</details>  
<details>
  <summary>DefaultSpeed</summary>

Sets the default speed MusicBot will play songs at.<br>
Must be a value from 0.5 to 100.0 for ffmpeg to use it.<br>
A value of 1 is normal playback speed.<br>
Note: Streamed media does not support speed adjustments.<br>  
<strong>Default Value:</strong> <code>1.000</code>  
</details>  
<details>
  <summary>SkipsRequired</summary>

Number of channel member votes required to skip a song.<br>
Acts as a minimum when SkipRatio would require more votes.<br>  
<strong>Default Value:</strong> <code>4</code>  
</details>  
<details>
  <summary>SkipRatio</summary>

This percent of listeners in voice must vote for skip.<br>
If SkipsRequired is lower than the computed value, it will be used instead.<br>
You can set this from 0 to 1, or 0% to 100%.<br>  
<strong>Default Value:</strong> <code>0.5</code>  
</details>  
<details>
  <summary>AllowAuthorSkip</summary>

Allow the member who requested the song to skip it, bypassing votes.<br>  
<strong>Default Value:</strong> <code>yes</code>  
</details>  
<details>
  <summary>LegacySkip</summary>

Enable users with the InstaSkip permission to bypass skip voting and force skips.<br>  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>AutoPause</summary>

MusicBot will automatically pause playback when no users are listening.<br>  
<strong>Default Value:</strong> <code>yes</code>  
</details>  
<details>
  <summary>PersistentQueue</summary>

Allow MusicBot to save the song queue, so queued songs will survive restarts.<br>  
<strong>Default Value:</strong> <code>yes</code>  
</details>  
<details>
  <summary>PreDownloadNextSong</summary>

Enable MusicBot to download the next song in the queue while a song is playing.<br>
Currently this option does not apply to auto playlist or songs added to an empty queue.<br>  
<strong>Default Value:</strong> <code>yes</code>  
</details>  
<details>
  <summary>UseExperimentalEqualization</summary>

Tries to use ffmpeg to get volume normalizing options for use in playback.<br>
This option can cause delay between playing songs, as the whole track must be processed.<br>  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>RoundRobinQueue</summary>

If enabled and multiple members are adding songs, MusicBot will organize playback for one song per member.<br>  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>EnableLocalMedia</summary>

Enable playback of local media files using the play command.<br>
When enabled, users can use:  `play file://path/to/file.ext`<br>
to play files from the local MediaFileDirectory path.<br>  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>UnpausePlayerOnPlay</summary>

Allow MusicBot to automatically unpause when play commands are used.<br>  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>UseOpusAudio</summary>

May reduce CPU usage by avoiding PCM-to-Opus encoding in python.<br>
When enabled, volume is controlled via FFmpeg filter instead of python.<br>
May cause a short delay when tracks first start for bitrate discovery.<br>  
<strong>Default Value:</strong> <code>yes</code>  
</details>  
<details>
  <summary>UseOpusProbe</summary>

Similar to UseOpusAudio, but reduces CPU usage even more where possible.<br>
If the media is already Opus encoded (like YouTube) no re-encoding is done.<br>
This option will disable speed, volume, and UseExperimentalEqualization options.<br>  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>DefaultSearchService</summary>

This option sets the default search service used by MusicBot through ytdlp.<br>
Read ytdlp's list of supported sites to find supported prefixes you can use here.<br>
Some prefix examples:   ytsearch, scsearch, gvsearch, yvsearch, bilisearch, nicosearch<br>  
<strong>Default Value:</strong> <code>ytsearch</code>  
</details>  


#### [AutoPlaylist]

<details>
  <summary>UseAutoPlaylist</summary>

Enable MusicBot to automatically play music from the auto playlist when the queue is empty.<br>  
<strong>Default Value:</strong> <code>yes</code>  
</details>  
<details>
  <summary>AutoPlaylistRandom</summary>

Shuffles the auto playlist tracks before playing them.<br>  
<strong>Default Value:</strong> <code>yes</code>  
</details>  
<details>
  <summary>AutoPlaylistAutoSkip</summary>

Enable automatic skip of auto playlist songs when a user plays a new song.<br>
This only applies to the current playing song if it was added by the auto playlist.<br>  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>AutoPlaylistRemoveBlocked</summary>

Remove songs from the auto playlist if they are found in the song block list.<br>  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>SavePlayedHistoryGlobal</summary>

Enable saving all songs played by MusicBot to a global playlist file:  config/playlists/history.txt<br>
This will contain all songs from all servers.<br>  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>SavePlayedHistoryGuilds</summary>

Enable saving songs played per-server to a playlist file:  config/playlists/history[Server ID].txt<br>  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>RemoveFromAPOnError</summary>

Enable MusicBot to automatically remove unplayable entries from the auto playlist.<br>  
<strong>Default Value:</strong> <code>yes</code>  
</details>  


#### [MusicBot]

<details>
  <summary>DebugLevel</summary>

Set the log verbosity of MusicBot. Normally this should be set to INFO.<br>
It can be set to one of the following:<br>
 CRITICAL, ERROR, WARNING, INFO, DEBUG, VOICEDEBUG, FFMPEG, NOISY, or EVERYTHING<br>  
<strong>Default Value:</strong> <code>INFO</code>  
</details>  
<details>
  <summary>AutojoinChannels</summary>

A list of Voice Channel IDs that MusicBot should automatically join on start up.<br>
Use spaces to separate multiple IDs.<br>  
<strong>Default Value:</strong> <i>*empty*</i>  
</details>  
<details>
  <summary>SaveVideos</summary>

Allow MusicBot to keep downloaded media, or delete it right away.<br>  
<strong>Default Value:</strong> <code>yes</code>  
</details>  
<details>
  <summary>StorageLimitBytes</summary>

If SaveVideos is enabled, set a limit on how much storage space should be used.<br>  
<strong>Default Value:</strong> <code>0</code>  
</details>  
<details>
  <summary>StorageLimitDays</summary>

If SaveVideos is enabled, set a limit on how long files should be kept.<br>  
<strong>Default Value:</strong> <code>0</code>  
</details>  
<details>
  <summary>StorageRetainAutoPlay</summary>

If SaveVideos is enabled, never purge auto playlist songs from the cache regardless of limits.<br>  
<strong>Default Value:</strong> <code>yes</code>  
</details>  
<details>
  <summary>AutoSummon</summary>

Automatically join the owner if they are in an accessible voice channel when bot starts.<br>  
<strong>Default Value:</strong> <code>yes</code>  
</details>  
<details>
  <summary>StatusMessage</summary>

Specify a custom message to use as the bot's status. If left empty, the bot<br>
will display dynamic info about music currently being played in its status instead.<br>
Status messages may also use the following variables:<br>
 {n_playing}   = Number of currently Playing music players.<br>
 {n_paused}    = Number of currently Paused music players.<br>
 {n_connected} = Number of connected music players, in any player state.<br>
<br>
The following variables give access to information about the player and track.<br>
These variables may not be accurate in multi-guild bots:<br>
 {p0_length}   = The total duration of the track, if available. Ex: [2:34]<br>
 {p0_title}    = The track title for the currently playing track.<br>
 {p0_url}      = The track URL for the currently playing track.<br>  
<strong>Default Value:</strong> <i>*empty*</i>  
</details>  
<details>
  <summary>StatusIncludePaused</summary>

If enabled, status messages will report info on paused players.<br>  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>WriteCurrentSong</summary>

If enabled, MusicBot will save the track title to:  data/[Server ID]/current.txt<br>  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>ShowConfigOnLaunch</summary>

Display MusicBot config settings in the logs at startup.<br>  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>LeaveServersWithoutOwner</summary>

If enabled, MusicBot will leave servers if the owner is not in their member list.<br>  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>SelfDeafen</summary>

MusicBot will automatically deafen itself when entering a voice channel.<br>  
<strong>Default Value:</strong> <code>yes</code>  
</details>  
<details>
  <summary>LeaveInactiveVC</summary>

If enabled, MusicBot will leave a voice channel when no users are listening,<br>
after waiting for a period set in LeaveInactiveVCTimeOut option.<br>
Listeners are channel members, excluding bots, who are not deafened.<br>  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>LeaveInactiveVCTimeOut</summary>

Set a period of time to wait before leaving an inactive voice channel.<br>
You can set this to a number of seconds or phrase like:  4 hours<br>  
<strong>Default Value:</strong> <code>0:05:00</code>  
</details>  
<details>
  <summary>LeaveAfterQueueEmpty</summary>

If enabled, MusicBot will leave the channel immediately when the song queue is empty.<br>  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>LeavePlayerInactiveFor</summary>

When paused or no longer playing, wait for this amount of time then leave voice.<br>
You can set this to a number of seconds of phrase like:  15 minutes<br>
Set it to 0 to disable leaving in this way.<br>  
<strong>Default Value:</strong> <code>0:00:00</code>  
</details>  
<details>
  <summary>EnableNetworkChecker</summary>

Allow MusicBot to use timed pings to detect network outage and availability.<br>
This may be useful if you keep the bot joined to a channel or playing music 24/7.<br>
MusicBot must be restarted to enable network testing.<br>
By default this is disabled.<br>  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>YtdlpProxy</summary>

Experimental, HTTP/HTTPS proxy settings to use with ytdlp media downloader.<br>
The value set here is passed to `ytdlp --proxy` and aiohttp header checking.<br>
Leave blank to disable.<br>  
<strong>Default Value:</strong> <i>*empty*</i>  
</details>  
<details>
  <summary>YtdlpUserAgent</summary>

Experimental option to set a static User-Agent header in yt-dlp.<br>
It is not typically recommended by yt-dlp to change the UA string.<br>
For examples of what you might put here, check the following two links:<br>
   https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/User-Agent <br>
   https://www.useragents.me/ <br>
Leave blank to use default, dynamically generated UA strings.<br>  
<strong>Default Value:</strong> <i>*empty*</i>  
</details>  
<details>
  <summary>YtdlpSourceAddress</summary>

Force yt-dlp to bind to a specific IP address or IP version on your system.<br>
To force any available IPv4, set this to:  0.0.0.0<br>
To force any available IPv6, set this to:  ::<br>
To allow either IPv4 or v6, set this to:  *<br>  
<strong>Default Value:</strong> <code>*</code>  
</details>  
<details>
  <summary>EnableUserBlocklist</summary>

Toggle the user block list feature, without emptying the block list.<br>  
<strong>Default Value:</strong> <code>yes</code>  
</details>  
<details>
  <summary>EnableSongBlocklist</summary>

Enable the song block list feature, without emptying the block list.<br>  
<strong>Default Value:</strong> <code>no</code>  
</details>  


#### [Files]

<details>
  <summary>UserBlocklistFile</summary>

An optional file path to a text file listing Discord User IDs, one per line.<br>  
<strong>Default Value:</strong> <code>./config/blocklist_users.txt</code>  
</details>  
<details>
  <summary>SongBlocklistFile</summary>

An optional file path to a text file that lists URLs, words, or phrases one per line.<br>
Any song title or URL that contains any line in the list will be blocked.<br>  
<strong>Default Value:</strong> <code>./config/blocklist_songs.txt</code>  
</details>  
<details>
  <summary>AutoPlaylistDirectory</summary>

An optional path to a directory containing auto playlist files.<br>
Each file should contain a list of playable URLs or terms, one track per line.<br>  
<strong>Default Value:</strong> <code>./config/playlists</code>  
</details>  
<details>
  <summary>MediaFileDirectory</summary>

An optional directory path where playable media files can be stored.<br>
All files and sub-directories can then be accessed by using 'file://' as a protocol.<br>
Example:  file://some/folder/name/file.ext<br>
Maps to:  ./media/some/folder/name/file.ext<br>  
<strong>Default Value:</strong> <code>./media</code>  
</details>  
<details>
  <summary>AudioCachePath</summary>

An optional directory path where MusicBot will store long and short-term cache for playback.<br>  
<strong>Default Value:</strong> <code>./audio_cache</code>  
</details>  
<details>
  <summary>LogsMaxKept</summary>

Configure automatic log file rotation at restart, and limit the number of files kept.<br>
When disabled, only one log is kept and its contents are replaced each run.<br>
Set to 0 to disable.  Maximum allowed number is 100.<br>  
<strong>Default Value:</strong> <code>3</code>  
</details>  
<details>
  <summary>LogsDateFormat</summary>

Configure the log file date format used when LogsMaxKept is enabled.<br>
If left blank, a warning is logged and the default will be used instead.<br>
Learn more about time format codes from the tables and data here:<br>
    https://docs.python.org/3/library/datetime.html#strftime-strptime-behavior<br>  
<strong>Default Value:</strong> <code>.ended-%Y-%j-%H%m%S</code>  
</details>  


---

<a class="expand-all-details">Show/Hide All</a>
