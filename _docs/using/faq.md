---
title: FAQ
category: Using the bot
order: 7
---

## How do I get an ID?

<img class="doc-img-right" src="{{ site.baseurl }}/images/ids.gif" alt="Example of getting discord IDs"/>

The bot has a `!listids` command that you can use to obtain IDs, or you can turn on Developer Mode in the Discord client by going to User Settings -> Appearance. Afterwards, you can right-click on any user, channel, role, whatever and you will get a Copy ID option on the context menu. The GIF demonstrates this.

## What can the bot play?

MusicBot depends on yt-dlp and ffmpeg to get and play media.  
In theory, you can play any media ffmpeg can play from any service listed on [yt-dlp supported sites](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md).  

MusicBot also supports playing streams like Twitch and internet radio streams. 
To do this, use the `!stream` command instead of `!play` and provide a direct URL 
to the media stream.  

In recent `dev` branch versions, MusicBot optionally supports playing media files 
which can be manually uploaded to the `media` directory at the root of MusicBot directory.  

If you supply an attachment to the `!play` command, MusicBot will also attempt to play the first attachment.  

## How can I sign into youtube?

You'll need to research what [yt-dlp](https://github.com/yt-dlp/yt-dlp/) recommends as the modern method of choice.  

MusicBot provides support for using `--cookies` with yt-dlp.  
You can place your cookies file in `data/cookies.txt` or optionally use the [`setcookies` command]({{ site.baseurl }}/using/commands).
The cookies should be in Netscape format.  
Extractor plugins:
- [Chrome (Chromium, etc.)](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)  
- [Firefox](https://github.com/hrdl-github/cookies-txt)  


## Can I modify the bot?

MusicBot is provided under an MIT License.  
Under this license you are allowed to modify the source code as you please!  
Understand that you may be on your own getting support for MusicBot with modifications.  
It is recommended that you are familiar with Python and the Asyncio library first.  

If your modifications are general improvements, please consider contributing your changes to improve MusicBot for everyone.  

## Can I change the bot's responses?

Short answer is yes!  
There are several options which impact how bot responds, in addition to using translation 
files to modify the content or format of messages sent by the bot.  

#### After the UI/i18n PR #2436

MusicBot is almost fully translation ready, allowing you to translate or modify 
text used by MusicBot in both Discord messages and MusicBot logs.  
Translations use the Gettext format.  For more information, see the [i18n readme](https://github.com/Just-Some-Bots/MusicBot/blob/dev/i18n/readme.md).

#### Before the UI/i18n PR #2436

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
