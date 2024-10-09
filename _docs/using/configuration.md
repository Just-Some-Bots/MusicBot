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
<br>

</details>

---

## Documentation for options.ini

### [Credentials]

<details>
  <summary>Token</summary>

Discord bot authentication token for your Bot. Visit Discord Developer Portal to create a bot App and generate your Token. Never publish your bot token!  
<strong>Default Value:</strong> <i>*empty*</i>  
</details>  
<details>
  <summary>Spotify_ClientID</summary>

Provide an optional Spotify Client ID to enable MusicBot to interact with Spotify API.  
<strong>Default Value:</strong> <i>*empty*</i>  
</details>  
<details>
  <summary>Spotify_ClientSecret</summary>

Provide an optional Spotify Client Secret to enable MusicBot to interact with Spotify API.  
<strong>Default Value:</strong> <i>*empty*</i>  
</details>  
<details>
  <summary>YtdlpOAuth2ClientID</summary>

Sets the YouTube API Client ID, used by Yt-dlp OAuth2 plugin.
Optional, unless built-in credentials are not working.  
<strong>Default Value:</strong> <code>861556708454-d6dlm3lh05idd8npek18k6be8ba3oc68.apps.googleusercontent.com</code>  
</details>  
<details>
  <summary>YtdlpOAuth2ClientSecret</summary>

Sets the YouTube API Client Secret key, used by Yt-dlp OAuth2 plugin.
Optional, unless YtdlpOAuth2ClientID is set.  
<strong>Default Value:</strong> <code>SboVhoG9s0rNafixCSGGKXAT</code>  
</details>  


### [Permissions]

<details>
  <summary>OwnerID</summary>

Provide a Discord User ID number or the word 'auto' to set the owner of this bot.  
<strong>Default Value:</strong> <code>0</code>  
</details>  
<details>
  <summary>DevIDs</summary>

A list of Discord User ID numbers who can remotely execute code using MusicBot dev-only commands. Warning, you should only set this if you plan to do development of MusicBot!  
<strong>Default Value:</strong> <i>*empty*</i>  
</details>  
<details>
  <summary>BotExceptionIDs</summary>

Discord Member IDs for other bots that MusicBot should not ignore.  All bots are ignored by default.  
<strong>Default Value:</strong> <i>*empty*</i>  
</details>  


### [Chat]

<details>
  <summary>CommandPrefix</summary>

Command prefix is how all MusicBot commands must be started  
<strong>Default Value:</strong> <code>!</code>  
</details>  
<details>
  <summary>CommandsByMention</summary>

Enable using commands with @[YourBotNameHere]
The CommandPrefix is still available, but can be replaced with @ mention.  
<strong>Default Value:</strong> <code>yes</code>  
</details>  
<details>
  <summary>BindToChannels</summary>

ID numbers for text channels that MusicBot should exclusively use for commands. All channels are used if this is not set.  
<strong>Default Value:</strong> <i>*empty*</i>  
</details>  
<details>
  <summary>AllowUnboundServers</summary>

Allow MusicBot to respond in all text channels of a server, when no channels are set in BindToChannels option.  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>AutojoinChannels</summary>

A list of Voice Channel IDs that MusicBot should automatically join on start up.  
<strong>Default Value:</strong> <i>*empty*</i>  
</details>  
<details>
  <summary>DMNowPlaying</summary>

MusicBot will try to send Now Playing notices directly to the member who requested the song instead of posting in server channel.  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>DisableNowPlayingAutomatic</summary>

Disable now playing messages for songs played via auto playlist.  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>NowPlayingChannels</summary>

Forces MusicBot to use a specific channel to send now playing messages. One text channel ID per server.  
<strong>Default Value:</strong> <i>*empty*</i>  
</details>  
<details>
  <summary>DeleteNowPlaying</summary>

MusicBot will automatically delete Now Playing messages.  
<strong>Default Value:</strong> <code>yes</code>  
</details>  


### [MusicBot]

<details>
  <summary>DebugLevel</summary>

Set the log verbosity of MusicBot. Normally this should be set to INFO.
It can be set to one of the following:
 CRITICAL, ERROR, WARNING, INFO, DEBUG, VOICEDEBUG, FFMPEG, NOISY, or EVERYTHING  
<strong>Default Value:</strong> <code>INFO</code>  
</details>  
<details>
  <summary>DefaultVolume</summary>

