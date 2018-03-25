---
title: Spotify
category: Using the bot
order: 5
---

> Discord has native support for listening to music with friends using Spotify. If you want to use the bot solely to listen to Spotify music with friends, you should use the native feature instead. For more information, see [their page](https://support.spotify.com/uk/using_spotify/app_integrations/discord/).

MusicBot has limited integration with Spotify, in that it automatically converts Spotify URIs to their nearest match equivalents on YouTube. Full integration isn't possible because Spotify does not allow you to stream or download full tracks per its Terms of Service, but this is a reasonable alternative.

## Enabling Spotify integration

1. First, create a new [Spotify application](https://beta.developer.spotify.com/dashboard/applications). You will be asked to login to a Spotify account. Do so, and then click 'Create an app' at the top right and then 'No' when asked if you're developing a commercial integration. Name it what you like, and give it a short description. Tick all three boxes, then press 'Create'.
2. Finally, [configure](/using/configuration) your bot with your Spotify client ID and client secret, both obtainable on your Spotify application page. Restart the bot, and provided your details are okay, you will be able to use Spotify URIs with the `!play` command.

## Supported URIs

* Tracks (e.g `spotify:track:5SE57ljOIUJ1ybL9U6CuBH`)
* Albums (e.g `spotify:album:4ONwe8mcjVjNrzk9QL4H2w`)
* User playlists (e.g `spotify:user:topsify:playlist:1QM1qz09ZzsAPiXphF1l4S`)

## How to get a URI
Right-click on any supported media in the Spotify application, go to Share, then Copy Spotify URI.

<img class="doc-img" src="{{ site.baseurl }}/images/spotify-uri.png" alt="Spotify URI example" style="width: 500px;"/>