import inspect
import logging
from . import exceptions

log = logging.getLogger(__name__)

# @TheerapakG: TODO: when blacklist a command, it should also blacklist alias

class Cog:
    def __init__(self, name):
        self.name = name
        self.commands = set()
        self.load()

    def __hash__(self):
        return hash(self.name)

    def __str__(self):
        return repr(self)[:-1] + " name: {0}>".format(self.name)

    def __eq__(self, other):
        return self.name == other.name

    def add_command(self, command):
        if(command in self.commands):
            self.commands.discard(command)
        self.commands.add(command)

    def delete_command(self, command):
        self.commands.discard(command)
    
    def load(self):
        self.loaded = True

    def unload(self):
        self.loaded = False

cogs = set()
cmdlookup = dict()

class Command:
    def __init__(self, cog, name):
        self.name = name
        self.cog = cog
        if Cog(cog) not in cogs:
            cogs.add(Cog(cog))
        for itcog in cogs:
            if itcog.name == cog:
                itcog.add_command(self)
        self.add_alias(name)

    def __hash__(self):
        return hash(self.name)

    def __str__(self):
        return repr(self)[:-1] + " name: {0}>".format(self.name)

    def __eq__(self, other):
        return self.name == other.name
            
    def add_alias(self, alias):
        cmdlookup[alias] = self

    def remove_alias(self, alias):
        try:
            cmdlookup.pop(alias)
        except KeyError:
            log.error("{0} is not an alias of command {1}".format(alias, self.name))

    def remove_all_alias(self):
        for alias, cmd in cmdlookup.items():
            if cmd.name == self.name:
                cmdlookup.pop(alias)

# for the day we know there exist malformed function in module and we can get partial attr
# very hopeful dream right there
class UncallableCommand(Command):
    def __init__(self, cog, name):
        super().__init__(cog, name)

    def __call__(self, *args, **kwargs):
        log.error("Command {0} in cog {1} is not callable.".format(self.name, self.cog))
        

class CallableCommand(Command):
    def __init__(self, cog, name, func):
        super().__init__(cog, name)
        self.func = func
        self.__doc__ = func.__doc__

    def __call__(self, bot, *args, **kwargs):
        for itcog in cogs:
            if itcog.name == self.cog:
                if not itcog.loaded:
                    log.error("Command {0} in cog {1} have been unloaded.".format(self.name, self.cog))
                try:
                    res = self.func(bot, *args, **kwargs)
                    return res
                # @TheerapakG: TODO: add callback to unload cog using something similar to below instead
                except (exceptions.CommandError, exceptions.HelpfulError, exceptions.ExtractionError):
                    log.error("unloading cog {0}".format(self.cog))  
                    itcog.unload()
                    raise

                except exceptions.Signal:
                    raise

                except Exception:
                    log.error("unloading cog {0}".format(self.cog))    
                    itcog.unload()
                    raise

        log.error("Command {0} in cog {1} not found, very weird. Please try restarting the bot if this issue persist".format(self.name, self.cog))

    def params(self):
        argspec = inspect.signature(self.func)
        return argspec.parameters.copy()

def command(cog, name, func):
    return CallableCommand(cog, name, func)

def call(cmd, *args, **kwargs):
    try:
        cmdlookup[cmd](*args, **kwargs)
    except ValueError:
        log.error("command (or alias) {0} not found".format(cmd))

def getcmd(cmd):
    try:
        return cmdlookup[cmd]
    except ValueError:
        log.error("command (or alias) {0} not found".format(cmd))