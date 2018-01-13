---
title: Commands
position: 2
---

This is a list of the **commands** that can be used to control the MusicBot. You **cannot** use commands in private messages. Every command starts with the prefix that you [configured](#guidesconfiguration). This page assumes your prefix is `!`, the default. Required parameters are indicated with `<` and `>`, while optional parameters are indicated with `[` and `]`.

----

### General

#### `!help [command]`
Prints a basic list of commands, or info on a command if one is specified.

#### `!play <URL/query>`
Plays audio from a specific URL or searches for a query on YouTube ([you can make it do others](https://github.com/Just-Some-Bots/MusicBot/wiki/FAQ#is-some-other-website-or-service-supported)) and queues the first result.

#### `!queue`
Displays all of the media that is queued.

#### `!np`
Displays the media that is currently being played.

#### `!skip`
Vote to skip the current media. Required skips or skip ratio are set in the configuration file. The bot's owner will instantly skip when using this command.

#### `!search [service] [#] <query>`
Searches a specific service (default: YouTube) for a query and returns the first few results (default: 3, limit: 10). The user can then select from the results if they want to add any to the queue.

#### `!shuffle`
Shuffles the queue.

#### `!clear`
Clears the queue.

#### `!pause`
Pauses the current media.

#### `!resume`
Resumes the current media

#### `!volume [number]`
Sets the volume of the bot for everyone. Should be a number between 1 and 100. Can be relative (e.g `+10` to add 10 to current volume). If no parameter is given, it will display the current volume.

#### `!summon`
Connects the bot to your current voice channel, if it has permission.

#### `!clean <number>`
Searches through the number of messages given and deletes those that were sent by the bot, effectively cleaning the channel. If the bot has `Manage Messages` on the server, it will delete user command messages too, like `!play`.

#### `!blacklist <status> <@user1>...`
Add or remove users from the blacklist. Blacklisted users cannot use any bot commands. This overrides any permissions settings set in the permissions file. The owner cannot be blacklisted. Multiple users can be specified in the command. Users must be @mentioned. Status should be either `+`, `-`, `add`, or `remove`.

#### `!id [@user]`
Prints the user's ID in the chat, or prints the ID of the specified user. User must be @mentioned if not yourself.

#### `!listids`
Sends a message to the user with a list of all of the IDs on the server, so that permissions and such can be configured. This shouldn't be required anymore, as Discord allows you to enable `Developer Mode` in your User Settings.

#### `!perms`
Sends a message to the user with their bot permissions.

#### `!stream <url>`
Streams a URL. This can be a Twitch, YouTube, etc livestream, or a radio stream. This feature of the bot is experimental and may have some issues.

#### `!save`
Saves the current song to the autoplaylist.

----

### Admin

#### `!joinserver`
Provides the URL that can be used to add the bot to another server. This command is **always restricted to the owner of the bot**.

#### `!pldump <playlist>`
Collects URLs from a YouTube playlist or Soundcloud set and dumps them into a text file that can be copied into the autoplaylist.

#### `!setavatar [url]`
Changes the bot's avatar to the specified URL or uploaded image. A URL does not need to be specified if an image is uploaded with the command as the message (comment).

#### `!setname <name>`
Changes the bot's Discord username (**not** nickname). Discord limits these changes to 2/hr.

#### `!setnick <nick>`
Changes the bot's nickname on a server, if it has permission to do so.

#### `!disconnect`
Disconnects the bot from the voice channel.

#### `!restart`
Restarts the bot.

#### `!shutdown`
Shuts down the bot and terminates the process.

----

### Dev

These commands are intended for people who know how Python works and/or developers of the bot. As such, they are restricted behind additional permissions that must be granted in the options file. Please do not run any of these commands unless you are absolutely sure that you are aware what you are doing and the potential consequences, as they can be **very dangerous**.
{: .warning }

#### `!breakpoint`
Activates a debugging breakpoint.

#### `!objgraph [func]`
Returns an object graph.

#### `!debug`
Evaluates arbitrary code. **This can be an extremely dangerous command**.