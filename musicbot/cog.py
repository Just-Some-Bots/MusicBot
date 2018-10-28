import logging
from .exceptions import MusicbotException

log = logging.getLogger(__name__)

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
        if cog not in cogs:
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


class UncallableCommand(Command):
    def __init__(self, cog, name):
        super().__init__(cog, name)

    def __call__(self, *args, **kwargs):
        log.error("Command {0} in cog {1} is not callable.".format(self.name, self.cog))
        

class CallableCommand(Command):
    def __init__(self, cog, name, func):
        super().__init__(cog, name)
        self.func = func

    def __call__(self, *args, **kwargs):
        for itcog in cogs:
            if itcog.name == self.cog:
                if not itcog.loaded:
                    log.error("Command {0} in cog {1} have been unloaded.".format(self.name, self.cog))
                try:
                    res = self.func(*args, **kwargs)
                    return res
                except MusicbotException as e:
                    log.error(e.message)
                    log.error("Exception caught in command {0} in cog {1}, unloading cog".format(self.name, self.cog))
                    itcog.unload()
                except Exception as e:
                    log.error(e)
                    log.error("Exception caught in command {0} in cog {1}, unloading cog".format(self.name, self.cog))
                    itcog.unload()

        log.error("Command {0} in cog {1} not found, very weird. Please try restarting the bot if this issue persist".format(self.name, self.cog))


def command(func):
    def wrap(cog, name, dependencies = list()):
        return CallableCommand(cog, name, func)    
    return wrap

def call(cmd, *args, **kwargs):
    try:
        cmdlookup[cmd](*args, **kwargs)
    except ValueError:
        log.error("command (or alias) {0} not found".format(cmd))