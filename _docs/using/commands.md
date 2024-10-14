---
title: Commands
category: Using the bot
order: 3
---

This page contains a list of all commands that can be used to control the MusicBot.  
Every command must start with the prefix that is [configured]({{ site.baseurl }}/using/configuration) for your bot.  
The default prefix for MusicBot is `!` but we omit it in this documentation.  

For command usage, MusicBot uses the following rules:  
1. All literal parameters must be lower case and alphanumeric.  
2. All placeholder parameters must be upper case and alphanumeric.  
3. `< >` denotes a required parameter.  
4. `[ ]` denotes an optional parameter.  
5. ` | ` denotes multiple choices for the parameter.  
6. Literal terms may appear without parameter marks.  

---

<a class="expand-all-details">Show/Hide All</a>

### General Command  

<details>
  <summary>autoplaylist</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
autoplaylist <add | remove> [URL]
    Adds or removes the specified song or currently playing song to/from the current playlist.

autoplaylist add all
    Adds the entire queue to the guilds playlist.

autoplaylist show
    Show a list of existing playlist files.

autoplaylist restart
    Reset the auto playlist queue, restarting at the first track unless randomized.

autoplaylist set <NAME>
    Set a playlist as default for this guild and reloads the guild auto playlist.

{% endhighlight %}
<strong>Description:</strong><br>  
Manage auto playlist files and per-guild settings.
</details>

<details>
  <summary>blocksong</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
blocksong <add | remove> [SUBJECT]

{% endhighlight %}
<strong>Description:</strong><br>  
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
blockuser add <@USER>
    Block a mentioned user.
blockuser remove <@USER>
    Unblock a mentioned user.
blockuser status <@USER>
    Show the block status of a mentioned user.
{% endhighlight %}
<strong>Description:</strong><br>  
Manage the users in the user block list.<br>
Blocked users are forbidden from using all bot commands.<br>

</details>

<details>
  <summary>botversion</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
botversion
{% endhighlight %}
<strong>Description:</strong><br>  
Display MusicBot version number in the chat.
</details>

<details>
  <summary>clean</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
clean [RANGE]
{% endhighlight %}
<strong>Description:</strong><br>  
Search for and remove bot messages and commands from the calling text channel.<br>
Optionally supply a number of messages to search through, 50 by default 500 max.<br>
This command may be slow if larger ranges are given.<br>

</details>

<details>
  <summary>clear</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
clear
{% endhighlight %}
<strong>Description:</strong><br>  
Removes all songs currently in the queue.
</details>

<details>
  <summary>disconnect</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
disconnect
{% endhighlight %}
<strong>Description:</strong><br>  
Force MusicBot to disconnect from the discord server.
</details>

<details>
  <summary>follow</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
follow
{% endhighlight %}
<strong>Description:</strong><br>  
Makes MusicBot follow a user when they change channels in a server.<br>

</details>

<details>
  <summary>help</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
help [COMMAND]
{% endhighlight %}
<strong>Description:</strong><br>  
Show usage and description of a command, or list all available commands.<br>

</details>

<details>
  <summary>id</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
id [@USER]
{% endhighlight %}
<strong>Description:</strong><br>  
Display your Discord User ID, or the ID of a mentioned user.<br>
This command is deprecated in favor of Developer Mode in Discord clients.<br>

</details>

<details>
  <summary>karaoke</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
karaoke
{% endhighlight %}
<strong>Description:</strong><br>  
Toggle karaoke mode on or off. While enabled, only karaoke members may queue songs.<br>
Groups with BypassKaraokeMode permission control which members are Karaoke members.<br>

</details>

<details>
  <summary>latency</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
latency
{% endhighlight %}
<strong>Description:</strong><br>  
Display API latency and Voice latency if MusicBot is connected.
</details>

<details>
  <summary>leaveserver</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
leaveserver <NAME | ID>
   Leave the discord server given by name or server ID.
{% endhighlight %}
<strong>Description:</strong><br>  
Force MusicBot to leave the given Discord server.<br>
Names are case-sensitive, so using an ID number is more reliable.<br>

</details>

<details>
  <summary>listids</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
