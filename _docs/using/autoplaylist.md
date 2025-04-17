---
title: Auto Playlists
category: Using the bot
order: 14
---

MusicBot provides an automatic playlist feature which has seen various changes.  

Historically, the autoplaylist was a single text file, shared between all discord servers connected to your bot. 
A simple text file containing mostly URLs which would be loaded into a dedicated queue to play music when 
no other music was in the primary queue.  

In more recent versions, it allows for multiple playlists, has more options, and is more flexible all around. 
Be sure to review the [config section]({{ site.baseurl }}/using/configuration#autoplaylist) 
and the `autoplaylist` [command]({{ site.baseurl}}/using/commands) for more details on exact features.  

## File Locations

Playlist files are stored in the `config` directory in all versions.  
In older versions, the files are:  
 - `autoplaylist.txt`  - The "working copy" of the playlist.  
 - `_autoplaylist.txt`  - The bundled "starter / example" playlist, updated when musicbot updates. 

In newer versions, a sub-directory named `playlists` is where the working copies are kept.  
Some playlist file names are reserved for use by MusicBot.  Those are:  
 - `default.txt`  -  Default playlist, automatically re-recreated, used for new servers.  
 - `history.txt`  -  If enabled, playback history from all servers is saved here.  
 - `history-*.txt`  -  If enabled, playback history from one server is saved here.  
   *Note:* The `*` is usually replaced with a server ID number.  


## How do playlists work?

By default, MusicBot will attempt to keep the legacy behaviour of using one default playlist file 
for all servers connected to your bot.  
This can be changed by using the `autoplaylist` command or other related config options.  

Each line in a playlist file is treated as an entry.  
URLs are used directly, while track titles are searched for the same way `play` command would use them.  
Lines which start with `#` are treated as comments, ignored and not included in the resulting playlist.  

> **NOTE:** The default playlist is copied from the bundled starter file if it does not exist. It is quite 
old, and you may want to edit the entries or make a new playlist instead.  

## How do I make playlists?

To set up a non-default playlist, make use of the `autoplaylist set` command.  
The `set` sub-command will create a playlist file if needed, and save that playlist choice 
to the per-server data so it will be used after restarts as well.  

To modify a playlist, you can either use the `autoplaylist` commands or edit the file 
with a plain-text editor.  If you edit the file you'll want to reload it or restart MusicBot.  

> **Note:** Unlike permissions and config files, auto playlist files *can* be edited with Windows notepad.exe.  
