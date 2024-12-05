---
title: PM2
category: Using the bot
order: 9
---


This guide will assist you in installing PM2 to run MusicBot in the background of Linux and Mac, automatically restart it if it crashes, and at startup.  
**Note:** Many modern Linux distros include SystemD, which you can use to set up a [SystemD service]({{ site.baseurl }}/using/systemd) instead of using PM2.  

To start out with, ensure you have installed [Node.js and NPM](https://nodejs.org/en/download/package-manager/).  
If you have node and npm installed, you can start running the following to install PM2:

{% highlight bash %}
# Use NPM to install PM2 latest version.
npm install pm2@latest -g

# Change to MusicBot directory. (We assume its in home directory here)
cd ~/MusicBot

# Use PM2 to set up a MusicBot process.
# Venv installs may need to use different launch options.
pm2 start run.py --name "MusicBot" --interpreter=python3
pm2 startup
pm2 save

{% endhighlight %}

With these commands done, your bot should be running in the background and should restart automatically on boot up and if MusicBot crashes.  

At any point after this, if you would like to view logs, start, stop, or restart MusicBot, you can use the following commands:  

{% highlight bash %}
# View MusicBot logs
pm2 logs MusicBot

# Restart MusicBot
pm2 restart MusicBot

# Stop MusicBot
pm2 stop MusicBot

# Start MusicBot
pm2 start MusicBot
{% endhighlight %}
