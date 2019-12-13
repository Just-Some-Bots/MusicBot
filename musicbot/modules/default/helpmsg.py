from collections import defaultdict
from discord.ext.commands import Cog, command
from discord.utils import get
from ...utils import check_restricted
from ... import exceptions

from ... import messagemanager

class Help(Cog):
    async def get_cmd(self, name, bot, user, list_all_cmds=False):
        cmd = bot.get_command(name)
        user_permissions = bot.permissions.for_user(user)
        if not check_restricted(cmd, user_permissions) or list_all_cmds:
            return cmd

    async def _gen_cog_cmd_dict(self, bot, user, list_all_cmds=False):
        user_permissions = bot.permissions.for_user(user)

        ret = defaultdict(dict)
        cmds = bot.commands if list_all_cmds else check_restricted(bot.commands, user_permissions)

        for cmd in cmds:
            # This will always return at least cmd_help, since they needed perms to run this command
            if not hasattr(cmd.callback, 'dev_cmd'):
                cog_name = cmd.cog.qualified_name if cmd.cog else 'unknown'
                ret[cog_name][cmd.qualified_name] = cmd

        return ret

    @command()
    async def help(self, ctx, *options):
        """
        Usage:
            {command_prefix}help [options...] [name]

        Options:
            (none)    prints a help message for the command with that 
                      name.
            cog       prints a help message for the command in the
                      cog with that name. name argument is required.
            all       list all commands available. name argument will 
                      be discarded if not used with cog option.

        Prints a help message. Supplying multiple names can leads to unexpected behavior.
        """
        prefix = ctx.bot.config.command_prefix

        options = list(options)

        list_all = True if 'all' in options else False
        options.remove('all') if list_all else None
        list_cog = True if 'cog' in options else False
        options.remove('cog') if list_cog else None

        name = '' if not options else ' '.join(options)

        cogs = await self._gen_cog_cmd_dict(ctx.bot, ctx.author, list_all_cmds=list_all)

        desc = ''
        if list_cog:
            cogdesc = ''
            try:
                cogs = {name[0]: cogs[name[0]]}
                cogdesc = ctx.bot.cogs[name[0]].description
            except KeyError:
                raise exceptions.CommandError(ctx.bot.str.get('help?cmd?help?fail@cog', "No such cog"), expire_in=10)
            desc = '\N{WHITE SMALL SQUARE} {}:\n{}\n\n'.format(name[0], cogdesc) if cogdesc else '\N{WHITE SMALL SQUARE} {}:\n'.format(name[0])
            
        else:
            if name:
                cmd = await self.get_cmd(name, ctx.bot, ctx.author, list_all_cmds=True)
                if not cmd:
                    raise exceptions.CommandError(ctx.bot.str.get('cmd-help-invalid', "No such command"), expire_in=10)
                if not hasattr(cmd.callback, 'dev_cmd'):
                    usage = cmd.help
                    if ctx.bot.config.help_display_sig and hasattr(cmd, 'commands'):
                        usage = '{}\n\nSignature: {} {}'.format(usage, cmd.qualified_name, cmd.signature)
                    await messagemanager.safe_send_normal(
                        ctx,
                        ctx,
                        "```\n{}\n\n{}Aliases (for this name): {}```".format(
                            usage,
                            '' if not hasattr(cmd, 'commands') else 'This is a command group with following subcommands:\n{}\n\n'.format(', '.join(c.name for c in cmd.commands) if cmd.commands else None),
                            ' '.join(cmd.aliases)
                        ).format(command_prefix=ctx.bot.config.command_prefix),
                        expire_in=60
                    )
                    return

            elif ctx.author.id == ctx.bot.config.owner_id:
                cogs = await self._gen_cog_cmd_dict(ctx.bot, ctx.author, list_all_cmds=True)

        cmdlisto = ''
        for cog, cmdlist in cogs.items():
            if len(cmdlist) > 0:
                cmdlisto += ('\N{WHITE SMALL SQUARE} '+ cog + ' [' + str(len(cmdlist)) + ']:\n') if not list_cog else ''
                cmdlisto += '```' + ', '.join([cmd for cmd in cmdlist.keys()]) + '```\n'

        desc += cmdlisto + ctx.bot.str.get(
                'cmd-help-response', 'For information about a particular command, run `{}help [command]`\n'
                                     'For further help, see https://just-some-bots.github.io/MusicBot/'
            ).format(prefix)

        if not list_all:
            desc += ctx.bot.str.get('cmd-help-all', '\nOnly showing commands you can use, for a list of all commands, run `{}help all`').format(prefix)

        await messagemanager.safe_send_normal(ctx, ctx, desc, reply=True, expire_in=60)

cogs = [Help]