import logging
import discord
import aiohttp
import queue
import asyncio
from threading import Thread, Lock
from functools import partial
from discord.ext.commands import Cog, command
from typing import Optional

from ...utils import _get_variable
from ...command_injector import InjectableMixin, inject_as_subcommand, inject_as_main_command
from ... import exceptions
from ...smart_guild import get_guild
from ...wrappers import owner_only

from ... import messagemanager

class BotManagement(InjectableMixin, Cog):
    @command()
    async def disconnect(self, ctx):
        """
        Usage:
            {command_prefix}disconnect
        
        Forces the bot leave the current voice channel.
        """
        await get_guild(ctx.bot, ctx.guild).player.set_voice_channel(None)
        await messagemanager.safe_send_normal(ctx, ctx, "Disconnected from `{0.name}`".format(ctx.guild), expire_in=20)
        return

    async def _restart(self, ctx):
        await messagemanager.safe_send_normal(ctx, ctx, "\N{WAVING HAND SIGN} Restarting. If you have updated your bot "
            "or its dependencies, you need to restart the bot properly, rather than using this command.")
        ctx.bot._restart = True
        ctx.bot.loop.stop()

    @command()
    async def restart(self, ctx):
        """
        Usage:
            {command_prefix}restart
        
        Restarts the bot.
        """
        await self._restart(ctx)

    @command()
    async def shutdown(self, ctx):
        """
        Usage:
            {command_prefix}shutdown
        
        Disconnects from voice channels and closes the bot process.
        """
        await messagemanager.safe_send_normal(ctx, ctx, "\N{WAVING HAND SIGN}")
        
        ctx.bot.loop.stop()

    @command()
    async def update(self, ctx):
        """
        Usage:
            {command_prefix}update
        
        Update the bot.
        """
        from update import _main

        async def discordinput(prompt = None):
            def check(msg):
                return msg.author == ctx.message.author

            if prompt is not None:
                pmsg = await messagemanager.safe_send_normal(ctx, ctx, str(prompt).rstrip())

            try:
                msg = await ctx.bot.wait_for('message', timeout=10.0, check=check)
            except asyncio.TimeoutError:
                await messagemanager.safe_delete_message(pmsg)

            return msg.content

        async def discordoutput(*values, sep = ' ', end = '\n'):
            await messagemanager.safe_send_normal(ctx, ctx, sep.join([str(v) for v in values]) + end)

        await _main(read = discordinput, write = discordoutput)
        await self._restart(ctx)

    @command()
    async def leaveserver(self, ctx, guild: discord.Guild):
        """
        Usage:
            {command_prefix}leaveserver <name/ID>

        Forces the bot to leave a server.
        When providing names, names are case-sensitive.
        """
        await guild.leave()
        await messagemanager.safe_send_normal(ctx, ctx, 'Left the guild: `{0.name}` (Owner: `{0.owner.name}`, ID: `{0.id}`)'.format(guild))

    @inject_as_subcommand('set', name = 'nick')
    @inject_as_main_command('setnick')
    async def setnick(self, ctx, *, nick:str):
        """
        Usage:
            {command_prefix}set nick nick

        Changes the bot's nickname.
        """

        if not ctx.guild.me.guild_permissions.change_nickname:
            raise exceptions.CommandError("Unable to change nickname: no permission.")

        try:
            await ctx.guild.me.edit(nick=nick)
        except Exception as e:
            raise exceptions.CommandError(e, expire_in=20)

        await messagemanager.safe_send_normal(ctx, ctx, "Set the bot's nickname to `{0}`".format(nick), expire_in=20)
        return

    @inject_as_subcommand('set', name = 'avatar')
    @inject_as_main_command('setavatar')
    @owner_only
    async def setavatar(self, ctx, url: Optional[str]):
        """
        Usage:
            {command_prefix}setavatar [url]

        Changes the bot's avatar.
        Attaching a file and leaving the url parameter blank also works.
        """

        if ctx.message.attachments:
            thing = ctx.message.attachments[0].url
        elif url:
            thing = url.strip('<>')
        else:
            raise exceptions.CommandError("You must provide a URL or attach a file.", expire_in=20)

        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with ctx.bot.aiosession.get(thing, timeout=timeout) as res:
                await ctx.bot.user.edit(avatar=await res.read())

        except Exception as e:
            raise exceptions.CommandError("Unable to change avatar: {}".format(e), expire_in=20)

        await messagemanager.safe_send_normal(ctx, ctx, "Changed the bot's avatar.", expire_in=20)
        return

    @inject_as_subcommand('set', name = 'name')
    @inject_as_main_command('setname')
    @owner_only
    async def setname(self, ctx, *, name: str):
        """
        Usage:
            {command_prefix}setname name

        Changes the bot's username.
        Note: This operation is limited by discord to twice per hour.
        """

        try:
            await ctx.user.edit(username=name)

        except discord.HTTPException:
            raise exceptions.CommandError(
                "Failed to change name. Did you change names too many times?  "
                "Remember name changes are limited to twice per hour.")

        except Exception as e:
            raise exceptions.CommandError(e, expire_in=20)

        await messagemanager.safe_send_normal(ctx, ctx, "Set the bot's username to **{0}**".format(name), expire_in=20)
        return

    @command()
    @owner_only
    async def option(self, ctx, option: str, value: str):
        """
        Usage:
            {command_prefix}option [option] [on/y/enabled/off/n/disabled]

        Changes a config option without restarting the bot. Changes aren't permanent and
        only last until the bot is restarted. To make permanent changes, edit the
        config file.

        Valid options:
            autoplaylist, autostream save_videos, now_playing_mentions, auto_playlist_stream_random,
            auto_pause, delete_messages, delete_invoking, write_current_song

        For information about these options, see the option's comment in the config file.
        """

        option = option.lower()
        value = value.lower()
        bool_y = ['on', 'y', 'enabled']
        bool_n = ['off', 'n', 'disabled']
        generic = ['save_videos', 'now_playing_mentions', 'auto_playlist_stream_random',
                    'auto_pause', 'delete_messages', 'delete_invoking',
                    'write_current_song']  # these need to match attribute names in the Config class

        is_generic = [o for o in generic if o == option]  # check if it is a generic bool option
        if is_generic and (value in bool_y or value in bool_n):
            name = is_generic[0]
            ctx.bot.log.debug('Setting attribute {0}'.format(name))
            setattr(ctx.bot.config, name, True if value in bool_y else False)  # this is scary but should work
            attr = getattr(ctx.bot.config, name)
            res = "The option {0} is now ".format(option) + ['disabled', 'enabled'][attr] + '.'
            ctx.bot.log.warning('Option overriden for this session: {0}'.format(res))
            await messagemanager.safe_send_normal(ctx, ctx, res)
            return
        else:
            raise exceptions.CommandError(ctx.bot.str.get('cmd-option-invalid-param' ,'The parameters provided were invalid.'))

    @command()
    async def summon(self, ctx):
        """
        Usage:
            {command_prefix}summon

        Call the bot to the summoner's voice channel.
        """

        if not ctx.author.voice:
            raise exceptions.CommandError(ctx.bot.str.get('cmd-summon-novc', 'You are not connected to voice. Try joining a voice channel!'))

        guild = get_guild(ctx.bot, ctx.guild)
        await guild.player.set_voice_channel(ctx.author.voice.channel)
        # TODO: check if autoplay

        ctx.bot.log.info("Joining {0.guild.name}/{0.name}".format(ctx.author.voice.channel))

        await messagemanager.safe_send_normal(ctx, ctx, ctx.bot.str.get('cmd-summon-reply', 'Connected to `{0.name}`').format(ctx.author.voice.channel))

    @command()
    @owner_only
    async def joinserver(self, ctx):
        """
        Usage:
            {command_prefix}joinserver invite_link

        Asks the bot to join a server.  Note: Bot accounts cannot use invite links.
        """

        url = await ctx.bot.generate_invite_link()
        await messagemanager.safe_send_normal(
            ctx,
            ctx,
            ctx.bot.str.get('cmd-joinserver-response', "Click here to add me to a server: \n{}").format(url),
            reply=True, expire_in=30
        )

cogs = [BotManagement]
deps = ['default.base']