Sets the default volume level MusicBot will play songs at. Must be a value from 0 to 1 inclusive.  
<strong>Default Value:</strong> <code>0.15</code>  
</details>  
<details>
  <summary>DefaultSpeed</summary>

Sets the default speed MusicBot will play songs at.
Must be a value from 0.5 to 100.0 for ffmpeg to use it.  
<strong>Default Value:</strong> <code>1.000</code>  
</details>  
<details>
  <summary>SkipsRequired</summary>

Number of members required to skip a song. Acts as a minimum when SkipRatio would require more votes.  
<strong>Default Value:</strong> <code>4</code>  
</details>  
<details>
  <summary>SkipRatio</summary>

This percent of listeners must vote for skip. If SkipsRequired is lower it will be used instead.  
<strong>Default Value:</strong> <code>0.5</code>  
</details>  
<details>
  <summary>SaveVideos</summary>

Allow MusicBot to keep downloaded media, or delete it right away.  
<strong>Default Value:</strong> <code>yes</code>  
</details>  
<details>
  <summary>StorageLimitBytes</summary>

If SaveVideos is enabled, set a limit on how much storage space should be used.  
<strong>Default Value:</strong> <code>0.000 B</code>  
</details>  
<details>
  <summary>StorageLimitDays</summary>

If SaveVideos is enabled, set a limit on how long files should be kept.  
<strong>Default Value:</strong> <code>0</code>  
</details>  
<details>
  <summary>StorageRetainAutoPlay</summary>

If SaveVideos is enabled, never purge auto playlist songs from the cache.  
<strong>Default Value:</strong> <code>yes</code>  
</details>  
<details>
  <summary>NowPlayingMentions</summary>

Mention the user who added the song when it is played.  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>AutoSummon</summary>

Automatically join the owner if they are in an accessible voice channel when bot starts.  
<strong>Default Value:</strong> <code>yes</code>  
</details>  
<details>
  <summary>UseAutoPlaylist</summary>

Enable MusicBot to automatically play music from the autoplaylist.txt  
<strong>Default Value:</strong> <code>yes</code>  
</details>  
<details>
  <summary>AutoPlaylistRandom</summary>

Shuffles the autoplaylist tracks before playing them.  
<strong>Default Value:</strong> <code>yes</code>  
</details>  
<details>
  <summary>AutoPlaylistAutoSkip</summary>

Enable automatic skip of auto-playlist songs when a user plays a new song.
This only applies to the current playing song if it was added by the auto-playlist.  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>AutoPlaylistRemoveBlocked</summary>

Remove songs from the auto-playlist if they are found in the song blocklist.  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>AutoPause</summary>

MusicBot will automatically pause playback when no users are listening.  
<strong>Default Value:</strong> <code>yes</code>  
</details>  
<details>
  <summary>DeleteMessages</summary>

Allow MusicBot to automatically delete messages it sends, after a short delay.  
<strong>Default Value:</strong> <code>yes</code>  
</details>  
<details>
  <summary>DeleteInvoking</summary>

Auto delete valid commands after a short delay.  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>PersistentQueue</summary>

Allow MusicBot to save the song queue, so they will survive restarts.  
<strong>Default Value:</strong> <code>yes</code>  
</details>  
<details>
  <summary>PreDownloadNextSong</summary>

Enable MusicBot to download the next song in the queue while a song is playing.
Currently this option does not apply to auto-playlist or songs added to an empty queue.  
<strong>Default Value:</strong> <code>yes</code>  
</details>  
<details>
  <summary>StatusMessage</summary>

Specify a custom message to use as the bot's status. If left empty, the bot
will display dynamic info about music currently being played in its status instead.
Status messages may also use the following variables:
 {n_playing}   = Number of currently Playing music players.
 {n_paused}    = Number of currently Paused music players.
 {n_connected} = Number of connected music players, in any player state.

The following variables give access to information about the player and track.
These variables may not be accurate in multi-guild bots:
 {p0_length}   = The total duration of the track, if available. Ex: [2:34]
 {p0_title}    = The track title for the currently playing track.
 {p0_url}      = The track url for the currently playing track.  
<strong>Default Value:</strong> <i>*empty*</i>  
</details>  
<details>
  <summary>StatusIncludePaused</summary>

If enabled, status messages will report info on paused players.  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>WriteCurrentSong</summary>

If enabled, MusicBot will save the track title to:  data/{server_ID}/current.txt  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>AllowAuthorSkip</summary>

