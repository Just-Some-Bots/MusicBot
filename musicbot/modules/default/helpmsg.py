from textwrap import dedent
from discord.ext.commands import Cog, command
from ... import exceptions

from ... import messagemanager

class Help(Cog):
    async def _gen_cmd_dict(self, bot, user, list_all_cmds=False):
        cmds = bot.commands.copy()
        commands = dict()
        for cmd in cmds:
            # This will always return at least cmd_help, since they needed perms to run this command
            if not hasattr(cmd.callback, 'dev_cmd'):
                user_permissions = bot.permissions.for_user(user)
                whitelist = user_permissions.command_whitelist
                blacklist = user_permissions.command_blacklist
                if list_all_cmds:
                    commands[cmd.qualified_name] = cmd

                elif blacklist and cmd.name in blacklist:
                    pass

                elif whitelist and cmd.name not in whitelist:
                    pass

                else:
                    commands[cmd.qualified_name] = cmd
        return commands

    async def _gen_cog_cmd_dict(self, bot, user, list_all_cmds=False):
        ret = dict()

        cogs = bot.cogs.copy()
        for name, cog in cogs.items():
            cmds = cog.get_commands()
            commands = dict()
            for cmd in cmds:
                # This will always return at least cmd_help, since they needed perms to run this command
                if not hasattr(cmd.callback, 'dev_cmd'):
                    user_permissions = bot.permissions.for_user(user)
                    whitelist = user_permissions.command_whitelist
                    blacklist = user_permissions.command_blacklist
                    if list_all_cmds:
                        commands[cmd.qualified_name] = cmd

                    elif blacklist and cmd.name in blacklist:
                        pass

                    elif whitelist and cmd.name not in whitelist:
                        pass

                    else:
                        commands[cmd.qualified_name] = cmd

            ret[name] = commands
        return ret

    @command()
    async def help(self, ctx, *options):
        """
        Usage:
            {command_prefix}help [options...] [name]

        Options:
            (none)    prints a help message for the command with that name.
            cog       prints a help message for the command in the cog with that name.
                      name argument is required.
            all       list all commands available.
                      name argument will be discarded if not used with cog option.

        Prints a help message. Supplying multiple names can leads to unexpected behavior.
        """
        prefix = ctx.bot.config.command_prefix

        options = set(options)

        list_all = True if 'all' in options else False
        options.remove('all') if list_all else None
        list_cog = True if 'cog' in options else False
        options.remove('cog') if list_cog else None

        p_name = (options - {'all', 'cog'})
        name = '' if not p_name else p_name.pop()

        cogs = await self._gen_cog_cmd_dict(ctx.bot, ctx.author, list_all_cmds=list_all)

        desc = ''
        if list_cog:
            cogdesc = ''
            try:
                cogs = {name: cogs[name]}
                cogdesc = ctx.bot.cogs[name].description
            except KeyError:
                raise exceptions.CommandError(ctx.bot.str.get('help?cmd?help?fail@cog', "No such cog"), expire_in=10)
            desc = '\N{WHITE SMALL SQUARE} {}:\n{}\n\n'.format(name, cogdesc) if cogdesc else '\N{WHITE SMALL SQUARE} {}:\n'.format(name)
            
        else:
            if name:
                cmd = await self._gen_cmd_dict(ctx.bot, ctx.author, list_all_cmds=True)
                try:
                    cmd = cmd[name]
                except:
                    raise exceptions.CommandError(ctx.bot.str.get('cmd-help-invalid', "No such command"), expire_in=10)
                if not hasattr(cmd.callback, 'dev_cmd'):
                    await messagemanager.safe_send_normal(
                        ctx,
                        ctx,
                        "```\n{}```".format(
                            dedent(cmd.help)
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