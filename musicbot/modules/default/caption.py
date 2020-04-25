import glob
import re
from discord.ext.commands import Cog, command

from ...lib.srtdecode.parser import gen_srt_block_list_from_file, get_transcript
from ...smart_guild import get_guild
from ... import messagemanager
from ... import exceptions
from ...constants import DISCORD_MSG_CHAR_LIMIT

class Caption(Cog):
    playlists: Optional[DefaultDict[SmartGuild, Dict[str, Playlist]]]
    player: Optional[Dict[SmartGuild, Player]]

    def __init__(self):
        self.playlists = None
        self.player = None

    def pre_init(self, bot):
        self.bot = bot
        self.playlists = bot.crossmodule.get_object('playlists')
        self.player = bot.crossmodule.get_object('player')

    @command()
    async def caption(self, ctx, lang):
        """
        Usage:
            {command_prefix}caption lang

        Displays the caption of the current song in the specified language in chat.
        """
        guild = get_guild(ctx.bot, ctx.guild)
        player = self.player[guild]
        entry = player.get_current_entry()
        if entry:
            if entry.stream:
                await messagemanager.safe_send_normal(
                    ctx,
                    ctx,
                    ctx.bot.str.get('cmd?caption?stream', 'Current entry is a stream, cannot extract caption.') .format(ctx.bot.config.command_prefix),
                    expire_in=30
                )
                return
            else:
                # @theerapakG: TODO: Do things more elegant
                curfile = entry._local_url.split('.')
                curfile[-1] = '{}.srt'.format(lang)
                curfile = '.'.join(curfile)
                try:
                    f = open(curfile, mode='r', encoding='utf-8')
                except OSError:
                    await messagemanager.safe_send_normal(
                        ctx,
                        ctx,
                        ctx.bot.str.get('cmd?caption?nofile', 'Cannot open caption file specified (caption does not exist). If the caption do exist on the platform then try clearing cache of this song and try again.'),
                        expire_in=30
                    )
                else:
                    content = gen_srt_block_list_from_file(f)
                    # for el in content:
                    #     log.debug(el)
                    content = get_transcript(content, ctx.bot.config.caption_split_duration)
                    ctx.bot.log.debug(content)
                    content_cut = ['']
                    for el in content:
                        if len('\n'.join((content_cut[-1], el))) > DISCORD_MSG_CHAR_LIMIT:
                            content_cut.append('')
                        content_cut[-1] = '\n'.join((content_cut[-1], el))

                    await messagemanager.safe_send_message(
                        ctx.author,
                        ctx.bot.str.get('cmd?caption?captionof', 'Caption of `{0}`:').format(entry.title)
                    )

                    for cut in content_cut:
                        if cut:
                            await messagemanager.safe_send_message(
                                ctx.author,
                                cut
                            )

                    await messagemanager.safe_send_normal(
                        ctx,
                        ctx,
                        ctx.bot.str.get('cmd?caption?sent', 'Finished sending caption of `{0}` as direct message.').format(entry.title)
                    )
                    return

        else:
            await messagemanager.safe_send_normal(
                ctx,
                ctx,
                ctx.bot.str.get('cmd?caption?none', 'There are no songs queued! Queue something with {0}play.').format(ctx.bot.config.command_prefix),
                expire_in=30
            )
            return

    @command()
    async def captlang(self, ctx):
        """
        Usage:
            {command_prefix}captlang

        Displays languages that are possible to get caption.
        """
        guild = get_guild(ctx.bot, ctx.guild)
        player = self.player[guild]
        entry = player.get_current_entry()
        if entry:
            if entry.stream:
                await messagemanager.safe_send_normal(
                    ctx,
                    ctx,
                    ctx.bot.str.get('cmd?caption?stream', 'Current entry is a stream, cannot extract caption.') .format(ctx.bot.config.command_prefix),
                    expire_in=30
                )
                return
            else:
                curfile = entry._local_url.split('.')
                curfile[-1] = '*.srt'
                curfile = '.'.join(curfile)
                flist = glob.glob(curfile)

                if flist:

                    mstr = r'.*\.(?P<lang>.*)\.srt'
                    matcher = re.compile(mstr)

                    flist = [matcher.match(f).group('lang') for f in flist]

                    await messagemanager.safe_send_normal(
                        ctx,
                        ctx,
                        ', '.join(flist),
                        expire_in=30
                    )
                    return

                else:
                    await messagemanager.safe_send_normal(
                        ctx,
                        ctx,
                        ctx.bot.str.get('cmd?captlang?nocapt', 'There is no cached caption in the bot. Try {0}reloadcapt to force the bot to download additional captions.').format(ctx.bot.config.command_prefix),
                        expire_in=30
                    )      

        else:
            await messagemanager.safe_send_normal(
                ctx,
                ctx,
                ctx.bot.str.get('cmd?caption?none', 'There are no songs queued! Queue something with {0}play.').format(ctx.bot.config.command_prefix),
                expire_in=30
            )

    @command()
    async def reloadcapt(self, ctx):
        guild = get_guild(ctx.bot, ctx.guild)
        player = self.player[guild]
        entry = player.get_current_entry()
        if entry:
            retry = True
            while retry:
                try:
                    await ctx.bot.downloader.extract_info(entry.source_url, download = True)
                    break
                except Exception as e:
                    raise exceptions.ExtractionError(e)
        
            await messagemanager.safe_send_normal(
                ctx,
                ctx,
                ctx.bot.str.get('cmd?reloadcapt?success', 'Successfully redownloaded captions.'),
                expire_in=30
            )
        else:
            await messagemanager.safe_send_normal(
                ctx,
                ctx,
                ctx.bot.str.get('cmd?caption?none', 'There are no songs queued! Queue something with {0}play.').format(ctx.bot.config.command_prefix),
                expire_in=30
            )

cogs = [Caption]
deps = ['default.playlist']