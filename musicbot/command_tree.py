from collections import Counter, defaultdict, namedtuple
from functools import partial
from discord.ext.commands import Group

CommandInfo = namedtuple('CommandInfo', ['childs', 'parents'])

def _make_commandinfo():
    return CommandInfo(Counter(), Counter())

class CommandTree:
    def __init__(self, bot):
        self.bot = bot
        self.registered_count = Counter()
        self.tree = defaultdict(_make_commandinfo)
        self.flattened_tree = defaultdict(_make_commandinfo)
        self.whitelist_counted = defaultdict(Counter)
        self.blacklist_counted = defaultdict(Counter)

    def add_command(self, command):
        self.registered_count[command.callback] += 1
        self.tree[command.callback]
        self.flattened_tree[command.callback]
        if command.parent:
            self.tree[command.parent.callback].childs[command.callback] += 1
            + self.tree[command.parent.callback].childs
            self.tree[command.callback].parents[command.parent.callback] += 1
            + self.tree[command.parent.callback].parents
            parents = self._updated_get_parents(command.parent.callback)
            parents[command.parent.callback] += 1
            for p in parents.elements():
                self.flattened_tree[p].childs[command.callback] += 1
            self.flattened_tree[command.callback].parents.update(parents)

        # @TheerapakG: I choose to eagerly evaluate whitelist & blacklist to make executing command overhead as low as possible
        cmd = command
        while cmd:
            for permissions in self.bot.permissions.groups:
                if cmd.qualified_name in permissions._command_whitelist:
                    self.whitelist_counted[permissions][command.callback] += 1
                if cmd.qualified_name in permissions._command_blacklist:
                    self.blacklist_counted[permissions][command.callback] += 1
            cmd = cmd.parent

        for permissions in self.bot.permissions.groups:
            permissions.command_whitelist = set(self.whitelist_counted[permissions].keys())
            permissions.command_blacklist = set(self.blacklist_counted[permissions].keys())
        
    def remove_command(self, command):
        # Do thing in reverse
        if isinstance(command, Group):
            childs = [c for c in command.walk_commands()]
            childs.append(command)
        else:
            childs = [command]

        cmd = command

        while cmd:
            for permissions in self.bot.permissions.groups:
                if cmd.qualified_name in permissions._command_whitelist:
                    self.whitelist_counted[permissions].subtract(childs)
                if cmd.qualified_name in permissions._command_blacklist:
                    self.blacklist_counted[permissions].subtract(childs)
            cmd = cmd.parent

        for permissions in self.bot.permissions.groups:
            + self.whitelist_counted[permissions]
            permissions.command_whitelist = set(self.whitelist_counted[permissions].keys())
            + self.blacklist_counted[permissions]
            permissions.command_blacklist = set(self.blacklist_counted[permissions].keys())

        if command.parent:
            self.tree[command.parent.callback].childs[command.callback] -= 1
            + self.tree[command.parent.callback].childs
            self.tree[command.callback].parents[command.parent.callback] -= 1
            + self.tree[command.parent.callback].parents
            parents = self._updated_get_parents(command.callback)
            childs = self._updated_get_childs(command.callback)
            for p in parents.elements():
                self.flattened_tree[p].childs.subtract(childs)
                self.flattened_tree[p].childs[command.callback] -= 1
                + self.flattened_tree[p].childs
            for c in childs.elements():
                self.flattened_tree[c].parents.subtract(parents)
                self.flattened_tree[c].parents[command.callback] -= 1
                + self.flattened_tree[p].parents

        self.registered_count[command.callback] -= 1
        if self.registered_count[command.callback] == 0:
            del self.tree[command.callback]
            del self.flattened_tree[command.callback]
            del self.registered_count[command.callback]


    def _updated_get_parents(self, callback):
        return self.flattened_tree[callback].parents.copy()

    def _updated_get_childs(self, callback):
        return self.flattened_tree[callback].childs.copy()

    def get_parents(self, callback):
        return set(self.flattened_tree[callback].parents.keys())

    def get_childs(self, callback):
        return set(self.flattened_tree[callback].childs.keys())
