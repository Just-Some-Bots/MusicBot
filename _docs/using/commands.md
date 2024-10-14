---
title: Commands
category: Using the bot
order: 3
---

This is a list of the commands that can be used to control the MusicBot. You cannot use commands in private messages. Every command starts with the prefix that you [configured]({{ site.baseurl }}/using/configuration). This page assumes your prefix is `!`, the default. Required parameters are indicated with `<` and `>`, while optional parameters are indicated with `[` and `]`.

#### General

- `!help [command]` - Prints a list of commands, or info on a command if one is specified.
- `!play <URL/query>` - Plays audio from a specific URL or searches for a query on YouTube and queues the first result.
- `!playnext <URL/query>` - Adds a song to the top of the queue to be played immediatly after what's already playing.
- `!shuffleplay <URL>` - Adds a playlist and shuffles it before playback begins. 
- `!playnow <URL/query>` - Skips the currently playing track and starts playback of requested song immediately.
- `!queue` - Displays all of the media that is queued.
- `!np` - Displays the media that is currently being played.
- `!skip` - Vote to skip the current media. Required skips/skip ratio is set in the config file. The bot's owner will instantly skip when using `!skip f`.
- `!search [service] [#] <query>` - Searches a specific service (default: YT) for a query and returns the first few results (default: 3, limit: 10). The user can then select from the results if they want to add any to the queue.
- `!shuffle` - Shuffles the queue.
- `!clear` - Clears the queue.
- `!pause` - Pauses the current media.
- `!resume` - Resumes the current media
- `!volume [number]` - Sets the volume of the bot for everyone. Should be a number between 1 and 100. Can be relative (e.g `+10` to add 10 to current volume). If no parameter is given, it will display the current volume.
- `!summon` - Connects the bot to your current voice channel, if it has permission.
- `!clean <number>` - Searches through the number of messages given and deletes those that were sent by the bot, effectively cleaning the channel. If the bot has `Manage Messages` on the server, it will delete user command messages too, like `!play`.
- <span class="badge warn">deprecated</span> `!id [@user]` - Prints the user's ID in the chat, or prints the ID of the specified user. User must be @mentioned if not yourself.
- <span class="badge warn">deprecated</span> `!listids` - Sends a message to the user with a list of all of the IDs on the server, so that permissions and such can be configured.
- `!perms` - Sends a message to the user with their bot permissions.
- `!stream <url>` - Streams a URL. This can be a Twitch, YouTube, etc livestream, or a radio stream. This feature of the bot is experimental and may have some issues.
- `!save` - Saves the current song to the autoplaylist.
- `!karaoke` - Enables karaoke mode in a server. During karaoke mode, only users with the `BypassKaraokeMode` permission can queue music.
- `!autoplaylist [+, -, add, remove] [show] [set] [URL]` - Manipulate the autoplaylist file, or set a playlist file to be used for the guild.
- `!latency` - Displays the latency between the bot and discord, and the latency in the server voice region.
- `!disconnect` - Disconnects the bot from the voice channel.
- `!follow [@user1]` - Follow a user around the guild VC's. The owner can set who to follow. 
- `!move <number number>` - Move an entry from a spot in the queue to another.
- `!seek <time>` - Seek to a certain spot of the current entry. 
- `!speed <rate>` - Applies a playback speed to the currently playing entry. 
- `!uptime` - Displays the bot uptime since last start or restart. 
A `subject` may be a song URL or a word or phrase found in the track title.
If `subject` is omitted, a currently playing track will be used instead.
- `!repeat [all | playlist | song | on | off]` -   Toggles playlist or song looping.
If no option is provided the bot will toggle through song repeating, playlist repeating, or off.
- `!botversion` - Prints the current bot version to chat.


#### Admin

