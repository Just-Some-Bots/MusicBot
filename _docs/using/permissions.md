---
title: Permissions
category: Using the bot
order: 2
---

This page gives information on how to setup **permissions**. When you install the bot, you will get a file inside the `config` folder named `example_permissions.ini`. This option contains an **example set** of permissions. Edit it, and then **save it as a new file** called `permissions.ini`.

> For Windows users, please note that file extensions are **hidden by default**, so you may just need to save the file as `permissions` if you are having difficulties as the `.ini` may be hidden.

> Do not edit any configuration file using Notepad or other basic text editors, otherwise it will break. Use something like [Notepad++](https://notepad-plus-plus.org/download/).

The permissions file contains **multiple sections**. The `[Default]` section should **not be renamed**. It contains the default permissions for users of the bot that are not the owner. **Each section is a group**. A user's roles do not allow them to have full permissions to use the bot, **this file does**.

#### Control what commands a group can use
**Add the command** in the `CommandWhitelist` section of the group. Each command should be separated by **spaces**. For example, to allow a group to use `!play` and `!skip` only:

    CommandWhitelist = play skip

#### Add a user to a group
**Add a user's ID** in the `UserList` section of the group. Each user ID should be separated by **spaces**. For example:

    UserList = 154748625350688768 104766296687656960

#### Add a role to a group

**Add a role's ID** in the `GrantToRoles` section of the group. Each role ID should be separated by **spaces**. For example:

    GrantToRoles = 173129876679688192 183343083063214081

However, **don't add an ID to the Default group!** This group is assigned to everyone that doesn't have any other groups assigned and therefore needs no ID.

### Available Permission Options  

<p><a class="expand-all-details">Show/Hide All</a></p>

<details>
  <summary>CommandWhitelist</summary>

List of command names allowed for use, separated by spaces.<br>
Sub-command access can be controlled by adding _ and the sub-command name.<br>
That is `config_set` grants only the `set` sub-command of the config command.<br>
This option overrides CommandBlacklist if set.<br>
<br>  
<strong>Default Value:</strong> <code>(All allowed)</code>  
</details>  
<details>
  <summary>CommandBlacklist</summary>

List of command names denied from use, separated by spaces.<br>
Will not work if CommandWhitelist is set!<br>  
<strong>Default Value:</strong> <code>(None denied)</code>  
</details>  
<details>
  <summary>AdvancedCommandLists</summary>

When enabled, CommandBlacklist and CommandWhitelist are used together.<br>
Only commands in the whitelist are allowed, however sub-commands may be denied by the blacklist.<br>
<br>  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>IgnoreNonVoice</summary>

List of command names that can only be used while in the same voice channel as MusicBot.<br>
Some commands will always require the user to be in voice, regardless of this list.<br>
Command names should be separated by spaces.<br>  
<strong>Default Value:</strong> <code>(No commands listed)</code>  
</details>  
<details>
  <summary>GrantToRoles</summary>

List of Discord server role IDs that are granted this permission group.<br>
This option is ignored if UserList is set.<br>  
<strong>Default Value:</strong> <i>*empty*</i>  
</details>  
<details>
  <summary>UserList</summary>

List of Discord member IDs that are granted permissions in this group.<br>
This option overrides GrantToRoles.<br>  
<strong>Default Value:</strong> <i>*empty*</i>  
</details>  
<details>
  <summary>MaxSongs</summary>

Maximum number of songs a user is allowed to queue.<br>
A value of 0 means unlimited.<br>  
<strong>Default Value:</strong> <code>8</code>  
</details>  
<details>
  <summary>MaxSongLength</summary>

Maximum length of a song in seconds. A value of 0 means unlimited.<br>
This permission may not be enforced if song duration is not available.<br>  
<strong>Default Value:</strong> <code>210</code>  
</details>  
<details>
  <summary>MaxPlaylistLength</summary>

Maximum number of songs a playlist is allowed to have when queued.<br>
A value of 0 means unlimited.<br>  
<strong>Default Value:</strong> <code>0</code>  
</details>  
<details>
  <summary>MaxSearchItems</summary>

The maximum number of items that can be returned in a search.<br>  
<strong>Default Value:</strong> <code>10</code>  
</details>  
<details>
  <summary>AllowPlaylists</summary>

Allow users to queue playlists, or multiple songs at once.<br>  
<strong>Default Value:</strong> <code>yes</code>  
</details>  
<details>
  <summary>InstaSkip</summary>

Allow users to skip without voting, if LegacySkip config option is enabled.<br>  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>SkipLooped</summary>

Allows the user to skip a looped song.<br>  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>Remove</summary>

Allows the user to remove any song from the queue.<br>
Does not remove or skip currently playing songs.<br>  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>SkipWhenAbsent</summary>

Skip songs added by users who are not in voice when their song is played.<br>  
<strong>Default Value:</strong> <code>yes</code>  
</details>  
<details>
  <summary>BypassKaraokeMode</summary>

Allows the user to add songs to the queue when Karaoke Mode is enabled.<br>  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>SummonNoVoice</summary>

Auto summon to user voice channel when using play commands, if bot isn't in voice already.<br>
The summon command must still be allowed for this group!<br>  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>Extractors</summary>

Specify yt-dlp extractor names, separated by spaces, that are allowed to be used.<br>
When empty, hard-coded defaults are used. The defaults are displayed above, but may change between versions.<br>
To allow all extractors, add `__` without quotes to the list.<br>
<br>
Services/extractors supported by yt-dlp are listed here:<br>
  https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md <br>
<br>
MusicBot also provides one custom service `spotify:musicbot` to enable or disable Spotify API extraction.<br>
NOTICE: MusicBot might not support all services available to yt-dlp!<br>
<br>  
<strong>Default Value:</strong> <code>Bandcamp, youtube, spotify:musicbot, soundcloud, generic</code>  
</details>

---

<p><a class="expand-all-details">Show/Hide All</a></p>
