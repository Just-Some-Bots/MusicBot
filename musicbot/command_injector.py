from discord.ext.commands import Group
from .lib.event_emitter import AsyncEventEmitter, on

class _MarkInject:
    def __init__(self, injectfunction, ejectfunction):
        self.inject = injectfunction
        self.eject = ejectfunction

class InjectableMixin(AsyncEventEmitter):
    @on('pre_init')
    async def pre_init(self, bot):
        self.bot = bot
        self.log = self.bot.log

    @on('init')
    async def init(self):
        for item in dir(self):
            iteminst = getattr(self, item)
            if isinstance(iteminst, _MarkInject):
                self.bot.log.debug('injecting with {}'.format(iteminst.inject))
                iteminst.inject(self.bot, self)

    @on('uninit')
    async def uninit(self):
        for item in dir(self):
            iteminst = getattr(self, item)
            if isinstance(iteminst, _MarkInject):
                self.bot.log.debug('ejecting with {}'.format(iteminst.eject))
                iteminst.eject(self.bot)

def inject_as_subcommand(groupcommand):
    def do_inject(subcommand):
        subcmd = subcommand.copy()
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

        return _MarkInject(inject, eject)
    return do_inject
