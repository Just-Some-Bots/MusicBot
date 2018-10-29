import logging

from .. import exceptions
from ..constructs import Response

log = logging.getLogger(__name__)

cog_name = 'playback'

async def cmd_volume(bot, message, player, new_volume=None):
    """
    Usage:
        {command_prefix}volume (+/-)[volume]

    Sets the playback volume. Accepted values are from 1 to 100.
    Putting + or - before the volume will make the volume change relative to the current volume.
    """

    if not new_volume:
        return Response(bot.str.get('cmd-volume-current', 'Current volume: `%s%%`') % int(player.volume * 100), reply=True, delete_after=20)

    relative = False
    if new_volume[0] in '+-':
        relative = True

    try:
        new_volume = int(new_volume)

    except ValueError:
        raise exceptions.CommandError(bot.str.get('cmd-volume-invalid', '`{0}` is not a valid number').format(new_volume), expire_in=20)

    vol_change = None
    if relative:
        vol_change = new_volume
        new_volume += (player.volume * 100)

    old_volume = int(player.volume * 100)

    if 0 < new_volume <= 100:
        player.volume = new_volume / 100.0

        return Response(bot.str.get('cmd-volume-reply', 'Updated volume from **%d** to **%d**') % (old_volume, new_volume), reply=True, delete_after=20)

    else:
        if relative:
            raise exceptions.CommandError(
                bot.str.get('cmd-volume-unreasonable-relative', 'Unreasonable volume change provided: {}{:+} -> {}%.  Provide a change between {} and {:+}.').format(
                    old_volume, vol_change, old_volume + vol_change, 1 - old_volume, 100 - old_volume), expire_in=20)
        else:
            raise exceptions.CommandError(
                bot.str.get('cmd-volume-unreasonable-absolute', 'Unreasonable volume provided: {}%. Provide a value between 1 and 100.').format(new_volume), expire_in=20)

async def cmd_resume(bot, player):
    """
    Usage:
        {command_prefix}resume

    Resumes playback of a paused song.
    """

    if player.is_paused:
        player.resume()
        return Response(bot.str.get('cmd-resume-reply', 'Resumed music in `{0.name}`').format(player.voice_client.channel), delete_after=15)

    else:
        raise exceptions.CommandError(bot.str.get('cmd-resume-none', 'Player is not paused.'), expire_in=30)

async def cmd_pause(bot, player):
    """
    Usage:
        {command_prefix}pause

    Pauses playback of the current song.
    """

    if player.is_playing:
        player.pause()
        return Response(bot.str.get('cmd-pause-reply', 'Paused music in `{0.name}`').format(player.voice_client.channel))

    else:
        raise exceptions.CommandError(bot.str.get('cmd-pause-none', 'Player is not playing.'), expire_in=30)