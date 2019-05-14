from functools import wraps
from discord.ext.commands import check as discord_check
from discord.ext.commands import Context

class CrossModule:
    def __init__(self):
        self._module_graph = dict()
        self._decorators = dict()
        self._preds = dict()
        self._objs = dict()
        self._features = dict()
        self._cogs = dict()
        self._commands = dict()
        self.imported = dict()

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

    def _add_module(self, module_name, module):
        self._features[module_name] = dict()
        self.imported[module_name] = module
        self._module_graph[module_name] = list()
        self._cogs[module_name] = list()
        self._commands[module_name] = list()

    def _remove_module(self, module_name):
        del self._features[module_name]
        del self.imported[module_name]
        del self._module_graph[module_name]
        del self._cogs[module_name]
        del self._commands[module_name]

    def _register_dependency(self, modulename, deps_module_list = []):
        for dep in deps_module_list:
            self._module_graph[dep].append(modulename)

    def modules_loaded(self):
        return list(self._features.keys())

    def _register_feature(self, module_name, feature, val):
        self._features[module_name][feature] = val

    def _unregister_feature(self, module_name, feature):
        del self._features[module_name][feature]

    def feature(self, module_name, feature):
        '''
        All behaving adults should not modify value returned by this method
        '''
        return self._features[module_name][feature]