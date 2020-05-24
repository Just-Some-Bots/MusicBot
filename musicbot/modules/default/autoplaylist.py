import logging
import time
from typing import Optional, Dict, DefaultDict
from threading import RLock

from discord.ext.commands import Cog, command

from ... import exceptions
from ...utils import write_file

from ...crossmodule import ExportableMixin, export_func, ContinueIteration
from ... import messagemanager
from ...messagemanager import safe_send_normal
from ...smart_guild import SmartGuild, get_guild
from ...ytdldownloader import get_unprocessed_entry, get_stream_entry
from ...playback import Playlist, Player

class Autoplaylist(ExportableMixin, Cog):
    playlists: Optional[DefaultDict[SmartGuild, Dict[str, Playlist]]]
    player: Optional[Dict[SmartGuild, Player]]
    ap: Dict[SmartGuild, Optional[Playlist]] = dict()
    swap: Dict[SmartGuild, Optional[Playlist]] = dict()
    _lock: DefaultDict[SmartGuild, RLock] = DefaultDict(RLock)

    def __init__(self):
        super().__init__()
        self.entrybuilders = None
        self.playlists = None
        self.player = None

    def pre_init(self, bot):
        self.bot = bot
        self.entrybuilders = bot.crossmodule.get_object('entrybuilders')
        self.playlists = bot.crossmodule.get_object('playlists')
        self.player = bot.crossmodule.get_object('player')

    def get_guild_data_dict(self, guild):
        return {
            'auto': {
                'ap': self.ap[guild]._name if self.ap[guild] else None,
                'swap': self.swap[guild]._name if self.swap[guild] else None
            }
        }

    def initialize_guild_data_dict(self, guild, data):
        data = data.get('auto', dict()) if data else dict() 

        try:
            self.ap[guild] = self.playlists[guild][data['ap']]
        except KeyError:
            if data.get('ap', None):
                self.bot.log.debug('Cannot locate playlist {} to use as ap'.format(data['ap']))
            self.ap[guild] = None

        try:
            self.swap[guild] = self.playlists[guild][data['swap']]
        except KeyError:
            if data.get('swap', None):
                self.bot.log.debug('Cannot locate playlist {} to use as swap'.format(data['swap']))
            self.swap[guild] = None

        def _autopause(player):
            if self._check_if_empty(player._guild._voice_channel):
                self.log.info("Initial autopause in empty channel")
                player.pause()
                self.bot.server_specific_data[guild]['auto_paused'] = True

        player = self.player[guild]

        if self.ap[guild] and player.voice.voice_channel:
            if self.bot.config.auto_pause:
                player.once('play', lambda player, **_: _autopause(player))

    def swap_player_playlist(self, guild, *, random = False, pull_persist = False):
        player = self.player[guild]
        with self._lock[guild]:
            if not self.swap[guild]:
                raise Exception('No swap target')
            player.random = random
            player.pull_persist = pull_persist
            current = player.get_playlist()
            player.set_playlist(self.swap[guild])
            self.swap[guild] = current

    @export_func
    async def on_player_play(self, guild, player, entry):
        self.bot.log.debug('Running autoplaylist on_player_play')

        if guild.is_currently_auto():
            channel = None
            author = None            
            newmsg = 'Now playing automatically added entry `%s` in `%s`' % (
                entry.title, player.voice.voice_channel().name)

            if self.bot.config.no_nowplaying_auto and not author:
                return

            last_np_msg = self.bot.server_specific_data[guild]['last_np_msg']

            if self.bot.config.nowplaying_channels:
                for potential_channel_id in self.bot.config.nowplaying_channels:
                    potential_channel = self.bot.get_channel(potential_channel_id)
                    if potential_channel and potential_channel.guild == guild.guild:
                        channel = potential_channel
                        break

            if last_np_msg:
                channel = last_np_msg.channel
            else:
                self.bot.log.debug('no channel to put now playing message into')
                return

            # send it in specified channel
            self.bot.server_specific_data[guild]['last_np_msg'] = await messagemanager.safe_send_message(channel, newmsg)

        else:
            return ContinueIteration

    @export_func
    async def on_player_finished_playing(self, guild, player, **_):
        def _autopause(player):
            if self.bot._check_if_empty(player.voice.voice_channel()):
                self.bot.log.info("Player finished playing, autopaused in empty channel")

                player.pause()
                self.bot.server_specific_data[guild]['auto_paused'] = True

        current = player.get_playlist()
        with self._lock[guild]:
            if await current.get_length() == 0 and self.ap[guild]:
                self.bot.log.info("Entering auto in {}".format(guild._id))
                self.swap[guild] = current
                self.swap_player_playlist(guild, random = guild.config.auto_random, pull_persist = True)

                if self.bot.config.auto_pause:
                    player.once('play', lambda player, **_: _autopause(player))
        
        return ContinueIteration

    @export_func
    def set_playlist(self, guild, playlist, swap = False):
        if swap and self.is_currently_auto():
            with self._lock[guild]:
                self.swap = playlist
        else:
            ContinueIteration(guild, playlist)

    @export_func
    def get_playlist(self, guild, incl_auto = False):
        if incl_auto:
           ContinueIteration(guild)
        else:
            with self._lock[guild]:
                if self.is_currently_auto(guild):
                    return self.swap[guild]
                else:
                    ContinueIteration(guild)

    @export_func
    def is_playlist_auto(self, guild: SmartGuild, pl: Playlist):
        with self._lock[guild]:
            return pl is self.ap[guild]

    @export_func
    def is_currently_auto(self, guild: SmartGuild):
        return self.is_playlist_auto(self.bot.call('get_playlist', guild, incl_auto = True))

    @export_func
    def return_from_auto(self, guild, *, also_skip = False):
        if self.is_currently_auto():
            self.bot.log.info("Leaving auto in {}".format(guild._id))
            with self._lock[guild]:
                self.set_playlist(guild, self.swap[guild], swap=False)
            self.bot.call('serialize_playlist', guild, self.ap[guild])
            self.player[guild].random = False
            self.player[guild].pull_persist = False
            if also_skip:
                self.player[guild].skip()

    @export_func
    def set_auto(self, guild, pl: Optional[Playlist] = None):
        self.bot.log.info("Setting auto in {}".format(guild._id))
        self.bot.call('serialize_playlist', guild, self.ap[guild])
        with self._lock[guild]:
            if self.is_currently_auto():
                self.set_playlist(guild, pl, swap=False)
            self.ap[guild] = pl

    @export_func
    def get_auto(self, guild):
        with self._lock[guild]:
            return self.ap[guild]

    @command()
    async def resetplaylist(self, ctx):
        """
        Usage:
            {command_prefix}resetplaylist

        Deprecated
        """
        bot = ctx.bot
        await safe_send_normal(ctx, ctx, bot.str.get('general?cmd@deprecated', 'This command is no longer available.'), expire_in=15)

    @command()
    async def aprandom(self, ctx):
        """
        Usage:
            {command_prefix}aprandom

        Change whether autoplaylist would randomize song
        """
        bot = ctx.bot
        guild = get_guild(bot, ctx.guild)

        guild.config.auto_random = not guild.config.auto_random
        safe_send_normal(ctx, ctx, 'Autoplaylist randomization is now set to {}.'.format(guild.config.auto_random), expire_in=15)

    @command()
    async def save(self, ctx, *, url:Optional[str] = None):
        """
        Usage:
            {command_prefix}save [url]

        Saves the specified song or current song if not specified to the autoplaylist playing.
        """
        bot = ctx.bot
        guild = get_guild(bot, ctx.guild)
        player = self.player[guild]
        current = player.get_current_entry()
        if not guild._auto:
            raise exceptions.CommandError('There is no autoplaylist.')
        if url or current:
            if not url:
                url = current.source_url
                current = await get_unprocessed_entry(url, None, bot.downloader, dict())
            if current.source_url not in [e.source_url for e in guild._auto.list_snapshot()]:
                await guild._auto.add_entry(current)
                await guild.serialize_playlist(guild._auto)
                ctx.bot.log.debug("Appended {} to autoplaylist".format(url))
                await safe_send_normal(ctx, ctx, bot.str.get('cmd-save-success', 'Added <{0}> to the autoplaylist.').format(url))
            else:
                raise exceptions.CommandError(bot.str.get('cmd-save-exists', 'This song is already in the autoplaylist.'))
        else:
            raise exceptions.CommandError(bot.str.get('cmd-save-invalid', 'There is no valid song playing.'))

    @command()
    async def swapap(self, ctx, *, name:Optional[str] = None):
        """
        Usage:
            {command_prefix}swapap [name]

        Swap autoplaylist to the specified playlist
        """
        bot = ctx.bot
        guild = get_guild(bot, ctx.guild)

        if not name:
            await guild.set_auto(None)

        elif name in self.playlists[guild]:
            await guild.set_auto(self.playlists[guild][name])

        else:
            raise exceptions.CommandError('There is no playlist with that name.')

    @command()
    async def fromfile(self, ctx):
        """
        Usage:
            {command_prefix}fromfile

        Load playlist from .txt file attached to the message.
        Check _autoplaylist.txt in the config folder for example.
        """
        bot = ctx.bot
        guild = get_guild(bot, ctx.guild)

        if not guild._auto:
            raise exceptions.CommandError('There is no autoplaylist.')

        processed = 0

        for f in ctx.message.attachments:
            if (f.filename.split('.'))[-1] != 'txt':
                continue

            try:
                load = await f.read()
                slines = str(load, 'utf-8').splitlines()
            except UnicodeError:
                await safe_send_normal(ctx, ctx, 'Cannot process {}, ensure that your playlist file is encoded as utf-8'.format(f.filename))
                continue

            results = []
            for line in slines:
                line = line.strip()

                if line and not line.startswith('#'):
                    results.append(line)

            for r in results:
                count, entry_iter = await self.entrybuilders.get_entry_from_query(None, r, process = False)
                # IF PY35 DEPRECATED
                # async for c_entry in entry_iter:
                for a_c_entry in entry_iter:
                    if a_c_entry:
                        c_entry = await a_c_entry
                    else:
                        c_entry = a_c_entry
                # END IF DEPRECATED
                if c_entry:
                    await guild._auto.add_entry(c_entry)

            processed += 1

        await safe_send_normal(ctx, ctx, 'successfully processed {} attachments'.format(processed))

cogs = [Autoplaylist]
deps = ['default.queryconverter', 'default.player']