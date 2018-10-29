# higher-level functions for interacting with cogs asynchronously
import traceback
import logging
import asyncio

from importlib import import_module, reload

from collections import defaultdict

from .cog import Cog, CallableCommand, UncallableCommand, command, call, getcmd, cmdlookup, getcog
from .config import Config, ConfigDefaults

log = logging.getLogger(__name__)

imported = dict()

aiolocks = defaultdict(asyncio.Lock)

cmdrun = 0

# @TheerapakG: dodgy asyncio locking ahead, __in my head__ it should be correct but I can't guarantee. Can someone check?

async def inclock():
    global cmdrun
    async with aiolocks['lock_cmdrun']:
        cmdrun += 1
        if cmdrun == 1:
            await aiolocks['lock_clear'].acquire()

async def declock():
    global cmdrun
    async with aiolocks['lock_cmdrun']:
        cmdrun -= 1
        if cmdrun == 0:
            aiolocks['lock_clear'].release()

# we cannot throw exception here because this is used when starting bot, or we need to have helper function that catch these exception
async def load(module):
    await aiolocks['lock_execute'].acquire()
    await aiolocks['lock_clear'].acquire()
    message = ""
    try:
        log.info("loading module `{0}`".format(module))
        loaded = None
        if module in imported:
            reload(imported[module])
            loaded = imported[module]
        else:
            loaded = import_module('.commands.{}'.format(module), 'musicbot')

        cogname = None

        try:
            cogname = getattr(loaded, 'cog_name')
            for att in dir(loaded):
                if att.startswith('cmd_'):
                    handler = getattr(loaded ,att, None)
                    command(cogname, att[4:], handler)
            log.info("successfully loaded/reloaded module `{0}`".format(module))
            message = "successfully loaded/reloaded module `{0}`".format(module)

        except AttributeError:
            log.error("module `{0}` doesn't specified cog name, skipping".format(module))
            message = "module `{0}` doesn't specified cog name, skipping".format(module)

    except Exception:
        log.debug(traceback.format_exc())
        log.error("can't load module `{0}`, skipping".format(module))
        message = "can't load module `{0}`, skipping".format(module)
    finally:
        aiolocks['lock_clear'].release()
        aiolocks['lock_execute'].release()
        return message

async def blockloading():
    await aiolocks['lock_execute'].acquire()
    aiolocks['lock_execute'].release()

async def unloadcog(cog):
    await blockloading()
    await inclock()
    cogobj = getcog(cog)
    if cogobj:
        cogobj.unload()
    await declock()

async def loadcog(cog):
    await blockloading()
    await inclock()
    cogobj = getcog(cog)
    if cogobj:
        cogobj.load()
    await declock()

async def callcmd(cmd, *args, **kwargs):
    await blockloading()
    await inclock()
    res = await call(cmd, *args, **kwargs)
    await declock()
    return res

async def add_alias(cmd, alias):
    await blockloading()
    await inclock()
    getcmd(cmd).add_alias(alias)
    await declock()

async def remove_alias(cmd, alias):
    await blockloading()
    await inclock()
    getcmd(cmd).remove_alias(alias)
    await declock()

async def gen_cmd_list_with_alias():
    await blockloading()
    await inclock()
    ret = cmdlookup.copy()
    await declock()
    return ret