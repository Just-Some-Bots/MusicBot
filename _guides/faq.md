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

Discord has native support for listening to music with friends using Spotify. If you want to use the bot solely to listen to Spotify music with friends, you should use the native feature instead. For more information, see [their page](https://support.spotify.com/uk/using_spotify/app_integrations/discord/).
{: .info }

MusicBot has limited integration with Spotify, in that it automatically converts Spotify URIs (e.g `spotify:track:5SE57ljOIUJ1ybL9U6CuBH`) to their nearest match equivalents on YouTube. Full integration isn't possible because Spotify does not allow you to stream or download full tracks per its Terms of Service, but this is a reasonable alternative. To enable it, follow these steps:

1. First, create a new [Spotify application](https://beta.developer.spotify.com/dashboard/applications). You will be asked to login to a Spotify account. Do so, and then click 'Create an app' at the top right and then 'No' when asked if you're developing a commercial integration. Name it what you like, and give it a short description. Tick all three boxes, then press 'Create'.
2. Finally, [configure](#guidesconfiguration) your bot with your Spotify client ID and client secret, both obtainable on your Spotify application page. Restart the bot, and provided your details are okay, you will be able to use Spotify URIs with the `!play` command.

#### Can I change the bot's responses?

If you would like to change the bot's responses, perhaps because your users have a different native language, it is possible without editing the bot's source code. As long as you have a basic understanding of JSON, you can create a new i18n file. Open up the `config/i18n` folder, copy `en.json` to `whatever.json`, and then open it up with a code editor (such as Notepad++, Atom, or Visual Studio Code).

It will look something like this:

```json
{
    "cmd-resetplaylist-response": "The server's autoplaylist has been reset.",
    "cmd-help-invalid": "No such command",
    ...
}
```

You can then change the values (after the colon on each line) to whatever you like. Make sure that you preserve variables that look like `{0}` and `%s` to ensure the bot can automatically insert things there.

Finally, ensure that your JSON is formatted correctly and valid, by pasting it into a tool like [JSONLint](https://jsonlint.com/), and then change the option `i18nFile` in your config file to equal `config/i18n/whatever.json`. Launch the bot, and off you go! If your file can't be loaded, the bot will try to fallback to the default (`en.json`). If it can't do that, it will throw an error.