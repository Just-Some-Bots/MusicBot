---
title: Commands
category: Using the bot
order: 2
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
