---
title: Aliases
category: Using the bot
order: 4
---

This page documents the command alias feature of MusicBot.  
Aliases currently can only be managed by editing the config file `config/aliases.json` to add or remove them. MusicBot must be restarted to reload aliases.  

There are two kinds of aliases supported:  

1. **Simple Alias**  
   These basically add extra, usually shorter, names for a command.  
   For Example:  
   `"play" : ["p"]` makes `!p` work like `!play` does.  

2. **Complex Alias**  
   These alias a command with pre-set arguments.  
   User-supplied arguments are added to the end.  
   For Example:  
   `"config set MusicBot": ["cfg"]` makes `!cfg` a command.  
   Using `!cfg DefaultVolume 0.40` is the same as:
   `!config set MusicBot DefaultVolume 0.40`
