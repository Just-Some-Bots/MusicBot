from textwrap import dedent

from ...cogsmanager import gen_cmd_list, gen_cog_list, gen_cmd_list_from_cog
from ... import exceptions
from ...constructs import Response

cog_name = 'help'

async def _gen_cmd_dict(bot, message, list_all_cmds=False):
    cmds = await gen_cmd_list()
    commands = dict()
    for cmd in cmds:
        if not hasattr(cmd, 'func'):
            pass # what will you run?

        # This will always return at least cmd_help, since they needed perms to run this command
        if not hasattr(cmd.func, 'dev_cmd'):
            user_permissions = bot.permissions.for_user(message.author)
            whitelist = user_permissions.command_whitelist
            blacklist = user_permissions.command_blacklist
            if list_all_cmds:
                commands[cmd.name] = cmd

            elif blacklist and cmd.name in blacklist:
                pass

            elif whitelist and cmd.name not in whitelist:
                pass

            else:
                commands[cmd.name] = cmd
    return commands

async def _gen_cog_cmd_dict(bot, message, list_all_cmds=False):
    ret = dict()

    cogs = await gen_cog_list()
    for cog in cogs:
        cmds = await gen_cmd_list_from_cog(cog.name)
        commands = list()
        for cmd in cmds:
            if not hasattr(cmd, 'func'):
                pass # what will you run?

            # This will always return at least cmd_help, since they needed perms to run this command
            if not hasattr(cmd.func, 'dev_cmd'):
                user_permissions = bot.permissions.for_user(message.author)
                whitelist = user_permissions.command_whitelist
                blacklist = user_permissions.command_blacklist
                if list_all_cmds:
                    commands.append(cmd)

                elif blacklist and cmd.name in blacklist:
                    pass

                elif whitelist and cmd.name not in whitelist:
                    pass

                else:
                    commands.append(cmd)

        ret[cog] = commands
    return ret

async def cmd_help(bot, message, channel, command=None, spcog=None):
    """
    Usage:
        {command_prefix}help [command]
        {command_prefix}help cog [cog]

    Prints a help message.
    If a command is specified, it prints a help message for that command.
    If a cog is specified, it prints a documentation of the cog.
    Otherwise, it lists the available commands.
    """
    cogs = dict()
    bot.is_all = False
    prefix = bot.config.command_prefix

    if command:
        if command.lower() == 'all':
            bot.is_all = True
            cogs = await _gen_cog_cmd_dict(bot, message, list_all_cmds=True)

        elif command.lower() == 'cog':
            cogs = await _gen_cog_cmd_dict(bot, message, list_all_cmds=True)
            for cog in cogs:
                if spcog == cog:
                    return Response(
                        "```\n{}```".format(
                            dedent(cog.__doc__)
                        ).format(command_prefix=bot.config.command_prefix),
                        delete_after=60
                    )
            raise exceptions.CommandError(bot.str.get('help?cmd?help?fail@cog', "No such cog"), expire_in=10) from None

        else:
            cmd = await _gen_cmd_dict(bot, message, list_all_cmds=True)
            try:
                cmd = cmd[command]
            except:
                raise exceptions.CommandError(bot.str.get('cmd-help-invalid', "No such command"), expire_in=10) from None
            if not hasattr(cmd.func, 'dev_cmd'):
                return Response(
                    "```\n{}```".format(
                        dedent(cmd.__doc__)
                    ).format(command_prefix=bot.config.command_prefix),
                    delete_after=60
                )

    elif message.author.id == bot.config.owner_id:
        cogs = await _gen_cog_cmd_dict(bot, message, list_all_cmds=True)

    else:
        cogs = await _gen_cog_cmd_dict(bot, message)

    cmdlisto = '\n'
    for cog, cmdlist in cogs.items():
        if len(cmdlist) > 0:
            cmdlisto += ('\N{WHITE SMALL SQUARE} ' if await cog.isload() else '\N{BLACK SMALL SQUARE} ')
            cmdlisto += cog.name + ' [' + str(len(cmdlist)) + ']:\n'
            cmdlisto += '```' + ', '.join([cmd.name for cmd in cmdlist]) + '```\n'

    desc = '\n' + cmdlisto + '\n' + bot.str.get(
        'cmd-help-response', 'For information about a particular command, run `{}help [command]`\n'
                                'For further help, see https://just-some-bots.github.io/MusicBot/').format(prefix)
    if not bot.is_all:
        desc += bot.str.get('cmd-help-all', '\nOnly showing commands you can use, for a list of all commands, run `{}help all`').format(prefix)

    return Response(desc, reply=True, delete_after=60)