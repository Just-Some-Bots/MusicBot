from .BaseEB import BaseEB
from urllib.parse import urlparse, urljoin
import re
import os

from ....ytdldownloader import get_entry, get_unprocessed_entry
from .... import messagemanager
from .... import exceptions

async def _get_url_info(ctx, song_url):
    info = await ctx.bot.downloader.extract_info(song_url, download=False, process=False)
    # If there is an exception arise when processing we go on and let extract_info down the line report it
    # because info might be a playlist and thing that's broke it might be individual entry
    try:
        info_process = await ctx.bot.downloader.extract_info(song_url, download=False)
        info_process_err = None
    except Exception as e:
        info_process = None
        info_process_err = e

    return (info, info_process, info_process_err)

class YtdlEB(BaseEB):
    @classmethod
    async def suitable(cls, ctx, url):
        info = await ctx.bot.downloader.extract_info(url, download=False, process=False)
        permissions = ctx.bot.permissions.for_user(ctx.author)

        if not info:
            raise exceptions.ExtractionError(
                ctx.bot.str.get('cmd-play-noinfo', "That video cannot be played. Try using the {0}stream command.").format(ctx.bot.config.command_prefix),
                expire_in=30
            )

        if info.get('extractor', '') not in permissions.extractors and permissions.extractors:
            raise exceptions.PermissionsError(
                ctx.bot.str.get('cmd-play-badextractor', "You do not have permission to play media from this service."), expire_in=30
            )
        
        return True

    @classmethod
    async def get_entry(cls, ctx, url):
        '''
        get entry (or entries) for given url
        '''
        # Make sure forward slashes work properly in search queries
        linksRegex = '((http(s)*:[/][/]|www.)([a-z]|[A-Z]|[0-9]|[/.]|[~])*)'
        pattern = re.compile(linksRegex)
        matchUrl = pattern.match(url)
        url = url.replace('/', '%2F') if matchUrl is None else song_url

        # Rewrite YouTube playlist URLs if the wrong URL type is given
        playlistRegex = r'watch\?v=.+&(list=[^&]+)'
        matches = re.search(playlistRegex, url)
        groups = matches.groups() if matches is not None else []
        url = "https://www.youtube.com/playlist?" + groups[0] if len(groups) > 0 else url

        # Try to determine entry type, if _type is playlist then there should be entries
        while True:
            info, info_process, info_process_err = await _get_url_info(ctx, song_url)
            if info_process and info:
                if info_process.get('_type', None) == 'playlist' and not ('entries' in info or info.get('url', '').startswith('ytsearch')):
                    use_url = info_process.get('webpage_url', None) or info_process.get('url', None)
                    if use_url == song_url:
                        ctx.bot.log.warning("Determined incorrect entry type, but suggested url is the same.  Help.")
                        break # If we break here it will break things down the line and give "This is a playlist" exception as a result

                    ctx.bot.log.debug("Assumed url \"%s\" was a single entry, was actually a playlist" % song_url)
                    ctx.bot.log.debug("Using \"%s\" instead" % use_url)
                    song_url = use_url
                    continue
            
            break

            if info_process_err:
                if 'unknown url type' in str(info_process_err):
                    song_url = song_url.replace(':', '')  # it's probably not actually an extractor
                    info, info_process, info_process_err = await _get_url_info(ctx, song_url)
                else:
                    raise exceptions.ExtractionError(str(info_process_err), expire_in=30)

        # abstract the search handling away from the user
        # our ytdl options allow us to use search strings as input urls
        if info.get('url', '').startswith('ytsearch'):
            # print("[Command:play] Searching for \"%s\"" % song_url)
            if info_process:
                info = info_process
            else:
                await messagemanager.safe_send_normal(ctx, ctx, "```\n%s\n```" % info_process_err, expire_in=120)
                raise exceptions.CommandError(
                    ctx.bot.str.get(
                        'cmd-play-nodata', 
                        "Error extracting info from search string, youtubedl returned no data. "
                        "You may need to restart the bot if this continues to happen."
                    ), 
                    expire_in=30
                )

            url = info_process.get('webpage_url', None) or info_process.get('url', None)

            if 'entries' in info:
                # if entry is playlist then only get the first one
                url = info['entries'][0]['webpage_url']
                info = info['entries'][0]

        if 'entries' in info_process:
            entries = list(info_process['entries'])
            yield len(entries)

            if ctx.bot.config.lazy_playlist:
                entry_initializer = get_unprocessed_entry
            else:
                entry_initializer = get_entry

            for entry_proc in entries:
                if not entry_proc:
                    yield None
                    continue
                url = entry_proc.get('webpage_url', None) or entry_proc.get('url', None)
                try:
                    entry_proc_o = await entry_initializer(url, ctx.author.id, ctx.bot.downloader, {'channel_id':ctx.channel.id})
                except Exception as e:
                    ctx.bot.log.info(e)
                    yield None
                    continue
                yield entry_proc_o

        else:
            yield get_entry(url, ctx.author.id, ctx.bot.downloader, {'channel_id':ctx.channel.id})
