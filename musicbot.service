[Unit]
Description=Just-Some-Bots/MusicBot a discord.py bot that plays music.

# Only start this service after networking is ready.
After=network.target


[Service]
# These options are useful if you set up MusicBot under a dedicated user account.
# Uncomment and set these to an existing User name and Group name.
# If you do not set these, MusicBot may run as root!  You've been warned!
#User=mbuser
#Group=mbusergroup

# Replace mbdirectory to the file path where MusicBot was cloned into.
WorkingDirectory=mbdirectory

# Replace mbdirectory same as above, also update the python path as needed for your system.
ExecStart=/usr/bin/pythonversionnum mbdirectory/run.py --no-checks

# Set the condition under which the service should be restarted.
# Using on-failure allows the bot's shutdown command to actually stop the service.
# Using always will require you to stop the service via the service manager.
Restart=on-failure

# Time to wait between restarts.  This is useful to avoid rate limits.
RestartSec=6


[Install]
WantedBy=default.target
