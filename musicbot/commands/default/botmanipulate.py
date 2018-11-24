import logging
import discord
import aiohttp

from ...utils import _get_variable
from ... import exceptions
from ...constructs import Response
from ...wrappers import owner_only

log = logging.getLogger(__name__)

cog_name = 'bot_management'

async def cmd_disconnect(bot, guild):
    """
    Usage:
        {command_prefix}disconnect
    
    Forces the bot leave the current voice channel.
    """
    await bot.disconnect_voice_client(guild)
    return Response("Disconnected from `{0.name}`".format(guild), delete_after=20)

async def cmd_restart(bot, channel):
    """
    Usage:
        {command_prefix}restart
    
    Restarts the bot.
    Will not properly load new dependencies or file updates unless fully shutdown
    and restarted.
    """
    await bot.safe_send_message(channel, "\N{WAVING HAND SIGN} Restarting. If you have updated your bot "
        "or its dependencies, you need to restart the bot properly, rather than using this command.")

    player = bot.get_player_in(channel.guild)
    if player and player.is_paused:
        player.resume()

    await bot.disconnect_all_voice_clients()
    raise exceptions.RestartSignal()

async def cmd_shutdown(bot, channel):
    """
    Usage:
        {command_prefix}shutdown
    
    Disconnects from voice channels and closes the bot process.
    """
    await bot.safe_send_message(channel, "\N{WAVING HAND SIGN}")
    
    player = bot.get_player_in(channel.guild)
    if player and player.is_paused:
        player.resume()
    
    await bot.disconnect_all_voice_clients()
    raise exceptions.TerminateSignal()

async def cmd_leaveserver(bot, val, leftover_args):
    """
    Usage:
        {command_prefix}leaveserver <name/ID>

    Forces the bot to leave a server.
    When providing names, names are case-sensitive.
    """
    if leftover_args:
        val = ' '.join([val, *leftover_args])

    t = bot.get_guild(val)
    if t is None:
        t = discord.utils.get(bot.guilds, name=val)
        if t is None:
            raise exceptions.CommandError('No guild was found with the ID or name as `{0}`'.format(val))
    await t.leave()
    return Response('Left the guild: `{0.name}` (Owner: `{0.owner.name}`, ID: `{0.id}`)'.format(t))

async def cmd_setnick(bot, guild, channel, leftover_args, nick):
    """
    Usage:
        {command_prefix}setnick nick

    Changes the bot's nickname.
    """

    if not channel.permissions_for(guild.me).change_nickname:
        raise exceptions.CommandError("Unable to change nickname: no permission.")

    nick = ' '.join([nick, *leftover_args])

    try:
        await guild.me.edit(nick=nick)
    except Exception as e:
        raise exceptions.CommandError(e, expire_in=20)

    return Response("Set the bot's nickname to `{0}`".format(nick), delete_after=20)

@owner_only
async def cmd_setavatar(bot, message, url=None):
    """
    Usage:
        {command_prefix}setavatar [url]

    Changes the bot's avatar.
    Attaching a file and leaving the url parameter blank also works.
    """

    if message.attachments:
        thing = message.attachments[0].url
    elif url:
        thing = url.strip('<>')
    else:
        raise exceptions.CommandError("You must provide a URL or attach a file.", expire_in=20)

    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with bot.aiosession.get(thing, timeout=timeout) as res:
            await bot.user.edit(avatar=await res.read())

    except Exception as e:
        raise exceptions.CommandError("Unable to change avatar: {}".format(e), expire_in=20)

    return Response("Changed the bot's avatar.", delete_after=20)

@owner_only
async def cmd_setname(bot, leftover_args, name):
    """
    Usage:
        {command_prefix}setname name

    Changes the bot's username.
    Note: This operation is limited by discord to twice per hour.
    """

    name = ' '.join([name, *leftover_args])

    try:
        await bot.user.edit(username=name)

    except discord.HTTPException:
        raise exceptions.CommandError(
            "Failed to change name. Did you change names too many times?  "
            "Remember name changes are limited to twice per hour.")

    except Exception as e:
        raise exceptions.CommandError(e, expire_in=20)

    return Response("Set the bot's username to **{0}**".format(name), delete_after=20)

