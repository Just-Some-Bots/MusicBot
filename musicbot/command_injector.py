from discord.ext.commands import Command, Group, command, group
import traceback
import inspect
from typing import Optional, Union, Iterable, AnyStr
from .lib.event_emitter import AsyncEventEmitter, on

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

        self.childs = set()

    def add_child(self, cmd_obj: Command):
        self.childs.add(cmd_obj)
        return self

    def make_command(self, **kwargs):
        cmd_kwargs = self.cmd_kwargs
        cmd_kwargs.update(kwargs)
        if self.group:
            new = group(**cmd_kwargs)(self.cmd_func)
        else:
            new = command(**cmd_kwargs)(self.cmd_func)
        self.childs.add(new)
        return new    

class _MarkInject:
    def __init__(self, injectfunction, ejectfunction, cmd: CommandGenerator):
        self.inject = injectfunction
        self.eject = ejectfunction
        self.cmd = cmd

class InjectableMixin(AsyncEventEmitter):
    @on('pre_init')
    async def pre_init(self, bot):
        self.bot = bot
        self.log = self.bot.log

    @on('init')
    async def init(self):
        for item in dir(self):
            if hasattr(type(self), item) and isinstance(getattr(type(self), item), property):
                continue
            iteminst = getattr(self, item)
            if isinstance(iteminst, _MarkInject):
                self.bot.log.debug('injecting with {}'.format(iteminst.inject))
                try:
                    iteminst.inject(self.bot, self)
                except:
                    self.bot.log.error(traceback.format_exc())

    @on('uninit')
    async def uninit(self):
        for item in dir(self):
            if hasattr(type(self), item) and isinstance(getattr(type(self), item), property):
                continue
            iteminst = getattr(self, item)
            if isinstance(iteminst, _MarkInject):
                self.bot.log.debug('ejecting with {}'.format(iteminst.eject))
                try:
                    iteminst.eject(self.bot)
                except:
                    self.bot.log.error(traceback.format_exc())

def ensure_inject(potentially_injected, *, group = False) -> _MarkInject:
    if not isinstance(potentially_injected, _MarkInject):
        if isinstance(potentially_injected, Command):
            return _MarkInject(
                lambda *args, **kwargs: None,
                lambda *args, **kwargs: None,
                CommandGenerator(potentially_injected, group = group).add_child(potentially_injected)
            )
        elif inspect.iscoroutinefunction(potentially_injected):
            return _MarkInject(
                lambda *args, **kwargs: None,
                lambda *args, **kwargs: None,
                CommandGenerator(potentially_injected, group = group)
            )
        else:
            raise ValueError("unknown type to ensure inject: {}".format(type(potentially_injected)))
    return potentially_injected

def try_append_payload(injected: _MarkInject, inject, eject):
    return _MarkInject(
        lambda *args, **kwargs: (inject(*args, **kwargs), injected.inject(*args, **kwargs)),
        lambda *args, **kwargs: (eject(*args, **kwargs), injected.eject(*args, **kwargs)),
        injected.cmd
    )

def inject_as_subcommand(groupcommand, **kwargs):
    def do_inject(subcommand):
        subcommand = ensure_inject(subcommand)
        subcmd = subcommand.cmd.make_command(**kwargs)
        def inject(bot, cog):
            bot.log.debug('Invoking inject_as_subcommand injecting {} to {}'.format(subcmd, groupcommand))
            subcmd.cog = cog
            cmd = bot.get_command(groupcommand)
            cmd.add_command(subcmd)
            bot.alias.fix_chained_command_alias(subcmd, 'injected')

        def eject(bot):
            bot.log.debug('Invoking inject_as_subcommand ejecting {} from {}'.format(subcmd, groupcommand))
            cmd = bot.get_command(groupcommand)
            cmd.remove_command(subcmd)

        return try_append_payload(subcommand, inject, eject)
    return do_inject

def inject_as_group(command):
    return ensure_inject(command, group = True)

def inject_as_cog_subcommand(groupcommand, **kwargs):
    def do_inject(subcommand):
        subcommand = ensure_inject(subcommand)
        subcmd = subcommand.cmd.make_command(**kwargs)
        def inject(bot, cog):
            bot.log.debug('Invoking inject_as_cog_subcommand injecting {} to {}'.format(subcmd, groupcommand))
            subcmd.cog = cog
            cmd = cog.get_command(groupcommand)
            cmd.add_command(subcmd)
            bot.alias.fix_chained_command_alias(subcmd, 'injected')

        def eject(bot):
            bot.log.debug('Invoking inject_as_cog_subcommand ejecting {} from {}'.format(subcmd, groupcommand))
            cmd = bot.get_command(groupcommand)
            cmd.remove_command(subcmd)

        return try_append_payload(subcommand, inject, eject)
    return do_inject

def inject_as_main_command(names:Union[AnyStr,Iterable[AnyStr]]):
    if isinstance(names, str):
        names = (names, )

    def do_inject(command):
        command = ensure_inject(command)
        def inject(bot, cog):
            bot.log.debug('Invoking inject_as_main_command injecting {} as {}'.format(command, names))
            for name in names:
                cmd = command.cmd.make_command(name = name)
                cmd.cog = cog
                bot.add_command(cmd)
                bot.alias.fix_chained_command_alias(cmd, 'injected')

        def eject(bot):
            bot.log.debug('Invoking inject_as_main_command ejecting {}'.format(names))
            for name in names:
                bot.remove_command(name)

        return try_append_payload(command, inject, eject)
    return do_inject
