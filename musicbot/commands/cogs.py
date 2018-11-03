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
    message = await load(module)
    return Response(message, delete_after=15)

@owner_only
async def cmd_loadcog(bot, name):
    await loadcog(name)
    return Response("Successfully reloaded cog `{0}`".format(name), delete_after=15)

@owner_only
async def cmd_unloadcog(bot, name):
    await unloadcog(name)
    return Response("Successfully unloaded cog `{0}`".format(name), delete_after=15)

@owner_only
async def cmd_addalias(bot, command, alias):
    await add_alias(command, alias)
    return Response("Successfully add alias `{0}` to command `{1}`".format(alias, command), delete_after=15)

@owner_only
async def cmd_removealias(bot, command, alias):
    await remove_alias(command, alias)
    return Response("Successfully add alias `{0}` to command `{1}`".format(alias, command), delete_after=15)