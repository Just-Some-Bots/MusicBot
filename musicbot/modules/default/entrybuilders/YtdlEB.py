from .BaseEB import BaseEB
from urllib.parse import urlparse, urljoin
import re
import os

from ....ytdldownloader import get_entry, get_unprocessed_entry
from .... import messagemanager
from .... import exceptions

class YtdlEB(BaseEB):
    def __init__(self, bot):
        super().__init__(bot)

    async def _get_url_info(self, song_url):
        info = await self.bot.downloader.extract_info(song_url, download=False, process=False)
        # If there is an exception arise when processing we go on and let extract_info down the line report it
        # because info might be a playlist and thing that's broke it might be individual entry
        try:
            info_process = await self.bot.downloader.extract_info(song_url, download=False)
            info_process_err = None
        except Exception as e:
            info_process = None
            info_process_err = e

        return (info, info_process, info_process_err)

    async def suitable(self, ctx, url):
        info = await self.bot.downloader.extract_info(url, download=False, process=False)
        if not info:
            raise exceptions.ExtractionError(
                self.bot.str.get('cmd-play-noinfo', "That video cannot be played. Try using the {0}stream command.").format(self.bot.config.command_prefix),
                expire_in=30
            )

        if ctx:
            permissions = self.bot.permissions.for_user(ctx.author)
            if info.get('extractor', '') not in permissions.extractors and permissions.extractors:
                raise exceptions.PermissionsError(
                    self.bot.str.get('cmd-play-badextractor', "You do not have permission to play media from this service."), expire_in=30
                )
        
        return True

    async def get_entry(self, ctx, url, process = True):
        '''
        get entry (or entries) for given url
        '''
        # Make sure forward slashes work properly in search queries
        linksRegex = '((http(s)*:[/][/]|www.)([a-z]|[A-Z]|[0-9]|[/.]|[~])*)'
        pattern = re.compile(linksRegex)
        matchUrl = pattern.match(url)
        url = url.replace('/', '%2F') if matchUrl is None else url

        # Rewrite YouTube playlist URLs if the wrong URL type is given
        playlistRegex = r'watch\?v=.+&(list=[^&]+)'
        matches = re.search(playlistRegex, url)
        groups = matches.groups() if matches is not None else []
        url = "https://www.youtube.com/playlist?" + groups[0] if len(groups) > 0 else url

        # If not process then just return unprocessed entry
        if not process:
            async def _get_entry_iterator():
                # IF PY35 DEPRECATED
                # yield await get_unprocessed_entry(url, ctx.author.id if ctx else None, self.bot.downloader, {'channel_id':ctx.channel.id} if ctx else None)
                return [get_unprocessed_entry(url, ctx.author.id if ctx else None, self.bot.downloader, {'channel_id':ctx.channel.id} if ctx else None)]
                # END IF DEPRECATED
            return (1, _get_entry_iterator())

        # Try to determine entry type, if _type is playlist then there should be entries
        while True:
            info, info_process, info_process_err = await self._get_url_info(url)
            if info_process and info:
                if info_process.get('_type', None) == 'playlist' and not ('entries' in info or info.get('url', '').startswith('ytsearch')):
                    use_url = info_process.get('webpage_url', None) or info_process.get('url', None)
                    if use_url == url:
                        self.bot.log.warning("Determined incorrect entry type, but suggested url is the same.  Help.")
                        break # If we break here it will break things down the line and give "This is a playlist" exception as a result

                    self.bot.log.debug("Assumed url \"%s\" was a single entry, was actually a playlist" % url)
                    self.bot.log.debug("Using \"%s\" instead" % use_url)
                    url = use_url
                    continue
            
            break

            if info_process_err:
                if 'unknown url type' in str(info_process_err):
                    url = url.replace(':', '')  # it's probably not actually an extractor
                    info, info_process, info_process_err = await self._get_url_info(url)
                else:
                    raise exceptions.ExtractionError(str(info_process_err), expire_in=30)

        # abstract the search handling away from the user
        # our ytdl options allow us to use search strings as input urls
        if info.get('url', '').startswith('ytsearch'):
            # print("[Command:play] Searching for \"%s\"" % url)
            if info_process:
                info = info_process
            else:
                if ctx:
                    await messagemanager.safe_send_normal(ctx, ctx, "```\n%s\n```" % info_process_err, expire_in=120)
                raise exceptions.CommandError(
                    self.bot.str.get(
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

        if 'entries' in info:
            entries = list(info_process['entries'])

            if self.bot.config.lazy_playlist:
                entry_initializer = get_unprocessed_entry
            else:
                entry_initializer = get_entry

            async def _get_entry_iterator():
                # IF PY35 DEPRECATED
                # for entry_proc in entries:
                #     if not entry_proc:
                #         yield None
                #         continue
                #     url = entry_proc.get('webpage_url', None) or entry_proc.get('url', None)
                #     try:
                #         entry_proc_o = await entry_initializer(url, ctx.author.id if ctx else None, self.bot.downloader, {'channel_id':ctx.channel.id} if ctx else None)
                #     except Exception as e:
                #         self.bot.log.info(e)
                #         yield None
                #         continue
                #     yield entry_proc_o
                entry_list = list()
                for entry_proc in entries:
                    if not entry_proc:
                        entry_list.append(None)
                        continue
                    url = entry_proc.get('webpage_url', None) or entry_proc.get('url', None)
                    entry_list.append(entry_initializer(url, ctx.author.id if ctx else None, self.bot.downloader, {'channel_id':ctx.channel.id} if ctx else None))
                return entry_list   
                # END IF DEPRECATED      

            return (len(entries), _get_entry_iterator())

        else:
            async def _get_entry_iterator():
                # IF PY35 DEPRECATED
                # yield await get_entry(url, ctx.author.id if ctx else None, self.bot.downloader, {'channel_id':ctx.channel.id} if ctx else None)
                return [get_entry(url, ctx.author.id if ctx else None, self.bot.downloader, {'channel_id':ctx.channel.id} if ctx else None)]
                # END IF DEPRECATED

            return (1, _get_entry_iterator())
