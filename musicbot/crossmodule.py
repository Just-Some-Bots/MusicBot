"""
MusicBot: The original Discord music bot written for Python 3.5+, using the discord.py library.
ModuBot: A modular discord bot with dependency management
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The MIT License (MIT)

Copyright (c) 2019 TheerapakG
Copyright (c) 2019 Just-Some-Bots (https://github.com/Just-Some-Bots)

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""

from functools import wraps
from collections import namedtuple
from discord.ext.commands import check as discord_check
from discord.ext.commands import Context

from .utils import DependencyResolver

ModuleInfo = namedtuple('ModuleInfo', ['name', 'imported_module_obj', 'cogs', 'commands'])

class CrossModule:
    def __init__(self):
        self._decorators = dict()
        self._preds = dict()
        self._objs = dict()

        self.dependency_graph = DependencyResolver()
        self.module = dict()

    def register_decorator(self, decorator):
        self._decorators[decorator.__name__] = decorator

    def unregister_decorator(self, decorator):
        del self._decorators[decorator.__name__]

    def decorate(self, name, *args, **kwargs):
        def decorate_use_name(func):
            @wraps(func)
            async def wrapper(*fargs, **fkwargs):
                return await (self._decorators[name](*args, **kwargs)(func))(*fargs, **fkwargs)
            return wrapper
        return decorate_use_name

    def raw_decorator(self, decorator):
        return self._decorators[decorator.__name__]

    def register_check(self, predicate):
        self._preds[predicate.__name__] = predicate

    def unregister_check(self, predicate):
        del self._preds[predicate.__name__]

    def check(self, name):
        def check_use_name(ctx):
            return discord_check(self._preds[name](ctx))
        return check_use_name

    def register_object(self, name, obj):
        self._objs[name] = obj

    def unregister_object(self, name):
        del self._objs[name]

    def get_object(self, name):
        return self._objs[name]

    async def async_call_object(self, name, *args, **kwargs):
        '''
        convenient function to call asynchronous object
        '''
        return await self._objs[name](*args, **kwargs)

    def call_object(self, name, *args, **kwargs):
        '''
        convenient function to call object
        '''
        return self._objs[name](*args, **kwargs)

    def assign_dict_object(self, name, index, value):
        '''
        convenient function to assign to a dict object
        '''
        self._objs[name][index] = value

    def register_module(self, module_name, module, dependencies = set()):
        self.dependency_graph.add_item(module_name, dependencies)
        self.module[module_name] = ModuleInfo(module_name, module, set(), set())

    def unregister_module(self, module_name):
        self.dependency_graph.remove_item(module_name)
        del self.module[module_name]

    def cogs_by_deps(self):
        '''
        yield cogs according to the dependency order of the module
        '''
        module_order = self.dependency_graph.get_state()[0]
        for module_name in module_order:
            for cog in self.module[module_name].cogs:
                yield cog

    def loaded_modules_name(self):
        return set(self.module.keys())