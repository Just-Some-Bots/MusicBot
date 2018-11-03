import inspect
import traceback
import logging
import asyncio

from collections import defaultdict
from abc import ABCMeta, abstractmethod
from . import exceptions

log = logging.getLogger(__name__)

class Cog:
    def __init__(self, name):
        # @TheerapakG: For anyone who will work on this, COG NAME SHALL NOT BE CHANGEABLE VIA A COMMAND. IT'S VERY UNREASONABLE WHY YOU'D WANT TO DO IT AND WILL BREAK THIS
        self.name = name
        self.commands = set()
        self.loaded = True
        self.cmdrun = 0
        self.aiolocks = defaultdict(asyncio.Lock)

    def __hash__(self):
        return hash(self.name)

    def __str__(self):
        return repr(self)[:-1] + " name: {0}>".format(self.name)

    def __eq__(self, other):
        return self.name == other.name

    async def inclock(self):
        async with self.aiolocks['lock_cmdrun']:
            self.cmdrun += 1
            if self.cmdrun == 1:
                await self.aiolocks['lock_clear'].acquire()

    async def declock(self):
        async with self.aiolocks['lock_cmdrun']:
            self.cmdrun -= 1
            if self.cmdrun == 0:
                self.aiolocks['lock_clear'].release()

    async def add_command(self, command):
        async with self.aiolocks['lock_cmdrun']:
            async with self.aiolocks['lock_clear']:
                if(command in self.commands):
                    self.commands.discard(command)
                self.commands.add(command)

    async def delete_command(self, command):
        async with self.aiolocks['lock_cmdrun']:
            async with self.aiolocks['lock_clear']:
                self.commands.discard(command)

    async def load(self):
        async with self.aiolocks['lock_cmdrun']:
            async with self.aiolocks['lock_clear']:
                self.loaded = True

    async def unload(self):
        async with self.aiolocks['lock_cmdrun']:
            async with self.aiolocks['lock_clear']:
                self.loaded = False

cogs = set()
commands = set()

# @TheerapakG: yea I know it's a hack, docstring aren't suppose to do this but I need it. Problems?
class ModifiabledocABCMeta(ABCMeta):
    def __new__(cls, clsname, bases, dct):

        fget = None

        fset = None

        for name, val in dct.copy().items():
            if name == 'doc':
                fget = val
            if name == 'setdoc':
                fset = val
        
        dct['__doc__'] = property(fget, fset, None, None)

        return super(ModifiabledocABCMeta, cls).__new__(cls, clsname, bases, dct)


class Command(metaclass = ModifiabledocABCMeta):
    def __init__(self, cog, name):
        self.name = name
        self.cog = cog
        self.alias = set()
        self.aiolocks = defaultdict(asyncio.Lock)
        commands.add(self)

    @abstractmethod
    def __call__(self, **kwargs):
        pass

    def __hash__(self):
        return hash(self.name)

    def __str__(self):
        return repr(self)[:-1] + " name: {0}>".format(self.name)

    def __eq__(self, other):
        return self.name == other.name
            
    async def add_alias(self, alias):
        async with self.aiolocks['lock_alias']:
            if alias in self.alias:
                log.warn("`{0}` is already an alias of command `{1}`".format(alias, self.name))
            else:
                self.alias.add(alias)

    async def remove_alias(self, alias):
        async with self.aiolocks['lock_alias']:
            try:
                self.alias.remove(alias)
            except KeyError:
                log.warn("`{0}` is not an alias of command `{1}`".format(alias, self.name))

    async def remove_all_alias(self):
        async with self.aiolocks['lock_alias']:
            self.alias = set([self.name])

    async def have_alias(self, cmd):
        async with self.aiolocks['lock_alias']:
            return True if cmd in self.alias else False

# for the day we know there exist malformed function in module and we can get partial attr
# very hopeful dream right there
class UncallableCommand(Command):
    def __init__(self, cog, name):
        super().__init__(cog, name)

    def __call__(self, **kwargs):
        log.error("Command `{0}` in cog `{1}` is not callable.".format(self.name, self.cog))
        

class CallableCommand(Command):
    def __init__(self, cog, name, func):
        super().__init__(cog, name)
        self.func = func
    
    def doc(self):
        return "{}\n    alias: {}".format(self.func.__doc__, " ".join(self.alias))

    async def with_callback(self, cog, **kwargs):
        try:
            res = await self.func(**kwargs)
        except (exceptions.CommandError, exceptions.HelpfulError, exceptions.ExtractionError):
            # TODO: Check if this need unloading cogs 
            raise

        except exceptions.Signal:
            raise

        except Exception:   
            await cog.unload()
            raise exceptions.CogError("unloaded cog `{0}`.".format(cog), expire_in= 40, traceback=traceback.format_exc()) from None
        return res

    async def __call__(self, **kwargs):
        for itcog in cogs:
            if itcog.name == self.cog:
                await itcog.inclock()
                loaded = itcog.loaded
                await itcog.declock()
                if not loaded:
                    raise exceptions.CogError("Command `{0}` in cog `{1}` have been unloaded.".format(self.name, self.cog), expire_in=20)

                return await self.with_callback(itcog, **kwargs)
        raise exceptions.CogError("Command `{0}` in cog `{1}` not found, very weird. Please try restarting the bot if this issue persist".format(self.name, self.cog), expire_in=20)

    def params(self):
        argspec = inspect.signature(self.func)
        return argspec.parameters.copy()

async def command(cog, name, func):
    cmd = CallableCommand(cog, name, func)
    if Cog(cog) not in cogs:
        cogs.add(Cog(cog))
    for itcog in cogs:
        if itcog.name == cog:
            await itcog.add_command(cmd)
    return cmd

async def getcommand(cmd):
    for command in commands:
        # log.debug("checking against {0}".format(str(command)))
        have = await command.have_alias(cmd)
        if have:
            return command
    log.debug("command (or alias) `{0}` not found".format(cmd))
    raise exceptions.CogError("command (or alias) `{0}` not found".format(cmd))

async def call(cmd, **kwargs):
    return await getcommand(cmd)(**kwargs)

def getcog(name):
    for itcog in cogs:
        if itcog.name == name:
            return itcog
    raise exceptions.CogError("cog `{0}` not found".format(name))