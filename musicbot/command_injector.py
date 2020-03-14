from discord.ext.commands import Command, Group, command, group
import traceback
import inspect
from typing import Optional, Union, Iterable, AnyStr, Set
from .lib.event_emitter import AsyncEventEmitter, on
from .utils import DependencyResolver, isiterable

class CommandGenerator:
    def __init__(self, cmd, *, group = False):
        """
        @TheerapakG: Passing Command object directly is heavily discouraged
        because creating new cmd based on old kwargs uses undocumented feature
        """
        if isinstance(cmd, Command):
            self.group = group or isinstance(cmd, Group)
            self.cmd_func = cmd.callback
            if hasattr(cmd, '__original_kwargs__'):
                self.cmd_kwargs = cmd.__original_kwargs__.copy()
            else:
                self.cmd_kwargs = dict()
        else:
            self.group = group
            self.cmd_func = cmd
            self.cmd_kwargs = dict()

        class PatchHelpMixin:
            def __init__(p_self, *args, bot = None, **kwargs):
                p_self.generator = self
                p_self.bot = bot
                super().__init__(*args, **kwargs)

            @property
            def help(p_self):
                return '{}\n\nAll names: {}'.format(p_self._help, ', '.join(p_self.bot.command_tree.registered_as[p_self.callback]))

            @help.setter
            def help(self, real_help):
                self._help = real_help

        if self.group:
            class DynHelpGroup(PatchHelpMixin, Group):
                pass
            self.cmd_cls = DynHelpGroup
        else:
            class DynHelpCommand(PatchHelpMixin, Command):
                pass
            self.cmd_cls = DynHelpCommand

    def __repr__(self):
        return 'CommandGenerator(func = {}, group = {})'.format(self.cmd_func, self.group)

    def make_command(self, **kwargs):
        cmd_kwargs = self.cmd_kwargs
        cmd_kwargs.update(kwargs)
        new = command(cls = self.cmd_cls, **cmd_kwargs)(self.cmd_func)
        return new    

class _MarkInject:
    def __init__(self, name, after: Optional[Set], injectfunction, ejectfunction, cmd: CommandGenerator, *, child = None):
        self.name = name
        self.after = after if after else set()
        self.inject = injectfunction
        self.eject = ejectfunction
        self.cmd = cmd
        self.child = child

    def __repr__(self):
        return '_MarkInject(name = {}, cmd = {})'.format(self.name, repr(self.cmd))

class InjectableMixin(AsyncEventEmitter):
    @on('pre_init')
    async def pre_init(self, bot):
        self.bot = bot
        self.log = self.bot.log
        self.injects = dict()
        self.injectdeps = DependencyResolver()

    @on('init')
    async def init(self):
        for item in dir(self):
            if hasattr(type(self), item) and isinstance(getattr(type(self), item), property):
                continue
            iteminst = getattr(self, item)
            if isinstance(iteminst, _MarkInject):
                self.injects[iteminst.name] = iteminst
                while iteminst.child:
                    iteminst.child.after.add(iteminst.name)
                    iteminst = iteminst.child
                    self.injects[iteminst.name] = iteminst

        for item in self.injects.values():
            self.injectdeps.add_item(item.name, item.after)

        satisfied, unsatisfied = self.injectdeps.get_state()

        if unsatisfied:
            self.log.warning('These following injections does not have dependencies required and will not be loaded: {}'.format(', '.join(unsatisfied)))
            for name in unsatisfied:
                self.injectdeps.remove_item(name)
                del self.injects[name]
        
        for name in satisfied:
            item = self.injects[name]
            self.bot.log.debug('injecting with {}'.format(item.inject))
            try:
                item.inject(self.bot, self)
            except:
                self.bot.log.error(traceback.format_exc())

    @on('uninit')
    async def uninit(self):
        unloadlist = self.injectdeps.get_state()[0]
        unloadlist.reverse()
        
        for name in unloadlist:
            item = self.injects[name]
            self.bot.log.debug('ejecting with {}'.format(item.eject))
            try:
                item.eject(self.bot)
            except:
                self.bot.log.error(traceback.format_exc())

def ensure_inject(potentially_injected, *, group = False) -> _MarkInject:
    if not isinstance(potentially_injected, _MarkInject):
        if isinstance(potentially_injected, Command):
            return _MarkInject(
                potentially_injected.name,
                None,
                lambda *args, **kwargs: None,
                lambda *args, **kwargs: None,
                CommandGenerator(potentially_injected, group = group)
            )
        elif inspect.iscoroutinefunction(potentially_injected):
            return _MarkInject(
                potentially_injected.__name__ if hasattr(potentially_injected, '__name__') else repr(potentially_injected),
                None,
                lambda *args, **kwargs: None,
                lambda *args, **kwargs: None,
                CommandGenerator(potentially_injected, group = group)
            )
        else:
            raise ValueError("unknown type to ensure inject: {}".format(type(potentially_injected)))
    return potentially_injected

def try_append_payload(name, injected: _MarkInject, inject, eject, after:Optional[Union[AnyStr,Iterable[AnyStr]]] = None):
    if not after:
        after = set()
    elif isinstance(after, str):
        after = set([after])
    elif isiterable(after):
        after = set(after)
    return _MarkInject(
        name,
        after,
        inject,
        eject,
        injected.cmd,
        child = injected
    )

def inject_as_subcommand(groupcommand, *, inject_name = None, after:Optional[Union[AnyStr,Iterable[AnyStr]]] = None, **kwargs):
    def do_inject(subcommand):
        subcommand = ensure_inject(subcommand)
        subcmd = None
        def inject(bot, cog):
            bot.log.debug('Invoking inject_as_subcommand injecting {} to {}'.format(subcommand.cmd, groupcommand))
            nonlocal subcmd
            subcmd = subcommand.cmd.make_command(bot = bot, **kwargs)
            subcmd.cog = cog
            bot.add_command(subcmd, base=groupcommand)

        def eject(bot):
            bot.log.debug('Invoking inject_as_subcommand ejecting {} from {}'.format(subcommand.cmd, groupcommand))
            nonlocal subcmd
            bot.remove_command(subcmd.qualified_name)

        name = kwargs.get('name', subcommand.cmd.cmd_func.__name__)

        return try_append_payload(
            inject_name if inject_name else 'inject_{}_{}'.format('_'.join(groupcommand.split()), name),
            subcommand, 
            inject, 
            eject,
            after
        )
    return do_inject

def inject_as_group(command):
    return ensure_inject(command, group = True)

def inject_as_main_command(names:Union[AnyStr,Iterable[AnyStr]], *, inject_name = None, after:Optional[Union[AnyStr,Iterable[AnyStr]]] = None, **kwargs):
    if isinstance(names, str):
        names = (names, )

    def do_inject(command):
        command = ensure_inject(command)
        def inject(bot, cog):
            bot.log.debug('Invoking inject_as_main_command injecting {} as {}'.format(command.cmd, names))
            for name in names:
                cmd = command.cmd.make_command(name = name, bot = bot, **kwargs)
                cmd.cog = cog
                bot.add_command(cmd)

        def eject(bot):
            bot.log.debug('Invoking inject_as_main_command ejecting {}'.format(names))
            for name in names:
                bot.remove_command(name)

        return try_append_payload(
            inject_name if inject_name else 'inject_{}'.format('_'.join(names)),
            command, 
            inject, 
            eject,
            after
        )
    return do_inject