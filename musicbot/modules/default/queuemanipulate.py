import time
import re
import asyncio
import traceback
import logging
import shlex
import random
import math
from typing import Optional, Union
from datetime import timedelta
from collections import defaultdict

from textwrap import dedent

from discord.ext.commands import Cog, command, Greedy
from discord import User

from ...utils import fixg, ftimedelta, _func_
from ... import exceptions

from ... import messagemanager
from ...rich_guild import get_guild
from ...playback import PlayerState
from ...ytdldownloader import get_stream_entry, get_entry

log = logging.getLogger(__name__)

cog_name = 'queue_management'

class QueueManagement(Cog):
    def __init__(self):
        self._aiolocks = defaultdict(asyncio.Lock)
        self.bot = None

    def pre_init(self, bot):
        self.bot = bot
        self.bot.crossmodule.register_object('_play', self._play)

    def uninit(self):
        self.bot.crossmodule.unregister_object('_play')

    async def _do_playlist_checks(self, ctx, testobj):
        guild = get_guild(ctx.bot, ctx.guild)
        player = await guild.get_player()

        num_songs = sum(1 for _ in testobj)

        permissions = ctx.bot.permissions.for_user(ctx.author)

        # I have to do exe extra checks anyways because you can request an arbitrary number of search results
        if not permissions.allow_playlists and num_songs > 1:
            raise exceptions.PermissionsError(ctx.bot.str.get('playlists-noperms', "You are not allowed to request playlists"), expire_in=30)

        if permissions.max_playlist_length and num_songs > permissions.max_playlist_length:
            raise exceptions.PermissionsError(
                ctx.bot.str.get('playlists-big', "Playlist has too many entries ({0} > {1})").format(num_songs, permissions.max_playlist_length),
                expire_in=30
            )

        # This is a little bit weird when it says (x + 0 > y), I might add the other check back in
        if permissions.max_songs and player.playlist.num_entry_of(ctx.author.id) + num_songs > permissions.max_songs:
            raise exceptions.PermissionsError(
                ctx.bot.str.get('playlists-limit', "Playlist entries + your already queued songs reached limit ({0} + {1} > {2})").format(
                    num_songs, player.playlist.num_entry_of(ctx.author.id), permissions.max_songs),
                expire_in=30
            )
        return True

    @command()
    async def play(self, ctx, *song_url):
        """
        Usage:
            {command_prefix}play song_link
            {command_prefix}play text to search for
            {command_prefix}play spotify_uri

        Adds the song to the playlist.  If a link is not provided, the first
        result from a youtube search is added to the queue.

        If enabled in the config, the bot will also support Spotify URIs, however
        it will use the metadata (e.g song name and artist) to find a YouTube
        equivalent of the song. Streaming from Spotify is not possible.
        """
        guild = get_guild(ctx.bot, ctx.guild)
        playlist = await guild.get_playlist()
        await self._play(ctx, playlist, song_url = ' '.join(song_url))

    @command()
    async def replay(self, ctx, option= None):
        """
        Usage:
            {command_prefix}replay [head/h]

        Add currently playing song to the end queue, if added 'head' or 'h' to the
        command current entry will be added to the head of the queue instead.
        """
        guild = get_guild(ctx.bot, ctx.guild)
        player = await guild.get_player()
        playlist = await guild.get_playlist()
        current_entry = await player.get_current_entry()

        head = False
        if option in ['head', 'h']:
            head = True

        await self._play(ctx, playlist, current_entry.source_url, head = head)

    async def _play(self, ctx, playlist, song_url, *, head=False, send_reply=True):
        guild = get_guild(ctx.bot, ctx.guild)

        permissions = ctx.bot.permissions.for_user(ctx.author)

        song_url = song_url.strip('<>')

        # Make sure forward slashes work properly in search queries
        linksRegex = '((http(s)*:[/][/]|www.)([a-z]|[A-Z]|[0-9]|[/.]|[~])*)'
        pattern = re.compile(linksRegex)
        matchUrl = pattern.match(song_url)
        song_url = song_url.replace('/', '%2F') if matchUrl is None else song_url

        # Rewrite YouTube playlist URLs if the wrong URL type is given
        playlistRegex = r'watch\?v=.+&(list=[^&]+)'
        matches = re.search(playlistRegex, song_url)
        groups = matches.groups() if matches is not None else []
        song_url = "https://www.youtube.com/playlist?" + groups[0] if len(groups) > 0 else song_url

        if ctx.bot.config._spotify:
            if 'open.spotify.com' in song_url:
                # remove session id (and other query stuff)
                song_url = re.sub('\?.*', '', song_url)
                song_url = 'spotify:' + re.sub('(http[s]?:\/\/)?(open.spotify.com)\/', '', song_url).replace('/', ':') # pylint: disable=anomalous-backslash-in-string
            if song_url.startswith('spotify:'):
                parts = song_url.split(":")
                try:
                    if 'track' in parts:
                        res = await ctx.bot.spotify.get_track(parts[-1])
                        song_url = res['artists'][0]['name'] + ' ' + res['name'] 

                    elif 'album' in parts:
                        res = await ctx.bot.spotify.get_album(parts[-1])
                        await self._do_playlist_checks(ctx, res['tracks']['items'])
                        procmesg = await messagemanager.safe_send_normal(ctx, ctx, ctx.bot.str.get('cmd-play-spotify-album-process', 'Processing album `{0}` (`{1}`)').format(res['name'], song_url))
                        for i in res['tracks']['items']:
                            song_url = i['name'] + ' ' + i['artists'][0]['name']
                            ctx.bot.log.debug('Processing {0}'.format(song_url))
                            await self._play(ctx, playlist, song_url = song_url, head = head, send_reply = send_reply)
                        await messagemanager.safe_delete_message(procmesg)
                        await messagemanager.safe_send_normal(ctx, ctx, ctx.bot.str.get('cmd-play-spotify-album-queued', "Enqueued `{0}` with **{1}** songs.").format(res['name'], len(res['tracks']['items'])))
                        return

                    elif 'playlist' in parts:
                        res = []
                        r = await ctx.bot.spotify.get_playlist_tracks(parts[-1])
                        while True:
                            res.extend(r['items'])
                            if r['next'] is not None:
                                r = await ctx.bot.spotify.make_spotify_req(r['next'])
                                continue
                            else:
                                break
                        await self._do_playlist_checks(ctx, res)
                        procmesg = await messagemanager.safe_send_normal(ctx, ctx, ctx.bot.str.get('cmd-play-spotify-playlist-process', 'Processing playlist `{0}` (`{1}`)').format(parts[-1], song_url))
                        for i in res:
                            song_url = i['track']['name'] + ' ' + i['track']['artists'][0]['name']
                            ctx.bot.log.debug('Processing {0}'.format(song_url))
                            await self._play(ctx, playlist, song_url = song_url, head=head, send_reply=send_reply)
                        await messagemanager.safe_delete_message(procmesg)
                        await messagemanager.safe_send_normal(ctx, ctx, ctx.bot.str.get('cmd-play-spotify-playlist-queued', "Enqueued `{0}` with **{1}** songs.").format(parts[-1], len(res)))
                        return

                    else:
                        raise exceptions.ExtractionError(ctx.bot.str.get('cmd-play-spotify-unsupported', 'That is not a supported Spotify URI.'), expire_in=30)
                except exceptions.SpotifyError:
                    raise exceptions.ExtractionError(ctx.bot.str.get('cmd-play-spotify-invalid', 'You either provided an invalid URI, or there was a problem.'))

        # This lock prevent spamming play command to add entries that exceeds time limit/ maximum song limit
        async with self._aiolocks[_func_() + ':' + str(ctx.author.id)]:
            if permissions.max_songs and playlist.num_entry_of(ctx.author.id) >= permissions.max_songs:
                raise exceptions.PermissionsError(
                    ctx.bot.str.get('cmd-play-limit', "You have reached your enqueued song limit ({0})").format(permissions.max_songs), expire_in=30
                )

            if playlist.karaoke_mode and not permissions.bypass_karaoke_mode:
                raise exceptions.PermissionsError(
                    ctx.bot.str.get('karaoke-enabled', "Karaoke mode is enabled, please try again when its disabled!"),
                    expire_in=30
                )

            # Try to determine entry type, if _type is playlist then there should be entries
            while True:
                try:
                    info = await ctx.bot.downloader.extract_info(song_url, download=False, process=False)
                    try:
                        info_process = await ctx.bot.downloader.safe_extract_info(song_url, download=False)
                    except:
                        info_process = None
                    if info_process and info and info_process.get('_type', None) == 'playlist' and 'entries' not in info and not info.get('url', '').startswith('ytsearch'):
                        use_url = info_process.get('webpage_url', None) or info_process.get('url', None)
                        if use_url == song_url:
                            ctx.bot.log.warning("Determined incorrect entry type, but suggested url is the same.  Help.")
                            break # If we break here it will break things down the line and give "This is a playlist" exception as a result

                        ctx.bot.log.debug("Assumed url \"%s\" was a single entry, was actually a playlist" % song_url)
                        ctx.bot.log.debug("Using \"%s\" instead" % use_url)
                        song_url = use_url
                    else:
                        break

                except Exception as e:
                    if 'unknown url type' in str(e):
                        song_url = song_url.replace(':', '')  # it's probably not actually an extractor
                        info = await ctx.bot.downloader.extract_info(song_url, download=False, process=False)
                    else:
                        raise exceptions.ExtractionError(str(e), expire_in=30)

            if not info:
                raise exceptions.ExtractionError(
                    ctx.bot.str.get('cmd-play-noinfo', "That video cannot be played. Try using the {0}stream command.").format(ctx.bot.config.command_prefix),
                    expire_in=30
                )

            if info.get('extractor', '') not in permissions.extractors and permissions.extractors:
                raise exceptions.PermissionsError(
                    ctx.bot.str.get('cmd-play-badextractor', "You do not have permission to play media from this service."), expire_in=30
                )

            # abstract the search handling away from the user
            # our ytdl options allow us to use search strings as input urls
            if info.get('url', '').startswith('ytsearch'):
                # print("[Command:play] Searching for \"%s\"" % song_url)
                info = await ctx.bot.downloader.extract_info(
                    song_url,
                    download=False,
                    process=True,    # ASYNC LAMBDAS WHEN
                    on_error=lambda e: asyncio.ensure_future(
                        messagemanager.safe_send_normal(ctx, ctx, "```\n%s\n```" % e, expire_in=120),
                        loop=ctx.bot.loop
                    ),
                    retry_on_error=True
                )

                if not info:
                    raise exceptions.CommandError(
                        ctx.bot.str.get('cmd-play-nodata', "Error extracting info from search string, youtubedl returned no data. "
                                                           "You may need to restart the bot if this continues to happen."), expire_in=30
                    )

                if not all(info.get('entries', [])):
                    # empty list, no data
                    ctx.bot.log.debug("Got empty list, no data")
                    return

                # TODO: handle 'webpage_url' being 'ytsearch:...' or extractor type
                song_url = info['entries'][0]['webpage_url']
                info = await ctx.bot.downloader.extract_info(song_url, download=False, process=False)
                info_process = await ctx.bot.downloader.extract_info(song_url, download=False)
                # Now I could just do: return await self.cmd_play(player, channel, author, song_url)
                # But this is probably fine

            async with self._aiolocks['play_{}'.format(ctx.author.id)]:
                async with ctx.typing():
                    # If it's playlist
                    if 'entries' in info:
                        entries = list(info_process['entries'])
                        await self._do_playlist_checks(ctx, entries)

                        num_songs = sum(1 for _ in entries)

                        num_songs_playlist = await playlist.num_entry_of(ctx.author.id)
                        total_songs = num_songs + num_songs_playlist

                        t0 = time.time()

                        # My test was 1.2 seconds per song, but we maybe should fudge it a bit, unless we can
                        # monitor it and edit the message with the estimated time, but that's some ADVANCED SHIT
                        # I don't think we can hook into it anyways, so this will have to do.
                        # It would probably be a thread to check a few playlists and get the speed from that
                        # Different playlists might download at different speeds though
                        wait_per_song = 1.2
                        drop_count = 0

                        procmesg = await messagemanager.safe_send_normal(
                            ctx,
                            ctx,
                            'Gathering playlist information for {0} songs{1}'.format(
                                num_songs,
                                ', ETA: {0} seconds'.format(
                                    fixg(num_songs * wait_per_song)
                                ) if num_songs >= 10 else '.'
                            )
                        )

                        # TODO: I can create an event emitter object instead, add event functions, and every play list might be asyncified
                        #       Also have a "verify_entry" hook with the entry as an arg and returns the entry if its ok

                        entry = None
                        position = None
                        for entry_proc in entries:
                            if not entry_proc:
                                drop_count += 1
                                continue
                            url = entry_proc.get('webpage_url', None) or entry_proc.get('url', None)
                            try:
                                entry_proc_o = await get_entry(url, ctx.author.id, ctx.bot.downloader, {'channel_id':ctx.channel.id})
                            except Exception as e:
                                ctx.bot.log.info(e)
                                drop_count += 1
                                continue
                            duration = entry_proc_o.get_duration()
                            if permissions.max_song_length and duration > timedelta(seconds=permissions.max_song_length):
                                drop_count += 1
                                continue
                            position_potent = await playlist.add_entry(entry_proc_o)
                            if not position:
                                entry = entry_proc_o
                                position = position_potent

                        tnow = time.time()
                        ttime = tnow - t0
                        listlen = len(entries)

                        ctx.bot.log.info("Processed {} songs in {} seconds at {:.2f}s/song, {:+.2g}/song from expected ({}s)".format(
                            listlen,
                            fixg(ttime),
                            ttime / listlen if listlen else 0,
                            ttime / listlen - wait_per_song if listlen - wait_per_song else 0,
                            fixg(wait_per_song * num_songs))
                        )

                        await messagemanager.safe_delete_message(procmesg)

                        reply_text = "Enqueued **%s** songs to be played. Position of the first entry in queue: %s"
                        btext = str(listlen - drop_count)

                    # If it's an entry
                    else:
                        if permissions.max_song_length and info.get('duration', 0) > permissions.max_song_length:
                            raise exceptions.PermissionsError(
                                ctx.bot.str.get('cmd-play-song-limit', "Song duration exceeds limit ({0} > {1})").format(info['duration'], permissions.max_song_length),
                                expire_in=30
                            )
                        entry = await get_entry(song_url, ctx.author.id, ctx.bot.downloader, {'channel_id':ctx.channel.id})
                        position = await playlist.add_entry(entry)

                        reply_text = "Enqueued `%s` to be played. Position in queue: %s"
                        btext = entry.title

                    if playlist is (await guild.get_playlist()):
                        await guild.return_from_auto(also_skip=ctx.bot.config.skip_if_auto)

                        player = await guild.get_player()

                        # Position msgs
                        time_until = await player.estimate_time_until_entry(entry)
                        if time_until == timedelta(seconds=0):
                            position = 'Up next!'
                            reply_text %= (btext, position)

                        else:                    
                            reply_text += ' - estimated time until playing: %s'
                            reply_text %= (btext, position, ftimedelta(time_until))

                    else:
                        reply_text %= (btext, position)

            if send_reply:
                await messagemanager.safe_send_normal(ctx, ctx, reply_text)

    @command()
    async def stream(self, ctx, song_url:str):
        """
        Usage:
            {command_prefix}stream song_link

        Enqueue a media stream.
        This could mean an actual stream like Twitch or shoutcast, or simply streaming
        media without predownloading it.  Note: FFmpeg is notoriously bad at handling
        streams, especially on poor connections.  You have been warned.
        """
        guild = get_guild(ctx.bot, ctx.guild)
        player = await guild.get_player()
        playlist = await guild.get_playlist()

        permissions = ctx.bot.permissions.for_user(ctx.author)

        song_url = song_url.strip('<>')

        if permissions.max_songs and (await playlist.num_entry_of(ctx.author.id)) >= permissions.max_songs:
            raise exceptions.PermissionsError(
                ctx.bot.str.get('cmd-stream-limit', "You have reached your enqueued song limit ({0})").format(permissions.max_songs), expire_in=30
            )

        if playlist.karaoke_mode and not permissions.bypass_karaoke_mode:
            raise exceptions.PermissionsError(
                ctx.bot.str.get('karaoke-enabled', "Karaoke mode is enabled, please try again when its disabled!"), expire_in=30
            )

        entry = await get_stream_entry(song_url, ctx.author.id, ctx.bot.downloader, {'channel':ctx.channel})
        position = await playlist.add_entry(entry)

        reply_text = "Enqueued `%s` to be streamed. Position in queue: %s"
        btext = entry.title

        await guild.return_from_auto(also_skip=ctx.bot.config.skip_if_auto)

        # Position msgs
        time_until = await player.estimate_time_until_entry(entry)
        if time_until == timedelta(seconds=0):
            position = 'Up next!'
            reply_text %= (btext, position)

        else:                    
            reply_text += ' - estimated time until streaming: %s'
            reply_text %= (btext, position, ftimedelta(time_until))

        await messagemanager.safe_send_normal(ctx, ctx, ctx.bot.str.get('cmd-stream-success', "Streaming."), expire_in=6)

    @command()
    async def search(self, ctx, *, leftover_args):
        """
        Usage:
            {command_prefix}search [service] [number] query

        Searches a service for a video and adds it to the queue.
        - service: any one of the following services:
            - youtube (yt) (default if unspecified)
            - soundcloud (sc)
            - yahoo (yh)
        - number: return a number of video results and waits for user to choose one
            - defaults to 3 if unspecified
            - note: If your search query starts with a number,
                    you must put your query in quotes
            - ex: {command_prefix}search 2 "I ran seagulls"
        The command issuer can use reactions to indicate their response to each result.
        """
        guild = get_guild(ctx.bot, ctx.guild)
        playlist = await guild.get_playlist()

        permissions = ctx.bot.permissions.for_user(ctx.author)

        if permissions.max_songs and (await playlist.num_entry_of(ctx.author.id)) > permissions.max_songs:
            raise exceptions.PermissionsError(
                ctx.bot.str.get('cmd-search-limit', "You have reached your playlist item limit ({0})").format(permissions.max_songs),
                expire_in=30
            )

        if playlist.karaoke_mode and not permissions.bypass_karaoke_mode:
            raise exceptions.PermissionsError(
                ctx.bot.str.get('karaoke-enabled', "Karaoke mode is enabled, please try again when its disabled!"), expire_in=30
            )

        async def argcheck():
            if not leftover_args:
                # noinspection PyUnresolvedReferences
                raise exceptions.CommandError(
                    ctx.bot.str.get('cmd-search-noquery', "Please specify a search query.\n%s") % dedent(
                        self.search.help_doc.format(command_prefix=ctx.bot.config.command_prefix)),          # pylint: disable=no-member
                    expire_in=60
                )

        await argcheck()

        try:
            leftover_args = shlex.split(' '.join(leftover_args))
        except ValueError:
            raise exceptions.CommandError(ctx.bot.str.get('cmd-search-noquote', "Please quote your search query properly."), expire_in=30)

        service = 'youtube'
        items_requested = 3
        max_items = permissions.max_search_items
        services = {
            'youtube': 'ytsearch',
            'soundcloud': 'scsearch',
            'yahoo': 'yvsearch',
            'yt': 'ytsearch',
            'sc': 'scsearch',
            'yh': 'yvsearch'
        }

        if leftover_args[0] in services:
            service = leftover_args.pop(0)
            await argcheck()

        if leftover_args[0].isdigit():
            items_requested = int(leftover_args.pop(0))
            await argcheck()

            if items_requested > max_items:
                raise exceptions.PermissionsError(ctx.bot.str.get('cmd-search-searchlimit', "You cannot search for more than %s videos") % max_items)

        # Look jake, if you see this and go "what the fuck are you doing"
        # and have a better idea on how to do this, i'd be delighted to know.
        # I don't want to just do ' '.join(leftover_args).strip("\"'")
        # Because that eats both quotes if they're there
        # where I only want to eat the outermost ones
        if leftover_args[0][0] in '\'"':
            lchar = leftover_args[0][0]
            leftover_args[0] = leftover_args[0].lstrip(lchar)
            leftover_args[-1] = leftover_args[-1].rstrip(lchar)

        search_query = '%s%s:%s' % (services[service], items_requested, ' '.join(leftover_args))

        search_msg = await messagemanager.safe_send_normal(ctx, ctx, ctx.bot.str.get('cmd-search-searching', "Searching for videos..."))
        # TODO: context mgr
        await messagemanager.send_typing(ctx)

        try:
            info = await ctx.bot.downloader.extract_info(search_query, download=False, process=True)

        except Exception as e:
            # TODO: embed
            await messagemanager.safe_edit_message(search_msg, str(e), send_if_fail=True)
            return
        else:
            await messagemanager.safe_delete_message(search_msg)

        if not info:
            raise exceptions.ExtractionError(ctx.bot.str.get('cmd-search-none', "No videos found."), expire_in=30)

        for e in info['entries']:
            result_message = await messagemanager.safe_send_normal(ctx, ctx, ctx.bot.str.get('cmd-search-result', "Result {0}/{1}: {2}").format(
                info['entries'].index(e) + 1, len(info['entries']), e['webpage_url']))

            def check(reaction, user):
                return user == ctx.message.author and reaction.message.id == result_message.id  # why can't these objs be compared directly?

            reactions = ['\u2705', '\U0001F6AB', '\U0001F3C1']
            for r in reactions:
                await result_message.add_reaction(r)

            try:
                reaction, user = await ctx.bot.wait_for('reaction_add', timeout=30.0, check=check) # pylint: disable=unused-variable
            except asyncio.TimeoutError:
                await messagemanager.safe_delete_message(result_message)
                return

            if str(reaction.emoji) == '\u2705':  # check
                await messagemanager.safe_delete_message(result_message)
                await self._play(ctx, playlist, song_url = e['webpage_url'])
                await messagemanager.safe_send_normal(ctx, ctx, ctx.bot.str.get('cmd-search-accept', "Alright, coming right up!"), expire_in=30)
                return
            elif str(reaction.emoji) == '\U0001F6AB':  # cross
                await messagemanager.safe_delete_message(result_message)
                continue
            else:
                await messagemanager.safe_delete_message(result_message)
                break

        messagemanager.safe_send_normal(ctx, ctx, ctx.bot.str.get('cmd-search-decline', "Oh well :("), expire_in=30)

    @command()
    async def shuffle(self, ctx):
        """
        Usage:
            {command_prefix}shuffle

        Shuffles the server's queue.
        """
        guild = get_guild(ctx.bot, ctx.guild)
        player = await guild.get_player()
        playlist = await player.get_playlist()

        await playlist.shuffle()

        cards = ['\N{BLACK SPADE SUIT}', '\N{BLACK CLUB SUIT}', '\N{BLACK HEART SUIT}', '\N{BLACK DIAMOND SUIT}']
        random.shuffle(cards)

        hand = await messagemanager.safe_send_normal(ctx, ctx, ' '.join(cards))
        await asyncio.sleep(0.6)

        for x in range(4): # pylint: disable=unused-variable
            random.shuffle(cards)
            await messagemanager.safe_edit_normal(ctx, hand, ' '.join(cards))
            await asyncio.sleep(0.6)

        await messagemanager.safe_delete_message(hand, quiet=True)
        await messagemanager.safe_send_normal(ctx, ctx, ctx.bot.str.get('cmd-shuffle-reply', "Shuffled `{0}`'s queue.").format(guild.guild), expire_in=15)

    @command()
    async def clear(self, ctx):
        """
        Usage:
            {command_prefix}clear

        Clears the playlist.
        """
        guild = get_guild(ctx.bot, ctx.guild)
        player = await guild.get_player()
        playlist = await player.get_playlist()

        await playlist.clear()
        await messagemanager.safe_send_normal(ctx, ctx, ctx.bot.str.get('cmd-clear-reply', "Cleared `{0}`'s queue").format(guild.guild), expire_in=20)

    @command()
    async def remove(self, ctx, index:Optional[Union[int, User]]=None):
        """
        Usage:
            {command_prefix}remove [# in queue]

        Removes queued songs. If a number is specified, removes that song in the queue, otherwise removes the most recently queued song.
        """
        guild = get_guild(ctx.bot, ctx.guild)
        player = await guild.get_player()
        playlist = await player.get_playlist()
        permissions = ctx.bot.permissions.for_user(ctx.author)

        num = await playlist.get_length()

        if num == 0:
            raise exceptions.CommandError(ctx.bot.str.get('cmd-remove-none', "There's nothing to remove!"), expire_in=20)

        if isinstance(index, User):
            if permissions.remove or ctx.author == index:
                try:
                    entry_indexes = [e for e in playlist if e.queuer_id == index.id]
                    for entry in entry_indexes:
                        pos = await playlist.get_entry_position(entry)
                        await playlist.remove_position(pos)
                    entry_text = '%s ' % len(entry_indexes) + 'item'
                    if len(entry_indexes) > 1:
                        entry_text += 's'
                    await messagemanager.safe_send_normal(ctx, ctx, ctx.bot.str.get('cmd-remove-reply', "Removed `{0}` added by `{1}`").format(entry_text, index.name).strip())
                    return

                except ValueError:
                    raise exceptions.CommandError(ctx.bot.str.get('cmd-remove-missing', "Nothing found in the queue from user `%s`") % index.name, expire_in=20)

            raise exceptions.PermissionsError(
                ctx.bot.str.get('cmd-remove-noperms', "You do not have the valid permissions to remove that entry from the queue, make sure you're the one who queued it or have instant skip permissions"),
                expire_in=20
            )

        if not index:
            index = num

        try:
            index = int(index)
        except (TypeError, ValueError):
            raise exceptions.CommandError(ctx.bot.str.get('cmd-remove-invalid', "Invalid number. Use {}queue to find queue positions.").format(ctx.bot.config.command_prefix), expire_in=20)

        if index > num:
            raise exceptions.CommandError(ctx.bot.str.get('cmd-remove-invalid', "Invalid number. Use {}queue to find queue positions.").format(ctx.bot.config.command_prefix), expire_in=20)

        if permissions.remove or ctx.author.id == playlist[index - 1].queuer_id:
            entry = await playlist.remove_position((index - 1))
            if entry.queuer_id:
                await messagemanager.safe_send_normal(ctx, ctx, ctx.bot.str.get('cmd-remove-reply-author', "Removed entry `{0}` added by `{1}`").format(entry.title, guild.guild.get_member(entry.queuer_id)).strip())
                return
            else:
                await messagemanager.safe_send_normal(ctx, ctx, ctx.bot.str.get('cmd-remove-reply-noauthor', "Removed entry `{0}`").format(entry.title).strip())
                return
        else:
            raise exceptions.PermissionsError(
                ctx.bot.str.get('cmd-remove-noperms', "You do not have the valid permissions to remove that entry from the queue, make sure you're the one who queued it or have instant skip permissions"), expire_in=20
            )

    @command()
    async def skip(self, ctx, param:Optional[str]=''):
        """
        Usage:
            {command_prefix}skip [force/f]

        Skips the current song when enough votes are cast.
        Owners and those with the instaskip permission can add 'force' or 'f' after the command to force skip.
        """
        guild = get_guild(ctx.bot, ctx.guild)
        player = await guild.get_player()
        playlist = await player.get_playlist()
        permissions = ctx.bot.permissions.for_user(ctx.author)

        current_entry = await player.get_current_entry()

        permission_force_skip = permissions.instaskip or (ctx.bot.config.allow_author_skip and ctx.author.id == current_entry.queuer_id)
        force_skip = param.lower() in ['force', 'f']

        if permission_force_skip and (force_skip or ctx.bot.config.legacy_skip):
            await player.skip()  # TODO: check autopause stuff here
            await messagemanager.safe_send_normal(
                ctx,
                ctx,
                ctx.bot.str.get('cmd-skip-force', 'Force skipped `{}`.').format(current_entry.title),
                reply=True, 
                expire_in=30
            )

        if not permission_force_skip and force_skip:
            raise exceptions.PermissionsError(ctx.bot.str.get('cmd-skip-force-noperms', 'You do not have permission to force skip.'), expire_in=30)

        # TODO: ignore person if they're deaf or take them out of the list or something?
        # Currently is recounted if they vote, deafen, then vote

        num_voice = sum(1 for m in guild._voice_channel.members if not (
            m.voice.deaf or m.voice.self_deaf or m == ctx.bot.user))
        if num_voice == 0: num_voice = 1 # incase all users are deafened, to avoid divison by zero

        num_skips = guild.skip_state.add_skipper(ctx.author.id, ctx.message)

        skips_remaining = min(
            ctx.bot.config.skips_required,
            math.ceil(ctx.bot.config.skip_ratio_required / (1 / num_voice))  # Number of skips from config ratio
        ) - num_skips

        if skips_remaining <= 0:
            await player.skip()
            await messagemanager.safe_send_normal(
                ctx,
                ctx,
                ctx.bot.str.get('cmd-skip-reply-skipped-1', 'Your skip for `{0}` was acknowledged.\nThe vote to skip has been passed.{1}').format(
                    current_entry.title,
                    ctx.bot.str.get('cmd-skip-reply-skipped-2', ' Next song coming up!') if (((await playlist.get_length()) > 0) or ((await player.status()) != PlayerState.WAITING)) else ''
                ),
                reply=True,
                expire_in=20
            )

        else:
            # TODO: When a song gets skipped, delete the old x needed to skip messages
            await messagemanager.safe_send_normal(
                ctx,
                ctx,
                ctx.bot.str.get('cmd-skip-reply-voted-1', 'Your skip for `{0}` was acknowledged.\n**{1}** more {2} required to vote to skip this song.').format(
                    current_entry.title,
                    skips_remaining,
                    ctx.bot.str.get('cmd-skip-reply-voted-2', 'person is') if skips_remaining == 1 else ctx.bot.str.get('cmd-skip-reply-voted-3', 'people are')
                ),
                reply=True,
                expire_in=20
            )

cogs = [QueueManagement]