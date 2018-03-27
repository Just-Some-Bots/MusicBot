---
title: Troubleshooting
category: Using the bot
order: 6
---

This is a table of common issues and solutions for the bot. Please check here before leaving an issue on GitHub or asking for help in our [support server](https://discord.gg/bots).

Issue | Solution
--- | ---
"Bot was not installed using Git" | You didn't install the bot correctly. Rather than downloading a ZIP, you must install using Git. Use our official installation guides rather than a YouTube video.
Lagging while playing music | Check your CPU and disk usage. Ensure that you have enough bandwidth. Check your voice channel's bitrate. Check there isn't a [Discord issue](https://status.discordapp.com).
"Bot can't login, bad credentials" | Check you copied the correct token from your [bot application page](https://discordapp.com/developers/applications/me) into your config file. It is called **Token**, not Client Secret.
"WebSocket connection is closed" | The bot tries to handle websocket disconnects, but sometimes there can be a problem, for example if Discord's voice servers go down. Try restarting the bot or switching server region if this error is persistent.
"./run.sh: command not found" | While Git *should* preserve file permissions, you may need to set `run.sh` to be executable by running `chmod a+x run.sh`.
"Your config file is missing some options." | This will usually occur if you have updated the bot. In order to avoid issues, bot updates do **not** update your config file with new options, but **do** update `example_options.ini`. Therefore, you should check that file and copy new options to your config file when you can (or delete your config file and re-configure entirely). The bot will use default settings for the missing options until you configure them, so the message is only a warning and will not impact the bot's performance.