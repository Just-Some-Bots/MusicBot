import logging
from functools import wraps

from ..utils import _get_variable
from .. import exceptions
from ..constructs import Response
from ..cogsmanager import load, unloadcog, loadcog

log = logging.getLogger(__name__)

cog_name = 'botmanipulate'

# @TheerapakG: TODO: move wrappers into one place
# TODO: Add some sort of `denied` argument for a message to send when someone else tries to use it
def owner_only(func):
    @wraps(func)
    async def wrapper(bot, *args, **kwargs):
        # Only allow the owner to use these commands
        orig_msg = _get_variable('message')

        if not orig_msg or orig_msg.author.id == bot.config.owner_id:
            # noinspection PyCallingNonCallable
            return await func(bot, *args, **kwargs)
        else:
            raise exceptions.PermissionsError("Only the owner can use this command.", expire_in=30)

    return wrapper

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