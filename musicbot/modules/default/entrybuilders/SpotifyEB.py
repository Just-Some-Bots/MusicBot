from .BaseEB import BaseEB
from .YtdlEB import YtdlEB

import itertools
import re

from .... import messagemanager
from .... import exceptions

class SpotifyEB(BaseEB):
    def __init__(self, ytdl_eb):
        super().__init__(ytdl_eb.bot)
        self.ytdl_eb = ytdl_eb
    
    async def _get_entry_iterator(self, ctx, url_iterable, process = True):
        for url in url_iterable:
            self.bot.log.debug('Processing {0}'.format(url))
            # IF PY35 DEPRECATED
            # return (await self.ytdl_eb.get_entry(ctx, url))[1]
            return await (await self.ytdl_eb.get_entry(ctx, url, process = process))[1]
            # END IF DEPRECATED

    async def suitable(self, ctx, url):
        return self.bot.config._spotify and ('open.spotify.com' in url or url.startswith('spotify:'))

    async def get_entry(self, ctx, url, process = True):
        '''
        get entry (or entries) for given url
        '''
        if 'open.spotify.com' in url:
            # remove session id (and other query stuff)
            url = re.sub(r'\?.*', '', url)
            url = 'spotify:' + re.sub(r'(http[s]?://)?(open.spotify.com)/', '', url).replace('/', ':')

        if url.startswith('spotify:'):
            parts = url.split(":")
            try:
                if 'track' in parts:
                    res = await self.bot.spotify.get_track(parts[-1])

                    return (
                        1,
                        self._get_entry_iterator(
                            ctx,
                            (res['artists'][0]['name'] + ' ' + res['name'], ), 
                            process = process
                        )
                    )

                elif 'album' in parts:
                    res = await self.bot.spotify.get_album(parts[-1])
                    # procmesg = await messagemanager.safe_send_normal(ctx, ctx, ctx.bot.str.get('cmd-play-spotify-album-process', 'Processing album `{0}` (`{1}`)').format(res['name'], song_url))
                                  
                    return (
                        len(res['tracks']['items']),
                        self._get_entry_iterator(
                            ctx,
                            (i['name'] + ' ' + i['artists'][0]['name'] for i in res['tracks']['items']), 
                            process = process
                        )
                    )                    

                    # await messagemanager.safe_delete_message(procmesg)
                    # await messagemanager.safe_send_normal(ctx, ctx, ctx.bot.str.get('cmd-play-spotify-album-queued', "Enqueued `{0}` with **{1}** songs.").format(res['name'], len(res['tracks']['items'])))

                elif 'playlist' in parts:
                    res = []
                    r = await self.bot.spotify.get_playlist_tracks(parts[-1])
                    while True:
                        res.extend(r['items'])
                        if r['next'] is not None:
                            r = await self.bot.spotify.make_spotify_req(r['next'])
                            continue
                        else:
                            break
                    # procmesg = await messagemanager.safe_send_normal(ctx, ctx, ctx.bot.str.get('cmd-play-spotify-playlist-process', 'Processing playlist `{0}` (`{1}`)').format(parts[-1], song_url))
                    
                    return (
                        len(res),
                        self._get_entry_iterator(
                            ctx,
                            (i['track']['name'] + ' ' + i['track']['artists'][0]['name'] for i in res), 
                            process = process
                        )
                    )
                    
                    # await messagemanager.safe_delete_message(procmesg)
                    # await messagemanager.safe_send_normal(ctx, ctx, ctx.bot.str.get('cmd-play-spotify-playlist-queued', "Enqueued `{0}` with **{1}** songs.").format(parts[-1], len(res)))
                    return

                else:
                    raise exceptions.ExtractionError(self.bot.str.get('cmd-play-spotify-unsupported', 'That is not a supported Spotify URI.'), expire_in=30)

            except exceptions.SpotifyError:
                raise exceptions.ExtractionError(self.bot.str.get('cmd-play-spotify-invalid', 'You either provided an invalid URI, or there was a problem.'))