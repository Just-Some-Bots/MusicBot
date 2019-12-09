from discord.ext.commands import Command, Group, command
import traceback
from typing import Optional, Union, Iterable, AnyStr
from .lib.event_emitter import AsyncEventEmitter, on

class _MarkInject:
    def __init__(self, injectfunction, ejectfunction, *, cmd = None):
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

def get_new_command_instance(potentially_injected, **kwargs):
    if isinstance(potentially_injected, _MarkInject):
        potentially_injected = potentially_injected.cmd
    if isinstance(potentially_injected, Command):
        cmd = potentially_injected.copy()
        cmd.update(**kwargs)
        return cmd
    return command(**kwargs)(potentially_injected)

def try_append_payload(potentially_injected, inject, eject):
    if isinstance(potentially_injected, _MarkInject):
        return _MarkInject(
            lambda *args, **kwargs: (inject(*args, **kwargs), potentially_injected.inject(*args, **kwargs)),
            lambda *args, **kwargs: (eject(*args, **kwargs), potentially_injected.eject(*args, **kwargs)),
            cmd = potentially_injected.cmd
        )
    else:
        return _MarkInject(inject, eject, cmd = potentially_injected)

def inject_as_subcommand(groupcommand, **kwargs):
    def do_inject(subcommand):
        subcmd = get_new_command_instance(subcommand, **kwargs)
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

def inject_as_cog_subcommand(groupcommand, **kwargs):
    def do_inject(subcommand):
        subcmd = get_new_command_instance(subcommand, **kwargs)
        def inject(bot, cog):
            bot.log.debug('Invoking inject_as_cog_subcommand injecting {} to {}'.format(subcmd, groupcommand))
            subcmd.cog = cog
            cmd = cog.get_command(groupcommand)
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
        def inject(bot, cog):
            bot.log.debug('Invoking inject_as_main_command injecting {} as {}'.format(command, names))
            for name in names:
                cmd = get_new_command_instance(command, name = name)
                cmd.cog = cog
                bot.add_command(cmd)
                bot.alias.fix_chained_command_alias(cmd, 'injected')

        def eject(bot):
            bot.log.debug('Invoking inject_as_main_command ejecting {}'.format(names))
            for name in names:
                bot.remove_command(name)

        return try_append_payload(command, inject, eject)
    return do_inject
