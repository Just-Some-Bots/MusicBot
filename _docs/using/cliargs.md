---
title: CLI Flags
category: Using the bot
order: 13
---

This page describes the command line arguments (aka flags) available to use with 
any of the bundled run scripts (`run.sh`, `run.bat`, and `run.py`) provided by MusicBot.  

> Note: These docs may not contain details for features in the `dev` or `review` branches.  Use the `--help` flag for details on options not listed here.

These are the options available for use:
```text

  -h, --help            show this help message and exit.

  -V, --version         Print the MusicBot version information and exit.

  --lang LANG_BOTH      Override the default / system detected language for all text in MusicBot.

  --log_lang LANG_LOGS  Use this language for all server-side log messages from MusicBot.

  --msg_lang LANG_MSGS  Use this language for all messages sent to discord from MusicBot.
                        This does not prevent per-guild language selection.

  --no-checks           Skip all optional startup checks, including the update check.

  --no-disk-check       Skip only the disk space check at startup.

  --no-update-check     Skip only the update check at startup.

  --no-install-deps     Disable MusicBot from trying to install dependencies when it cannot import them.

  --logs-kept KEEP_N_LOGS
                        Specify how many log files to keep, between 0 and 100 inclusive. (Default: 0)

  --log-level LOG_LEVEL
                        Override the log level settings set in config. Must be one of: 
                        CRITICAL, ERROR, WARNING, INFO, DEBUG, VOICEDEBUG, FFMPEG, NOISY, EVERYTHING

  --log-rotate-fmt OLD_LOG_FMT
                        Override the default date format used when rotating log files. 
                        This should contain values compatible with strftime().
                        Default: .ended-%Y-%j-%H%m%S 

```