listids [all | users | roles | channels]
{% endhighlight %}
<strong>Description:</strong><br>  
List the Discord IDs for the selected category.<br>
Returns all ID data by default, but one or more categories may be selected.<br>
This command is deprecated in favor of using Developer mode in Discord clients.<br>

</details>

<details>
  <summary>move</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
move <FROM> <TO>
    Move song at position FROM to position TO.

{% endhighlight %}
<strong>Description:</strong><br>  
Swap existing songs in the queue using their position numbers.<br>
Use the queue command to find track position numbers.<br>

</details>

<details>
  <summary>np</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
np
{% endhighlight %}
<strong>Description:</strong><br>  
Show information on what is currently playing.
</details>

<details>
  <summary>pause</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
pause
{% endhighlight %}
<strong>Description:</strong><br>  
Pause playback if a track is currently playing.
</details>

<details>
  <summary>perms</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
perms [@USER]
{% endhighlight %}
<strong>Description:</strong><br>  
Get a list of your permissions, or the permisions of the mentioned user.
</details>

<details>
  <summary>play</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
play <URL | SEARCH>
{% endhighlight %}
<strong>Description:</strong><br>  
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
playnext <URL | SEARCH>
{% endhighlight %}
<strong>Description:</strong><br>  
A play command that adds the song as the next to play rather than last.<br>
Read help for the play command for information on supported inputs.<br>

</details>

<details>
  <summary>playnow</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
playnow <URL | SEARCH>
{% endhighlight %}
<strong>Description:</strong><br>  
A play command which skips any current song and plays immediately.<br>
Read help for the play command for information on supported inputs.<br>

</details>

<details>
  <summary>pldump</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
pldump <URL>
{% endhighlight %}
<strong>Description:</strong><br>  
Dump the individual urls of a playlist to a file.
</details>

<details>
  <summary>queue</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
queue [PAGE]
{% endhighlight %}
<strong>Description:</strong><br>  
Display information about the current player queue.<br>
Optional page number shows later entries in the queue.<br>

</details>

<details>
  <summary>remove</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
remove [POSITION]
{% endhighlight %}
<strong>Description:</strong><br>  
Remove a song from the queue, optionally at the given queue position.<br>
If the position is omitted, the song at the end of the queue is removed.<br>
Use the queue command to find position number of your track.<br>
However, positions of all songs are changed when a new song starts playing.<br>

</details>

<details>
  <summary>repeat</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
repeat [all | song | playlist | on | off]
{% endhighlight %}
<strong>Description:</strong><br>  
Toggles playlist or song looping.<br>
If no option is provided the current song will be repeated.<br>
If no option is provided and the song is already repeating, repeating will be turned off.<br>

</details>

<details>
  <summary>resetplaylist</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
resetplaylist
{% endhighlight %}
<strong>Description:</strong><br>  
Reset the auto playlist queue by copying it back into player memory.<br>
This command will be removed in a future version, replaced by the autoplaylist command(s).
</details>

<details>
  <summary>restart</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
restart [soft]
    Attempt to reload without process restart. The default option.

restart full
    Attempt to restart the entire MusicBot process, reloading everything.

restart uppip
    Full restart, but attempt to update pip packages before restart.

restart upgit
    Full restart, but update MusicBot source code with git first.

restart upgrade
    Attempt to update all dependency and source code before fully restarting.

{% endhighlight %}
<strong>Description:</strong><br>  
Attempts to restart the MusicBot in a number of different ways.<br>
With no option supplied, a `soft` restart is implied.<br>
It can be used to remotely update a MusicBot installation, but should be used with care.<br>
If you have a service manager, we recommend using it instead of this command for restarts.<br>

</details>

<details>
  <summary>resume</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
resume
{% endhighlight %}
<strong>Description:</strong><br>  
Resumes playback if the player was previously paused.
</details>

<details>
  <summary>search</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
search [SERVICE] [NUMBER] <QUERY>
    Search with service for a number of results with the search query.

search [NUMBER] "<QUERY>"
    Search youtube for query but get a custom number of results.
    Note: the double-quotes are required in this case.

