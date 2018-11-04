from textwrap import dedent

from ..cogsmanager import gen_cmd_list
from .. import exceptions
from ..constructs import Response

cog_name = 'help'

async def _gen_cmd_list(bot, message, list_all_cmds=False):
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

async def cmd_help(bot, message, channel, command=None):
    """
    Usage:
        {command_prefix}help [command]

    Prints a help message.
    If a command is specified, it prints a help message for that command.
    Otherwise, it lists the available commands.
    """
    commands = dict()
    bot.is_all = False
    prefix = bot.config.command_prefix

    if command:
        if command.lower() == 'all':
            bot.is_all = True
            commands = await _gen_cmd_list(bot, message, list_all_cmds=True)

        else:
            cmd = await _gen_cmd_list(bot, message, list_all_cmds=True)
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
        commands = await _gen_cmd_list(bot, message, list_all_cmds=True)

    else:
        commands = await _gen_cmd_list(bot, message).keys()

    desc = '```\n' + ', '.join(commands.keys()) + '\n```\n' + bot.str.get(
        'cmd-help-response', 'For information about a particular command, run `{}help [command]`\n'
                                'For further help, see https://just-some-bots.github.io/MusicBot/').format(prefix)
    if not bot.is_all:
        desc += bot.str.get('cmd-help-all', '\nOnly showing commands you can use, for a list of all commands, run `{}help all`').format(prefix)

    return Response(desc, reply=True, delete_after=60)