- `!joinserver` - Provides the URL that can be used to add the bot to another server. This command is always restricted to the owner of the bot.
- `!leaveserver <name/id>` - Forces the bot to leave a server. You must specify either the server name or id.
- `!pldump <playlist>` - Collects URLs from a YouTube playlist or Soundcloud set and dumps them into a text file that can be copied into the autoplaylist.
- `!setavatar [url]` - Changes the bot's avatar to the specified URL or uploaded image. A URL does not need to be specified if an image is uploaded with the command as the message (comment).
- `!setname <name>` - Changes the bot's Discord username (not nickname). Discord limits these changes to 2/hr.
- `!setnick <nick>` - Changes the bot's nickname on a server, if it has permission to do so.
- `!setperms [list, reload, add, remove, help, show, save, set]` - Allows numerous operations of modification to the current permissions config.
- `setprefix <prefix>` - Set the bot prefix for the guild.
- `!restart [soft, full, uppip, upgit, upgrade]` - Restarts the bot with various options. Soft is used by default if no option is provided.
Uppip will check for pip packages to update then restart fully, upgit will check for updates on the repo, attempt to pull them and then restart fully, upgrade will attemp to
update the bot and pip packages then restart fully.
- `!shutdown` - Shuts down the bot and terminates the process.
- `!option <option> <y/n>` - Changes a config option without restarting the bot for the current session. Run `!help option` for info.
- `!remove <number>` - Removes a song from the queue by its numbered position. Use `!queue` to find out song positions.
- `!resetplaylist` - Resets all songs in the server's autoplaylist.
- `!config [diff, missing, list, help, show, save, set]` - Allows numerous operations of modification to the current config options.
- `!blocksong [+, -, add, remove] <subject>` - Manage a block list applied to song requests and extracted info.
- `!blockuser [+, -, add, remove, ?, status] <@user1>` - Manage users in the block list.
Blocked users are forbidden from using all bot commands.
- `!checkupdates` - Display the current bot version and check for updates to MusicBot or dependencies.
The option `GitUpdatesBranch` must be set to check for updates to MusicBot.
- `!botlatency` -  Prints latency info for all voice clients as well as API latency.


#### Dev

> These commands are intended for people who know how Python works and/or developers of the bot. As such, they are restricted behind additional permissions that must be granted in the options file. Please do not run any of these commands unless you are absolutely sure that you are aware what you are doing and the potential consequences, as they can be very dangerous.

- `!breakpoint` - Activates a debugging breakpoint.
- `!objgraph [func]` - Returns an object graph.
- `!debug` - Evaluates arbitrary code. This can be an extremely dangerous command.

---


# Command List  

<details>
  <summary>autoplaylist</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_autoplaylist <add | remove> [URL]<br>
    Adds or removes the specified song or currently playing song to/from the current playlist.<br>
<br>
cmd_autoplaylist add all<br>
    Adds the entire queue to the guilds playlist.<br>
<br>
cmd_autoplaylist show<br>
    Show a list of existing playlist files.<br>
<br>
cmd_autoplaylist restart<br>
    Reset the auto playlist queue, restarting at the first track unless randomized.<br>
<br>
cmd_autoplaylist set <NAME><br>
    Set a playlist as default for this guild and reloads the guild auto playlist.<br>

{% endhighlight %}<strong>Description:<strong><br>  
Manage auto playlist files and per-guild settings.
</details>

<details>
  <summary>blocksong</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_blocksong <add | remove> [SUBJECT]<br>

{% endhighlight %}<strong>Description:<strong><br>  
Manage a block list applied to song requests and extracted song data.<br>
A subject may be a song URL or a word or phrase found in the track title.<br>
If subject is omitted, any currently playing track URL will be added instead.<br>
<br>
The song block list matches loosely, but is case-sensitive.<br>
This means adding 'Pie' will match 'cherry Pie' but not 'piecrust' in checks.<br>

</details>

<details>
  <summary>blockuser</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_blockuser add <@USER><br>
    Block a mentioned user.<br>
cmd_blockuser remove <@USER><br>
    Unblock a mentioned user.<br>
cmd_blockuser status <@USER><br>
    Show the block status of a mentioned user.
{% endhighlight %}<strong>Description:<strong><br>  
Manage the users in the user block list.<br>
Blocked users are forbidden from using all bot commands.<br>

</details>

<details>
  <summary>botversion</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_botversion
{% endhighlight %}<strong>Description:<strong><br>  
Display MusicBot version number in the chat.
</details>

