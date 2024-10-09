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

Usage:
    autoplaylist [+ | - | add | remove] [url]
        Adds or removes the specified song or currently playing song to/from the current playlist.

    autoplaylist [+ all | add all]
        Adds the entire queue to the guilds playlist.

    autoplaylist show
        Show a list of existing playlist files.

    autoplaylist set [playlist.txt]
        Set a playlist as default for this guild and reloads the guild auto playlist.

</details>

<details>
  <summary>blocksong</summary>

Usage:
    blocksong [ + | - | add | remove ] [subject]

Manage a block list applied to song requests and extracted info.
A `subject` may be a song URL or a word or phrase found in the track title.
If `subject` is omitted, a currently playing track will be used instead.

Song block list matches loosely, but is case sensitive.
So adding "Pie" will match "cherry Pie" but not "cherry pie" in checks.

</details>

<details>
  <summary>blockuser</summary>

Usage:
    blockuser [ + | - | ? | add | remove | status ] @UserName [@UserName2 ...]

Manage users in the block list.
Blocked users are forbidden from using all bot commands.

</details>

<details>
  <summary>botversion</summary>

Usage:
    botversion

Prints the current bot version to chat.

</details>

<details>
  <summary>clean</summary>

Usage:
    clean [range]

Removes up to [range] messages the bot has posted in chat. Default: 50, Max: 1000

</details>

<details>
  <summary>clear</summary>

Usage:
    clear

Clears the playlist.

</details>

<details>
  <summary>disconnect</summary>

Usage:
    disconnect

Forces the bot leave the current voice channel.

</details>

<details>
  <summary>follow</summary>

Usage:
    follow

MusicBot will automatically follow a user when they change channels.

</details>

<details>
  <summary>help</summary>

Usage:
    help [command]

Prints a help message.
If a command is specified, it prints a help message for that command.
Otherwise, it lists the available commands.

</details>

<details>
  <summary>id</summary>

Usage:
    id [@user]

Tells the user their id or the id of another user.

</details>

<details>
  <summary>karaoke</summary>

Usage:
    karaoke

Activates karaoke mode. During karaoke mode, only groups with the BypassKaraokeMode
permission in the config file can queue music.

</details>

<details>
  <summary>latency</summary>

Usage:
    latency

Prints the latency info available to MusicBot.
If connected to a voice channel, voice latency is also returned.

</details>

<details>
  <summary>leaveserver</summary>

Usage:
    leaveserver <name/ID>

Forces the bot to leave a server.
When providing names, names are case-sensitive.

</details>

<details>
  <summary>listids</summary>

Usage:
    listids [categories]

Lists the ids for various things.  Categories are:
   all, users, roles, channels

</details>

<details>
  <summary>move</summary>

Usage:
    move [Index of song to move] [Index to move song to]
    Ex: !move 1 3

Swaps the location of a song within the playlist.

</details>

<details>
  <summary>np</summary>

Usage:
    np

Displays the current song in chat.

</details>

<details>
  <summary>pause</summary>

Usage:
    pause

Pauses playback of the current song.

</details>

<details>
  <summary>perms</summary>

Usage:
    perms [@user]
Sends the user a list of their permissions, or the permissions of the user specified.

</details>

<details>
  <summary>play</summary>

Usage:
    play song_link
    play text to search for
    play spotify_uri

Adds the song to the playlist.  If a link is not provided, the first
result from a youtube search is added to the queue.

If enabled in the config, the bot will also support Spotify URLs, however
it will use the metadata (e.g song name and artist) to find a YouTube
equivalent of the song. Streaming from Spotify is not possible.

</details>

<details>
  <summary>playnext</summary>

Usage:
    playnext song_link
    playnext text to search for
    playnext spotify_uri

Adds the song to the playlist next.  If a link is not provided, the first
result from a youtube search is added to the queue.

If enabled in the config, the bot will also support Spotify URLs, however
it will use the metadata (e.g song name and artist) to find a YouTube
equivalent of the song. Streaming from Spotify is not possible.

</details>

<details>
  <summary>playnow</summary>

Usage:
    play song_link
    play text to search for
    play spotify_uri

Adds the song to be played back immediately.  If a link is not provided, the first
result from a youtube search is added to the queue.

