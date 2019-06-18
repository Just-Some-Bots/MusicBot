from discord.ext.commands import Cog, command

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
            

cogs = [PlaylistManagement]