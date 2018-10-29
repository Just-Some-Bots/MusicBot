from textwrap import dedent

from .. import exceptions
from ..constructs import Response

cog_name = 'help'

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
            commands = await bot.gen_cmd_list(message, list_all_cmds=True)

        else:
            cmd = await bot.gen_cmd_list(message, list_all_cmds=True)
            try:
                cmd = cmd['{0}{1}'.format(prefix, command)]
            except:
                raise exceptions.CommandError(bot.str.get('cmd-help-invalid', "No such command"), expire_in=10)
            if not hasattr(cmd, 'dev_cmd'):
                return Response(
                    "```\n{}```".format(
                        dedent(cmd.__doc__)
                    ).format(command_prefix=bot.config.command_prefix),
                    delete_after=60
                )

    elif message.author.id == bot.config.owner_id:
        commands = await bot.gen_cmd_list(message, list_all_cmds=True)

    else:
        commands = await bot.gen_cmd_list(message).keys()

    desc = '```\n' + ', '.join(commands.keys()) + '\n```\n' + bot.str.get(
        'cmd-help-response', 'For information about a particular command, run `{}help [command]`\n'
                                'For further help, see https://just-some-bots.github.io/MusicBot/').format(prefix)
    if not bot.is_all:
        desc += bot.str.get('cmd-help-all', '\nOnly showing commands you can use, for a list of all commands, run `{}help all`').format(prefix)

    return Response(desc, reply=True, delete_after=60)