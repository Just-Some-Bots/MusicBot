import logging

from ..utils import _get_variable
from .. import exceptions
from ..constructs import Response
from ..cogsmanager import load, unloadcog, loadcog
from ..wrappers import owner_only

log = logging.getLogger(__name__)

cog_name = 'botmanipulate'

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