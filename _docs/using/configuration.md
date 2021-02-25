---
title: Configuration
category: Using the bot
order: 1
---

Configuring the bot is relatively straight forward. First, open your bot folder and then the `config` folder within it. Copy `example_options.ini` to `options.ini`. This will be the file that you save your configuration into. Open it with a code editor like Notepad++, Atom, or Visual Studio Code.

> Editing your configuration file using Notepad or WordPad will result in problems as they save files in strange formats and aren't designed for editing .ini files.

#### Intents

Due to the new Discord update regarding intents, you have to enable the intents to get some options to work.
More information is [here]({{ site.baseurl }}/using/intents).

#### Credentials

<img class="doc-img" src="{{ site.baseurl }}/images/token.png" alt="Token" style="width: 500px;"/>

- `Token` - *This is the only required option for your bot to run.* You must provide the token for your Discord bot account. To create a bot account, go to your [applications page](https://discordapp.com/developers/applications/me) (logging in if prompted), and then follow this [10 second video](https://drive.google.com/file/d/1wZG_TBVfjQfj0CEYaRTzS60D-cbfeeYZ/view). If you followed it entirely, you should have revealed your token and can now copy it into the config file.

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
- <span class="badge major">review only</span> `CustomEmbedFooter` - Changes the footer text found in embeds from the default version footer

#### Files

- `i18nFile` - The internationalization file to use for the bot (relative path, e.g `config/i18n/en.json`)