{% endhighlight %}
<strong>Description:</strong><br>  
Search a supported service and select from results to add to queue.<br>
Service and number arguments can be omitted, default number is 3 results.<br>
Select from these services:<br>
- yt, youtube (default)<br>
- sc, soundcloud<br>
- yh, yahoo<br>

</details>

<details>
  <summary>seek</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
seek <TIME>
{% endhighlight %}
<strong>Description:</strong><br>  
Restarts the current song at the given time.<br>
If time starts with + or - seek will be relative to current playback time.<br>
Time should be given in seconds, fractional seconds are accepted.<br>
Due to codec specifics in ffmpeg, this may not be accurate.<br>

</details>

<details>
  <summary>setnick</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
setnick <NICK>
{% endhighlight %}
<strong>Description:</strong><br>  
Change the MusicBot's nickname.
</details>

<details>
  <summary>setprefix</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
setprefix <PREFIX>
{% endhighlight %}
<strong>Description:</strong><br>  
Override the default command prefix in the server.<br>
The option EnablePrefixPerGuild must be enabled first.
</details>

<details>
  <summary>shuffle</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
shuffle
{% endhighlight %}
<strong>Description:</strong><br>  
Shuffle all current tracks in the queue.
</details>

<details>
  <summary>shuffleplay</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
shuffleplay [URL]
{% endhighlight %}
<strong>Description:</strong><br>  
Play command that shuffles playlist entries before adding them to the queue.<br>

</details>

<details>
  <summary>shutdown</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
shutdown
{% endhighlight %}
<strong>Description:</strong><br>  
Disconnect from all voice channels and close the MusicBot process.
</details>

<details>
  <summary>skip</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
skip [force | f]
{% endhighlight %}
<strong>Description:</strong><br>  
Skip or vote to skip the current playing song.<br>
Members with InstaSkip permission may use force parameter to bypass voting.<br>
If LegacySkip option is enabled, the force parameter can be ignored.<br>

</details>

<details>
  <summary>speed</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
speed [RATE]
{% endhighlight %}
<strong>Description:</strong><br>  
Change the playback speed of the currently playing track only.<br>
The rate must be between 0.5 and 100.0 due to ffmpeg limits.<br>
Streaming playback does not support speed adjustments.<br>

</details>

<details>
  <summary>stream</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
stream <URL>
{% endhighlight %}
<strong>Description:</strong><br>  
Add a media URL to the queue as a Stream.<br>
The URL may be actual streaming media, like Twitch, Youtube, or a shoutcast like service.<br>
You can also use non-streamed media to play it without downloading it.<br>
Note: FFmpeg may drop the stream randomly or if connection hiccups happen.<br>

</details>

<details>
  <summary>summon</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
summon
{% endhighlight %}
<strong>Description:</strong><br>  
Tell MusicBot to join the channel you're in.
</details>

<details>
  <summary>uptime</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
uptime
{% endhighlight %}
<strong>Description:</strong><br>  
Displays the MusicBot uptime, or time since last start / restart.
</details>

<details>
  <summary>volume</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
volume [VOLUME]
{% endhighlight %}
<strong>Description:</strong><br>  
Set the output volume level of MusicBot from 1 to 100.<br>
Volume parameter allows a leading + or - for relative adjustments.<br>
The volume setting is retained until MusicBot is restarted.<br>

</details>

### Admin Commands  

<details>
  <summary>botlatency</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
botlatency
{% endhighlight %}
<strong>Description:</strong><br>  
Display latency information for Discord API and all connected voice clients.
</details>

<details>
  <summary>cache</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
cache <info | clear | update>
{% endhighlight %}
<strong>Description:</strong><br>  
Display information about cache storage or clear cache according to configured limits.<br>
Using update option will scan the cache for external changes before displaying details.
</details>

<details>
  <summary>checkupdates</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
checkupdates
{% endhighlight %}
<strong>Description:</strong><br>  
Display the current bot version and check for updates to MusicBot or dependencies.<br>

</details>

<details>
  <summary>config</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
config missing
    Shows help text about any missing config options.

config diff
    Lists the names of options which have been changed since loading config file.

config list
    List the available config options and their sections.

config reload
    Reload the options.ini file from disk.

config help <SECTION> <OPTION>
    Shows help text for a specific option.

