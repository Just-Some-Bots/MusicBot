from ..cogsmanager import callcmd

cog_name = 'intercog_example'

async def cmd_interplay(bot, message, player, channel, author, permissions, leftover_args, song_url):
    res = await callcmd('play', bot=bot, message=message, player=player, channel=channel, author=author, permissions=permissions, leftover_args=leftover_args, song_url=song_url)
    return res