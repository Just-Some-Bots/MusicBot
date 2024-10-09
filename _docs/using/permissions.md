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

---

### [Owner (auto)]

<details>
  <summary>CommandWhitelist</summary>

List of command names allowed for use, separated by spaces.
This option overrides CommandBlacklist if set.  
<strong>Default Value:</strong> <code>(All allowed)</code>  
</details>  
<details>
  <summary>CommandBlacklist</summary>

List of command names denied from use, separated by spaces.
Will not work if CommandWhitelist is set!  
<strong>Default Value:</strong> <code>(None denied)</code>  
</details>  
<details>
  <summary>IgnoreNonVoice</summary>

List of command names that can only be used while in the same voice channel as MusicBot.
Some commands will always require the user to be in voice, regardless of this list.
Command names should be separated by spaces.  
<strong>Default Value:</strong> <code>(No commands listed)</code>  
</details>  
<details>
  <summary>GrantToRoles</summary>

List of Discord server role IDs that are granted this permission group. This option is ignored if UserList is set.  
<strong>Default Value:</strong> <i>*empty*</i>  
</details>  
<details>
  <summary>UserList</summary>

List of Discord member IDs that are granted permissions in this group. This option overrides GrantToRoles.  
<strong>Default Value:</strong> <i>*empty*</i>  
</details>  
<details>
  <summary>MaxSongs</summary>

Maximum number of songs a user is allowed to queue. A value of 0 means unlimited.  
<strong>Default Value:</strong> <code>0</code>  
</details>  
<details>
  <summary>MaxSongLength</summary>

Maximum length of a song in seconds. A value of 0 means unlimited.
This permission may not be enforced if song duration is not available.  
<strong>Default Value:</strong> <code>0</code>  
</details>  
<details>
  <summary>MaxPlaylistLength</summary>

Maximum number of songs a playlist is allowed to have to be queued. A value of 0 means unlimited.  
<strong>Default Value:</strong> <code>0</code>  
</details>  
<details>
  <summary>MaxSearchItems</summary>

The maximum number of items that can be returned in a search.  
<strong>Default Value:</strong> <code>10</code>  
</details>  
<details>
  <summary>AllowPlaylists</summary>

Allow users to queue playlists, or multiple songs at once.  
<strong>Default Value:</strong> <code>yes</code>  
</details>  
<details>
  <summary>InstaSkip</summary>

Allow users to skip without voting, if LegacySkip config option is enabled.  
<strong>Default Value:</strong> <code>yes</code>  
</details>  
<details>
  <summary>SkipLooped</summary>

Allows the user to skip a looped song.  
<strong>Default Value:</strong> <code>yes</code>  
</details>  
<details>
  <summary>Remove</summary>

Allows the user to remove any song from the queue.
Does not remove or skip currently playing songs.  
<strong>Default Value:</strong> <code>yes</code>  
</details>  
<details>
  <summary>SkipWhenAbsent</summary>

Skip songs added by users who are not in voice when their song is played.  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>BypassKaraokeMode</summary>

Allows the user to add songs to the queue when Karaoke Mode is enabled.  
<strong>Default Value:</strong> <code>yes</code>  
</details>  
<details>
  <summary>SummonNoVoice</summary>

Auto summon to user voice channel when using play commands, if bot isn't in voice already.
The summon command must still be allowed for this group!  
<strong>Default Value:</strong> <code>yes</code>  
</details>  
<details>
  <summary>Extractors</summary>

List of yt_dlp extractor keys, separated by spaces, that are allowed to be used.
Extractor names are matched partially, to allow for strict and flexible permissions.
Example:  <code>youtube:search</code> allows only search, but <code>youtube</code> allows all of youtube extractors.
When empty, hard-coded defaults are used. If you set this, you may want to add those defaults as well.
To allow all extractors, add <code>__</code> to the list of extractors.
Services supported by yt_dlp shown here:  https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md 
MusicBot also provides one custom service <code>spotify:musicbot</code> to enable or disable spotify API extraction.
NOTICE: MusicBot might not support all services available to yt_dlp!
  
