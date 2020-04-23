from ... import exceptions
from ...utils import write_file

from discord import User
from discord.ext.commands import Cog, command, Greedy

from ...smart_guild import get_guild
from ... import messagemanager

class Moderation(Cog):
    @command()
    async def blacklist(self, ctx, option:str, users: Greedy[User]):
        """
        Usage:
            {command_prefix}blacklist option users...

        Options:
            +, add       add users to the blacklist
            -, remove    remove users from the blacklist

        Blacklisted users are forbidden from using bot commands.
        """

        if not users:
            raise exceptions.CommandError("No users listed.", expire_in=20)

        if option not in ['+', '-', 'add', 'remove']:
            raise exceptions.CommandError(
                ctx.bot.str.get('cmd-blacklist-invalid', 'Invalid option "{0}" specified, use +, -, add, or remove').format(option), expire_in=20
            )

        for user in users.copy():
            if user.id in ctx.bot.config.owner_id:
                print("[Commands:Blacklist] The owner cannot be blacklisted.")
                users.remove(user)

        old_len = len(ctx.bot.blacklist)

        if option in ['+', 'add']:
            ctx.bot.blacklist.update(user.id for user in users)

            write_file(ctx.bot.config.blacklist_file, ctx.bot.blacklist)

            await messagemanager.safe_send_normal(
                ctx,
                ctx,
                ctx.bot.str.get('cmd-blacklist-added', '{0} users have been added to the blacklist').format(len(ctx.bot.blacklist) - old_len),
                reply=True, expire_in=10
            )

        else:
            if ctx.bot.blacklist.isdisjoint(user.id for user in users):
                await messagemanager.safe_send_normal(
                    ctx,
                    ctx,
                    ctx.bot.str.get('cmd-blacklist-none', 'None of those users are in the blacklist.'), reply=True, expire_in=10
                )

            else:
                ctx.bot.blacklist.difference_update(user.id for user in users)
                write_file(ctx.bot.config.blacklist_file, ctx.bot.blacklist)

                await messagemanager.safe_send_normal(
                    ctx,
                    ctx,
                    ctx.bot.str.get('cmd-blacklist-removed', '{0} users have been removed from the blacklist').format(old_len - len(ctx.bot.blacklist)),
                    reply=True, expire_in=10
                )

cogs = [Moderation]