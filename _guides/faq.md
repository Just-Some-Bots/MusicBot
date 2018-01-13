---
title: FAQ
position: 5
---

#### How do I get an ID?

<img class="doc-img" src="images/ids.gif" alt="IDs" style="width: 500px;"/>

The bot has a `!listids` command that you can use to obtain IDs, or you can turn on Developer Mode in the Discord client by going to User Settings -> Appearance. Afterwards, you can right-click on any user, channel, role, whatever and you will get a Copy ID option on the context menu. The GIF demonstrates this.

#### What can the bot play?

The bot was developed to support YouTube and SoundCloud URLs, but it can theoretically support most of what youtube-dl [supports](https://rg3.github.io/youtube-dl/supportedsites.html). If there is a site that isn't supported by the bot but is by youtube-dl, create an [issue](https://github.com/Just-Some-Bots/MusicBot/issues/new) and let us know you want support added for it. The bot supports also streams like Twitch and internet radio (provided you give it a direct URL), however it is an experimental feature. To do this, use the `!stream` command instead of `!play`.

Currently, the bot can't play music that is saved on your computer locally, though it is a [planned feature](https://github.com/Just-Some-Bots/MusicBot/issues/168).

#### Can I modify the bot?

MusicBot is licensed under MIT. If you want to modify it, you can. Please bare in mind that we won't give any support for you doing this. If you don't know how to write asynchronous code in Python, don't even attempt this.

#### How do I enable Spotify integration?

This is an **upcoming feature** and is not yet available in the latest version of the bot.
{: .error }

MusicBot has limited integration with Spotify, in that it automatically converts Spotify URIs (e.g `spotify:track:5SE57ljOIUJ1ybL9U6CuBH`) to their nearest match equivalents on YouTube. Full integration isn't possible because Spotify does not allow you to stream or download full tracks per its Terms of Service, but this is a reasonable alternative. To enable it, follow these steps:

1. First, create a new [Spotify application](https://beta.developer.spotify.com/dashboard/applications). You will be asked to login to a Spotify account. Do so, and then click 'Create an app' at the top right and then 'No' when asked if you're developing a commercial integration. Name it what you like, and give it a short description. Tick all three boxes, then press 'Create'.
2. Finally, [configure](#guidesconfiguration) your bot with your Spotify client ID and client secret, both obtainable on your Spotify application page. Restart the bot, and provided your details are okay, you will be able to use Spotify URIs with the `!play` command.