If enabled in the config, the bot will also support Spotify URLs, however
it will use the metadata (e.g song name and artist) to find a YouTube
equivalent of the song. Streaming from Spotify is not possible.

</details>

<details>
  <summary>pldump</summary>

Usage:
    pldump url

Dumps the individual urls of a playlist

</details>

<details>
  <summary>queue</summary>

Usage:
    queue [page_number]

Prints the current song queue.
Show later entries if available by giving optional page number.

</details>

<details>
  <summary>remove</summary>

Usage:
    remove [# in queue]

Removes queued songs. If a number is specified, removes that song in the queue, otherwise removes the most recently queued song.

</details>

<details>
  <summary>repeat</summary>

Usage:
    repeat [all | playlist | song | on | off]

Toggles playlist or song looping.
If no option is provided the current song will be repeated.
If no option is provided and the song is already repeating, repeating will be turned off.

</details>

<details>
  <summary>resetplaylist</summary>

Usage:
    resetplaylist

Resets all songs in the server's autoplaylist

</details>

<details>
  <summary>restart</summary>

Usage:
    restart [soft|full|upgrade|upgit|uppip]

Restarts the bot, uses soft restart by default.
`soft` reloads config without reloading bot code.
`full` restart reloading source code and configs.
`uppip` upgrade pip packages then fully restarts.
`upgit` upgrade bot with git then fully restarts.
`upgrade` upgrade bot and packages then restarts.

</details>

<details>
  <summary>resume</summary>

Usage:
    resume

Resumes playback of a paused song.

</details>

<details>
  <summary>search</summary>

Usage:
    search [service] [number] query

Searches a service for a video and adds it to the queue.
- service: any one of the following services:
    - youtube (yt) (default if unspecified)
    - soundcloud (sc)
    - yahoo (yh)
- number: return a number of video results and waits for user to choose one
  - defaults to 3 if unspecified
  - note: If your search query starts with a number,
          you must put your query in quotes
    - ex: search 2 "I ran seagulls"
The command issuer can use reactions to indicate their response to each result.

</details>

<details>
  <summary>seek</summary>

Usage:
    seek [time]

Restarts the current song at the given time.
If time starts with + or - seek will be relative to current playback time.
Time should be given in seconds, fractional seconds are accepted.
Due to codec specifics in ffmpeg, this may not be accurate.

</details>

<details>
  <summary>setnick</summary>

Usage:
    setnick nick

Changes the bot's nickname.

</details>

<details>
  <summary>setprefix</summary>

Usage:
    setprefix prefix

If enabled by owner, set an override for command prefix with a custom prefix.

</details>

<details>
  <summary>shuffle</summary>

Usage:
    shuffle

Shuffles the server's queue.

</details>

<details>
  <summary>shuffleplay</summary>

Usage:
    shuffleplay playlist_link

Like play command but explicitly shuffles entries before adding them to the queue.

</details>

<details>
  <summary>shutdown</summary>

Usage:
    shutdown

Disconnects from voice channels and closes the bot process.

</details>

<details>
  <summary>skip</summary>

Usage:
    skip [force/f]

Skips the current song when enough votes are cast.
Owners and those with the instaskip permission can add 'force' or 'f' after the command to force skip.

</details>

<details>
  <summary>speed</summary>

Usage:
    speed [rate]

Apply a speed to the currently playing track.
The rate must be between 0.5 and 100.0 due to ffmpeg limits.
Stream playback does not support speed adjustments.

</details>

<details>
  <summary>stream</summary>

Usage:
    stream song_link

Enqueue a media stream.
This could mean an actual stream like Twitch or shoutcast, or simply streaming
media without pre-downloading it.  Note: FFmpeg is notoriously bad at handling
streams, especially on poor connections.  You have been warned.

</details>

<details>
  <summary>summon</summary>

Usage:
    summon

Call the bot to the summoner's voice channel.

</details>

<details>
  <summary>uptime</summary>

Usage:
    uptime

Displays the MusicBot uptime, since last start/restart.

</details>

<details>
  <summary>volume</summary>

Usage:
    volume (+/-)[volume]

Sets the playback volume. Accepted values are from 1 to 100.
Putting + or - before the volume will make the volume change relative to the current volume.

</details>

# Admin Commands  

<details>
  <summary>botlatency</summary>

Usage:
    botlatency

Prints latency info for all voice clients.

</details>

<details>
  <summary>cache</summary>

Usage:
    cache

Display cache storage info or clear cache files.
Valid options are:  info, update, clear

</details>

<details>
  <summary>checkupdates</summary>

Usage:
    checkupdates

Display the current bot version and check for updates to MusicBot or dependencies.
The option `GitUpdatesBranch` must be set to check for updates to MusicBot.

</details>

<details>
  <summary>config</summary>

Usage:
    config missing
        Shows help text about any missing config options.

    config diff
        Lists the names of options which have been changed since loading config file.

    config list
        List the available config options and their sections.

    config reload
        Reload the options.ini file from disk.

    config help [Section] [Option]
        Shows help text for a specific option.

    config show [Section] [Option]
        Display the current value of the option.

    config save [Section] [Option]
        Saves the current current value to the options file.

    config set [Section] [Option] [value]
        Validates the option and sets the config for the session, but not to file.

This command allows management of MusicBot config options file.

</details>

<details>
  <summary>joinserver</summary>

Usage:
    joinserver

Generate an invite link that can be used to add this bot to another server.

</details>

<details>
  <summary>option</summary>

Usage:
    option [option] [on/y/enabled/off/n/disabled]

Changes a config option without restarting the bot. Changes aren't permanent and
only last until the bot is restarted. To make permanent changes, edit the
config file.

Valid options:
    autoplaylist, save_videos, now_playing_mentions, auto_playlist_random, auto_pause,
    delete_messages, delete_invoking, write_current_song, round_robin_queue

For information about these options, see the option's comment in the config file.

</details>

<details>
  <summary>setavatar</summary>

Usage:
    setavatar [url]

Changes the bot's avatar.
Attaching a file and leaving the url parameter blank also works.

</details>

<details>
  <summary>setcookies</summary>

Usage:
    setcookies [ off | on ]
        Disable or enable cookies.txt file without deleting it.

    setcookies
        Update the cookies.txt file using a supplied attachment.

Note:
  When updating cookies, you must upload a file named cookies.txt
  If cookies are disabled, uploading will enable the feature.
  Uploads will delete existing cookies, including disabled cookies file.

WARNING:
  Copying cookies can risk exposing your personal information or accounts,
  and may result in account bans or theft if you are not careful.
  It is not recommended due to these risks, and you should not use this
  feature if you do not understand how to avoid the risks.

</details>

<details>
  <summary>setname</summary>

Usage:
    setname name

Changes the bot's username.
Note: This operation is limited by discord to twice per hour.

</details>

<details>
  <summary>setperms</summary>

Usage:
    setperms list
        show loaded groups and list permission options.

    setperms reload
        reloads permissions from the permissions.ini file.

    setperms add [GroupName]
        add new group with defaults.

    setperms remove [GroupName]
        remove existing group.

    setperms help [PermName]
        show help text for the permission option.

    setperms show [GroupName] [PermName]
        show permission value for given group and permission.

    setperms save [GroupName]
        save permissions group to file.

    setperms set [GroupName] [PermName] [Value]
        set permission value for the group.

</details>

# Dev Commands  

<details>
  <summary>breakpoint</summary>

Do nothing but print a critical level error to the log.

</details>

<details>
  <summary>debug</summary>

Usage:
    debug [one line of code]
        OR
    debug ` ` `py
    many lines
    of python code.
    ` ` `

    This command will execute python code in the commands scope.
    First eval() is attempted, if exceptions are thrown exec() is tried.
    If eval is successful, its return value is displayed.
    If exec is successful, a value can be set to local variable `result`
    and that value will be returned.

</details>

<details>
  <summary>makemarkdown</summary>

Usage:
    makemarkdown opts
        Make markdown for options.
    makemarkdown perms
        Make markdown for permissions.
    makemarkdown help
        Make markdown for commands and help.

Command to generate markdown for options and permissions files.
Contents are generated from code and not pulled from the files!

</details>

<details>
  <summary>objgraph</summary>

Interact with objgraph to make it spill the beans.

</details>

<details>
  <summary>testready</summary>
Command used to signal command testing.
</details>