@owner_only
async def cmd_option(bot, player, option, value):
    """
    Usage:
        {command_prefix}option [option] [on/y/enabled/off/n/disabled]

    Changes a config option without restarting the bot. Changes aren't permanent and
    only last until the bot is restarted. To make permanent changes, edit the
    config file.

    Valid options:
        autoplaylist, save_videos, now_playing_mentions, auto_playlist_random, auto_pause,
        delete_messages, delete_invoking, write_current_song

    For information about these options, see the option's comment in the config file.
    """

    option = option.lower()
    value = value.lower()
    bool_y = ['on', 'y', 'enabled']
    bool_n = ['off', 'n', 'disabled']
    generic = ['save_videos', 'now_playing_mentions', 'auto_playlist_random',
                'auto_pause', 'delete_messages', 'delete_invoking',
                'write_current_song']  # these need to match attribute names in the Config class
    if option in ['autoplaylist', 'auto_playlist']:
        if value in bool_y:
            if bot.config.auto_playlist:
                raise exceptions.CommandError(bot.str.get('cmd-option-autoplaylist-enabled', 'The autoplaylist is already enabled!'))
            else:
                if not bot.autoplaylist:
                    raise exceptions.CommandError(bot.str.get('cmd-option-autoplaylist-none', 'There are no entries in the autoplaylist file.'))
                bot.config.auto_playlist = True
                await bot.on_player_finished_playing(player)
        elif value in bool_n:
            if not bot.config.auto_playlist:
                raise exceptions.CommandError(bot.str.get('cmd-option-autoplaylist-disabled', 'The autoplaylist is already disabled!'))
            else:
                bot.config.auto_playlist = False
        else:
            raise exceptions.CommandError(bot.str.get('cmd-option-invalid-value', 'The value provided was not valid.'))
        return Response("The autoplaylist is now " + ['disabled', 'enabled'][bot.config.auto_playlist] + '.')
    else:
        is_generic = [o for o in generic if o == option]  # check if it is a generic bool option
        if is_generic and (value in bool_y or value in bool_n):
            name = is_generic[0]
            log.debug('Setting attribute {0}'.format(name))
            setattr(bot.config, name, True if value in bool_y else False)  # this is scary but should work
            attr = getattr(bot.config, name)
            res = "The option {0} is now ".format(option) + ['disabled', 'enabled'][attr] + '.'
            log.warning('Option overriden for this session: {0}'.format(res))
            return Response(res)
        else:
            raise exceptions.CommandError(bot.str.get('cmd-option-invalid-param' ,'The parameters provided were invalid.'))

async def cmd_summon(bot, channel, guild, author, voice_channel):
    """
    Usage:
        {command_prefix}summon

    Call the bot to the summoner's voice channel.
    """

    if not author.voice:
        raise exceptions.CommandError(bot.str.get('cmd-summon-novc', 'You are not connected to voice. Try joining a voice channel!'))

    voice_client = bot.voice_client_in(guild)
    if voice_client and guild == author.voice.channel.guild:
        await voice_client.move_to(author.voice.channel)
    else:
        # move to _verify_vc_perms?
        chperms = author.voice.channel.permissions_for(guild.me)

        if not chperms.connect:
            log.warning("Cannot join channel '{0}', no permission.".format(author.voice.channel.name))
            raise exceptions.CommandError(
                bot.str.get('cmd-summon-noperms-connect', "Cannot join channel `{0}`, no permission to connect.").format(author.voice.channel.name),
                expire_in=25
            )

        elif not chperms.speak:
            log.warning("Cannot join channel '{0}', no permission to speak.".format(author.voice.channel.name))
            raise exceptions.CommandError(
                bot.str.get('cmd-summon-noperms-speak', "Cannot join channel `{0}`, no permission to speak.").format(author.voice.channel.name),
                expire_in=25
            )

        player = await bot.get_player(author.voice.channel, create=True, deserialize=bot.config.persistent_queue)

        if player.is_stopped:
            player.play()

        if bot.config.auto_playlist:
            await bot.on_player_finished_playing(player)

    log.info("Joining {0.guild.name}/{0.name}".format(author.voice.channel))

    return Response(bot.str.get('cmd-summon-reply', 'Connected to `{0.name}`').format(author.voice.channel))

@owner_only
async def cmd_joinserver(bot, message, server_link=None):
    """
    Usage:
        {command_prefix}joinserver invite_link

    Asks the bot to join a server.  Note: Bot accounts cannot use invite links.
    """

    url = await bot.generate_invite_link()
    return Response(
        bot.str.get('cmd-joinserver-response', "Click here to add me to a server: \n{}").format(url),
        reply=True, delete_after=30
    )