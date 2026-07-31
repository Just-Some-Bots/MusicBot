"""
musicbot/slash_commands.py
--------------------------
Slash command wrappers for MusicBot.

All 53 user-facing commands covered across 6 batches:

  Batch 1 — resetplaylist, help, blockuser (group), blocksong (group),
             autoplaylist (group), joinserver, karaoke, play, shuffleplay, playnext
  Batch 2 — playnow, seek, repeat, move, stream, search, np, summon, follow, pause
  Batch 3 — resume, shuffle, clear, remove, skip, volume, speed,
             setalias (group), config (group), option
  Batch 4 — cache (group), queue, clean, pldump, id, listids, perms
  Batch 5 — setperms (group), setname, setnick, setprefix, language (group),
             setavatar, disconnect, restart (group), shutdown, leaveserver
  Batch 6 — checkupdates, uptime, botlatency, latency, botversion, setcookies

Dev-only commands intentionally excluded:
  testready, breakpoint, objgraph, debug, makemarkdown, makeini

Strategy
--------
* Each slash handler defers the interaction, resolves the same context objects
  that on_message normally injects (player, ssd_, permissions, …), then calls
  the existing cmd_* method directly. Zero business-logic duplication.
* The custom permissions system is preserved via _check_perms().
* A shared _send() helper converts Response/ErrorResponse → interaction reply.
* SearchView and QueueView provide interactive UI for /search and /queue.
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



# ---------------------------------------------------------------------------
# QueueView — paginated queue display for /queue
# ---------------------------------------------------------------------------

class QueueView(discord.ui.View):
    """
    Prev / Next / Close pagination for the /queue command.
    Any user in the guild can flip pages.
    Auto-disables after the bot's configured delete_delay_long timeout.
    """

    def __init__(
        self,
        *,
        bot: "MusicBot",
        player: "MusicPlayer",
        guild: discord.Guild,
        channel,
        ssd,
        start_page: int = 0,
    ) -> None:
        super().__init__(timeout=bot.config.delete_delay_long)
        self.bot = bot
        self.player = player
        self.guild = guild
        self.channel = channel
        self.ssd = ssd
        self.page = start_page
        self.message: Optional[discord.Message] = None

    @property
    def pages_total(self) -> int:
        import math
        total = len(self.player.playlist.entries)
        if not total:
            return 1
        return math.ceil(total / self.bot.config.queue_length)

    async def build_page(self) -> str:
        """Build the text content for the current page."""
        from .utils import format_song_duration

        player = self.player
        ssd = self.ssd
        total_entry_count = len(player.playlist.entries)

        if not total_entry_count:
            return "There are no songs queued! Queue something with a play command."

        current_progress = ""
        if player.is_playing and player.current_entry:
            song_progress = format_song_duration(player.progress)
            song_total = (
                format_song_duration(player.current_entry.duration_td)
                if player.current_entry.duration is not None
                else "(unknown duration)"
            )
            added_by = "[autoplaylist]"
            if player.current_entry.channel and player.current_entry.author:
                added_by = player.current_entry.author.name
            current_progress = (
                f"Currently playing: `{player.current_entry.title}`\n"
                f"Added by: `{added_by}`\n"
                f"Progress: `[{song_progress}/{song_total}]`\n\n"
            )

        start_index = self.bot.config.queue_length * self.page
        end_index = start_index + self.bot.config.queue_length
        starting_at = start_index + 1

        tracks_list = ""
        queue_segment = list(player.playlist.entries)[start_index:end_index]
        for idx, item in enumerate(queue_segment, starting_at):
            if item == player.current_entry:
                continue
            added_by = "[autoplaylist]"
            if item.channel and item.author:
                added_by = item.author.name
            title = item.title[:40] + " ..." if len(item.title) > 40 else item.title
            entry_str = f"**#{idx}:** `{title}` — added by `{added_by}`\n"
            if len(tracks_list) + len(entry_str) < 1800:
                tracks_list += entry_str

        page_info = f"Page **{self.page + 1}/{self.pages_total}**"
        return (
            f"**Songs in queue** — {page_info}\n\n"
            f"{current_progress}"
            f"There are `{total_entry_count}` entries total.\n\n"
            f"{tracks_list}"
        )

    def _update_buttons(self) -> None:
        self.prev_button.disabled = self.page <= 0
        self.next_button.disabled = self.page >= self.pages_total - 1

    @discord.ui.button(emoji="⬅️", style=discord.ButtonStyle.secondary)
    async def prev_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        self.page = max(0, self.page - 1)
        self._update_buttons()
        content = await self.build_page()
        await interaction.response.edit_message(content=content, view=self)

    @discord.ui.button(emoji="➡️", style=discord.ButtonStyle.secondary)
    async def next_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        self.page = min(self.pages_total - 1, self.page + 1)
        self._update_buttons()
        content = await self.build_page()
        await interaction.response.edit_message(content=content, view=self)

    @discord.ui.button(emoji="✖️", style=discord.ButtonStyle.danger)
    async def close_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        self.stop()
        await interaction.response.edit_message(content="Queue closed.", view=None)

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass

class SlashCommands(commands.Cog):
    """Slash command surface for MusicBot."""

    def __init__(self, bot: MusicBot) -> None:
        self.bot = bot

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        """
        Slash command callbacks run through discord.py's app_commands error
        path, which never reaches Client.on_error. Without this, the
        RestartSignal/TerminateSignal that _restart()/slash_shutdown() raise
        would just be logged and swallowed here, leaving the bot running.
        Mirror on_error's signal handling (see MusicBot.on_error in bot.py).
        """
        original = getattr(error, "original", error)
        if isinstance(original, (exceptions.RestartSignal, exceptions.TerminateSignal)):
            self.bot.exit_signal = original
            await self.bot.logout()
            return
        log.error(
            "Error in slash command %s",
            interaction.command.name if interaction.command else "?",
            exc_info=original,
        )

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

    # =======================================================================
    # BATCH 3
    # resume, shuffle, clear, remove, skip, volume, speed,
    # setalias (group), config (group), option
    # =======================================================================

    # -----------------------------------------------------------------------
    # /resume
    # -----------------------------------------------------------------------

    @app_commands.command(name="resume", description="Resume a paused player.")
    async def slash_resume(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        if not await self._check_perms(interaction, "resume"):
            return
        try:
            player = await self._get_player(interaction)
            resp = await self.bot.cmd_resume(
                ssd_=self._ssd(interaction),
                player=player,
            )
            await self._send(interaction, resp)
        except Exception as e:
            await self._err(interaction, e)

    # -----------------------------------------------------------------------
    # /shuffle
    # -----------------------------------------------------------------------

    @app_commands.command(name="shuffle", description="Shuffle all tracks currently in the queue.")
    async def slash_shuffle(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        if not await self._check_perms(interaction, "shuffle"):
            return
        try:
            player = await self._get_player(interaction)
            resp = await self.bot.cmd_shuffle(
                ssd_=self._ssd(interaction),
                channel=interaction.channel,
                player=player,
            )
            await self._send(interaction, resp)
        except Exception as e:
            await self._err(interaction, e)

    # -----------------------------------------------------------------------
    # /clear
    # -----------------------------------------------------------------------

    @app_commands.command(name="clear", description="Remove all songs from the queue.")
    async def slash_clear(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        if not await self._check_perms(interaction, "clear"):
            return
        try:
            guild = interaction.guild
            if not guild:
                await interaction.followup.send("Guild only.", ephemeral=True)
                return
            _player = self.bot.get_player_in(guild)
            resp = await self.bot.cmd_clear(
                ssd_=self._ssd(interaction),
                _player=_player,
                guild=guild,
            )
            await self._send(interaction, resp)
        except Exception as e:
            await self._err(interaction, e)

    # -----------------------------------------------------------------------
    # /remove
    # Three modes: by position, by range (from+to), by user mention.
    # Omitting all args removes the last item in the queue.
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="remove",
        description="Remove a song from the queue by position, range, or user.",
    )
    @app_commands.describe(
        position="Queue position to remove (omit to remove last item).",
        to_position="End of range — removes FROM position through this one.",
        user="Remove all songs queued by this member.",
    )
    async def slash_remove(
        self,
        interaction: discord.Interaction,
        position: Optional[int] = None,
        to_position: Optional[int] = None,
        user: Optional[discord.Member] = None,
    ) -> None:
        await interaction.response.defer()
        if not await self._check_perms(interaction, "remove"):
            return
        try:
            author = interaction.user
            if not isinstance(author, discord.Member):
                await interaction.followup.send("Guild only.", ephemeral=True)
                return
            player = await self._get_player(interaction)
            perms = self.bot.permissions.for_user(author)

            # Map slash args back to what cmd_remove expects:
            # position=""  leftover_args=[]           → remove last
            # position="N" leftover_args=[]           → remove at N
            # position="N" leftover_args=["M"]        → remove range N-M
            # user_mentions=[user]                    → remove by user
            pos_str = str(position) if position is not None else ""
            leftover = [str(to_position)] if to_position is not None else []

            resp = await self.bot.cmd_remove(
                ssd_=self._ssd(interaction),
                user_mentions=[user] if user else [],
                author=author,
                permissions=perms,
                player=player,
                leftover_args=leftover,
                position=pos_str,
            )
            await self._send(interaction, resp)
        except Exception as e:
            await self._err(interaction, e)

    # -----------------------------------------------------------------------
    # /skip
    # NOTE: Vote-skip via slash passes message=None, so add_skipper is skipped
    # (guarded in bot.py). Vote tallying is based on existing skip state only.
    # Force skip works fully.
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="skip",
        description="Skip or vote to skip the current song.",
    )
    @app_commands.describe(force="Force skip — requires InstaSkip permission.")
    async def slash_skip(
        self,
        interaction: discord.Interaction,
        force: Optional[bool] = None,
    ) -> None:
        await interaction.response.defer()
        if not await self._check_perms(interaction, "skip"):
            return
        try:
            guild = interaction.guild
            user = interaction.user
            if not guild or not isinstance(user, discord.Member):
                await interaction.followup.send("Guild only.", ephemeral=True)
                return
            player = await self._get_player(interaction)
            voice_channel = user.voice.channel if user.voice else None
            param = "force" if force else ""
            resp = await self.bot.cmd_skip(
                ssd_=self._ssd(interaction),
                guild=guild,
                player=player,
                author=user,
                message=None,       # guarded in bot.py — vote-skip add_skipper skipped
                permissions=self.bot.permissions.for_user(user),
                voice_channel=voice_channel,
                param=param,
            )
            await self._send(interaction, resp)
        except Exception as e:
            await self._err(interaction, e)

    # -----------------------------------------------------------------------
    # /volume
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="volume",
        description="Set or show the playback volume (1–100). Prefix with + or - for relative.",
    )
    @app_commands.describe(level="Volume level 1–100. Use +10 or -10 for relative change.")
    async def slash_volume(
        self,
        interaction: discord.Interaction,
        level: Optional[str] = None,
    ) -> None:
        await interaction.response.defer()
        if not await self._check_perms(interaction, "volume"):
            return
        try:
            player = await self._get_player(interaction)
            resp = await self.bot.cmd_volume(
                ssd_=self._ssd(interaction),
                player=player,
                new_volume=level or "",
            )
            await self._send(interaction, resp)
        except Exception as e:
            await self._err(interaction, e)

    # -----------------------------------------------------------------------
    # /speed
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="speed",
        description="Change playback speed of the current track (0.5–100.0).",
    )
    @app_commands.describe(rate="Playback rate, e.g. 1.5 for 50% faster, 0.75 for slower.")
    async def slash_speed(
        self,
        interaction: discord.Interaction,
        rate: str,
    ) -> None:
        await interaction.response.defer()
        if not await self._check_perms(interaction, "speed"):
            return
        try:
            guild = interaction.guild
            if not guild:
                await interaction.followup.send("Guild only.", ephemeral=True)
                return
            player = await self._get_player(interaction)
            resp = await self.bot.cmd_speed(
                ssd_=self._ssd(interaction),
                guild=guild,
                player=player,
                new_speed=rate,
            )
            await self._send(interaction, resp)
        except Exception as e:
            await self._err(interaction, e)

    # -----------------------------------------------------------------------
    # /setalias  (owner-only group)
    # -----------------------------------------------------------------------

    setalias = app_commands.Group(
        name="setalias",
        description="Manage bot command aliases. Owner only.",
        default_permissions=discord.Permissions(administrator=True),
    )

    async def _owner_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.bot.config.owner_id:
            await interaction.followup.send(
                "This command is restricted to the bot owner.", ephemeral=True
            )
            return False
        return True

    @setalias.command(name="add", description="Add a new alias for a command.")
    @app_commands.describe(
        alias="The alias name to create.",
        command="The command the alias maps to.",
        args="Optional arguments to bake into the alias.",
    )
    async def slash_setalias_add(
        self,
        interaction: discord.Interaction,
        alias: str,
        command: str,
        args: Optional[str] = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        if not await self._owner_check(interaction):
            return
        try:
            resp = await self.bot.cmd_setalias(
                ssd_=self._ssd(interaction),
                opt="add",
                leftover_args=args.split() if args else [],
                alias=alias,
                cmd=command,
            )
            await self._send(interaction, resp, ephemeral=True)
        except Exception as e:
            await self._err(interaction, e)

    @setalias.command(name="remove", description="Remove an existing alias.")
    @app_commands.describe(alias="The alias name to remove.")
    async def slash_setalias_remove(
        self,
        interaction: discord.Interaction,
        alias: str,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        if not await self._owner_check(interaction):
            return
        try:
            resp = await self.bot.cmd_setalias(
                ssd_=self._ssd(interaction),
                opt="remove",
                leftover_args=[],
                alias=alias,
                cmd="",
            )
            await self._send(interaction, resp, ephemeral=True)
        except Exception as e:
            await self._err(interaction, e)

    @setalias.command(name="save", description="Save current aliases to the config file.")
    async def slash_setalias_save(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        if not await self._owner_check(interaction):
            return
        try:
            resp = await self.bot.cmd_setalias(
                ssd_=self._ssd(interaction),
                opt="save",
                leftover_args=[],
            )
            await self._send(interaction, resp, ephemeral=True)
        except Exception as e:
            await self._err(interaction, e)

    @setalias.command(name="load", description="Reload aliases from the config file.")
    async def slash_setalias_load(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        if not await self._owner_check(interaction):
            return
        try:
            resp = await self.bot.cmd_setalias(
                ssd_=self._ssd(interaction),
                opt="load",
                leftover_args=[],
            )
            await self._send(interaction, resp, ephemeral=True)
        except Exception as e:
            await self._err(interaction, e)

    # -----------------------------------------------------------------------
    # /config  (owner-only group)
    # -----------------------------------------------------------------------

    config = app_commands.Group(
        name="config",
        description="Manage bot configuration. Owner only.",
        default_permissions=discord.Permissions(administrator=True),
    )

    @config.command(name="missing", description="Show any missing config options.")
    async def slash_config_missing(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        if not await self._owner_check(interaction):
            return
        try:
            resp = await self.bot.cmd_config(
                ssd_=self._ssd(interaction),
                user_mentions=[], channel_mentions=[],
                option="missing", leftover_args=[],
            )
            await self._send(interaction, resp, ephemeral=True)
        except Exception as e:
            await self._err(interaction, e)

    @config.command(name="diff", description="List options changed since last config load.")
    async def slash_config_diff(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        if not await self._owner_check(interaction):
            return
        try:
            resp = await self.bot.cmd_config(
                ssd_=self._ssd(interaction),
                user_mentions=[], channel_mentions=[],
                option="diff", leftover_args=[],
            )
            await self._send(interaction, resp, ephemeral=True)
        except Exception as e:
            await self._err(interaction, e)

    @config.command(name="list", description="List all available config options.")
    async def slash_config_list(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        if not await self._owner_check(interaction):
            return
        try:
            resp = await self.bot.cmd_config(
                ssd_=self._ssd(interaction),
                user_mentions=[], channel_mentions=[],
                option="list", leftover_args=[],
            )
            await self._send(interaction, resp, ephemeral=True)
        except Exception as e:
            await self._err(interaction, e)

    @config.command(name="reload", description="Reload options.ini from disk.")
    async def slash_config_reload(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        if not await self._owner_check(interaction):
            return
        try:
            resp = await self.bot.cmd_config(
                ssd_=self._ssd(interaction),
                user_mentions=[], channel_mentions=[],
                option="reload", leftover_args=[],
            )
            await self._send(interaction, resp, ephemeral=True)
        except Exception as e:
            await self._err(interaction, e)

    @config.command(name="help", description="Show help text for a specific config option.")
    @app_commands.describe(option="Option name (section can be omitted if unambiguous).")
    async def slash_config_help(self, interaction: discord.Interaction, option: str) -> None:
        await interaction.response.defer(ephemeral=True)
        if not await self._owner_check(interaction):
            return
        try:
            resp = await self.bot.cmd_config(
                ssd_=self._ssd(interaction),
                user_mentions=[], channel_mentions=[],
                option="help", leftover_args=option.split(),
            )
            await self._send(interaction, resp, ephemeral=True)
        except Exception as e:
            await self._err(interaction, e)

    @config.command(name="show", description="Show the current value of a config option.")
    @app_commands.describe(option="Option name (section can be omitted if unambiguous).")
    async def slash_config_show(self, interaction: discord.Interaction, option: str) -> None:
        await interaction.response.defer(ephemeral=True)
        if not await self._owner_check(interaction):
            return
        try:
            resp = await self.bot.cmd_config(
                ssd_=self._ssd(interaction),
                user_mentions=[], channel_mentions=[],
                option="show", leftover_args=option.split(),
            )
            await self._send(interaction, resp, ephemeral=True)
        except Exception as e:
            await self._err(interaction, e)

    @config.command(name="set", description="Set a config option for this session (not saved to file).")
    @app_commands.describe(
        option="Option name (section can be omitted if unambiguous).",
        value="New value to set.",
    )
    async def slash_config_set(
        self, interaction: discord.Interaction, option: str, value: str
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        if not await self._owner_check(interaction):
            return
        try:
            resp = await self.bot.cmd_config(
                ssd_=self._ssd(interaction),
                user_mentions=[], channel_mentions=[],
                option="set", leftover_args=[*option.split(), value],
            )
            await self._send(interaction, resp, ephemeral=True)
        except Exception as e:
            await self._err(interaction, e)

    @config.command(name="save", description="Save the current value of a config option to disk.")
    @app_commands.describe(option="Option name (section can be omitted if unambiguous).")
    async def slash_config_save(self, interaction: discord.Interaction, option: str) -> None:
        await interaction.response.defer(ephemeral=True)
        if not await self._owner_check(interaction):
            return
        try:
            resp = await self.bot.cmd_config(
                ssd_=self._ssd(interaction),
                user_mentions=[], channel_mentions=[],
                option="save", leftover_args=option.split(),
            )
            await self._send(interaction, resp, ephemeral=True)
        except Exception as e:
            await self._err(interaction, e)

    @config.command(name="reset", description="Reset a config option to its default value.")
    @app_commands.describe(option="Option name (section can be omitted if unambiguous).")
    async def slash_config_reset(self, interaction: discord.Interaction, option: str) -> None:
        await interaction.response.defer(ephemeral=True)
        if not await self._owner_check(interaction):
            return
        try:
            resp = await self.bot.cmd_config(
                ssd_=self._ssd(interaction),
                user_mentions=[], channel_mentions=[],
                option="reset", leftover_args=option.split(),
            )
            await self._send(interaction, resp, ephemeral=True)
        except Exception as e:
            await self._err(interaction, e)

    # -----------------------------------------------------------------------
    # /option  (deprecated — just surfaces the error message)
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="option",
        description="Deprecated. Use /config instead.",
    )
    async def slash_option(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send(
            "❌ The `option` command is deprecated. Use `/config` instead.",
            ephemeral=True,
        )

    # =======================================================================
    # BATCH 4
    # cache (group), queue, clean, pldump, id, listids, perms
    # + QueueView helper class (defined below SlashCommands — see bottom)
    # =======================================================================

    # -----------------------------------------------------------------------
    # /cache  (owner-only group)
    # -----------------------------------------------------------------------

    cache = app_commands.Group(
        name="cache",
        description="Manage the audio file cache. Owner only.",
        default_permissions=discord.Permissions(administrator=True),
    )

    @cache.command(name="info", description="Show current cache size and settings.")
    async def slash_cache_info(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        if not await self._owner_check(interaction):
            return
        try:
            resp = await self.bot.cmd_cache(ssd_=self._ssd(interaction), opt="info")
            await self._send(interaction, resp, ephemeral=True)
        except Exception as e:
            await self._err(interaction, e)

    @cache.command(name="update", description="Scan the cache folder then show info.")
    async def slash_cache_update(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        if not await self._owner_check(interaction):
            return
        try:
            resp = await self.bot.cmd_cache(ssd_=self._ssd(interaction), opt="update")
            await self._send(interaction, resp, ephemeral=True)
        except Exception as e:
            await self._err(interaction, e)

    @cache.command(name="clear", description="Clear the audio cache according to configured limits.")
    async def slash_cache_clear(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        if not await self._owner_check(interaction):
            return
        try:
            resp = await self.bot.cmd_cache(ssd_=self._ssd(interaction), opt="clear")
            await self._send(interaction, resp, ephemeral=True)
        except Exception as e:
            await self._err(interaction, e)

    # -----------------------------------------------------------------------
    # /queue
    # Pagination is handled by QueueView (defined after SlashCommands).
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="queue",
        description="Show the current song queue with pagination.",
    )
    @app_commands.describe(page="Queue page number to start on.")
    async def slash_queue(
        self,
        interaction: discord.Interaction,
        page: Optional[int] = None,
    ) -> None:
        await interaction.response.defer()
        if not await self._check_perms(interaction, "queue"):
            return
        try:
            guild = interaction.guild
            if not guild:
                await interaction.followup.send("Guild only.", ephemeral=True)
                return
            player = await self._get_player(interaction)
            ssd = self._ssd(interaction)

            import math
            total = len(player.playlist.entries)
            pages_total = math.ceil(total / self.bot.config.queue_length) if total else 1
            start_page = max(0, (page or 1) - 1)

            view = QueueView(
                bot=self.bot,
                player=player,
                guild=guild,
                channel=interaction.channel,
                ssd=ssd,
                start_page=start_page,
            )
            content = await view.build_page()

            # Mirror original behaviour: no pagination UI when everything fits on one page.
            if pages_total <= 1:
                await interaction.followup.send(content=content)
            else:
                await interaction.followup.send(content=content, view=view)
                view.message = await interaction.original_response()
        except Exception as e:
            await self._err(interaction, e)

    # -----------------------------------------------------------------------
    # /clean
    # NOTE: Without a triggering message, purge runs against the most recent
    # messages (before=utcnow()) rather than stopping before the command msg.
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="clean",
        description="Delete bot messages and command invocations from this channel.",
    )
    @app_commands.describe(range="Number of messages to search through (default 50, max 500).")
    async def slash_clean(
        self,
        interaction: discord.Interaction,
        range: Optional[int] = 50,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        if not await self._check_perms(interaction, "clean"):
            return
        try:
            guild = interaction.guild
            user = interaction.user
            if not guild or not isinstance(user, discord.Member):
                await interaction.followup.send("Guild only.", ephemeral=True)
                return
            resp = await self.bot.cmd_clean(
                ssd_=self._ssd(interaction),
                message=None,           # guarded in bot.py — purge uses utcnow() instead
                channel=interaction.channel,
                guild=guild,
                author=user,
                search_range_str=str(range),
            )
            await self._send(interaction, resp, ephemeral=True)
        except Exception as e:
            await self._err(interaction, e)

    # -----------------------------------------------------------------------
    # /pldump
    # Original sends the file as a DM. Slash version sends it as an
    # ephemeral file attachment in-channel instead.
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="pldump",
        description="Dump all URLs from a playlist to a text file.",
    )
    @app_commands.describe(url="Playlist URL to dump.")
    async def slash_pldump(self, interaction: discord.Interaction, url: str) -> None:
        await interaction.response.defer(ephemeral=True)
        if not await self._check_perms(interaction, "pldump"):
            return
        try:
            user = interaction.user
            if not isinstance(user, discord.Member):
                await interaction.followup.send("Guild only.", ephemeral=True)
                return
            resp = await self.bot.cmd_pldump(
                ssd_=self._ssd(interaction),
                author=user,
                song_subject=url,
            )
            if resp and getattr(resp, "files", None):
                await interaction.followup.send(
                    _content(resp), files=resp.files, ephemeral=True
                )
            else:
                await self._send(interaction, resp, ephemeral=True)
        except Exception as e:
            await self._err(interaction, e)

    # -----------------------------------------------------------------------
    # /id
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="id",
        description="Show your Discord user ID, or the ID of another member.",
    )
    @app_commands.describe(user="Member to look up (omit to show your own ID).")
    async def slash_id(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.Member] = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        if not await self._check_perms(interaction, "id"):
            return
        try:
            author = interaction.user
            if not isinstance(author, discord.Member):
                await interaction.followup.send("Guild only.", ephemeral=True)
                return
            resp = await self.bot.cmd_id(
                ssd_=self._ssd(interaction),
                author=author,
                user_mentions=[user] if user else [],
            )
            await self._send(interaction, resp, ephemeral=True)
        except Exception as e:
            await self._err(interaction, e)

    # -----------------------------------------------------------------------
    # /listids
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="listids",
        description="Dump Discord IDs for this server's users, roles, and channels to a file.",
    )
    @app_commands.describe(category="Which IDs to include (default: all).")
    @app_commands.choices(category=[
        app_commands.Choice(name="All",      value="all"),
        app_commands.Choice(name="Users",    value="users"),
        app_commands.Choice(name="Roles",    value="roles"),
        app_commands.Choice(name="Channels", value="channels"),
    ])
    async def slash_listids(
        self,
        interaction: discord.Interaction,
        category: Optional[app_commands.Choice[str]] = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        if not await self._check_perms(interaction, "listids"):
            return
        try:
            guild = interaction.guild
            user = interaction.user
            if not guild or not isinstance(user, discord.Member):
                await interaction.followup.send("Guild only.", ephemeral=True)
                return
            cat = category.value if category else "all"
            resp = await self.bot.cmd_listids(
                ssd_=self._ssd(interaction),
                guild=guild,
                author=user,
                leftover_args=[],
                cat=cat,
            )
            if resp and getattr(resp, "files", None):
                await interaction.followup.send(
                    _content(resp), files=resp.files, ephemeral=True
                )
            else:
                await self._send(interaction, resp, ephemeral=True)
        except Exception as e:
            await self._err(interaction, e)

    # -----------------------------------------------------------------------
    # /perms
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="perms",
        description="Show your MusicBot permissions, or another member's.",
    )
    @app_commands.describe(user="Member to check (omit to check your own permissions).")
    async def slash_perms(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.Member] = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        if not await self._check_perms(interaction, "perms"):
            return
        try:
            guild = interaction.guild
            author = interaction.user
            if not guild or not isinstance(author, discord.Member):
                await interaction.followup.send("Guild only.", ephemeral=True)
                return
            resp = await self.bot.cmd_perms(
                ssd_=self._ssd(interaction),
                author=author,
                user_mentions=[user] if user else [],
                guild=guild,
                permissions=self.bot.permissions.for_user(author),
                target=str(user.id) if user else "",
            )
            # cmd_perms sends to DM via send_to=author — extract content and
            # send as ephemeral instead so it stays in-channel for slash.
            await self._send(interaction, resp, ephemeral=True)
        except Exception as e:
            await self._err(interaction, e)

    # =======================================================================
    # BATCH 5
    # setperms (group), setname, setnick, setprefix, language (group),
    # setavatar, disconnect, restart (group), shutdown, leaveserver
    # =======================================================================

    # -----------------------------------------------------------------------
    # /setperms  (owner-only group)
    # -----------------------------------------------------------------------

    setperms = app_commands.Group(
        name="setperms",
        description="Manage permissions.ini configuration. Owner only.",
        default_permissions=discord.Permissions(administrator=True),
    )

    async def _sp(
        self,
        interaction: discord.Interaction,
        option: str,
        leftover_args: Optional[list] = None,
    ) -> None:
        """Shared dispatcher for /setperms subcommands."""
        if not await self._owner_check(interaction):
            return
        try:
            resp = await self.bot.cmd_setperms(
                ssd_=self._ssd(interaction),
                user_mentions=[],
                leftover_args=leftover_args or [],
                option=option,
            )
            await self._send(interaction, resp, ephemeral=True)
        except Exception as e:
            await self._err(interaction, e)

    @setperms.command(name="list", description="Show loaded groups and available permission options.")
    async def slash_setperms_list(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        await self._sp(interaction, "list")

    @setperms.command(name="reload", description="Reload permissions from permissions.ini.")
    async def slash_setperms_reload(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        await self._sp(interaction, "reload")

    @setperms.command(name="add", description="Add a new permissions group with defaults.")
    @app_commands.describe(group="Name of the new group to create.")
    async def slash_setperms_add(self, interaction: discord.Interaction, group: str) -> None:
        await interaction.response.defer(ephemeral=True)
        await self._sp(interaction, "add", [group])

    @setperms.command(name="remove", description="Remove an existing permissions group.")
    @app_commands.describe(group="Name of the group to remove.")
    async def slash_setperms_remove(self, interaction: discord.Interaction, group: str) -> None:
        await interaction.response.defer(ephemeral=True)
        await self._sp(interaction, "remove", [group])

    @setperms.command(name="save", description="Save a permissions group to file.")
    @app_commands.describe(group="Name of the group to save.")
    async def slash_setperms_save(self, interaction: discord.Interaction, group: str) -> None:
        await interaction.response.defer(ephemeral=True)
        await self._sp(interaction, "save", [group])

    @setperms.command(name="help", description="Show help text for a permission option.")
    @app_commands.describe(permission="Permission option name.")
    async def slash_setperms_help(self, interaction: discord.Interaction, permission: str) -> None:
        await interaction.response.defer(ephemeral=True)
        await self._sp(interaction, "help", [permission])

    @setperms.command(name="show", description="Show the current value of a permission for a group.")
    @app_commands.describe(group="Group name.", permission="Permission option name.")
    async def slash_setperms_show(
        self, interaction: discord.Interaction, group: str, permission: str
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        await self._sp(interaction, "show", [group, permission])

    @setperms.command(name="set", description="Set a permission value for a group.")
    @app_commands.describe(
        group="Group name.",
        permission="Permission option name.",
        value="Value to set.",
    )
    async def slash_setperms_set(
        self, interaction: discord.Interaction, group: str, permission: str, value: str
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        await self._sp(interaction, "set", [group, permission, value])

    # -----------------------------------------------------------------------
    # /setname  (owner-only)
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="setname",
        description="Change the bot's Discord username. Limited to twice per hour.",
    )
    @app_commands.describe(name="New username for the bot.")
    async def slash_setname(self, interaction: discord.Interaction, name: str) -> None:
        await interaction.response.defer(ephemeral=True)
        if not await self._owner_check(interaction):
            return
        try:
            resp = await self.bot.cmd_setname(
                ssd_=self._ssd(interaction),
                leftover_args=[],
                name=name,
            )
            await self._send(interaction, resp, ephemeral=True)
        except Exception as e:
            await self._err(interaction, e)

    # -----------------------------------------------------------------------
    # /setnick
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="setnick",
        description="Change the bot's nickname in this server.",
    )
    @app_commands.describe(nick="New nickname for the bot.")
    async def slash_setnick(self, interaction: discord.Interaction, nick: str) -> None:
        await interaction.response.defer()
        if not await self._check_perms(interaction, "setnick"):
            return
        try:
            guild = interaction.guild
            if not guild:
                await interaction.followup.send("Guild only.", ephemeral=True)
                return
            resp = await self.bot.cmd_setnick(
                ssd_=self._ssd(interaction),
                guild=guild,
                channel=interaction.channel,
                leftover_args=[],
                nick=nick,
            )
            await self._send(interaction, resp)
        except Exception as e:
            await self._err(interaction, e)

    # -----------------------------------------------------------------------
    # /setprefix
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="setprefix",
        description="Set or clear a per-server command prefix. Requires EnablePrefixPerGuild.",
    )
    @app_commands.describe(prefix="New prefix, or 'clear' to remove the server prefix.")
    async def slash_setprefix(self, interaction: discord.Interaction, prefix: str) -> None:
        await interaction.response.defer()
        if not await self._check_perms(interaction, "setprefix"):
            return
        try:
            resp = await self.bot.cmd_setprefix(
                ssd_=self._ssd(interaction),
                prefix=prefix,
            )
            await self._send(interaction, resp)
        except Exception as e:
            await self._err(interaction, e)

    # -----------------------------------------------------------------------
    # /language  (group)
    # -----------------------------------------------------------------------

    language = app_commands.Group(
        name="language",
        description="Manage the bot's language for this server.",
    )

    @language.command(name="show", description="Show the current language and available options.")
    async def slash_language_show(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        if not await self._check_perms(interaction, "language"):
            return
        try:
            resp = await self.bot.cmd_language(
                ssd_=self._ssd(interaction),
                subcmd="show",
            )
            await self._send(interaction, resp, ephemeral=True)
        except Exception as e:
            await self._err(interaction, e)

    @language.command(name="set", description="Set the language for this server.")
    @app_commands.describe(locale="Language code, e.g. en_US, de_DE.")
    async def slash_language_set(self, interaction: discord.Interaction, locale: str) -> None:
        await interaction.response.defer()
        if not await self._check_perms(interaction, "language"):
            return
        try:
            resp = await self.bot.cmd_language(
                ssd_=self._ssd(interaction),
                subcmd="set",
                lang_code=locale,
            )
            await self._send(interaction, resp)
        except Exception as e:
            await self._err(interaction, e)

    @language.command(name="reset", description="Reset this server's language to the bot default.")
    async def slash_language_reset(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        if not await self._check_perms(interaction, "language"):
            return
        try:
            resp = await self.bot.cmd_language(
                ssd_=self._ssd(interaction),
                subcmd="reset",
            )
            await self._send(interaction, resp)
        except Exception as e:
            await self._err(interaction, e)

    # -----------------------------------------------------------------------
    # /setavatar  (owner-only)
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="setavatar",
        description="Change the bot's avatar. Provide a URL or attach an image.",
    )
    @app_commands.describe(
        url="Direct image URL.",
        attachment="Upload an image file directly.",
    )
    async def slash_setavatar(
        self,
        interaction: discord.Interaction,
        url: Optional[str] = None,
        attachment: Optional[discord.Attachment] = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        if not await self._owner_check(interaction):
            return
        if not url and not attachment:
            await interaction.followup.send(
                "❌ You must provide a URL or attach an image.", ephemeral=True
            )
            return
        try:
            import aiohttp
            thing = attachment.url if attachment else url
            timeout = aiohttp.ClientTimeout(total=10)
            if self.bot.user and self.bot.session:
                async with self.bot.session.get(thing, timeout=timeout) as res:
                    await self.bot.user.edit(avatar=await res.read())
            ssd = self._ssd(interaction)
            from .i18n import _D
            await interaction.followup.send(
                _D("Changed the bot's avatar.", ssd), ephemeral=True
            )
        except Exception as e:
            await self._err(interaction, e)

    # -----------------------------------------------------------------------
    # /disconnect
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="disconnect",
        description="Force MusicBot to disconnect from voice in this server.",
    )
    async def slash_disconnect(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        if not await self._check_perms(interaction, "disconnect"):
            return
        try:
            guild = interaction.guild
            if not guild:
                await interaction.followup.send("Guild only.", ephemeral=True)
                return
            resp = await self.bot.cmd_disconnect(guild=guild)
            await self._send(interaction, resp)
        except Exception as e:
            await self._err(interaction, e)

    # -----------------------------------------------------------------------
    # /restart  (owner-only group)
    # -----------------------------------------------------------------------

    restart = app_commands.Group(
        name="restart",
        description="Restart the bot in various ways. Owner only.",
        default_permissions=discord.Permissions(administrator=True),
    )

    async def _restart(self, interaction: discord.Interaction, opt: str) -> None:
        if not await self._owner_check(interaction):
            return
        guild = interaction.guild
        if not guild:
            await interaction.followup.send("Guild only.", ephemeral=True)
            return
        _player = self.bot.get_player_in(guild)
        try:
            await self.bot.cmd_restart(
                _player=_player,
                guild=guild,
                channel=interaction.channel,
                opt=opt,
            )
        except (exceptions.RestartSignal, exceptions.TerminateSignal):
            raise
        except Exception as e:
            await self._err(interaction, e)

    @restart.command(name="soft", description="Reload the bot without a full process restart.")
    async def slash_restart_soft(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send("♻️ Restarting (soft)…", ephemeral=True)
        await self._restart(interaction, "soft")

    @restart.command(name="full", description="Fully restart the bot process.")
    async def slash_restart_full(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send("♻️ Restarting (full)…", ephemeral=True)
        await self._restart(interaction, "full")

    @restart.command(name="uppip", description="Update pip packages then fully restart.")
    async def slash_restart_uppip(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send("📦 Updating pip and restarting…", ephemeral=True)
        await self._restart(interaction, "uppip")

    @restart.command(name="upgit", description="Update bot code with git then fully restart.")
    async def slash_restart_upgit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send("🔄 Updating via git and restarting…", ephemeral=True)
        await self._restart(interaction, "upgit")

    @restart.command(name="upgrade", description="Update everything (pip + git) then fully restart.")
    async def slash_restart_upgrade(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send("⬆️ Upgrading everything and restarting…", ephemeral=True)
        await self._restart(interaction, "upgrade")

    # -----------------------------------------------------------------------
    # /shutdown  (owner-only)
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="shutdown",
        description="Disconnect from all voice channels and shut down the bot.",
    )
    async def slash_shutdown(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        if not await self._owner_check(interaction):
            return
        guild = interaction.guild
        if not guild:
            await interaction.followup.send("Guild only.", ephemeral=True)
            return
        await interaction.followup.send("👋 Shutting down…", ephemeral=True)
        try:
            await self.bot.cmd_shutdown(guild=guild, channel=interaction.channel)
        except exceptions.TerminateSignal:
            raise

    # -----------------------------------------------------------------------
    # /leaveserver  (owner-only)
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="leaveserver",
        description="Force the bot to leave a server by name or ID.",
    )
    @app_commands.describe(server="Server ID (preferred) or exact server name.")
    async def slash_leaveserver(self, interaction: discord.Interaction, server: str) -> None:
        await interaction.response.defer(ephemeral=True)
        if not await self._owner_check(interaction):
            return
        try:
            resp = await self.bot.cmd_leaveserver(
                ssd_=self._ssd(interaction),
                val=server,
                leftover_args=[],
            )
            await self._send(interaction, resp, ephemeral=True)
        except Exception as e:
            await self._err(interaction, e)

    # =======================================================================
    # BATCH 6  (final)
    # checkupdates, uptime, botlatency, latency, botversion, setcookies
    # Dev-only commands excluded: testready, breakpoint, objgraph, debug,
    #                             makemarkdown, makeini
    # =======================================================================

    # -----------------------------------------------------------------------
    # /checkupdates  (owner-only)
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="checkupdates",
        description="Check for MusicBot source code and dependency updates.",
    )
    async def slash_checkupdates(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        if not await self._owner_check(interaction):
            return
        try:
            resp = await self.bot.cmd_checkupdates(
                ssd_=self._ssd(interaction),
                channel=interaction.channel,
            )
            await self._send(interaction, resp, ephemeral=True)
        except Exception as e:
            await self._err(interaction, e)

    # -----------------------------------------------------------------------
    # /uptime
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="uptime",
        description="Show how long MusicBot has been online since last start.",
    )
    async def slash_uptime(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        if not await self._check_perms(interaction, "uptime"):
            return
        try:
            resp = await self.bot.cmd_uptime(ssd_=self._ssd(interaction))
            await self._send(interaction, resp)
        except Exception as e:
            await self._err(interaction, e)

    # -----------------------------------------------------------------------
    # /botlatency  (owner-only — all voice clients)
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="botlatency",
        description="Show API and voice client latency for all connected guilds.",
    )
    async def slash_botlatency(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        if not await self._owner_check(interaction):
            return
        try:
            resp = await self.bot.cmd_botlatency(ssd_=self._ssd(interaction))
            await self._send(interaction, resp, ephemeral=True)
        except Exception as e:
            await self._err(interaction, e)

    # -----------------------------------------------------------------------
    # /latency  (this guild only)
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="latency",
        description="Show API and voice latency for this server.",
    )
    async def slash_latency(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        if not await self._check_perms(interaction, "latency"):
            return
        try:
            guild = interaction.guild
            if not guild:
                await interaction.followup.send("Guild only.", ephemeral=True)
                return
            resp = await self.bot.cmd_latency(
                ssd_=self._ssd(interaction),
                guild=guild,
            )
            await self._send(interaction, resp)
        except Exception as e:
            await self._err(interaction, e)

    # -----------------------------------------------------------------------
    # /botversion
    # -----------------------------------------------------------------------

    @app_commands.command(
        name="botversion",
        description="Display the current MusicBot version.",
    )
    async def slash_botversion(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        if not await self._check_perms(interaction, "botversion"):
            return
        try:
            resp = await self.bot.cmd_botversion(ssd_=self._ssd(interaction))
            await self._send(interaction, resp, ephemeral=True)
        except Exception as e:
            await self._err(interaction, e)

    # -----------------------------------------------------------------------
    # /setcookies  (owner-only)
    # Original relies on message.attachments. Slash version accepts a
    # discord.Attachment directly and bypasses cmd_setcookies for uploads,
    # handling the file save inline. on/off subcommands call cmd_setcookies.
    # -----------------------------------------------------------------------

    setcookies = app_commands.Group(
        name="setcookies",
        description="Manage yt-dlp cookies. Owner only.",
        default_permissions=discord.Permissions(administrator=True),
    )

    @setcookies.command(name="on", description="Enable a previously uploaded cookies.txt.")
    async def slash_setcookies_on(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        if not await self._owner_check(interaction):
            return
        try:
            resp = await self.bot.cmd_setcookies(
                ssd_=self._ssd(interaction),
                message=None,
                opt="on",
            )
            await self._send(interaction, resp, ephemeral=True)
        except Exception as e:
            await self._err(interaction, e)

    @setcookies.command(name="off", description="Disable cookies without deleting the file.")
    async def slash_setcookies_off(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        if not await self._owner_check(interaction):
            return
        try:
            resp = await self.bot.cmd_setcookies(
                ssd_=self._ssd(interaction),
                message=None,
                opt="off",
            )
            await self._send(interaction, resp, ephemeral=True)
        except Exception as e:
            await self._err(interaction, e)

    @setcookies.command(
        name="upload",
        description="Upload a new cookies.txt file. WARNING: see /help setcookies for risks.",
    )
    @app_commands.describe(file="A cookies.txt file exported from your browser.")
    async def slash_setcookies_upload(
        self, interaction: discord.Interaction, file: discord.Attachment
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        if not await self._owner_check(interaction):
            return
        try:
            # Remove any existing disabled cookies file first.
            if self.bot.config.disabled_cookies_path.is_file():
                try:
                    self.bot.config.disabled_cookies_path.unlink()
                except OSError as e:
                    log.warning("Could not remove old disabled cookies file: %s", e)

            # Download and save the attachment to cookies_path.
            try:
                await file.save(self.bot.config.cookies_path)
            except discord.HTTPException as e:
                raise exceptions.CommandError(
                    "Error downloading the cookies file from Discord:  %(raw_error)s",
                    fmt_args={"raw_error": e},
                ) from e
            except OSError as e:
                raise exceptions.CommandError(
                    "Could not save cookies to disk:  %(raw_error)s",
                    fmt_args={"raw_error": e},
                ) from e

            if not self.bot.downloader.cookies_enabled:
                self.bot.downloader.enable_ytdl_cookies()

            from .i18n import _D
            await interaction.followup.send(
                _D("Cookies uploaded and enabled.", self._ssd(interaction)),
                ephemeral=True,
            )
        except Exception as e:
            await self._err(interaction, e)
