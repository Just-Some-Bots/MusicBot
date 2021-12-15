---
title: 15th December 2021
type: major
---

**Review merge**

This release merges all changes from the `review` branch of MusicBot into the main branch. This contains multiple bug fixes, improvements, and changes. MusicBot requires Python 3.8 or higher.

**Important: Discord gateway intents**

Please note that MusicBot requires privileged intents to function. You need to enable each of the Gateway Intents on your [Discord Application](https://discord.com/developers/applications)'s 'Bot' page.

<img class="doc-img" src="{{ site.baseurl }}/images/intents.png" alt="Intents" style="width: 500px;"/>

**Changes:**

* ⚡️ Switched from `discord.py` to `pycord` fork, which is maintained.
* ⚡️ Switched from `youtube-dl` to `yt-dlp` fork, which is maintained.
* Add example `docker-compose.yml` file for Docker deployment.
* Bot will deafen itself if it has permission.
* Fix for Soundcloud sets.
* A lot of cleanup and changes for underlying code, fixing a myriad of issues.