<details>
  <summary>clean</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_clean [RANGE]
{% endhighlight %}<strong>Description:<strong><br>  
Search for and remove bot messages and commands from the calling text channel.<br>
Optionally supply a number of messages to search through, 50 by default 500 max.<br>
This command may be slow if larger ranges are given.<br>

</details>

<details>
  <summary>clear</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_clear
{% endhighlight %}<strong>Description:<strong><br>  
Removes all songs currently in the queue.
</details>

<details>
  <summary>disconnect</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_disconnect
{% endhighlight %}<strong>Description:<strong><br>  
Force MusicBot to disconnect from the discord server.
</details>

<details>
  <summary>follow</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_follow
{% endhighlight %}<strong>Description:<strong><br>  
Makes MusicBot follow a user when they change channels in a server.<br>

</details>

<details>
  <summary>help</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_help [COMMAND]
{% endhighlight %}<strong>Description:<strong><br>  
Show usage and description of a command, or list all available commands.<br>

</details>

<details>
  <summary>id</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_id [@USER]
{% endhighlight %}<strong>Description:<strong><br>  
Display your Discord User ID, or the ID of a mentioned user.<br>
This command is deprecated in favor of Developer Mode in Discord clients.<br>

</details>

<details>
  <summary>karaoke</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_karaoke
{% endhighlight %}<strong>Description:<strong><br>  
Toggle karaoke mode on or off. While enabled, only karaoke members may queue songs.<br>
Groups with BypassKaraokeMode permission control which members are Karaoke members.<br>

</details>

<details>
  <summary>latency</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_latency
{% endhighlight %}<strong>Description:<strong><br>  
Display API latency and Voice latency if MusicBot is connected.
</details>

<details>
  <summary>leaveserver</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_leaveserver <NAME | ID><br>
   Leave the discord server given by name or server ID.
{% endhighlight %}<strong>Description:<strong><br>  
Force MusicBot to leave the given Discord server.<br>
Names are case-sensitive, so using an ID number is more reliable.<br>

</details>

<details>
  <summary>listids</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_listids [all | users | roles | channels]
{% endhighlight %}<strong>Description:<strong><br>  
List the Discord IDs for the selected category.<br>
Returns all ID data by default, but one or more categories may be selected.<br>
This command is deprecated in favor of using Developer mode in Discord clients.<br>

</details>

<details>
  <summary>move</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_move <FROM> <TO><br>
    Move song at position FROM to position TO.<br>

{% endhighlight %}<strong>Description:<strong><br>  
Swap existing songs in the queue using their position numbers.<br>
Use the queue command to find track position numbers.<br>

</details>

<details>
  <summary>np</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_np
{% endhighlight %}<strong>Description:<strong><br>  
Show information on what is currently playing.
</details>

<details>
  <summary>pause</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_pause
{% endhighlight %}<strong>Description:<strong><br>  
Pause playback if a track is currently playing.
</details>

<details>
  <summary>perms</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_perms [@USER]
{% endhighlight %}<strong>Description:<strong><br>  
Get a list of your permissions, or the permisions of the mentioned user.
</details>

<details>
  <summary>play</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_play <URL | SEARCH>
{% endhighlight %}<strong>Description:<strong><br>  
Add a song to be played in the queue. If no song is playing or paused, playback will be started.<br>
<br>
You may supply a URL to a video or audio file or the URL of a service supported by yt-dlp.<br>
Playlist links will be extracted into multiple links and added to the queue.<br>
If you enter a non-URL, the input will be used as search criteria on youtube and the first result played.<br>
MusicBot also supports Spotify URIs and URLs, but audio is fetched from youtube regardless.<br>

</details>

<details>
  <summary>playnext</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_playnext <URL | SEARCH>
{% endhighlight %}<strong>Description:<strong><br>  
A play command that adds the song as the next to play rather than last.<br>
Read help for the play command for information on supported inputs.<br>

</details>

<details>
  <summary>playnow</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_playnow <URL | SEARCH>
{% endhighlight %}<strong>Description:<strong><br>  
A play command which skips any current song and plays immediately.<br>
Read help for the play command for information on supported inputs.<br>

