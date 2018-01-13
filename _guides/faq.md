---
title: FAQ
position: 5
---

#### How do I get an ID?

<img class="doc-img" src="images/ids.gif" alt="IDs" style="width: 500px;"/>

The bot has a `listids` command that you can use to obtain IDs, or you can turn on Developer Mode in the Discord client by going to User Settings -> Appearance. Afterwards, you can right-click on any user, channel, role, whatever and you will get a Copy ID option on the context menu. The GIF demonstrates this.

#### What can the bot play?

The bot was developed to support YouTube and SoundCloud URLs, but it can theoretically support most of what youtube-dl [supports](https://rg3.github.io/youtube-dl/supportedsites.html). If there is a site that isn't supported by the bot but is by youtube-dl, create an [issue](https://github.com/Just-Some-Bots/MusicBot/issues/new) and let us know you want support added for it. The bot supports also streams like Twitch and internet radio (provided you give it a direct URL), however it is an experimental feature. To do this, use the `stream` command instead of `play`.

Currently, the bot can't play music that is saved on your computer locally, though it is a [planned feature](https://github.com/Just-Some-Bots/MusicBot/issues/168).

#### Can I modify the bot?

MusicBot is licensed under MIT. If you want to modify it, you can. Please bare in mind that we won't give any support for you doing this. If you don't know how to write asynchronous code in Python, don't even attempt this.