import logging
import re
import copy

from ...constructs import Response

log = logging.getLogger(__name__)

cog_name = 'utility'

async def cmd_clean(bot, message, channel, guild, author, search_range=50):
    """
    Usage:
        {command_prefix}clean [range]

    Removes up to [range] messages the bot has posted in chat. Default: 50, Max: 1000
    """

    try:
        float(search_range)  # lazy check
        search_range = min(int(search_range), 1000)
    except:
        return Response(bot.str.get('cmd-clean-invalid', "Invalid parameter. Please provide a number of messages to search."), reply=True, delete_after=8)

    await bot.safe_delete_message(message, quiet=True)

    def is_possible_command_invoke(entry):
        valid_call = any(
            entry.content.startswith(prefix) for prefix in [bot.config.command_prefix])  # can be expanded
        return valid_call and not entry.content[1:2].isspace()

    delete_invokes = True
    delete_all = channel.permissions_for(author).manage_messages or bot.config.owner_id == author.id

    def check(message):
        if is_possible_command_invoke(message) and delete_invokes:
            return delete_all or message.author == author
        return message.author == bot.user

    if bot.user.bot:
        if channel.permissions_for(guild.me).manage_messages:
            deleted = await channel.purge(check=check, limit=search_range, before=message)
            return Response(bot.str.get('cmd-clean-reply', 'Cleaned up {0} message{1}.').format(len(deleted), 's' * bool(deleted)), delete_after=15)

async def cmd_sudo(bot, user_mentions, message, channel, guild, leftover_args):
    """
    Usage:
        {command_prefix}sudo @users {command_prefix}command

    Run command as another user in current text channel. Only supply users (not roles, everyone nor here) to users argument
    """
    await bot.safe_send_message(channel, 'warning! sudo command is highly experimental, use it with care!', expire_in=10)
    mention = re.compile('<@[!]?(?P<id>[0-9]+)>')
    command = leftover_args
    usr = [] # we need to resolve each user because some commands rely on user_mention
    usr_command = []
    for s in leftover_args:
        if mention.match(s):
            command.pop(0)
            usr.append(int(mention.match(s).groupdict()['id']))
        else:
            break
    log.debug(command)
    for s in command:
        if mention.match(s):
            usr_command.append(int(mention.match(s).groupdict()['id']))
    for i in range(len(usr_command)):
        usr_command[i] = guild.get_member(usr_command[i])
    log.debug(usr)
    log.debug(usr_command)
    fakemsg = copy.copy(message)
    for u in usr:
        fakemsg.author = guild.get_member(u)
        fakemsg.content = ' '.join(command)
        fakemsg.mentions = usr_command
        await bot.on_message(fakemsg)
    await bot.safe_send_message(channel, 'sudo ran successfully', expire_in=10)