Allow the member who requested the song to skip it, bypassing votes.  
<strong>Default Value:</strong> <code>yes</code>  
</details>  
<details>
  <summary>UseExperimentalEqualization</summary>

Tries to use ffmpeg to get volume normalizing options for use in playback.  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>UseEmbeds</summary>

Allow MusicBot to format it's messages as embeds.  
<strong>Default Value:</strong> <code>yes</code>  
</details>  
<details>
  <summary>QueueLength</summary>

The number of entries to show per-page when using q command to list the queue.  
<strong>Default Value:</strong> <code>10</code>  
</details>  
<details>
  <summary>RemoveFromAPOnError</summary>

Enable MusicBot to automatically remove unplayable entries from tha auto playlist.  
<strong>Default Value:</strong> <code>yes</code>  
</details>  
<details>
  <summary>ShowConfigOnLaunch</summary>

Display MusicBot config settings in the logs at startup.  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>LegacySkip</summary>

Enable users with the InstaSkip permission to bypass skip voting and force skips.  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>LeaveServersWithoutOwner</summary>

If enabled, MusicBot will leave servers if the owner is not in their member list.  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>UseAlias</summary>

If enabled, MusicBot will allow commands to have multiple names using data in:  config/aliases.json  
<strong>Default Value:</strong> <code>yes</code>  
</details>  
<details>
  <summary>CustomEmbedFooter</summary>

Replace MusicBot name/version in embed footer with custom text. Only applied when UseEmbeds is enabled and it is not blank.  
<strong>Default Value:</strong> <code>Just-Some-Bots/MusicBot (release-250723-943-ge08259b4-modded)</code>  
</details>  
<details>
  <summary>SelfDeafen</summary>

MusicBot will automatically deafen itself when entering a voice channel.  
<strong>Default Value:</strong> <code>yes</code>  
</details>  
<details>
  <summary>LeaveInactiveVC</summary>

If enabled, MusicBot will leave a voice channel when no users are listening, after waiting for a period set in LeaveInactiveVCTimeOut.  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>LeaveInactiveVCTimeOut</summary>

Set a period of time to wait before leaving an inactive voice channel. You can set this to a number of seconds or phrase like:  4 hours  
<strong>Default Value:</strong> <code>0:05:00</code>  
</details>  
<details>
  <summary>LeaveAfterQueueEmpty</summary>

If enabled, MusicBot will leave the channel immediately when the song queue is empty.  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>LeavePlayerInactiveFor</summary>

MusicBot will wait for this period of time before leaving voice channel when player is not playing or is paused. Set to 0 to disable.  
<strong>Default Value:</strong> <code>0:00:00</code>  
</details>  
<details>
  <summary>SearchList</summary>

If enabled, users must indicate search result choices by sending a message instead of using reactions.  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>DefaultSearchResults</summary>

Sets the default number of search results to fetch when using search command without a specific number.  
<strong>Default Value:</strong> <code>3</code>  
</details>  
<details>
  <summary>EnablePrefixPerGuild</summary>

Allow MusicBot to save a per-server command prefix, and enables setprefix command.  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>RoundRobinQueue</summary>

If enabled and multiple members are adding songs, MusicBot will organize playback for one song per member.  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>EnableNetworkChecker</summary>

Allow MusicBot to use system ping command to detect network outage and availability.
This is useful if you keep the bot joined to a channel or playing music 24/7.
MusicBot must be restarted to enable network testing.
By default this is disabled.  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>SavePlayedHistoryGlobal</summary>

Enable saving all songs played by MusicBot to a playlist, history.txt  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>SavePlayedHistoryGuilds</summary>

Enable saving songs played per-guild/server to a playlist, history-{guild_id}.txt  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>EnableLocalMedia</summary>

Enable playback of local media files using the play command.
When enabled, users can use:  'play file://path/to/file.ext'
to play files from the local MediaFileDirectory path.  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>UnpausePlayerOnPlay</summary>

Allow MusicBot to automatically unpause when play commands are used.  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>YtdlpProxy</summary>

Experimental, HTTP/HTTPS proxy settings to use with ytdlp media downloader.
The value set here is passed to 'ytdlp --proxy' and aiohttp header checking.
Leave blank to disable.  
<strong>Default Value:</strong> <i>*empty*</i>  
</details>  
<details>
  <summary>YtdlpUserAgent</summary>

