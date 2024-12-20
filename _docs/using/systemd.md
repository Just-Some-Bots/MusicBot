---
title: SystemD
category: Using the bot
order: 10
---

This guide will show how to set up automation for MusicBot via SystemD service configuration.  
SystemD is a multi-featured management suite included in many modern Linux distros.  

If your OS includes SystemD, you can use these steps to set up a service:  

1. Copy the `musicbot.service.example` file and rename it `musicbot.service`.  
2. Open the new service and edit as needed.  
3. Install the new service file.  
4. Reload systemd and enable the service.  

<details>
  <summary>Example command line steps.</summary>

Update these commands to use an editor of your choice, and correct paths as needed.  

{% highlight bash%}
# Open the clone directory.
cd ~/MusicBot

# Copy the example file.
cp ./musicbot.service.example ./musicbot.service

# Edit the copied file (use any text editor you like here).
vim ./musicbot.service

# Install the service file into the system.
sudo cp ./musicbot.service /etc/systemd/system/musicbot.service

# Load the newly installed service. This does not start or enable it.
sudo systemctl daemon-reload

# To start MusicBot at boot time, use:
sudo systemctl enable musicbot

# To start MusicBot run:
sudo systemctl start musicbot

# To stop MusicBot run:
sudo systemctl stop musicbot

# To restart MusicBot run:
sudo systemctl restart musicbot

# To check if its running use:
sudo systemctl status musicbot

# To review system logs for the service:
sudo journalctl -u musicbot

{% endhighlight %}

</details>


<details>
  <summary>A Completed Example <code>.service</code> file.</summary>

{% highlight systemd %}
[Unit]
Description=Just-Some-Bots/MusicBot a discord.py bot that plays music.

# Only start this service after networking is ready.
After=network.target


[Service]
# These control the user/group used to start MusicBot.
# It is important to set this to the user who installed MusicBot
User=musicuser
Group=musicgroup

# This should be the path where MusicBot was cloned into.
WorkingDirectory=/home/musicuser/MusicBot/

# Use system Python to run the bot.
ExecStart=/usr/bin/python3 /home/musicuser/MusicBot/run.py --no-checks
# For Venv installs, replace the above with something like:
#ExecStart=/home/musicuser/MusicBotVenv/bin/python3 /home/musicuser/MusicBotVenv/MusicBot/run.py

# Set the condition under which the service should be restarted.
# Using 'on-failure' allows the bot's shutdown command to actually stop the service.
# Using 'always' will require you to stop the service via the service manager.
Restart=on-failure

# Time to wait between restarts.  This is useful to avoid rate limits.
RestartSec=6


[Install]
WantedBy=default.target

{% endhighlight %}

</details>
