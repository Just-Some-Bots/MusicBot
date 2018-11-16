import logging

from ..utils import _get_variable
from .. import exceptions
from ..constructs import Response
from ..cogsmanager import load, unloadcog, loadcog, add_alias, remove_alias
from ..wrappers import owner_only

log = logging.getLogger(__name__)

cog_name = 'cogs'

@owner_only
async def cmd_loadmodule(bot, module):
    """
    Usage:
        {command_prefix}loadmodule module

    Load (or reload) specified module.
    """
    try:
        await load(module)
    except:
        raise
    else:
        return Response(bot.str.get('cogs?cmd?loadmodule?success', "successfully loaded/reloaded module `{0}`").format(module), delete_after=15)

@owner_only
async def cmd_loadcog(bot, name):
    """
    Usage:
        {command_prefix}loadcog cog

    Load (or reload) specified cog. The module that implement the cog must already be loaded.
    """
    await loadcog(name)
    return Response(bot.str.get('cogs?cmd?loadcog?success', "Successfully reloaded cog `{0}`").format(name), delete_after=15)

@owner_only
async def cmd_unloadcog(bot, name):
    """
    Usage:
        {command_prefix}unloadcog cog

    Unload specified cog.
    """
    await unloadcog(name)
    return Response(bot.str.get('cogs?cmd?unloadcog?success', "Successfully unloaded cog `{0}`").format(name), delete_after=15)

@owner_only
async def cmd_addalias(bot, command, alias, param=''):
    """
    Usage:
        {command_prefix}addalias command alias [force/f]

    Add alias to the command.
    """
    if (param.lower() in ['force', 'f']):
        await add_alias(command, alias, forced = True)
    else:
        await add_alias(command, alias)
    return Response(bot.str.get('cogs?cmd?addalias?success', "Successfully add alias `{0}` to command `{1}`").format(alias, command), delete_after=15)

@owner_only
async def cmd_removealias(bot, alias):
    """
    Usage:
        {command_prefix}removealias command alias

    Remove alias from the command.
    """
    await remove_alias(alias)
    return Response(bot.str.get('cogs?cmd?removealias?success', "Successfully remove alias `{0}`").format(alias), delete_after=15)