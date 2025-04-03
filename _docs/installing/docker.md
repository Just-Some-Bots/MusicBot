---
title: Docker
category: Installing the bot
order: 13
---

MusicBot provides a `Dockerfile` which can be used to build a docker image for MusicBot.  
The basic steps on this page should get you up-and-running using docker. You are 
encouraged to read the Dockerfile and make edits to fit your needs.  

These steps use the `dev` branch, you may also change this to `master` or `review` as desired.  

> Note: If you are a regular user of docker, consider contributing to make these instructions 
and the basic `Dockerfile` better for all docker users.  

## Building with Docker

~~~bash
# Clone the `dev` branch of MusicBot to a folder called MusicBot.
git clone -b dev https://github.com/Just-Some-Bots/MusicBot.git MusicBot

# Switch into that directory.
cd MusicBot

# Now build an image with docker.
# Change 'yournamehere/musicbot:latest' as desired.
docker build -f Dockerfile -t yournamehere/musicbot:latest ~/MusicBot
~~~

## Using Docker-Compose

After following the above steps, you can also use docker-compose to run MusicBot.  
To set up, create a file called `docker-compose.yml` and the following configuration.  
You are also encouraged to modify these to meet your specific needs:  

~~~yaml
version: '3.7'
services:
    musicbot:
        image: yournamehere/musicbot:latest
        restart: unless-stopped
        volumes:
            - ./config:/musicbot/config
            - /mnt/storage/musicbot_cache:/musicbot/audio_cache # optional. relocate the audio cache with this
~~~

Make sure to change the above image name (`yournamehere/musicbot:latest`) to match the name 
you used when building the image.  
This file can be used with docker-compose, but you may want to 
[Configure]({{ site.baseurl }}/using/configuration) MusicBot before you start it.  
