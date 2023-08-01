---
title: Troubleshooting
category: Using the bot
order: 6
---

This is a table of common issues and solutions for the bot. Please check here before leaving an issue on GitHub or asking for help in our [support server](https://discord.gg/bots).

Issue | Solution
--- | ---
`Intents missing/` | 1. Go to Discord's [applications page](https://discord.com/developers/applications/me) (logging in if prompted).
2. Select your bot.
3. Go to the page called "Bot", and scroll until you see "Privileged Gateway Intents"
4. Now enable "PRESENCE INTENT" and "SERVER MEMBERS INTENT" and you should be good to go!
`Bot was not installed using Git` | You didn't install the bot correctly. Rather than downloading a ZIP, you must install using Git. Use our official installation guides rather than a YouTube video.
Lagging while playing music | Check your CPU and disk usage. Ensure that you have enough bandwidth. Check your voice channel's bitrate. Check there isn't a [Discord issue](https://status.discord.com).
`Bot can't login, bad credentials` | Check you copied the correct token from your [bot application page](https://discord.com/developers/applications/me) into your config file. It is called **Token**, not Client Secret.
`WebSocket connection is closed` | The bot tries to handle websocket disconnects, but sometimes there can be a problem, for example if Discord's voice servers go down. Try restarting the bot or switching server region if this error is persistent.
`./run.sh: command not found` | While Git *should* preserve file permissions, you may need to set `run.sh` to be executable by running `chmod a+x run.sh`.
`Your config file is missing some options.` | This will usually occur if you have updated the bot. In order to avoid issues, bot updates do **not** update your config file with new options, but **do** update `example_options.ini`. Therefore, you should check that file and copy new options to your config file when you can (or delete your config file and re-configure entirely). The bot will use default settings for the missing options until you configure them, so the message is only a warning and will not impact the bot's performance.
`git: unable to access 'https://github.com/Just-Some-Bots/MusicBot.git' SSL certificate problem: self signed certificate in certificate chain` | Try disabling your antivirus. Some antivirus software is known to interfere with git.
`ValueError: Invalid format '.' for '%' style` | You're likely using Python 3.8 with the master branch of the bot. Resolving this is as simple as either installing [Python 3.7](https://www.python.org/ftp/python/3.7.0/python-3.7.0.exe), or updating to review by running `git checkout review`
`TypeError: __new__() got an unexpected keyword argument 'deny_new'` | This occurs due to an outdated version of `discord.py`. To resolve this, update `discord.py` with the following command: `python -m pip install -U discord.py[voice]`
