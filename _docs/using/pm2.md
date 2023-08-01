---
title: PM2
category: Using the bot
order: 9
---

This guide will assist you in installing PM2 to run MusicBot in the background of Linux and Mac, automatically restart it if it crashes, and at startup.
To start out with, ensure you have installed [Node.js and NPM](https://nodejs.org/en/download/package-manager/).
This guide also assumes you clones MusicBot in your home folder. If you didn't, you'll need to replace those commands with the path to your MusicBot folder.
If you have node and npm installed, you can start running the following to install PM2:

<pre class="code bash">npm <span class="kw2">install</span> pm2<span class="sy0">@</span>latest <span class="re5">-g</span>
<span class="kw3">cd</span> ~<span class="sy0">/</span>MusicBot
pm2 start run.py <span class="re5">--name</span> <span class="st0">"MusicBot"</span> <span class="re5">--interpreter</span>=python3
pm2 startup
pm2 save</pre>

With these commands done, your bot should be running in the background, should restart if it crashes, and should start whenever you start your system.

At any point after this, if you would like to view logs, start, stop, or restart MusicBot, you can use the following.

<pre class="code bash">pm2 logs MusicBot      - View MusicBot logs
pm2 restart MusicBot   - Restart MusicBot
pm2 stop MusicBot      - Stop MusicBot
pm2 start MusicBot     - Start MusicBot</pre>
