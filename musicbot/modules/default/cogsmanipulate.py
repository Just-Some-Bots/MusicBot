import logging
from typing import Optional

from discord.ext.commands import Cog, command

from ...utils import _get_variable
from ... import exceptions
from ...wrappers import owner_only, dev_only

from ... import messagemanager

log = logging.getLogger(__name__)

# TODO: changing alias interact with alias.py

class CogManagement(Cog):
    @command()
    @owner_only
    async def loadmodule(self, ctx, *, module:str):
        """
        Usage:
            {command_prefix}loadmodule module

        Load (or reload) specified module.
        """
        try:
            await ctx.bot.load_modules([module])
        except:
            raise
        else:
            await messagemanager.safe_send_normal(ctx, ctx, ctx.bot.str.get('cogs?cmd?loadmodule?success', "successfully loaded/reloaded module `{0}`").format(module), expire_in=15)

    @command()
    @owner_only
    async def cogmodule(self, ctx, *, name:str):
        """
        Usage:
            {command_prefix}cogmodule cog

        Get module name of specified cog.
        """
        # TODO:
        module = 'not implemented'
        await messagemanager.safe_send_normal(ctx, ctx, '```{}```'.format(module), expire_in=15)

    @command()
    @owner_only
    async def addalias(self, ctx, command:str, alias:str, *, param:Optional[str]):
        """
        Usage:
            {command_prefix}addalias command alias [force/f]

        Add alias to the command.
        """
        origc = ctx.bot.get_command(alias)
        if origc and not (param.lower() in ['force', 'f']):
            raise Exception('already have alias')
        elif origc:
            try:
                origc.aliases.remove(alias)
            except ValueError:
                raise Exception('alias is a command')

        c = ctx.bot.get_command(command)
        c.aliases.append(alias)

        await messagemanager.safe_send_normal(ctx, ctx, ctx.bot.str.get('cogs?cmd?addalias?success', "Successfully add alias `{0}` to command `{1}`").format(alias, command), expire_in=15)

    @command()
    @owner_only
    async def removealias(self, ctx, alias:str):
        """
        Usage:
            {command_prefix}removealias command alias

        Remove alias from the command.
        """
        origc = ctx.bot.get_command(alias)
        if origc:
            try:
                origc.aliases.remove(alias)
            except ValueError:
                raise Exception('alias is a command')
            await messagemanager.safe_send_normal(ctx, ctx, ctx.bot.str.get('cogs?cmd?removealias?success', "Successfully remove alias `{0}`").format(alias), expire_in=15)
        else:
            raise Exception('no such alias')

cogs = [CogManagement]