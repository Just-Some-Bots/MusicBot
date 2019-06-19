from discord.ext.commands import Cog, command
from discord import User

from typing import Optional, Union

from ... import exceptions

from ...rich_guild import get_guild
from ...playback import Playlist
from ... import messagemanager

class PlaylistManagement(Cog):
    @command()
    async def addpl(self, ctx, name):
        """
        Usage:
            {command_prefix}addpl name

        Add a playlist.
        """
        bot = ctx.bot
        guild = get_guild(bot, ctx.guild)

        if name in guild._playlists:
            raise exceptions.CommandError('There is already a playlist with that name.')
        else:
            guild._playlists[name] = Playlist(name, bot)
            await guild.serialize_playlist(guild._playlists[name])

    @command()
    async def removepl(self, ctx, name):
        """
        Usage:
            {command_prefix}removepl name

        Remove a playlist.
        """
        bot = ctx.bot
        guild = get_guild(bot, ctx.guild)

        if name in guild._playlists:
            pl = guild._playlists[name]
            if pl is guild._internal_auto:
                # @TheerapakG: TODO: figure out if toggling then maybe move to next playlist?
                raise exceptions.CommandError('This playlist is in use.')
            elif pl in guild._autos:
                guild._autos.remove(pl)
                await guild.remove_serialized_playlist(name)
                del guild._playlists[name]
                await guild.serialize_to_file()
            else:
                await guild.remove_serialized_playlist(name)
                del guild._playlists[name]
        else:
            raise exceptions.CommandError('There is not any playlist with that name.')

    @command()
    async def removeen(self, ctx, name, index:Optional[Union[int, User]]=None):
        """
        Usage:
            {command_prefix}removeen name [# in playlist]

        Removes entries in the specified playlist. If a number is specified, removes that song in the queue, otherwise removes the most recently queued song.
        """
        guild = get_guild(ctx.bot, ctx.guild)
        playlist = await guild._playlists[name]
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
            

cogs = [PlaylistManagement]