import logging
from typing import Optional
from asyncio import ensure_future

from discord.ext.commands import Cog, command

from ... import exceptions

from ...rich_guild import get_guild
from ... import messagemanager
from ...playback import PlayerState

log = logging.getLogger(__name__)

class Playback(Cog):

    async def volume(self, ctx, new_volume:Optional[str]=None):
        """
        Usage:
            {command_prefix}volume [[+|-]volume]

        Sets the playback volume. Accepted values are from 1 to 100.
        Putting + or - before the volume will make the volume change relative to the current volume.
        """
        guild = get_guild(ctx.bot, ctx.guild)
        player = await guild.get_player()

        if not new_volume:
            await messagemanager.safe_send_message(ctx, ctx.bot.str.get('cmd-volume-current', 'Current volume: `%s%%`') % int(player.volume * 100), reply=True, expire_in=20)
            return

        relative = False
        if new_volume[0] in '+-':
            relative = True

        try:
            new_volume = int(new_volume)

        except ValueError:
            await messagemanager.safe_send_message(ctx, ctx.bot.str.get('cmd-volume-invalid', '`{0}` is not a valid number').format(new_volume), expire_in=20)
            raise exceptions.CommandError(ctx.bot.str.get('cmd-volume-invalid', '`{0}` is not a valid number').format(new_volume), expire_in=20)

        vol_change = None
        if relative:
            vol_change = new_volume
            new_volume += (player.volume * 100)

        old_volume = int(player.volume * 100)

        if 0 < new_volume <= 100:
            player.volume = new_volume / 100.0

            await messagemanager.safe_send_message(ctx, ctx.bot.str.get('cmd-volume-reply', 'Updated volume from **%d** to **%d**') % (old_volume, new_volume), reply=True, expire_in=20)
            return

        else:
            if relative:
                await messagemanager.safe_send_message(
                    ctx, 
                    ctx.bot.str.get('cmd-volume-unreasonable-relative', 'Unreasonable volume change provided: {}{:+} -> {}%.  Provide a change between {} and {:+}.').format(
                        old_volume, vol_change, old_volume + vol_change, 1 - old_volume, 100 - old_volume), expire_in=20)
            else:
                await messagemanager.safe_send_message(
                    ctx, 
                    ctx.bot.str.get('cmd-volume-unreasonable-absolute', 'Unreasonable volume provided: {}%. Provide a value between 1 and 100.').format(new_volume), expire_in=20)

    async def resume(self, ctx):
        """
        Usage:
            {command_prefix}resume

        Resumes playback of a paused song.
        """
        guild = get_guild(ctx.bot, ctx.guild)
        player = await guild.get_player()
        def fail(exc):
            async def _fail():
                exceptionstr = 'Cannot resume! {}'.format(str(exc))
                ctx.bot.log.error(exceptionstr)
                await messagemanager.safe_send_message(ctx, exceptionstr, expire_in=30)
            ensure_future(_fail())
        def success():
            async def _success():
                await messagemanager.safe_send_message(ctx, ctx.bot.str.get('cmd-resume-reply', 'Resumed music in `{0.name}`'.format(guild._voice_channel), expire_in=15))
            ensure_future(_success())
        def wait():
            async def _wait():
                await messagemanager.safe_send_message(ctx, ctx.bot.str.get('playback?cmd?resume?reply@wait', 'Resumed music in `{0.name}, waiting for entries to be added`'.format(guild._voice_channel), expire_in=15))
            ensure_future(_wait())
        await player.play(play_fail_cb = fail, play_success_cb = success, play_wait_cb = wait)

    async def cmd_pause(self, ctx):
        """
        Usage:
            {command_prefix}pause

        Pauses playback of the current song.
        """
        guild = get_guild(ctx.bot, ctx.guild)
        player = await guild.get_player()
        state = await player.status()
        if state != PlayerState.PAUSE:
            await player.pause()
            await messagemanager.safe_send_message(ctx, ctx.bot.str.get('cmd-pause-reply', 'Paused music in `{0.name}`').format(player.voice_client.channel))

        else:
            await messagemanager.safe_send_message(ctx, ctx.bot.str.get('cmd-pause-none', 'Player is not playing.'), expire_in=30)

    # TODO: effects

cogs = [Playback]