</details>

<details>
  <summary>pldump</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_pldump <URL>
{% endhighlight %}<strong>Description:<strong><br>  
Dump the individual urls of a playlist to a file.
</details>

<details>
  <summary>queue</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_queue [PAGE]
{% endhighlight %}<strong>Description:<strong><br>  
Display information about the current player queue.<br>
Optional page number shows later entries in the queue.<br>

</details>

<details>
  <summary>remove</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_remove [POSITION]
{% endhighlight %}<strong>Description:<strong><br>  
Remove a song from the queue, optionally at the given queue position.<br>
If the position is omitted, the song at the end of the queue is removed.<br>
Use the queue command to find position number of your track.<br>
However, positions of all songs are changed when a new song starts playing.<br>

</details>

<details>
  <summary>repeat</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_repeat [all | song | playlist | on | off]
{% endhighlight %}<strong>Description:<strong><br>  
Toggles playlist or song looping.<br>
If no option is provided the current song will be repeated.<br>
If no option is provided and the song is already repeating, repeating will be turned off.<br>

</details>

<details>
  <summary>resetplaylist</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_resetplaylist
{% endhighlight %}<strong>Description:<strong><br>  
Reset the auto playlist queue by copying it back into player memory.<br>
This command will be removed in a future version, replaced by the autoplaylist command(s).
</details>

<details>
  <summary>restart</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_restart [soft]<br>
    Attempt to reload without process restart. The default option.<br>
<br>
cmd_restart full<br>
    Attempt to restart the entire MusicBot process, reloading everything.<br>
<br>
cmd_restart uppip<br>
    Full restart, but attempt to update pip packages before restart.<br>
<br>
cmd_restart upgit<br>
    Full restart, but update MusicBot source code with git first.<br>
<br>
cmd_restart upgrade<br>
    Attempt to update all dependency and source code before fully restarting.<br>

{% endhighlight %}<strong>Description:<strong><br>  
Attempts to restart the MusicBot in a number of different ways.<br>
With no option supplied, a `soft` restart is implied.<br>
It can be used to remotely update a MusicBot installation, but should be used with care.<br>
If you have a service manager, we recommend using it instead of this command for restarts.<br>

</details>

<details>
  <summary>resume</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_resume
{% endhighlight %}<strong>Description:<strong><br>  
Resumes playback if the player was previously paused.
</details>

<details>
  <summary>search</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
No usage given.
{% endhighlight %}<strong>Description:<strong><br>  
No description given.
</details>

<details>
  <summary>seek</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_seek <TIME>
{% endhighlight %}<strong>Description:<strong><br>  
Restarts the current song at the given time.<br>
If time starts with + or - seek will be relative to current playback time.<br>
Time should be given in seconds, fractional seconds are accepted.<br>
Due to codec specifics in ffmpeg, this may not be accurate.<br>

</details>

<details>
  <summary>setnick</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_setnick <NICK>
{% endhighlight %}<strong>Description:<strong><br>  
Change the MusicBot's nickname.
</details>

<details>
  <summary>setprefix</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_setprefix <PREFIX>
{% endhighlight %}<strong>Description:<strong><br>  
Override the default command prefix in the server.<br>
The option EnablePrefixPerGuild must be enabled first.
</details>

<details>
  <summary>shuffle</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_shuffle
{% endhighlight %}<strong>Description:<strong><br>  
Shuffle all current tracks in the queue.
</details>

<details>
  <summary>shuffleplay</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_shuffleplay [URL]
{% endhighlight %}<strong>Description:<strong><br>  
Play command that shuffles playlist entries before adding them to the queue.<br>

</details>

<details>
  <summary>shutdown</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_shutdown
{% endhighlight %}<strong>Description:<strong><br>  
Disconnect from all voice channels and close the MusicBot process.
</details>

<details>
  <summary>skip</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_skip [force | f]
{% endhighlight %}<strong>Description:<strong><br>  
Skip or vote to skip the current playing song.<br>
Members with InstaSkip permission may use force parameter to bypass voting.<br>
If LegacySkip option is enabled, the force parameter can be ignored.<br>