config show <SECTION> <OPTION>
    Display the current value of the option.

config save <SECTION> <OPTION>
    Saves the current current value to the options file.

config set <SECTION> <OPTION> <VALUE>
    Validates the option and sets the config for the session, but not to file.

config reset <SECTION> <OPTION>
    Reset the option to it's default value.

{% endhighlight %}
<strong>Description:</strong><br>  
Manage options.ini configuration from within Discord.
</details>

<details>
  <summary>joinserver</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
joinserver
{% endhighlight %}
<strong>Description:</strong><br>  
Generate an invite link that can be used to add this bot to another server.
</details>

<details>
  <summary>option</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
option
{% endhighlight %}
<strong>Description:</strong><br>  
Deprecated command, use the config command instead.
</details>

<details>
  <summary>setalias</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
setalias + <ALIAS> <CMD> [ARGS]
    Add an new alias with optional arguments.

setalias - <ALIAS>
    Remove an alias with the given name.
setalias <save | load>
    Reload or save aliases from/to the config file.
{% endhighlight %}
<strong>Description:</strong><br>  
Allows management of aliases from discord. To see aliases use the help command.
</details>

<details>
  <summary>setavatar</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
setavatar [URL]
{% endhighlight %}
<strong>Description:</strong><br>  
Change MusicBot's avatar.<br>
Attaching a file and omitting the url parameter also works.<br>

</details>

<details>
  <summary>setcookies</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
setcookies
    Update the cookies.txt file using a cookies.txt attachment.
setcookies [off | on]
    Enable or disable cookies.txt file without deleting it.
{% endhighlight %}
<strong>Description:</strong><br>  
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
setname <NAME>
{% endhighlight %}
<strong>Description:</strong><br>  
Change the bot's username on discord.Note: The API may limit name changes to twice per hour.
</details>

<details>
  <summary>setperms</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
setperms list
    Show loaded groups and list permission options.

setperms reload
    Reloads permissions from the permissions.ini file.

setperms add <GROUP>
    Add new group with defaults.

setperms remove <GROUP>
    Remove existing group.

setperms help <PERMISSION>
    Show help text for the permission option.

setperms show <GROUP> <PERMISSION>
    Show permission value for given group and permission.

setperms save <GROUP>
    Save permissions group to file.

setperms set <GROUP> <PERMISSION> [VALUE]
    Set permission value for the group.

{% endhighlight %}
<strong>Description:</strong><br>  
Manage permissions.ini configuration from within discord.
</details>

### Dev Commands  

<details>
  <summary>breakpoint</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
breakpoint
{% endhighlight %}
<strong>Description:</strong><br>  
This command issues a log at level CRITICAL, but does nothing else.<br>
Can be used to manually pin-point events in the MusicBot log file.<br>

</details>

<details>
  <summary>debug</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
debug [PYCODE]

{% endhighlight %}
<strong>Description:</strong><br>  
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
makemarkdown < opts | perms | help >
{% endhighlight %}
<strong>Description:</strong><br>  
Create 'markdown' for options, permissions, or commands from the code.<br>
The output is used to update github pages and is thus unsuitable for normal reference use.
</details>

<details>
  <summary>objgraph</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
objgraph
    View most common types reported by objgraph.

objgraph growth
    View limited objgraph.show_growth() output.

objgraph leaks
    View most common types of leaking objects.

objgraph leakstats
    View typestats of leaking objects.

objgraph [objgraph.function(...)]
    Evaluate the given function and args on objgraph.

{% endhighlight %}
<strong>Description:</strong><br>  
Interact with objgraph, if it is installed, to gain insight into memory usage.<br>
You can pass an arbitrary method with arguments (but no spaces!) that is a member of objgraph.<br>
Since this method evaluates arbitrary code, it is considered dangerous like the debug command.<br>

</details>

<details>
  <summary>testready</summary>
<strong>Example usage:</strong><br>  
{% highlight text %}
testready
{% endhighlight %}
<strong>Description:</strong><br>  
Command used for testing. It prints a list of commands which can be verified by a test suite.
</details>

---

<a class="expand-all-details">Show/Hide All</a>
