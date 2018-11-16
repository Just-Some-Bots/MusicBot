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
looped = dict()

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

async def load(module):
    global alias
    await aiolocks['lock_execute'].acquire()
    await aiolocks['lock_clear'].acquire()
    try:
        loaded = None
        if module in imported:
            log.info("reloading module `{0}`".format(module))
            # stop loop
            log.debug('stopping {} loop(s)'.format(len(looped[module])))
            for callab in looped[module]:
                await callab.stop()

            for att in dir(imported[module]):
                # lookup code for cleanup
                if att.startswith('cleanup_'):
                    handler = getattr(imported[module] ,att, None)
                    if iscoroutinefunction(handler):
                        await handler(bot)
            reload(imported[module])
            loaded = imported[module]
        else:
            log.info("loading module `{0}`".format(module))
            loaded = import_module('.commands.{}'.format(module), 'musicbot')
            imported[module] = loaded

        looped[module] = list()

        cogname = None

        try:
            cogname = getattr(loaded, 'cog_name')
        except AttributeError:
            raise exceptions.CogError("module `{0}` doesn't specified cog name, skipping".format(module)) from None
        else:
            importfuncs = dict()
            importfuncs['init'] = list()
            importfuncs['cmd'] = list()
            importfuncs['asyncloop'] = list()

            for att in dir(loaded):
                if att.startswith('init_'):
                    importfuncs['init'].append((att, getattr(loaded ,att, None)))
                if att.startswith('cmd_'):
                    importfuncs['cmd'].append((att, getattr(loaded ,att, None)))
                if att.startswith('asyncloop_'):
                    importfuncs['asyncloop'].append((att, getattr(loaded ,att, None)))

            for att, handler in importfuncs['init']:
                if iscoroutinefunction(handler):
                    await handler(bot)

            for att, handler in importfuncs['cmd']:
                # second pass, do actual work
                if iscoroutinefunction(handler):
                    cmd = await command(cogname, att[4:], handler)
                    if att[4:] not in alias.aliases[att[4:]]:
                        log.debug("command `{0}` does not have alias of itself, fixing...".format(att[4:]))
                        alias.aliases[att[4:]].append(att[4:])
                    for als in alias.aliases[att[4:]]:
                        await cmd.add_alias(als, forced = True)

            for att, handler in importfuncs['asyncloop']:
                if iscoroutinefunction(handler):

                    class wraploop():

                        def __init__(self, func, fname):
                            self.fname = fname
                            self.func = func
                            self._stop = False
                            self.lock = defaultdict(asyncio.Lock)

                        async def __call__(self):
                            try:
                                await self.func(bot)
                            except Exception as e:
                                log.error(e)
                                return
                            if(hasattr(self.func, 'delay')):
                                await asyncio.sleep(self.func.delay)
                            else:
                                await asyncio.sleep(0)
                            async with self.lock['stop']:
                                if not self._stop:
                                    asyncio.create_task(self())

                        async def stop(self):
                            async with self.lock['stop']:
                                log.debug('{} will stop looping'.format(self.fname))
                                self._stop = True

                    looped[module].append(wraploop(handler, att))
                    asyncio.create_task(looped[module][-1]())
                        
            log.info("successfully loaded/reloaded module `{0}`".format(module))

    except Exception:
        raise exceptions.CogError("can't load module `{0}`, skipping".format(module), traceback=traceback.format_exc()) from None
    finally:
        aiolocks['lock_clear'].release()
        aiolocks['lock_execute'].release()

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
    try:
        res = await getcommand(cmd)
    except:
        await declock()
        raise
    await declock()
    return res

async def callcmd(cmd, *args, **kwargs):
    await checkblockloading()
    await inclock()
    try:
        res = await call(cmd, *args, **kwargs)
    except:
        await declock()
        raise
    await declock()
    return res

async def add_alias(cmd, als, forced = False):
    global alias
    await checkblockloading()
    await inclock()
    command = await getcmd(cmd)
    await command.add_alias(als, forced)
    alias.aliases[cmd].append(als)
    if bot.config.persistent_alias:
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
    if bot.config.persistent_alias:
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