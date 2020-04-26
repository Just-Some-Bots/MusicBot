import logging
from typing import Optional
from asyncio import ensure_future

from discord.ext.commands import Cog, command

from ... import exceptions

from ...smart_guild import get_guild
from ... import messagemanager
from ...playback import PlayerState

log = logging.getLogger(__name__)

class Playback(Cog):
    @command()
    async def volume(self, ctx, new_volume:Optional[str]=None):
        """
        Usage:
            {command_prefix}volume [[+|-]volume]

        Sets the playback volume. Accepted values are from 1 to 100.
        Putting + or - before the volume will make the volume change relative to the current volume.
        """
        guild = get_guild(ctx.bot, ctx.guild)
        player = self.player[guild]

        if not new_volume:
            await messagemanager.safe_send_normal(ctx, ctx, ctx.bot.str.get('cmd-volume-current', 'Current volume: `%s%%`') % int(player.volume * 100), reply=True, expire_in=20)
            return

        relative = False
        if new_volume[0] in '+-':
            relative = True

        try:
            new_volume = int(new_volume)

        except ValueError:
            raise exceptions.CommandError(ctx.bot.str.get('cmd-volume-invalid', '`{0}` is not a valid number').format(new_volume), expire_in=20)

        vol_change = None
        if relative:
            vol_change = new_volume
            new_volume += (player.volume * 100)

        old_volume = int(player.volume * 100)

        if 0 < new_volume <= 100:
            player.volume = new_volume / 100.0

            await messagemanager.safe_send_normal(ctx, ctx, ctx.bot.str.get('cmd-volume-reply', 'Updated volume from **%d** to **%d**') % (old_volume, new_volume), reply=True, expire_in=20)
            return

        else:
            if relative:
                raise exceptions.CommandError(
                    ctx.bot.str.get('cmd-volume-unreasonable-relative', 'Unreasonable volume change provided: {}{:+} -> {}%.  Provide a change between {} and {:+}.').format(
                        old_volume, vol_change, old_volume + vol_change, 1 - old_volume, 100 - old_volume), expire_in=20)
            else:
                raise exceptions.CommandError(
                    ctx.bot.str.get('cmd-volume-unreasonable-absolute', 'Unreasonable volume provided: {}%. Provide a value between 1 and 100.').format(new_volume), expire_in=20)

    @command()
    async def resume(self, ctx):
        """
        Usage:
            {command_prefix}resume

        Resumes playback of a paused song.
        """
        guild = get_guild(ctx.bot, ctx.guild)
        player = self.player[guild]
        def fail(exc):
            async def _fail():
                exceptionstr = 'Cannot resume! {}'.format(str(exc))
                ctx.bot.log.error(exceptionstr)
                await messagemanager.safe_send_message(ctx, exceptionstr, expire_in=30)
            ensure_future(_fail())
        def success():
            async def _success():
                await messagemanager.safe_send_normal(ctx, ctx, ctx.bot.str.get('cmd-resume-reply', 'Resumed music in `{0.name}`'.format(guild._voice_channel), expire_in=15))
            ensure_future(_success())
        def wait():
            async def _wait():
                await messagemanager.safe_send_normal(ctx, ctx, ctx.bot.str.get('playback?cmd?resume?reply@wait', 'Resumed music in `{0.name}`, waiting for entries to be added').format(guild._voice_channel), expire_in=15)
            ensure_future(_wait())
        await player.play(play_fail_cb = fail, play_success_cb = success, play_wait_cb = wait)

    @command()
    async def pause(self, ctx):
        """
        Usage:
            {command_prefix}pause

        Pauses playback of the current song.
        """
        guild = get_guild(ctx.bot, ctx.guild)
        player = self.player[guild]
        state = await player.status()
        if state != PlayerState.PAUSE:
            await player.pause()
            await messagemanager.safe_send_normal(ctx, ctx, ctx.bot.str.get('cmd-pause-reply', 'Paused music in `{0.name}`').format(guild._voice_channel))

        else:
            raise exceptions.CommandError(ctx.bot.str.get('cmd-pause-none', 'Player is not playing.'), expire_in=30)

    @command()
    async def effect(self, ctx, mode, fx, *leftover_args):
        """
        Usage:
            {command_prefix}effect add/a [effect] [args]
            {command_prefix}effect remove/r [position]
            {command_prefix}effect move/m [positionbef] [positionaft]
        Apply or remove effects to the playback player, took effect on next entry.
        """
        guild = get_guild(ctx.bot, ctx.guild)
        player = self.player[guild]
        # @TheerapakG: TODO: FUTURE#1776?EFFECT: effectloader
        reply_msg = ''
        await messagemanager.safe_send_normal(ctx, ctx, 'warning! effect command is highly experimental!', expire_in=10)
        if mode in ['add', 'a']:
            if fx in ['fadein']:
                duration = leftover_args[0]
                player.effects.append(('afade=in:', 'd={}'.format(duration)))
                reply_msg += 'Successfully add effect {} '.format('fadein')
                reply_msg += 'with duration {} '.format(duration)
            elif fx in ['fadeout']:
                duration = leftover_args[0]
                player.effects.append(('afade=out:', 'd={}'.format(duration)))
                reply_msg += 'Successfully add effect {} '.format('fadeout')
                reply_msg += 'with duration {} '.format(duration)
            elif fx in ['declick']:
                player.effects.append(('adeclick', ''))
                reply_msg += 'Successfully add effect {} '.format('declick')
            elif fx in ['echo']:
                await messagemanager.safe_send_normal(ctx, ctx, 'warning! echo effect is untested', expire_in=10)
                # @TheerapakG: untested
                ingain = leftover_args[0]
                outgain = leftover_args[1]
                delaydecay = leftover_args[2:]
                delays = []
                decays = []
                for idx, el in enumerate(delaydecay):
                    if el == '|':
                        delays = delaydecay[:idx]
                        decays = delaydecay[idx+1:]
                player.effects.append(('aecho=', '{}:{}:{}:{}'.format(ingain, outgain, '|'.join(delays), '|'.join(decays))))
                reply_msg += 'Successfully add effect {} '.format('echo')
            elif fx in ['phaser']:
                ingain = leftover_args[0]
                outgain = leftover_args[1]
                delay = leftover_args[2]
                decay = leftover_args[3]
                speed = leftover_args[4]
                ptype = leftover_args[5]
                if ptype in ['triangular', 't', 'sinusoidal', 's']:
                    player.effects.append(('aphaser=', '{}:{}:{}:{}:{}:{}'.format(ingain, outgain, delay, decay, speed, ptype)))
                    reply_msg += 'Successfully add effect {} '.format('phaser')
                else:
                    reply_msg += '{} argument in effect {} need to be {}'.format('ptype', 'echo', ['triangular', 't', 'sinusoidal', 's'])
            elif fx in ['reverse']:
                player.effects.append(('areverse', ''))
                reply_msg += 'Successfully add effect {} '.format('reverse')
            elif fx in ['tempo']:
                tempo = leftover_args[0]
                player.effects.append(('atempo=', '{}'.format(tempo)))
                reply_msg += 'Successfully add effect {} '.format('tempo')
            elif fx in ['trim']:
                start = leftover_args[0]
                end = leftover_args[1]
                player.effects.append(('atrim=', '{}:{}'.format(start, end)))
                reply_msg += 'Successfully add effect {} '.format('trim')
        elif mode in ['remove', 'r']:
            position = int(fx)-1
            player.effects.pop(position)
        elif mode in ['move', 'm']:
            positionbef = int(fx)-1
            positionaft = int(leftover_args[0]) -1
            player.effects.insert(positionaft, player.effects.pop(positionbef))
        await messagemanager.safe_send_normal(ctx, ctx, reply_msg, delete_after=15)

cogs = [Playback]
deps = ['default.playlist']