Experimental option to set a static User-Agent header in yt-dlp.
It is not typically recommended by yt-dlp to change the UA string.
For examples of what you might put here, check the following two links:
   https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/User-Agent 
   https://www.useragents.me/ 
Leave blank to use default, dynamically generated UA strings.  
<strong>Default Value:</strong> <i>*empty*</i>  
</details>  
<details>
  <summary>YtdlpUseOAuth2</summary>

Experimental option to enable yt-dlp to use a YouTube account via OAuth2.
When enabled, you must use the generated URL and code to authorize an account.
The authorization token is then stored in the 'data//oauth2.token' file.
This option should not be used when cookies are enabled.
Using a personal account may not be recommended.
Set yes to enable or no to disable.  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>YtdlpOAuth2URL</summary>

Optional youtube video URL used at start-up for triggering OAuth2 authorization.
This starts the OAuth2 prompt early, rather than waiting for a song request.
The URL set here should be an accessible youtube video URL.
Authorization must be completed before start-up will continue when this is set.  
<strong>Default Value:</strong> <i>*empty*</i>  
</details>  
<details>
  <summary>EnableUserBlocklist</summary>

Enable the user block list feature, without emptying the block list.  
<strong>Default Value:</strong> <code>yes</code>  
</details>  
<details>
  <summary>EnableSongBlocklist</summary>

Enable the song block list feature, without emptying the block list.  
<strong>Default Value:</strong> <code>no</code>  
</details>  


### [Files]

<details>
  <summary>UserBlocklistFile</summary>

An optional file path to a text file listing Discord User IDs, one per line.  
<strong>Default Value:</strong> <code>config/blocklist_users.txt</code>  
</details>  
<details>
  <summary>SongBlocklistFile</summary>

An optional file path to a text file that lists URLs, words, or phrases one per line.
Any song title or URL that contains any line in the list will be blocked.  
<strong>Default Value:</strong> <code>config/blocklist_songs.txt</code>  
</details>  
<details>
  <summary>AutoPlaylistDirectory</summary>

An optional path to a directory containing auto playlist files.Each file should contain a list of playable URLs or terms, one track per line.  
<strong>Default Value:</strong> <code>config/playlists</code>  
</details>  
<details>
  <summary>MediaFileDirectory</summary>

An optional directory path where playable media files can be stored.
All files and sub-directories can then be accessed by using 'file://' as a protocol.
Example:  file://some/folder/name/file.ext
Maps to:  ./media/some/folder/name/file.ext  
<strong>Default Value:</strong> <code>media</code>  
</details>  
<details>
  <summary>i18nFile</summary>

An optional file path to an i18n language file.
This option may be removed or replaced in the future!  
<strong>Default Value:</strong> <code>config/i18n/en.json</code>  
</details>  
<details>
  <summary>AudioCachePath</summary>

An optional directory path where MusicBot will store long and short-term cache for playback.  
<strong>Default Value:</strong> <code>/home/main/git-repos/MusicBot/audio_cache</code>  
</details>  
<details>
  <summary>LogsMaxKept</summary>

Configure automatic log file rotation at restart, and limit the number of files kept.
When disabled, only one log is kept and its contents are replaced each run.
Default is 0, or disabled.  Maximum allowed number is 100.  
<strong>Default Value:</strong> <code>0</code>  
</details>  
<details>
  <summary>LogsDateFormat</summary>

Configure the log file date format used when LogsMaxKept is enabled.
If left blank, a warning is logged and the default will be used instead.
Learn more about time format codes from the tables and data here:
    https://docs.python.org/3/library/datetime.html#strftime-strptime-behavior
Default value is:  .ended-%Y-%j-%H%m%S  
<strong>Default Value:</strong> <code>.ended-%Y-%j-%H%m%S</code>  
</details>  






---

#### Credentials

<img class="doc-img" src="{{ site.baseurl }}/images/token.png" alt="Token" style="width: 500px;"/>