</details>

<details>
  <summary>speed</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_speed [RATE]
{% endhighlight %}<strong>Description:<strong><br>  
Change the playback speed of the currently playing track only.<br>
The rate must be between 0.5 and 100.0 due to ffmpeg limits.<br>
Streaming playback does not support speed adjustments.<br>

</details>

<details>
  <summary>stream</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_stream <URL>
{% endhighlight %}<strong>Description:<strong><br>  
Add a media URL to the queue as a Stream.<br>
The URL may be actual streaming media, like Twitch, Youtube, or a shoutcast like service.<br>
You can also use non-streamed media to play it without downloading it.<br>
Note: FFmpeg may drop the stream randomly or if connection hiccups happen.<br>

</details>

<details>
  <summary>summon</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_summon
{% endhighlight %}<strong>Description:<strong><br>  
Tell MusicBot to join the channel you're in.
</details>

<details>
  <summary>uptime</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_uptime
{% endhighlight %}<strong>Description:<strong><br>  
Displays the MusicBot uptime, or time since last start / restart.
</details>

<details>
  <summary>volume</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_volume [VOLUME]
{% endhighlight %}<strong>Description:<strong><br>  
Set the output volume level of MusicBot from 1 to 100.<br>
Volume parameter allows a leading + or - for relative adjustments.<br>
The volume setting is retained until MusicBot is restarted.<br>

</details>

# Admin Commands  

<details>
  <summary>botlatency</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_botlatency
{% endhighlight %}<strong>Description:<strong><br>  
Display latency information for Discord API and all connected voice clients.
</details>

<details>
  <summary>cache</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_cache <info | clear | update>
{% endhighlight %}<strong>Description:<strong><br>  
Display information about cache storage or clear cache according to configured limits.<br>
Using update option will scan the cache for external changes before displaying details.
</details>

<details>
  <summary>checkupdates</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_checkupdates
{% endhighlight %}<strong>Description:<strong><br>  
Display the current bot version and check for updates to MusicBot or dependencies.<br>

</details>

<details>
  <summary>config</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_config missing<br>
    Shows help text about any missing config options.<br>
<br>
cmd_config diff<br>
    Lists the names of options which have been changed since loading config file.<br>
<br>
cmd_config list<br>
    List the available config options and their sections.<br>
<br>
cmd_config reload<br>
    Reload the options.ini file from disk.<br>
<br>
cmd_config help <SECTION> <OPTION><br>
    Shows help text for a specific option.<br>
<br>
cmd_config show <SECTION> <OPTION><br>
    Display the current value of the option.<br>
<br>
cmd_config save <SECTION> <OPTION><br>
    Saves the current current value to the options file.<br>
<br>
cmd_config set <SECTION> <OPTION> <VALUE><br>
    Validates the option and sets the config for the session, but not to file.<br>
<br>
cmd_config reset <SECTION> <OPTION><br>
    Reset the option to it's default value.<br>

{% endhighlight %}<strong>Description:<strong><br>  
Manage options.ini configuration from within Discord.
</details>

<details>
  <summary>joinserver</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_joinserver
{% endhighlight %}<strong>Description:<strong><br>  
Generate an invite link that can be used to add this bot to another server.
</details>

<details>
  <summary>option</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_option
{% endhighlight %}<strong>Description:<strong><br>  
Deprecated command, use the config command instead.
</details>

<details>
  <summary>setalias</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_setalias + <ALIAS> <CMD> [ARGS]<br>
    Add an new alias with optional arguments.<br>
<br>
cmd_setalias - <ALIAS><br>
    Remove an alias with the given name.<br>
cmd_setalias <save | load><br>
    Reload or save aliases from/to the config file.
{% endhighlight %}<strong>Description:<strong><br>  
Allows management of aliases from discord. To see aliases use the help command.
</details>

<details>
  <summary>setavatar</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_setavatar [URL]
{% endhighlight %}<strong>Description:<strong><br>  
Change MusicBot's avatar.<br>
Attaching a file and omitting the url parameter also works.<br>

</details>

<details>
  <summary>setcookies</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_setcookies<br>
    Update the cookies.txt file using a cookies.txt attachment.<br>
