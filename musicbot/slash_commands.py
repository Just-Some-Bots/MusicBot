"""
musicbot/slash_commands.py
--------------------------
Slash command wrappers for MusicBot — Batch 1 of N.

Covered here (10 commands):
  resetplaylist, help, blockuser (group), blocksong (group),
  autoplaylist (group), joinserver, karaoke, play, shuffleplay, playnext

Strategy
--------
* Each slash handler defers the interaction, resolves the same context objects
  that on_message normally injects (player, ssd_, permissions, …), then calls
  the existing cmd_* method directly.  Zero business-logic duplication.
* The custom permissions system is preserved via _check_perms().
* A shared _send() helper converts Response/ErrorResponse → interaction reply.

Required one-time change in bot.py
------------------------------------
1.  Class declaration:
        class MusicBot(discord.Client):
    →   from discord.ext import commands
        class MusicBot(commands.Bot):

2.  __init__: replace super().__init__ call:
        super().__init__(intents=intents)
    →   super().__init__(
            command_prefix=[],   # prefix dispatch stays in custom on_message
            intents=intents,
        )

3.  setup_hook: add at the end (after existing code):
        await self.add_cog(SlashCommands(self))
        await self.tree.sync()

4.  _do_cmd_unpause_check signature — make message Optional so slash calls
    that pass None don't crash:

        async def _do_cmd_unpause_check(
            self,
            player: Optional[MusicPlayer],
            channel: MessageableChannel,
            author: discord.Member,
            message: Optional[discord.Message],   # ← was discord.Message
        ) -> None:
            ...
            if pvc != avc and perms.summonplay:
                if message is None:                # ← guard added
                    return
                await self.cmd_summon(ssd, author.guild, author, message)
                return
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

import discord
from discord import app_commands
from discord.ext import commands

from . import exceptions
from .constructs import GuildSpecificData, MusicBotResponse

if TYPE_CHECKING:
    from .bot import MusicBot
    from .permissions import PermissionGroup
    from .player import MusicPlayer

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper: flatten a Response content field for an interaction reply
# ---------------------------------------------------------------------------

def _content(resp: Optional[MusicBotResponse]) -> str:
    if resp is None:
        return "✅"
    text = getattr(resp, "content", None) or "✅"
    # Discord followup limit is 2 000 chars
    return text[:1997] + "…" if len(text) > 2000 else text


# ---------------------------------------------------------------------------
# Cog
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# SearchView — interactive Select-based search picker for /search
# ---------------------------------------------------------------------------

class SearchView(discord.ui.View):
    """
    Presents yt-dlp search results as a Select dropdown.
    Only the user who ran /search can interact with it.
    Auto-disables after 60 seconds.
    """

    SERVICES = {
        "yt": "ytsearch", "youtube": "ytsearch",
        "sc": "scsearch", "soundcloud": "scsearch",
        "yh": "yvsearch", "yahoo": "yvsearch",
        "gv": "gvsearch", "google": "gvsearch",
        "nv": "nicosearch", "nico": "nicosearch",
        "bb": "bilisearch", "bili": "bilisearch",
    }

    def __init__(
        self,
        *,
        bot: "MusicBot",
        entries: list,
        author: discord.Member,
        guild: discord.Guild,
        channel,
        player: "MusicPlayer",
        permissions: "PermissionGroup",
        service_label: str,
    ) -> None:
        super().__init__(timeout=60)
        self.bot = bot
        self.entries = entries
        self.author = author
        self.guild = guild
        self.channel = channel
        self.player = player
        self.permissions = permissions
        self.service_label = service_label
        self.queued: bool = False

        # Build the Select options — Discord caps labels at 100 chars,
        # descriptions at 100 chars, and total options at 25.
        options = []
        for i, entry in enumerate(entries[:25]):
            title = entry["title"] or "Unknown title"
            url = entry["url"]
            duration = ""
            try:
                from .utils import format_song_duration
                duration = format_song_duration(entry.duration_td)
            except Exception:
                pass

            label = title[:97] + "…" if len(title) > 100 else title
            desc = duration[:97] + "…" if len(duration) > 100 else duration

            options.append(
                discord.SelectOption(
                    label=label,
                    value=str(i),
                    description=desc or None,
                )
            )

        select = discord.ui.Select(
            placeholder="Pick a result to queue…",
            min_values=1,
            max_values=1,
            options=options,
        )
        select.callback = self._on_select
        self.add_item(select)

        cancel = discord.ui.Button(
            label="Cancel",
            style=discord.ButtonStyle.secondary,
        )
        cancel.callback = self._on_cancel
        self.add_item(cancel)

    def _label(self) -> str:
        return f"Search results from **{self.service_label}**"

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                "Only the person who ran `/search` can pick a result.", ephemeral=True
            )
            return False
        return True

    async def _on_select(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        idx = int(interaction.data["values"][0])  # type: ignore[index]
        entry = self.entries[idx]
        url = entry["url"]
        title = entry["title"] or url

        self._disable_all()
        await interaction.edit_original_response(
            content=f"⏳ Queuing **{title}**…", view=self
        )

        try:
            resp = await self.bot.cmd_play(
                message=None,
                player=self.player,
                channel=self.channel,
                guild=self.guild,
                author=self.author,
                permissions=self.permissions,
                leftover_args=[],
                song_url=url,
            )
            content = _content(resp) if resp else f"✅ **{title}** added to the queue."
        except Exception as e:
            msg = getattr(e, "message", str(e))
            fmt = getattr(e, "fmt_args", {})
            if fmt:
                try:
                    msg = msg % fmt
                except Exception:
                    pass
            content = f"❌ {msg}"

        self.queued = True
        self.stop()
        await interaction.edit_original_response(content=content, view=None)

    async def _on_cancel(self, interaction: discord.Interaction) -> None:
        self._disable_all()
        self.stop()
        await interaction.response.edit_message(content="Search cancelled.", view=None)

    def _disable_all(self) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]

    async def on_timeout(self) -> None:
        # We don't have the original interaction here to edit, but the view
        # components will be visually greyed out once disabled on next render.
        self._disable_all()


class SlashCommands(commands.Cog):
    """Slash command surface for MusicBot."""

    def __init__(self, bot: MusicBot) -> None:
        self.bot = bot

    # -----------------------------------------------------------------------
    # Shared context helpers  (mirror on_message kwarg injection)
    # -----------------------------------------------------------------------

    async def _check_perms(
        self,
        interaction: discord.Interaction,
        command_name: str,
        sub_cmd: str = "",
    ) -> bool:
        """
        Replicates the permission gate in on_message.
        Returns True if allowed, sends ephemeral error and returns False otherwise.
        """
        if not isinstance(interaction.user, discord.Member):
            await interaction.followup.send(
                "This command must be used in a server.", ephemeral=True
            )
            return False
        perms: PermissionGroup = self.bot.permissions.for_user(interaction.user)
        if (
            interaction.user.id != self.bot.config.owner_id
            and not perms.can_use_command(command_name, sub_cmd)
        ):
            await interaction.followup.send(
                f"Your permissions group (`{perms.name}`) is not allowed to use `/{command_name}`.",
                ephemeral=True,
            )
            return False
        return True

    async def _get_player(self, interaction: discord.Interaction) -> MusicPlayer:
        """
        Resolve a MusicPlayer from an Interaction.
        Mirrors the 'player' kwarg branch in on_message; auto-summons if
        the user has summonplay permission.
        Raises CommandError on failure.
        """
        user = interaction.user
        if not isinstance(user, discord.Member) or not interaction.guild:
            raise exceptions.CommandError("This command requires a server context.")
        if not user.voice or not user.voice.channel:
            raise exceptions.CommandError(
                "This command requires you to be in a Voice channel."
            )
        perms: PermissionGroup = self.bot.permissions.for_user(user)
        return await self.bot.get_player(
            user.voice.channel, create=perms.summonplay
        )

    def _ssd(self, interaction: discord.Interaction) -> Optional[GuildSpecificData]:
        if interaction.guild:
            return self.bot.server_data[interaction.guild.id]
        return None

    async def _send(
        self,
        interaction: discord.Interaction,
        resp: Optional[MusicBotResponse],
        *,
        ephemeral: bool = False,
    ) -> None:
        await interaction.followup.send(_content(resp), ephemeral=ephemeral)

    async def _err(self, interaction: discord.Interaction, exc: Exception) -> None:
        msg = getattr(exc, "message", str(exc))
        fmt = getattr(exc, "fmt_args", {})
        if fmt:
            try:
                msg = msg % fmt
            except Exception:
                pass
        await interaction.followup.send(f"❌ {msg}", ephemeral=True)

    # -----------------------------------------------------------------------
    # /resetplaylist
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="resetplaylist",
        description="Reload a fresh copy of this server's autoplaylist into the player.",
    )
    async def slash_resetplaylist(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        if not await self._check_perms(interaction, "resetplaylist"):
            return
        try:
            if not interaction.guild:
                await interaction.followup.send("Guild only.", ephemeral=True)
                return
            player = await self._get_player(interaction)
            resp = await self.bot.cmd_resetplaylist(
                ssd_=self._ssd(interaction),
                guild=interaction.guild,
                player=player,
            )
            await self._send(interaction, resp)
        except Exception as e:
            await self._err(interaction, e)

    # -----------------------------------------------------------------------
    # /help
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="help",
        description="Show bot commands or get details on a specific command.",
    )
    @app_commands.describe(command="Command name for details, or 'all' for the full list.")
    async def slash_help(
        self,
        interaction: discord.Interaction,
        command: Optional[str] = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            guild = interaction.guild
            if command:
                cmd_name = command.lower()
                cmd_fn = getattr(self.bot, f"cmd_{cmd_name}", None)
                if not cmd_fn:
                    await interaction.followup.send(
                        f"No command named `{cmd_name}`.", ephemeral=True
                    )
                    return
                help_text = await self.bot.gen_cmd_help(cmd_name, guild)
                await interaction.followup.send(help_text, ephemeral=True)
            else:
                nat_cmds = sorted(
                    c.replace("cmd_", "")
                    for c in dir(self.bot)
                    if c.startswith("cmd_") and not c.startswith("cmd__")
                )
                prefix = self.bot.config.command_prefix
                body = (
                    f"**Available commands** *(prefix: `{prefix}`)*\n"
                    f"```{', '.join(nat_cmds)}```\n"
                    f"For details: `/help command:<name>`"
                )
                await interaction.followup.send(body, ephemeral=True)
        except Exception as e:
            await self._err(interaction, e)

    # -----------------------------------------------------------------------
    # /blockuser  (group)
    # -----------------------------------------------------------------------

    blockuser = app_commands.Group(
        name="blockuser",
        description="Manage the user block list.",
        default_permissions=discord.Permissions(manage_guild=True),
    )

    @blockuser.command(name="add", description="Block a user from using the bot.")
    @app_commands.describe(user="The member to block.")
    async def slash_blockuser_add(
        self, interaction: discord.Interaction, user: discord.Member
    ) -> None:
        await interaction.response.defer()
        if not await self._check_perms(interaction, "blockuser", "add"):
            return
        try:
            resp = await self.bot.cmd_blockuser(
                ssd_=self._ssd(interaction),
                user_mentions=[user],
                option="add",
                leftover_args=[],
            )
            await self._send(interaction, resp)
        except Exception as e:
            await self._err(interaction, e)

    @blockuser.command(name="remove", description="Unblock a user.")
    @app_commands.describe(user="The member to unblock.")
    async def slash_blockuser_remove(
        self, interaction: discord.Interaction, user: discord.Member
    ) -> None:
        await interaction.response.defer()
        if not await self._check_perms(interaction, "blockuser", "remove"):
            return
        try:
            resp = await self.bot.cmd_blockuser(
                ssd_=self._ssd(interaction),
                user_mentions=[user],
                option="remove",
                leftover_args=[],
            )
            await self._send(interaction, resp)
        except Exception as e:
            await self._err(interaction, e)

    @blockuser.command(name="status", description="Check if a user is blocked.")
    @app_commands.describe(user="The member to check.")
    async def slash_blockuser_status(
        self, interaction: discord.Interaction, user: discord.Member
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        if not await self._check_perms(interaction, "blockuser", "status"):
            return
        try:
            resp = await self.bot.cmd_blockuser(
                ssd_=self._ssd(interaction),
                user_mentions=[user],
                option="status",
                leftover_args=[],
            )
            await self._send(interaction, resp, ephemeral=True)
        except Exception as e:
            await self._err(interaction, e)

    # -----------------------------------------------------------------------
    # /blocksong  (group)
    # -----------------------------------------------------------------------

    blocksong = app_commands.Group(
        name="blocksong",
        description="Manage the song block list.",
        default_permissions=discord.Permissions(manage_guild=True),
    )

    @blocksong.command(name="add", description="Block a song by URL or keyword.")
    @app_commands.describe(
        subject="URL or phrase to block. Leave empty to block the currently playing song."
    )
    async def slash_blocksong_add(
        self,
        interaction: discord.Interaction,
        subject: Optional[str] = None,
    ) -> None:
        await interaction.response.defer()
        if not await self._check_perms(interaction, "blocksong", "add"):
            return
        try:
            guild = interaction.guild
            _player = self.bot.get_player_in(guild) if guild else None
            resp = await self.bot.cmd_blocksong(
                ssd_=self._ssd(interaction),
                guild=guild,
                _player=_player,
                option="add",
                leftover_args=[],
                song_subject=subject or "",
            )
            await self._send(interaction, resp)
        except Exception as e:
            await self._err(interaction, e)

    @blocksong.command(name="remove", description="Unblock a song by URL or keyword.")
    @app_commands.describe(subject="URL or phrase to remove from the block list.")
    async def slash_blocksong_remove(
        self,
        interaction: discord.Interaction,
        subject: str,
    ) -> None:
        await interaction.response.defer()
        if not await self._check_perms(interaction, "blocksong", "remove"):
            return
        try:
            guild = interaction.guild
            _player = self.bot.get_player_in(guild) if guild else None
            resp = await self.bot.cmd_blocksong(
                ssd_=self._ssd(interaction),
                guild=guild,
                _player=_player,
                option="remove",
                leftover_args=[],
                song_subject=subject,
            )
            await self._send(interaction, resp)
        except Exception as e:
            await self._err(interaction, e)

    # -----------------------------------------------------------------------
    # /autoplaylist  (group — 8 subcommands)
    # -----------------------------------------------------------------------

    autoplaylist = app_commands.Group(
        name="autoplaylist",
        description="Manage the server autoplaylist.",
    )

    async def _ap(
        self,
        interaction: discord.Interaction,
        option: str,
        opt_url: str = "",
    ) -> None:
        """Shared dispatcher for all /autoplaylist subcommands."""
        if not await self._check_perms(interaction, "autoplaylist", option):
            return
        try:
            guild = interaction.guild
            user = interaction.user
            if not guild or not isinstance(user, discord.Member):
                await interaction.followup.send("Guild only.", ephemeral=True)
                return
            player = await self._get_player(interaction)
            _player = self.bot.get_player_in(guild)
            voice_channel = user.voice.channel if user.voice else None
            resp = await self.bot.cmd_autoplaylist(
                ssd_=self._ssd(interaction),
                guild=guild,
                author=user,
                channel=interaction.channel,
                voice_channel=voice_channel,
                message=None,   # guarded in _do_cmd_unpause_check — see module docstring
                _player=_player,
                player=player,
                option=option,
                opt_url=opt_url,
            )
            await self._send(interaction, resp)
        except Exception as e:
            await self._err(interaction, e)

    @autoplaylist.command(name="add", description="Add a song to the autoplaylist.")
    @app_commands.describe(url="Song URL. Leave empty to add the currently playing song.")
    async def slash_ap_add(self, interaction: discord.Interaction, url: Optional[str] = None) -> None:
        await interaction.response.defer()
        await self._ap(interaction, "add", url or "")

    @autoplaylist.command(name="remove", description="Remove a song from the autoplaylist.")
    @app_commands.describe(url="Song URL. Leave empty to remove the currently playing song.")
    async def slash_ap_remove(self, interaction: discord.Interaction, url: Optional[str] = None) -> None:
        await interaction.response.defer()
        await self._ap(interaction, "remove", url or "")

    @autoplaylist.command(name="restart", description="Reload the autoplaylist from disk into the player.")
    async def slash_ap_restart(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        await self._ap(interaction, "restart")

    @autoplaylist.command(name="show", description="List available autoplaylist files on this server.")
    async def slash_ap_show(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        await self._ap(interaction, "show")

    @autoplaylist.command(name="set", description="Switch the server autoplaylist to a different file.")
    @app_commands.describe(filename="Playlist filename, e.g. mylist.txt")
    async def slash_ap_set(self, interaction: discord.Interaction, filename: str) -> None:
        await interaction.response.defer()
        await self._ap(interaction, "set", filename)

    @autoplaylist.command(name="clear", description="Clear all tracks from a playlist file.")
    @app_commands.describe(filename="Playlist filename. Leave empty to clear the current server playlist.")
    async def slash_ap_clear(self, interaction: discord.Interaction, filename: Optional[str] = None) -> None:
        await interaction.response.defer()
        await self._ap(interaction, "clear", filename or "")

    @autoplaylist.command(name="queue", description="Dump all tracks from a playlist into the queue.")
    @app_commands.describe(filename="Playlist filename. Leave empty to use the current server playlist.")
    async def slash_ap_queue(self, interaction: discord.Interaction, filename: Optional[str] = None) -> None:
        await interaction.response.defer()
        await self._ap(interaction, "queue", filename or "")

    @autoplaylist.command(name="reload", description="Hot-reload a playlist file from disk.")
    @app_commands.describe(filename="Playlist filename. Leave empty to reload the current server playlist.")
    async def slash_ap_reload(self, interaction: discord.Interaction, filename: Optional[str] = None) -> None:
        await interaction.response.defer()
        await self._ap(interaction, "reload", filename or "")

    # -----------------------------------------------------------------------
    # /joinserver  (owner-only)
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="joinserver",
        description="Generate an OAuth invite link for this bot. (Owner only)",
    )
    async def slash_joinserver(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        if interaction.user.id != self.bot.config.owner_id:
            await interaction.followup.send("This command is restricted to the bot owner.", ephemeral=True)
            return
        try:
            resp = await self.bot.cmd_joinserver(ssd_=self._ssd(interaction))
            await self._send(interaction, resp, ephemeral=True)
        except Exception as e:
            await self._err(interaction, e)

    # -----------------------------------------------------------------------
    # /karaoke
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="karaoke",
        description="Toggle karaoke mode — only karaoke-permitted members may queue songs while active.",
    )
    async def slash_karaoke(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        if not await self._check_perms(interaction, "karaoke"):
            return
        try:
            player = await self._get_player(interaction)
            resp = await self.bot.cmd_karaoke(
                ssd_=self._ssd(interaction),
                player=player,
            )
            await self._send(interaction, resp)
        except Exception as e:
            await self._err(interaction, e)

    # -----------------------------------------------------------------------
    # /play
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="play",
        description="Add a song to the queue. Accepts a URL or a search query.",
    )
    @app_commands.describe(
        query="YouTube/Spotify URL, any yt-dlp supported URL, or a search term."
    )
    async def slash_play(self, interaction: discord.Interaction, query: str) -> None:
        await interaction.response.defer()
        if not await self._check_perms(interaction, "play"):
            return
        try:
            guild = interaction.guild
            user = interaction.user
            if not guild or not isinstance(user, discord.Member):
                await interaction.followup.send("Guild only.", ephemeral=True)
                return
            player = await self._get_player(interaction)
            resp = await self.bot.cmd_play(
                message=None,           # guarded in _do_cmd_unpause_check
                player=player,
                channel=interaction.channel,
                guild=guild,
                author=user,
                permissions=self.bot.permissions.for_user(user),
                leftover_args=[],
                song_url=query,
            )
            await self._send(interaction, resp)
        except Exception as e:
            await self._err(interaction, e)

    # -----------------------------------------------------------------------
    # /shuffleplay
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="shuffleplay",
        description="Add a playlist to the queue with entries shuffled before insertion.",
    )
    @app_commands.describe(url="Playlist URL to shuffle into the queue.")
    async def slash_shuffleplay(self, interaction: discord.Interaction, url: str) -> None:
        await interaction.response.defer()
        if not await self._check_perms(interaction, "shuffleplay"):
            return
        try:
            guild = interaction.guild
            user = interaction.user
            if not guild or not isinstance(user, discord.Member):
                await interaction.followup.send("Guild only.", ephemeral=True)
                return
            player = await self._get_player(interaction)
            resp = await self.bot.cmd_shuffleplay(
                ssd_=self._ssd(interaction),
                message=None,           # guarded in _do_cmd_unpause_check
                player=player,
                channel=interaction.channel,
                guild=guild,
                author=user,
                permissions=self.bot.permissions.for_user(user),
                leftover_args=[],
                song_url=url,
            )
            await self._send(interaction, resp)
        except Exception as e:
            await self._err(interaction, e)

    # -----------------------------------------------------------------------
    # /playnext
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="playnext",
        description="Queue a song to play immediately after the current one.",
    )
    @app_commands.describe(query="URL or search term.")
    async def slash_playnext(self, interaction: discord.Interaction, query: str) -> None:
        await interaction.response.defer()
        if not await self._check_perms(interaction, "playnext"):
            return
        try:
            guild = interaction.guild
            user = interaction.user
            if not guild or not isinstance(user, discord.Member):
                await interaction.followup.send("Guild only.", ephemeral=True)
                return
            player = await self._get_player(interaction)
            resp = await self.bot.cmd_playnext(
                message=None,           # guarded in _do_cmd_unpause_check
                player=player,
                channel=interaction.channel,
                guild=guild,
                author=user,
                permissions=self.bot.permissions.for_user(user),
                leftover_args=[],
                song_url=query,
            )
            await self._send(interaction, resp)
        except Exception as e:
            await self._err(interaction, e)

    # =======================================================================
    # BATCH 2
    # playnow, seek, repeat, move, stream, search, np, summon, follow, pause
    # =======================================================================

    # -----------------------------------------------------------------------
    # /playnow
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="playnow",
        description="Skip the current song and play this immediately.",
    )
    @app_commands.describe(query="URL or search term.")
    async def slash_playnow(self, interaction: discord.Interaction, query: str) -> None:
        await interaction.response.defer()
        if not await self._check_perms(interaction, "playnow"):
            return
        try:
            guild = interaction.guild
            user = interaction.user
            if not guild or not isinstance(user, discord.Member):
                await interaction.followup.send("Guild only.", ephemeral=True)
                return
            player = await self._get_player(interaction)
            resp = await self.bot.cmd_playnow(
                message=None,
                player=player,
                channel=interaction.channel,
                guild=guild,
                author=user,
                permissions=self.bot.permissions.for_user(user),
                leftover_args=[],
                song_url=query,
            )
            await self._send(interaction, resp)
        except Exception as e:
            await self._err(interaction, e)

    # -----------------------------------------------------------------------
    # /seek
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="seek",
        description="Seek to a position in the current song. Prefix with + or - for relative seek.",
    )
    @app_commands.describe(time="Time in seconds, e.g. 90, 1:30, +30, -15")
    async def slash_seek(self, interaction: discord.Interaction, time: str) -> None:
        await interaction.response.defer()
        if not await self._check_perms(interaction, "seek"):
            return
        try:
            guild = interaction.guild
            if not guild:
                await interaction.followup.send("Guild only.", ephemeral=True)
                return
            player = await self._get_player(interaction)
            resp = await self.bot.cmd_seek(
                ssd_=self._ssd(interaction),
                guild=guild,
                player=player,
                leftover_args=[],
                seek_time=time,
            )
            await self._send(interaction, resp)
        except Exception as e:
            await self._err(interaction, e)

    # -----------------------------------------------------------------------
    # /repeat
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="repeat",
        description="Toggle repeat mode. No option = cycle through modes.",
    )
    @app_commands.describe(
        mode="song = loop current song | playlist = loop queue | on/off = explicit toggle"
    )
    @app_commands.choices(mode=[
        app_commands.Choice(name="song",     value="song"),
        app_commands.Choice(name="playlist", value="playlist"),
        app_commands.Choice(name="on",       value="on"),
        app_commands.Choice(name="off",      value="off"),
    ])
    async def slash_repeat(
        self,
        interaction: discord.Interaction,
        mode: Optional[app_commands.Choice[str]] = None,
    ) -> None:
        await interaction.response.defer()
        if not await self._check_perms(interaction, "repeat"):
            return
        try:
            player = await self._get_player(interaction)
            resp = await self.bot.cmd_repeat(
                ssd_=self._ssd(interaction),
                player=player,
                option=mode.value if mode else "",
            )
            await self._send(interaction, resp)
        except Exception as e:
            await self._err(interaction, e)

    # -----------------------------------------------------------------------
    # /move
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="move",
        description="Move a song from one queue position to another. Use /queue to see positions.",
    )
    @app_commands.describe(
        from_pos="Current position of the song in the queue.",
        to_pos="Target position to move the song to.",
    )
    async def slash_move(
        self,
        interaction: discord.Interaction,
        from_pos: int,
        to_pos: int,
    ) -> None:
        await interaction.response.defer()
        if not await self._check_perms(interaction, "move"):
            return
        try:
            guild = interaction.guild
            if not guild:
                await interaction.followup.send("Guild only.", ephemeral=True)
                return
            player = await self._get_player(interaction)
            resp = await self.bot.cmd_move(
                ssd_=self._ssd(interaction),
                player=player,
                guild=guild,
                channel=interaction.channel,
                command=str(from_pos),
                leftover_args=[str(to_pos)],
            )
            await self._send(interaction, resp)
        except Exception as e:
            await self._err(interaction, e)

    # -----------------------------------------------------------------------
    # /stream
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="stream",
        description="Add a URL to the queue as a live stream without downloading.",
    )
    @app_commands.describe(url="Direct stream URL (Twitch, YouTube live, shoutcast, etc.)")
    async def slash_stream(self, interaction: discord.Interaction, url: str) -> None:
        await interaction.response.defer()
        if not await self._check_perms(interaction, "stream"):
            return
        try:
            guild = interaction.guild
            user = interaction.user
            if not guild or not isinstance(user, discord.Member):
                await interaction.followup.send("Guild only.", ephemeral=True)
                return
            player = await self._get_player(interaction)
            resp = await self.bot.cmd_stream(
                ssd_=self._ssd(interaction),
                player=player,
                channel=interaction.channel,
                author=user,
                permissions=self.bot.permissions.for_user(user),
                message=None,
                song_url=url,
            )
            await self._send(interaction, resp)
        except Exception as e:
            await self._err(interaction, e)

    # -----------------------------------------------------------------------
    # /search  — full interactive picker via discord.ui.Select
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="search",
        description="Search for songs and pick from a dropdown of results.",
    )
    @app_commands.describe(
        query="Search query.",
        service="Service to search (yt, sc, yh, gv, nv, bb). Defaults to bot config.",
        results="Number of results to show (default 5, max set by your permissions).",
    )
    @app_commands.choices(service=[
        app_commands.Choice(name="YouTube (default)", value="yt"),
        app_commands.Choice(name="SoundCloud",        value="sc"),
        app_commands.Choice(name="Yahoo Video",       value="yh"),
        app_commands.Choice(name="Google Video",      value="gv"),
        app_commands.Choice(name="NicoNico",          value="nv"),
        app_commands.Choice(name="Bilibili",          value="bb"),
    ])
    async def slash_search(
        self,
        interaction: discord.Interaction,
        query: str,
        service: Optional[app_commands.Choice[str]] = None,
        results: Optional[int] = None,
    ) -> None:
        await interaction.response.defer()
        if not await self._check_perms(interaction, "search"):
            return

        guild = interaction.guild
        user = interaction.user
        if not guild or not isinstance(user, discord.Member):
            await interaction.followup.send("Guild only.", ephemeral=True)
            return

        try:
            player = await self._get_player(interaction)
        except Exception as e:
            await self._err(interaction, e)
            return

        perms = self.bot.permissions.for_user(user)

        if perms.max_songs and player.playlist.count_for_user(user) > perms.max_songs:
            await interaction.followup.send(
                f"❌ You have reached your playlist item limit ({perms.max_songs}).",
                ephemeral=True,
            )
            return

        if player.karaoke_mode and not perms.bypass_karaoke_mode:
            await interaction.followup.send(
                "❌ Karaoke mode is enabled.", ephemeral=True
            )
            return

        # Resolve service and result count
        svc_key = service.value if service else self.bot.config.default_search_service
        svc_label = service.name if service else svc_key
        srvc = SearchView.SERVICES.get(svc_key, svc_key)

        max_items = perms.max_search_items
        n = results if results is not None else self.bot.config.defaultsearchresults
        n = max(1, min(n, max_items, 25))  # clamp: at least 1, at most 25 or perms limit

        search_query = f"{srvc}{n}:{query}"

        try:
            self.bot._do_song_blocklist_check(query)
        except Exception as e:
            await self._err(interaction, e)
            return

        await interaction.followup.send(f"🔍 Searching **{svc_label}** for `{query}`…")

        try:
            info = await self.bot.downloader.extract_info(
                search_query, download=False, process=True
            )
        except Exception as e:
            await self._err(interaction, e)
            return

        if not info:
            await interaction.edit_original_response(content="No results found.")
            return

        entries = info.get_entries_objects()
        if not entries:
            await interaction.edit_original_response(content="No results found.")
            return

        view = SearchView(
            bot=self.bot,
            entries=entries,
            author=user,
            guild=guild,
            channel=interaction.channel,
            player=player,
            permissions=perms,
            service_label=svc_label,
        )

        await interaction.edit_original_response(
            content=f"**Search results from {svc_label}** — pick one to queue:",
            view=view,
        )

    # -----------------------------------------------------------------------
    # /np  (now playing)
    # cmd_np sends its own embed via safe_send_message and returns None.
    # We just trigger it and send a lightweight ephemeral ack so Discord
    # doesn't show "interaction failed".
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="np",
        description="Show what's currently playing.",
    )
    async def slash_np(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        if not await self._check_perms(interaction, "np"):
            return
        try:
            guild = interaction.guild
            if not guild:
                await interaction.followup.send("Guild only.", ephemeral=True)
                return
            player = await self._get_player(interaction)
            await self.bot.cmd_np(
                ssd_=self._ssd(interaction),
                player=player,
                channel=interaction.channel,
                guild=guild,
            )
            await interaction.followup.send("⬆️", ephemeral=True)
        except Exception as e:
            await self._err(interaction, e)

    # -----------------------------------------------------------------------
    # /summon
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="summon",
        description="Tell MusicBot to join your current voice channel.",
    )
    async def slash_summon(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        if not await self._check_perms(interaction, "summon"):
            return
        try:
            guild = interaction.guild
            user = interaction.user
            if not guild or not isinstance(user, discord.Member):
                await interaction.followup.send("Guild only.", ephemeral=True)
                return
            resp = await self.bot.cmd_summon(
                ssd_=self._ssd(interaction),
                guild=guild,
                author=user,
                message=None,   # guarded in cmd_summon
            )
            await self._send(interaction, resp)
        except Exception as e:
            await self._err(interaction, e)

    # -----------------------------------------------------------------------
    # /follow
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="follow",
        description="Make MusicBot follow you between voice channels. Run again to unfollow.",
    )
    @app_commands.describe(user="Owner only: follow a specific member instead of yourself.")
    async def slash_follow(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.Member] = None,
    ) -> None:
        await interaction.response.defer()
        if not await self._check_perms(interaction, "follow"):
            return
        try:
            guild = interaction.guild
            author = interaction.user
            if not guild or not isinstance(author, discord.Member):
                await interaction.followup.send("Guild only.", ephemeral=True)
                return
            mentions = [user] if user else []
            resp = await self.bot.cmd_follow(
                ssd_=self._ssd(interaction),
                guild=guild,
                author=author,
                user_mentions=mentions,
            )
            await self._send(interaction, resp)
        except Exception as e:
            await self._err(interaction, e)

    # -----------------------------------------------------------------------
    # /pause
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="pause",
        description="Pause the currently playing track.",
    )
    async def slash_pause(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        if not await self._check_perms(interaction, "pause"):
            return
        try:
            player = await self._get_player(interaction)
            resp = await self.bot.cmd_pause(
                ssd_=self._ssd(interaction),
                player=player,
            )
            await self._send(interaction, resp)
        except Exception as e:
            await self._err(interaction, e)
