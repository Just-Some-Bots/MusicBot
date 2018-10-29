from .. import exceptions
from ..utils import write_file
from ..constructs import Response

cog_name = 'moderate'

async def cmd_karaoke(self, player, channel, author):
    """
    Usage:
        {command_prefix}karaoke

    Activates karaoke mode. During karaoke mode, only groups with the BypassKaraokeMode
    permission in the config file can queue music.
    """
    player.karaoke_mode = not player.karaoke_mode
    return Response("\N{OK HAND SIGN} Karaoke mode is now " + ['disabled', 'enabled'][player.karaoke_mode], delete_after=15)

async def cmd_blacklist(self, message, user_mentions, option, something):
    """
    Usage:
        {command_prefix}blacklist [ + | - | add | remove ] @UserName [@UserName2 ...]

    Add or remove users to the blacklist.
    Blacklisted users are forbidden from using bot commands.
    """

    if not user_mentions:
        raise exceptions.CommandError("No users listed.", expire_in=20)

    if option not in ['+', '-', 'add', 'remove']:
        raise exceptions.CommandError(
            self.str.get('cmd-blacklist-invalid', 'Invalid option "{0}" specified, use +, -, add, or remove').format(option), expire_in=20
        )

    for user in user_mentions.copy():
        if user.id == self.config.owner_id:
            print("[Commands:Blacklist] The owner cannot be blacklisted.")
            user_mentions.remove(user)

    old_len = len(self.blacklist)

    if option in ['+', 'add']:
        self.blacklist.update(user.id for user in user_mentions)

        write_file(self.config.blacklist_file, self.blacklist)

        return Response(
            self.str.get('cmd-blacklist-added', '{0} users have been added to the blacklist').format(len(self.blacklist) - old_len),
            reply=True, delete_after=10
        )

    else:
        if self.blacklist.isdisjoint(user.id for user in user_mentions):
            return Response(self.str.get('cmd-blacklist-none', 'None of those users are in the blacklist.'), reply=True, delete_after=10)

        else:
            self.blacklist.difference_update(user.id for user in user_mentions)
            write_file(self.config.blacklist_file, self.blacklist)

            return Response(
                self.str.get('cmd-blacklist-removed', '{0} users have been removed from the blacklist').format(old_len - len(self.blacklist)),
                reply=True, delete_after=10
            )