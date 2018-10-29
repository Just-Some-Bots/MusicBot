from ..constructs import Response

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