- `Token` - *This is the only required option for your bot to run.* You must provide the token for your Discord bot account. To create a bot account, go to your [applications page](https://discord.com/developers/applications/me) (logging in if prompted), and then follow this [10 second video](https://drive.google.com/file/d/1wZG_TBVfjQfj0CEYaRTzS60D-cbfeeYZ/view). If you followed it entirely, you should have revealed your token and can now copy it into the config file.

Please note that MusicBot requires privileged intents to function. You need to enable each of the Gateway Intents on your [Discord Application](https://discord.com/developers/applications)'s 'Bot' page.

<img class="doc-img" src="{{ site.baseurl }}/images/intents.png" alt="Intents" style="width: 500px;"/>

After creating a bot account, you should probably add your bot to a server by clicking the 'Generate OAuth2 URL' button on the application page and copying the URL in the box to your address bar and pressing enter. You can then select what server you wish to add it to.
{: .info }

- `Spotify_ClientID` - The client ID for your Spotify application. Required for the bot's [Spotify integration]({{ site.baseurl }}/using/spotify).
- `Spotify_ClientSecret` - The client secret for your Spotify applicaton. Required for the bot's [Spotify integration]({{ site.baseurl }}/using/spotify).

#### Permissions

> This section is about the config options in options.ini. For help with the actual permissions file, see [here]({{ site.baseurl }}/using/permissions).

- `OwnerID` - The ID of your Discord user, who will gain full permissions for the bot. If this is set to `auto`, the bot will automatically determine its owner from who created the bot account
- `DevIDs` - The IDs of every Discord user that you would like to gain developer commands. These commands are dangerous and allow execution of arbitrary code. If you don't know what you're doing, don't add any IDs here

#### Chat

- `CommandPrefix` - The prefix that will be used before every command, e.g if my prefix is `!`, I would use `!play` to queue a song
- `BindToChannels` - You can enter text channel IDs in here (seperated by spaces) to only allow the bot to respond in those channels
- `AutojoinChannels` - You can enter voice channel IDs in here (seperated by spaces) to force the bot to join those channels on launch (one per server)

#### MusicBot

- `DefaultVolume` - The volume that your bot starts at when launched, between `0.01` and `1.0`. Recommended: `0.15`
- <span class="badge warn">deprecated</span> `WhiteListCheck` - If enabled, the bot can only be used by users whose IDs are in `whitelist.txt`.
- `SkipsRequired` & `SkipsRatio` - The required amount/ratio of votes to skip before skipping. The lower value of the two is used. Deafened users and the owner does not count towards the ratio
- `SaveVideos` - Whether videos should be saved to the disk for if they are queued again. If you care about disk space, keep this disabled
- `NowPlayingMentions` - Whether to mention the user that requested a song when their song starts playing
- `AutoSummon` - Whether the bot should automatically connect to the owner's voice channel on startup. This takes precendence over `AutojoinChannels`
- `UseAutoPlaylist` - Whether to play music from `autoplaylist.txt` when joining a voice channel and when nothing is queued
- `AutoPlaylistRandom` - Whether the autoplaylist should play music randomly or sequentially when it is enabled
- `AutoPause` - Whether the bot should pause if nobody is in the voice channel
- `DeleteMessages` - Whether the bot should delete its messages after a short period of time
- `DeleteInvoking` - Whether the bot should delete user command messages after a short period of time. `DeleteMessages` must be enabled for this to work too
- `PersistentQueue` - Whether the bot should save the queue to the disk regularly so it can recover if it is unexpectedly shutdown
- `DebugLevel` - Determines what messages are logged. This is generally not needed to be changed unless you are asked to do so when receiving support
- `StatusMessage` - Allows users to specify a custom "Playing" status message for the bot, rather than the dynamic ones the bot provides
- `WriteCurrentSong` - Whether the bot should write the current song to a text file on the disk, which can then be used in OBS or other software
- `AllowAuthorSkip` - Whether the person who queues a song should be allowed to instantly skip it if they use `!skip f`
- `UseExperimentalEqualization` - Whether the bot should try to equalize tracks to ensure they play at a consistent volume
- `UseEmbeds` - Whether the bot should use Discord embeds when sending messages
- `QueueLength` - How many songs should appear in the `queue` command
- `RemoveFromAPOnError` - Whether the bot should remove songs from the autoplaylist if there is an error
- `ShowConfigOnLaunch` - Whether the bot should print the configuration options when it starts
- `LegacySkip` - Whether to use legacy skip behavior, defaulting `!skip` to force skip
- `LeaveServersWithoutOwner` - Whether the bot should leave servers that the owner is not found in
- `UseAlias` - Whether the bot should use aliases defined in `aliases.json`
- `CustomEmbedFooter` - Changes the footer text found in embeds from the default version footer

#### Files

- `i18nFile` - The internationalization file to use for the bot (relative path, e.g `config/i18n/en.json`)
