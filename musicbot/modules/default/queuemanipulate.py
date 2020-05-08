import time
import re
import os
import asyncio
import traceback
import logging
import shlex
import random
import math
from urllib.parse import urljoin
from typing import Optional, Union
from datetime import timedelta
from collections import defaultdict
from typing import Dict, DefaultDict

from textwrap import dedent

from discord.ext.commands import Cog, command, Greedy
from discord import User

from ...utils import fixg, ftimedelta, _func_
from ... import exceptions

from ... import messagemanager
from ...smart_guild import SmartGuild, get_guild
from ...playback import PlayerState, Playlist, Player
from ...ytdldownloader import get_stream_entry, get_entry, get_local_entry, get_unprocessed_entry

log = logging.getLogger(__name__)

cog_name = 'queue_management'

class QueueManagement(Cog):
    playlists: Optional[DefaultDict[SmartGuild, Dict[str, Playlist]]]
    player: Optional[Dict[SmartGuild, Player]]        

    def __init__(self):
        self._aiolocks = defaultdict(asyncio.Lock)
        self.bot = None
        self.playlists = None
        self.player = None
        self.entrybuilders = None

    def pre_init(self, bot):
        self.bot = bot
        self.entrybuilders = self.bot.crossmodule.get_object('entrybuilders')
        self.playlists = bot.crossmodule.get_object('playlists')
        self.player = bot.crossmodule.get_object('player')
        self.bot.crossmodule.register_object('_play', self._play)

    def uninit(self):
        self.bot.crossmodule.unregister_object('_play')

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
        playlist = ctx.bot.call('get_playlist', guild)
        await self._play(ctx, playlist, song_url = ' '.join(song_url))

    @command()
    async def playnext(self, ctx, *song_url):
        """
        Usage:
            {command_prefix}playnext song_link
            {command_prefix}playnext text to search for
            {command_prefix}playnext spotify_uri

        Like {command_prefix}play, but prepend the entry instead.
        """
        guild = get_guild(ctx.bot, ctx.guild)
        playlist = ctx.bot.call('get_playlist', guild)
        await self._play(ctx, playlist, song_url = ' '.join(song_url), head = True)

    @command()
    async def replay(self, ctx, option= None):
        """
        Usage:
            {command_prefix}replay [head/h]

        Add currently playing song to the end queue, if added 'head' or 'h' to the
        command current entry will be added to the head of the queue instead.
        """
        guild = get_guild(ctx.bot, ctx.guild)
        player = self.player[guild]
        playlist = self.bot.call('get_playlist', guild)
        current_entry = player.get_current_entry()

        head = False
        if option in ['head', 'h']:
            head = True

        await self._play(ctx, playlist, current_entry.source_url, head = head)

    async def _play(self, ctx, playlist, song_url, *, head=False, send_reply=True):
        guild = get_guild(ctx.bot, ctx.guild)

        permissions = ctx.bot.permissions.for_user(ctx.author)

        try:
            player = self.player[guild]
        except Exception as e:
            if permissions.summonplay:
                await ctx.bot.cogs['BotManagement'].summon.callback(ctx.bot.cogs['BotManagement'], ctx)
                player = self.player[guild]
            else:
                raise e

        song_url = song_url.strip('<>')

        count, entry_iter = self.entrybuilders.get_entry_from_query(song_url)

        async with self._aiolocks['play_{}'.format(ctx.author.id)]:
            async with ctx.typing():
                entry = None
                position = None
                reply_text = None

                if count == 1:
                    # IF PY35 DEPRECATED
                    # async for c_entry in entry_iter:
                    for a_c_entry in entry_iter:
                        if a_c_entry:
                            c_entry = await a_c_entry
                        else:
                            c_entry = a_c_entry
                    # END IF DEPRECATED
                        duration = c_entry.get_duration()
                        if permissions.max_song_length and duration and duration > permissions.max_song_length:
                            raise exceptions.PermissionsError(
                                ctx.bot.str.get('cmd-play-song-limit', "Song duration exceeds limit ({0} > {1})").format(duration, permissions.max_song_length),
                                expire_in=30
                            )
                        entry = c_entry
                        position = await playlist.add_entry(c_entry)
                        reply_text = "Enqueued `%s` to be played. Position in queue: %s"
                        btext = c_entry.title
                        break

                else:
                    # If it's playlist

                    # I have to do exe extra checks anyways because you can request an arbitrary number of search results
                    if not permissions.allow_playlists and count > 1:
                        raise exceptions.PermissionsError(ctx.bot.str.get('playlists-noperms', "You are not allowed to request playlists"), expire_in=30)

                    if permissions.max_playlist_length and count > permissions.max_playlist_length:
                        raise exceptions.PermissionsError(
                            ctx.bot.str.get('playlists-big', "Playlist has too many entries ({0} > {1})").format(count, permissions.max_playlist_length),
                            expire_in=30
                        )

                    # This is a little bit weird when it says (x + 0 > y), I might add the other check back in
                    if permissions.max_songs and player.playlist.num_entry_of(ctx.author.id) + count > permissions.max_songs:
                        raise exceptions.PermissionsError(
                            ctx.bot.str.get('playlists-limit', "Playlist entries + your already queued songs reached limit ({0} + {1} > {2})").format(
                                count, player.playlist.num_entry_of(ctx.author.id), permissions.max_songs),
                            expire_in=30
                        )

                    t0 = time.time()

                    # My test was 1.2 seconds per song, but we maybe should fudge it a bit, unless we can
                    # monitor it and edit the message with the estimated time, but that's some ADVANCED SHIT
                    # I don't think we can hook into it anyways, so this will have to do.
                    # It would probably be a thread to check a few playlists and get the speed from that
                    # Different playlists might download at different speeds though
                    wait_per_song = 1.2
                    drop_count = 0
                    actual_count = 0

                    procmesg = await messagemanager.safe_send_normal(
                        ctx,
                        ctx,
                        'Gathering playlist information for {0} songs{1}'.format(
                            count,
                            ', ETA: {0} seconds'.format(
                                fixg(count * wait_per_song)
                            ) if count >= 10 else '.'
                        )
                    )
                    
                    # TODO: I can create an event emitter object instead, add event functions, and every play list might be asyncified
                    #       Also have a "verify_entry" hook with the entry as an arg and returns the entry if its ok

                    # @TheerapakG: IDK if ^ is still applicable

                    # IF PY35 DEPRECATED
                    # async for c_entry in entry_iter:
                    for a_c_entry in entry_iter:
                        if a_c_entry:
                            c_entry = await a_c_entry
                        else:
                            c_entry = a_c_entry
                    # END IF DEPRECATED
                        actual_count += 1

                        if c_entry is None:
                            drop_count += 1
                            continue

                        duration = c_entry.get_duration()
                        if permissions.max_song_length and duration > timedelta(seconds=permissions.max_song_length):
                            drop_count += 1
                            continue
                            
                        position_potent = await playlist.add_entry(c_entry)
                        if not entry:
                            entry = c_entry
                            position = position_potent

                    tnow = time.time()
                    ttime = tnow - t0

                    ctx.bot.log.info(
                        "Processed {} songs in {} seconds at {:.2f}s/song, {:+.2g}/song from expected".format(
                            actual_count,
                            fixg(ttime),
                            ttime / actual_count if actual_count else 0,
                            ttime / actual_count - wait_per_song if actual_count - wait_per_song else 0
                        )
                    )

                    reply_text = "Enqueued **%s** songs to be played. Position of the first entry in queue: %s"
                    btext = str(actual_count - drop_count)                  

                if playlist is self.bot.call('get_playlist', guild):
                    await guild.return_from_auto(also_skip=ctx.bot.config.skip_if_auto)

                    player = self.player[guild]

                    try:
                        time_until = await player.estimate_time_until_entry(entry)

                        if time_until == timedelta(seconds=0):
                            position = 'Up next!'
                            reply_text %= (btext, position)

                        else:
                            reply_text %= (btext, position)
                            reply_text += (ctx.bot.str.get('cmd-play-eta', ' - estimated time until playing: %s') % ftimedelta(time_until))

                    except exceptions.InvalidDataError:
                        reply_text %= (btext, position)
                        reply_text += ctx.bot.str.get('cmd-play-eta-error', ' - cannot estimate time until playing')

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

        permissions = ctx.bot.permissions.for_user(ctx.author)

        try:
            player = self.player[guild]
        except Exception as e:
            if permissions.summonplay:
                await ctx.bot.cogs['BotManagement'].summon.callback(ctx.bot.cogs['BotManagement'], ctx)
                player = self.player[guild]
            else:
                raise e

        playlist = ctx.bot.call('get_playlist', guild)

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
        permissions = ctx.bot.permissions.for_user(ctx.author)

        try:
            player = self.player[guild]
        except Exception as e:
            if permissions.summonplay:
                await ctx.bot.cogs['BotManagement'].summon.callback(ctx.bot.cogs['BotManagement'], ctx)
                player = self.player[guild]
            else:
                raise e

        playlist = ctx.bot.call('get_playlist', guild)

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
        player = self.player[guild]
        playlist = ctx.bot.call('get_playlist', guild)

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
    async def skip(self, ctx, param:Optional[str]=''):
        """
        Usage:
            {command_prefix}skip [force/f]

        Skips the current song when enough votes are cast.
        Owners and those with the instaskip permission can add 'force' or 'f' after the command to force skip.
        """
        guild = get_guild(ctx.bot, ctx.guild)
        player = self.player[guild]
        playlist = self.bot.call('get_playlist', guild)
        current_entry = player.get_current_entry()
        permissions = ctx.bot.permissions.for_user(ctx.author)

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
deps = ['default.queryconverter', 'default.player']