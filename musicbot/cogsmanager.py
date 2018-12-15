# higher-level functions for interacting with cogs asynchronously
import traceback
import logging
import asyncio
import pkgutil
from textwrap import dedent
from inspect import iscoroutinefunction

from importlib import import_module, reload

from collections import defaultdict

from .cog import Cog, CallableCommand, UncallableCommand, command, call, getcommand, getcog, commands, cogs, cog
from .alias import Alias, AliasDefaults
from . import exceptions

log = logging.getLogger(__name__)

imported = dict()
looped = dict()
cleanup = dict()
cogmodule = dict()

aiolocks = defaultdict(asyncio.Lock)

cmdrun = 0

alias = None

bot = None

# @TheerapakG: TODO: FUTURE#1776?COG: implement cog class that will make it possible to have multiple cogs in one file
# for efficiency on loading (no need to iterate on which var is considered cog), I will probably implement it as some sort of metaclass (again)
# As I probably mentioned already in the PR that I won't do anything more, this will probably not be implement in #1766. #1766's main purpose is only to organize commands into place

def init_cog_system(botvar, alias_file=None):
    # @TheerapakG: TODO: FUTURE#1776?COG: prevent double initialization
    # @TheerapakG: TODO: FUTURE#1776?COG: commands should not work when not init
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

async def _try_cleanup_module(modname):
    if modname in looped:
        # stop loop
        log.debug('stopping {} loop(s)'.format(len(looped[modname])))
        for callab in looped[modname]:
            await callab.stop()
    
    if modname in cleanup:
        log.debug('running {} cleanup(s)'.format(len(cleanup[modname])))
        for hdlr in cleanup[modname]:
            await hdlr(bot)

async def _init_load_cog(loaded, modname):
    try:
        cogname = getattr(loaded, 'cog_name')
    except AttributeError:
        raise exceptions.CogError("module/submodule `{0}` doesn't specified cog name, skipping".format(modname)) from None
    else:
        log.debug("loading/reloading cog `{0}`".format(cogname))

        looped[modname] = list()
        cleanup[modname] = list()

        cogmodule[cogname] = modname

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
            if att.startswith('cleanup_'):
                cleanup[modname].append(getattr(loaded ,att, None))

        for att, handler in importfuncs['init']:
            if iscoroutinefunction(handler):
                await handler(bot)

        await cog(cogname)

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

                looped[modname].append(wraploop(handler, att))
                asyncio.create_task(looped[modname][-1]())
        
        # print notification if exist
        doc = getattr(loaded ,'notify', None)
        if doc:
            log.info("Notification from cog {}:".format(cogname))
            log.info(dedent(doc()))
            
        getcog(cogname).__doc__ = loaded.__doc__
        log.debug("successfully loaded/reloaded cog `{0}`".format(cogname))

async def _init_load_multicog(loaded, modname):
    log.debug("package `{0}` is specified as multicog, using multicog handler...".format(modname))
    coglist = getattr(loaded, 'coglist', 'ALL')
    if coglist == 'ALL':
        log.debug('loading all cogs on no coglist')
    for importer, submodname, ispkg in pkgutil.iter_modules(loaded.__path__): # pylint: disable=unused-variable
        if coglist == 'ALL' or submodname in coglist:
            if ispkg:
                log.debug("`{0}` is subpackage...".format(submodname))
                if '{}.{}'.format(modname, submodname) in imported:
                    log.debug("reloading `{0}`".format(submodname))
                    reload(imported['{}.{}'.format(modname, submodname)])
                    subpkg = imported['{}.{}'.format(modname, submodname)]
                else:
                    log.debug("loading `{0}`".format(submodname))
                    subpkg = import_module('.commands.{}.{}'.format(modname, submodname), 'musicbot')
                    imported['{}.{}'.format(modname, submodname)] = subpkg
                if hasattr(subpkg, 'use_multicog_loader') and getattr(subpkg, 'use_multicog_loader'):
                    await _init_load_multicog(subpkg, '{}.{}'.format(modname, submodname))
            else:
                if '{}.{}'.format(modname, submodname) in imported:
                    log.debug("reloading submodule `{0}`".format(submodname))
                    reload(imported['{}.{}'.format(modname, submodname)])
                    submodule = imported['{}.{}'.format(modname, submodname)]
                    await _try_cleanup_module('{}.{}'.format(modname, submodname))
                else:
                    log.debug("loading submodule `{0}`".format(submodname))
                    submodule = import_module('.commands.{}.{}'.format(modname, submodname), 'musicbot')
                    imported['{}.{}'.format(modname, submodname)] = submodule
                await _init_load_cog(submodule, '{}.{}'.format(modname, submodname))

async def uninit_cog_system():
    # @TheerapakG: TODO: FUTURE#1776?COG: clear commands when uninit
    # @TheerapakG: TODO: FUTURE#1776?COG: commands should not work when uninit
    await aiolocks['lock_execute'].acquire()
    await aiolocks['lock_clear'].acquire()
    for modname in looped:
        # stop loop
        log.debug('stopping {} loop(s)'.format(len(looped[modname])))
        for callab in looped[modname]:
            await callab.stop()

    for modname in cleanup:
        log.debug('running {} cleanup(s)'.format(len(cleanup[modname])))
        for hdlr in cleanup[modname]:
            await hdlr(bot)

    aiolocks['lock_clear'].release()
    aiolocks['lock_execute'].release()

async def load(module):
    global alias
    await aiolocks['lock_execute'].acquire()
    await aiolocks['lock_clear'].acquire()
    try:
        loaded = None
        if module in imported:
            await _try_cleanup_module(module)
            log.debug("reloading module/package `{0}`".format(module))
            reload(imported[module])
            loaded = imported[module]
        else:
            log.debug("loading module/package `{0}`".format(module))
            loaded = import_module('.commands.{}'.format(module), 'musicbot')
            imported[module] = loaded

        if hasattr(loaded, 'use_multicog_loader') and getattr(loaded, 'use_multicog_loader'):
            await _init_load_multicog(loaded, module)

        else:
            await _init_load_cog(loaded, module)

        log.debug("successfully loaded/reloaded module/package `{0}`".format(module))

    except Exception as e:
        raise exceptions.CogError("can't load module `{0}`, skipping".format(module)) from e
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

async def getcogmodule(cog):
    await checkblockloading()
    await inclock()
    try:
        return cogmodule[cog]
    except KeyError:
        raise exceptions.CogError('No specified cog: {0}'.format(cog)) from None
    finally:
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
    try:
        command = await getcmd(cmd)
        await command.add_alias(als, forced)
    except exceptions.CogError:
        await declock()
        raise exceptions.CogError('Attempt to add existing alias: {0}'.format(als)) from None
    else:
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