import glob, os
from functools import partial

from discord.ext.commands import Cog, command, group
from discord import User

from typing import Optional, Union, AnyStr, DefaultDict, Dict
from datetime import timedelta
from collections import defaultdict
from threading import RLock

from ... import exceptions

from ...crossmodule import ExportableMixin, export_func
from ...constants import DISCORD_MSG_CHAR_LIMIT
from ...utils import ftimedelta
from ...command_injector import InjectableMixin, inject_as_subcommand, inject_as_main_command, inject_as_group
from ...smart_guild import SmartGuild, get_guild
from ...playback import Player, Playlist, PlayerState
from ...ytdldownloader import get_unprocessed_entry
from ... import messagemanager

class Playlist_Cog(ExportableMixin, InjectableMixin, Cog):
    playlists: DefaultDict[SmartGuild, Dict[str, Playlist]] = defaultdict(dict)
    _lock: DefaultDict[str, RLock] = DefaultDict(RLock)

    def __init__(self):
        super().__init__()
        self.bot = None

    def pre_init(self, bot):
        self.bot = bot
        self.bot.crossmodule.register_object('playlists', self.playlists)

    @export_func
    def serialize_playlist(self, guild, playlist):
        """
        Serialize the playlist to json.
        """
        dir = guild._save_dir + '/playlists/{}.json'.format(playlist._name)

        with self._lock['{}_{}_serialization'.format(guild._id, playlist._name)]:
            self.bot.log.debug("Serializing `{}` for {}".format(playlist._name, guild._id))
            os.makedirs(os.path.dirname(dir), exist_ok=True)
            with open(dir, 'w', encoding='utf8') as f:
                f.write(playlist.serialize(sort_keys=True))

    def serialize_playlists(self, guild):
        for p in self.playlists[guild].values():
            self.serialize_playlist(guild, p)

    @export_func
    def remove_serialized_playlist(self, guild, name):
        """
        Remove the playlist serialized to json.
        """
        dir = guild._save_dir + '/playlists/{}.json'.format(name)

        with self._lock['{}_{}_serialization'.format(guild._id, name)]:
            self.bot.log.debug("Removing serialized `{}` for {}".format(name, guild._id))
            try:
                del self._playlists[guild][name]
            except KeyError:
                pass

            os.unlink(dir)

    def initialize_guild_data_dict(self, guild, *_):
        # Discard data arg because we save info in another file
        for path in glob.iglob(os.path.join(guild._save_dir + '/playlists', '*.json')):
            with open(path, 'r') as f:
                data = f.read()
                playlist = Playlist.from_json(data, self.bot, self.bot.downloader)
                self.playlists[guild][playlist._name] = playlist
            self.bot.log.debug("Loaded playlist {} for {}".format(playlist._name, guild.id))

    @inject_as_main_command('playlist', invoke_without_command=False)
    @inject_as_group
    async def playlist(self, ctx):
        """
        A command group for managing playlist
        """
        pass

    @inject_as_subcommand('list', name = 'playlist')
    @inject_as_subcommand('playlist', name = 'list', after = 'inject_playlist')
    async def listplaylist(self, ctx):
        """
        Usage:
            {command_prefix}list playlist

        List all playlists in the guild.
        """
        bot = ctx.bot
        guild = get_guild(bot, ctx.guild)

        pls = []
        apl = None

        for name, pl in self.playlists[guild].items():
            if pl is not guild._auto:
                pls.append(name)

        if guild._auto:
            apl = guild._auto._name

        plmsgtitle = 'playlist{}'.format('s' if len(pls)>1 else '')
        plmsgdesc = '\n'.join(pls) if pls else None
        
        aplmsgtitle = 'autoplaylist'
        aplmsgdesc = apl

        await messagemanager.safe_send_normal(ctx, ctx,
            [
                {'name': plmsgtitle, 'value': plmsgdesc, 'inline': False},
                {'name': aplmsgtitle, 'value': aplmsgdesc, 'inline': False}
            ]
        )

    async def add_pl(self, ctx, name):
        bot = ctx.bot
        guild = get_guild(bot, ctx.guild)

        if name in self.playlists[guild]:
            raise exceptions.CommandError('There is already a playlist with that name.')
        else:
            self.playlists[guild][name] = Playlist(name, bot)
            await guild.serialize_playlist(self.playlists[guild][name])
            return self.playlists[guild][name]

    @inject_as_subcommand('add', name = 'playlist')
    @inject_as_subcommand('playlist', name = 'add', after = 'inject_playlist')
    async def addplaylist(self, ctx, name):
        """
        Usage:
            {command_prefix}add playlist name

        Add a playlist.
        """
        await self.add_pl(ctx, name)
        await messagemanager.safe_send_normal(ctx, ctx, 'added playlist: {}'.format(name))
        

    @inject_as_subcommand('add', name = 'entries', invoke_without_command=False)
    @inject_as_group
    async def addentries(self, ctx):
        """
        A command group for adding entries to the playlist
        """

    @inject_as_subcommand('add entries', name = 'playlist', after = 'inject_add_entries')
    async def addentriesplaylist(self, ctx, name, target = None):
        """
        Usage:
            {command_prefix}add entries playlist name [target]

        Append entries from a playlist to the target.
        """
        bot = ctx.bot
        guild = get_guild(bot, ctx.guild)
        if target:
            g_pl = self.playlists[guild][target]
        else:
            g_pl = bot.call('get_playlist', guild)

        if name not in self.playlists[guild]:
            raise exceptions.CommandError('There is not any playlist with that name.')
        else:
            for e in self.playlists[guild][name]._list:
                bot.log.debug('{} ({})'.format(e, e.source_url))
                # @TheerapakG: TODO: make unprocessed from processed
                await g_pl.add_entry(await get_unprocessed_entry(e.source_url, ctx.author.id, bot.downloader, dict()))
            await guild.serialize_playlist(g_pl)

        await messagemanager.safe_send_normal(ctx, ctx, 'imported entries from playlist: {}'.format(name))    

    @inject_as_subcommand('remove', name = 'playlist')
    @inject_as_subcommand('playlist', name = 'remove', after = 'inject_playlist')
    async def removeplaylist(self, ctx, name):
        """
        Usage:
            {command_prefix}remove playlist name

        Remove a playlist.
        """
        bot = ctx.bot
        guild = get_guild(bot, ctx.guild)

        if name in self.playlists[guild]:
            pl = self.playlists[guild][name]
            if pl is guild._auto:
                guild._auto = None
                if (await guild.is_currently_auto()):
                    await guild.return_from_auto()
                await guild.remove_serialized_playlist(name)
                del self.playlists[guild][name]
                await guild.serialize_to_file()
            elif pl is bot.call('get_playlist', guild):
                raise exceptions.CommandError('Playlist is currently in use.')
            else:
                await guild.remove_serialized_playlist(name)
                del self.playlists[guild][name]
        else:
            raise exceptions.CommandError('There is not any playlist with that name.')

        await messagemanager.safe_send_normal(ctx, ctx, 'removed playlist: {}'.format(name))

    @command()
    async def swap(self, ctx, name):
        """
        Usage:
            {command_prefix}swap name

        Swap currently playing playlist.
        """
        bot = ctx.bot
        guild = get_guild(bot, ctx.guild)
        prev = bot.call('get_playlist', guild)

        if name in self.playlists[guild]:
            pl = self.playlists[guild][name]
            if pl is guild._auto:
                raise exceptions.CommandError('This playlist is not swapable (is autoplaylist).')
            else:
                await guild.set_playlist(pl)
                await guild.serialize_to_file()
        else:
            raise exceptions.CommandError('There is not any playlist with that name.')

        await messagemanager.safe_send_normal(ctx, ctx, 'swapped playlist from {} to {}'.format(prev._name, name))

    @inject_as_subcommand('add entries', name = 'url', after = 'inject_add_entries')
    async def addentriesurl(self, ctx, url, name = None):
        """
        Usage:
            {command_prefix}add entries url url [name]

        Retrieve entries of playlist from url and save it as a playlist named name.
        """
        bot = ctx.bot
        guild = get_guild(bot, ctx.guild)

        pl = self.playlists[guild][name] if name else bot.call('get_playlist', guild)
        await bot.crossmodule.async_call_object('_play', ctx, pl, url, send_reply = False)
        await guild.serialize_playlist(pl)

        await messagemanager.safe_send_normal(ctx, ctx, 'imported playlist from {} to {}'.format(url, pl._name))

    @inject_as_subcommand('remove', name = 'entry')
    @inject_as_main_command('re')
    async def removeentry(self, ctx, index:Optional[Union[int, User]]=None, name:Optional[str]=None):
        """
        Usage:
            {command_prefix}remove entry [# in playlist] [name]

        Removes entries in the specified playlist. If a number is specified, removes that song in the queue, 
        otherwise removes the most recently queued song. If playlist is unspecified, playlist is assumed to be the active playlist
        """
        guild = get_guild(ctx.bot, ctx.guild)
        if name:
            playlist = self.playlists[guild][name]
        else:
            playlist = bot.call('get_playlist', guild)

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
                    await guild.serialize_playlist(playlist)
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
            raise exceptions.CommandError(ctx.bot.str.get('cmd-remove-invalid', "Invalid number. Use {}list entries to find queue positions.").format(ctx.bot.config.command_prefix), expire_in=20)

        if index > num:
            raise exceptions.CommandError(ctx.bot.str.get('cmd-remove-invalid', "Invalid number. Use {}list entries to find queue positions.").format(ctx.bot.config.command_prefix), expire_in=20)

        if permissions.remove or ctx.author.id == playlist[index - 1].queuer_id:
            entry = await playlist.remove_position((index - 1))
            await guild.serialize_playlist(playlist)
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

    @inject_as_subcommand('remove', name = 'entries')
    @inject_as_main_command(['clear', 'res'])
    async def clear(self, ctx, name: Optional[AnyStr] = None):
        """
        Usage:
            {command_prefix}clear

        Clears the playlist.
        """
        guild = get_guild(ctx.bot, ctx.guild)
        if name:
            playlist = self.playlists[guild][name]
        else:
            playlist = bot.call('get_playlist', guild)

        await playlist.clear()
        await guild.serialize_playlist(playlist)
        await messagemanager.safe_send_normal(ctx, ctx, ctx.bot.str.get('cmd-clear-reply', "Cleared `{0}`").format(playlist._name), expire_in=20)

    @command()
    async def karaoke(self, ctx):
        """
        Usage:
            {command_prefix}karaoke

        Activates karaoke mode. During karaoke mode, only groups with the BypassKaraokeMode
        permission in the config file can queue music.
        """
        guild = get_guild(ctx.bot, ctx.guild)
        playlist = bot.call('get_playlist', guild)
        playlist.karaoke_mode = not playlist.karaoke_mode
        await messagemanager.safe_send_normal(ctx, ctx, "\N{OK HAND SIGN} Karaoke mode is now " + ['disabled', 'enabled'][playlist.karaoke_mode], expire_in=15)
            

cogs = [Playlist_Cog]
deps = ['default.base']