<strong>Default Value:</strong> <code>(All allowed)</code>  
</details>  


### [Default]

<details>
  <summary>CommandWhitelist</summary>

List of command names allowed for use, separated by spaces.
This option overrides CommandBlacklist if set.  
<strong>Default Value:</strong> <code>(All allowed)</code>  
</details>  
<details>
  <summary>CommandBlacklist</summary>

List of command names denied from use, separated by spaces.
Will not work if CommandWhitelist is set!  
<strong>Default Value:</strong> <code>(None denied)</code>  
</details>  
<details>
  <summary>IgnoreNonVoice</summary>

List of command names that can only be used while in the same voice channel as MusicBot.
Some commands will always require the user to be in voice, regardless of this list.
Command names should be separated by spaces.  
<strong>Default Value:</strong> <code>(No commands listed)</code>  
</details>  
<details>
  <summary>GrantToRoles</summary>

List of Discord server role IDs that are granted this permission group. This option is ignored if UserList is set.  
<strong>Default Value:</strong> <i>*empty*</i>  
</details>  
<details>
  <summary>UserList</summary>

List of Discord member IDs that are granted permissions in this group. This option overrides GrantToRoles.  
<strong>Default Value:</strong> <i>*empty*</i>  
</details>  
<details>
  <summary>MaxSongs</summary>

Maximum number of songs a user is allowed to queue. A value of 0 means unlimited.  
<strong>Default Value:</strong> <code>8</code>  
</details>  
<details>
  <summary>MaxSongLength</summary>

Maximum length of a song in seconds. A value of 0 means unlimited.
This permission may not be enforced if song duration is not available.  
<strong>Default Value:</strong> <code>210</code>  
</details>  
<details>
  <summary>MaxPlaylistLength</summary>

Maximum number of songs a playlist is allowed to have to be queued. A value of 0 means unlimited.  
<strong>Default Value:</strong> <code>0</code>  
</details>  
<details>
  <summary>MaxSearchItems</summary>

The maximum number of items that can be returned in a search.  
<strong>Default Value:</strong> <code>10</code>  
</details>  
<details>
  <summary>AllowPlaylists</summary>

Allow users to queue playlists, or multiple songs at once.  
<strong>Default Value:</strong> <code>yes</code>  
</details>  
<details>
  <summary>InstaSkip</summary>

Allow users to skip without voting, if LegacySkip config option is enabled.  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>SkipLooped</summary>

Allows the user to skip a looped song.  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>Remove</summary>

Allows the user to remove any song from the queue.
Does not remove or skip currently playing songs.  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>SkipWhenAbsent</summary>

Skip songs added by users who are not in voice when their song is played.  
<strong>Default Value:</strong> <code>yes</code>  
</details>  
<details>
  <summary>BypassKaraokeMode</summary>

Allows the user to add songs to the queue when Karaoke Mode is enabled.  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>SummonNoVoice</summary>

Auto summon to user voice channel when using play commands, if bot isn't in voice already.
The summon command must still be allowed for this group!  
<strong>Default Value:</strong> <code>no</code>  
</details>  
<details>
  <summary>Extractors</summary>

List of yt_dlp extractor keys, separated by spaces, that are allowed to be used.
Extractor names are matched partially, to allow for strict and flexible permissions.
Example:  <code>youtube:search</code> allows only search, but <code>youtube</code> allows all of youtube extractors.
When empty, hard-coded defaults are used. If you set this, you may want to add those defaults as well.
To allow all extractors, add <code>__</code> to the list of extractors.
Services supported by yt_dlp shown here:  https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md 
MusicBot also provides one custom service <code>spotify:musicbot</code> to enable or disable spotify API extraction.
NOTICE: MusicBot might not support all services available to yt_dlp!
  
<strong>Default Value:</strong> <code>generic, Bandcamp, spotify:musicbot, soundcloud, youtube</code>  
</details>  


