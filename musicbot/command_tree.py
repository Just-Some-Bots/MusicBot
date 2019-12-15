from collections import namedtuple, defaultdict, Counter
from functools import partial

CommandInfo = namedtuple('CommandInfo', ['childs', 'parents'])

def _make_commandinfo():
    return CommandInfo(Counter(), Counter())

class CommandTree:
    def __init__(self):
        self.registered_count = Counter()
        self.tree = defaultdict(_make_commandinfo)
        self.flattened_tree = defaultdict(_make_commandinfo)

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
        
    def remove_command(self, command):
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