cmd_setcookies [off | on]<br>
    Enable or disable cookies.txt file without deleting it.
{% endhighlight %}<strong>Description:<strong><br>  
Allows management of the cookies feature in yt-dlp.<br>
When updating cookies, you must upload a file named cookies.txt<br>
If cookies are disabled, uploading will enable the feature.<br>
Uploads will delete existing cookies, including disabled cookies file.<br>
<br>
WARNING:<br>
  Copying cookies can risk exposing your personal information or accounts,<br>
  and may result in account bans or theft if you are not careful.<br>
  It is not recommended due to these risks, and you should not use this<br>
  feature if you do not understand how to avoid the risks.
</details>

<details>
  <summary>setname</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_setname <NAME>
{% endhighlight %}<strong>Description:<strong><br>  
Change the bot's username on discord.Note: The API may limit name changes to twice per hour.
</details>

<details>
  <summary>setperms</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_setperms list<br>
    Show loaded groups and list permission options.<br>
<br>
cmd_setperms reload<br>
    Reloads permissions from the permissions.ini file.<br>
<br>
cmd_setperms add <GROUP><br>
    Add new group with defaults.<br>
<br>
cmd_setperms remove <GROUP><br>
    Remove existing group.<br>
<br>
cmd_setperms help <PERMISSION><br>
    Show help text for the permission option.<br>
<br>
cmd_setperms show <GROUP> <PERMISSION><br>
    Show permission value for given group and permission.<br>
<br>
cmd_setperms save <GROUP><br>
    Save permissions group to file.<br>
<br>
cmd_setperms set <GROUP> <PERMISSION> [VALUE]<br>
    Set permission value for the group.<br>

{% endhighlight %}<strong>Description:<strong><br>  
Manage permissions.ini configuration from within discord.
</details>

# Dev Commands  

<details>
  <summary>breakpoint</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_breakpoint
{% endhighlight %}<strong>Description:<strong><br>  
This command issues a log at level CRITICAL, but does nothing else.<br>
Can be used to manually pin-point events in the MusicBot log file.<br>

</details>

<details>
  <summary>debug</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_debug [PYCODE]<br>

{% endhighlight %}<strong>Description:<strong><br>  
This command will execute arbitrary python code in the command scope.<br>
First eval() is attempted, if exceptions are thrown exec() is tried next.<br>
If eval is successful, it's return value is displayed.<br>
If exec is successful, a value can be set to local variable `result` and that value will be returned.<br>
<br>
Multi-line code can be executed if wrapped in code-block.<br>
Otherwise only a single line may be executed.<br>
<br>
This command may be removed in a future version, and is used by developers to debug MusicBot behaviour.<br>
The danger of this command cannot be understated. Do not use it or give access to it if you do not understand the risks!<br>

</details>

<details>
  <summary>makemarkdown</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_makemarkdown < opts | perms | help >
{% endhighlight %}<strong>Description:<strong><br>  
Create 'markdown' for options, permissions, or commands from the code.<br>
The output is used to update github pages and is thus unsuitable for normal reference use.
</details>

<details>
  <summary>objgraph</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_objgraph<br>
    View most common types reported by objgraph.<br>
<br>
cmd_objgraph growth<br>
    View limited objgraph.show_growth() output.<br>
<br>
cmd_objgraph leaks<br>
    View most common types of leaking objects.<br>
<br>
cmd_objgraph leakstats<br>
    View typestats of leaking objects.<br>
<br>
cmd_objgraph [objgraph.function(...)]<br>
    Evaluate the given function and args on objgraph.<br>

{% endhighlight %}<strong>Description:<strong><br>  
Interact with objgraph, if it is installed, to gain insight into memory usage.<br>
You can pass an arbitrary method with arguments (but no spaces!) that is a member of objgraph.<br>
Since this method evaluates arbitrary code, it is considered dangerous like the debug command.<br>

</details>

<details>
  <summary>testready</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cmd_testready
{% endhighlight %}<strong>Description:<strong><br>  
Command used for testing. It prints a list of commands which can be verified by a test suite.
</details>

