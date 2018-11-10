# higher-level functions for interacting with cogs asynchronously
import traceback
import logging
import asyncio
from inspect import iscoroutinefunction

from importlib import import_module, reload

from collections import defaultdict

from .cog import Cog, CallableCommand, UncallableCommand, command, call, getcommand, getcog, commands, cogs
from .alias import Alias, AliasDefaults
from . import exceptions

log = logging.getLogger(__name__)

imported = dict()

aiolocks = defaultdict(asyncio.Lock)

cmdrun = 0

alias = None

bot = None

def init_cog_system(botvar, alias_file=None):
    global alias
    if alias_file is None:
        alias_file = AliasDefaults.alias_file
    alias = Alias(alias_file)
    global bot
    bot = botvar

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
    global alias
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
        except AttributeError:
            log.error("module `{0}` doesn't specified cog name, skipping".format(module))
            message = "module `{0}` doesn't specified cog name, skipping".format(module)
        else:
            for att in dir(loaded):
                # first pass, init
                if att.startswith('init_'):
                    handler = getattr(loaded ,att, None)
                    if iscoroutinefunction(handler):
                        await handler(bot)

            for att in dir(loaded):
                # second pass, do actual work
                if att.startswith('cmd_'):
                    handler = getattr(loaded ,att, None)
                    if iscoroutinefunction(handler):
                        cmd = await command(cogname, att[4:], handler)
                        if att[4:] not in alias.aliases[att[4:]]:
                            log.debug("command `{0}` does not have alias of itself, fixing...".format(att[4:]))
                            alias.aliases[att[4:]].append(att[4:])
                        for als in alias.aliases[att[4:]]:
                            await cmd.add_alias(als, forced = True)

                if att.startswith('asyncloop_'):
                    handler = getattr(loaded ,att, None)
                    if iscoroutinefunction(handler):
                        def wraploop(func):

                            async def wrapped():
                                try:
                                    await func(bot)
                                except Exception as e:
                                    log.error(e)
                                    return
                                if(hasattr(func, 'delay')):
                                    await asyncio.sleep(func.delay)
                                else:
                                    await asyncio.sleep(0)
                                asyncio.create_task(wrapped())

                            return wrapped()

                        await wraploop(handler)
                        
            log.info("successfully loaded/reloaded module `{0}`".format(module))
            message = "successfully loaded/reloaded module `{0}`".format(module)

    except Exception:
        log.debug(traceback.format_exc())
        log.error("can't load module `{0}`, skipping".format(module))
        message = "can't load module `{0}`, skipping".format(module)
    except:
        pass
    finally:
        aiolocks['lock_clear'].release()
        aiolocks['lock_execute'].release()
        return message

async def checkblockloading():
    await aiolocks['lock_execute'].acquire()
    aiolocks['lock_execute'].release()

async def unloadcog(cog):
    await checkblockloading()
    await inclock()
    cogobj = getcog(cog)
    await cogobj.unload()
    await declock()

async def loadcog(cog):
    await checkblockloading()
    await inclock()
    cogobj = getcog(cog)
    await cogobj.load()
    await declock()

async def getcmd(cmd):
    await checkblockloading()
    await inclock()
    res = await getcommand(cmd)
    await declock()
    return res

async def callcmd(cmd, *args, **kwargs):
    await checkblockloading()
    await inclock()
    res = await call(cmd, *args, **kwargs)
    await declock()
    return res

async def add_alias(cmd, als, forced = False):
    global alias
    await checkblockloading()
    await inclock()
    command = await getcmd(cmd)
    await command.add_alias(als, forced)
    alias.aliases[cmd].append(als)
    # @TheerapakG: TODO: add option persistentalias
    alias.write_alias()
    await declock()

async def remove_alias(als):
    global alias
    await checkblockloading()
    await inclock()
    command = await getcmd(als)
    if command.name == als:
        await declock()
        raise exceptions.CogError('Attempt to remove command name from an alias: {0}'.format(command.name))
    await command.remove_alias(als)
    alias.aliases[command.name].remove(als)
    # @TheerapakG: TODO: add option persistentalias
    alias.write_alias()
    await declock()

async def gen_cmd_list():
    await checkblockloading()
    await inclock()
    ret = list(commands)
    await declock()
    return ret

async def gen_cog_list():
    await checkblockloading()
    await inclock()
    ret = list(cogs)
    await declock()
    return ret

async def gen_cmd_list_from_cog(cogname):
    await checkblockloading()
    await inclock()
    ret = None
    try:
        cog = getcog(cogname)
        ret = list(cog.commands)
    finally:
        await declock()
        return ret