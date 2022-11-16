"""
The MIT License (MIT)

Copyright (c) 2015-2021 Rapptz
Copyright (c) 2021-present Pycord Development

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, overload

from .partial_emoji import _EmojiTag
from .utils import _get_as_snowflake, get

if TYPE_CHECKING:
    from .abc import Snowflake
    from .emoji import Emoji
    from .guild import Guild
    from .partial_emoji import PartialEmoji
    from .types.welcome_screen import WelcomeScreen as WelcomeScreenPayload
    from .types.welcome_screen import (
        WelcomeScreenChannel as WelcomeScreenChannelPayload,
    )

__all__ = (
    "WelcomeScreen",
    "WelcomeScreenChannel",
)


class WelcomeScreenChannel:
    """Represents a welcome channel displayed on :class:`WelcomeScreen`

    .. versionadded:: 2.0

    Attributes
    ----------

    channel: :class:`abc.Snowflake`
        The channel that is being referenced.
    description: :class:`str`
        The description of the channel that is shown on the welcome screen.
    emoji: Union[:class:`Emoji`, :class:`PartialEmoji`, :class:`str`]
        The emoji of the channel that is shown on welcome screen.
    """

    def __init__(
        self,
        channel: Snowflake,
        description: str,
        emoji: Emoji | PartialEmoji | str,
    ):
        self.channel = channel
        self.description = description
        self.emoji = emoji

    def __repr__(self):
        return f"WelcomeScreenChannel(channel={self.channel} description={self.description})"

    def to_dict(self) -> WelcomeScreenChannelPayload:
        dict_: WelcomeScreenChannelPayload = {
            "channel_id": self.channel.id,
            "description": self.description,
            "emoji_id": None,
            "emoji_name": None,
        }

        if isinstance(self.emoji, _EmojiTag):
            # custom guild emoji
            dict_["emoji_id"] = self.emoji.id  # type: ignore
            dict_["emoji_name"] = self.emoji.name  # type: ignore
        else:
            # unicode emoji or None
            dict_["emoji_name"] = self.emoji
            dict_["emoji_id"] = None  # type: ignore

        return dict_

    @classmethod
    def _from_dict(
        cls, data: WelcomeScreenChannelPayload, guild: Guild
    ) -> WelcomeScreenChannel:
        channel_id = _get_as_snowflake(data, "channel_id")
        channel = guild.get_channel(channel_id)
        description = data.get("description")
        _emoji_id = _get_as_snowflake(data, "emoji_id")
        _emoji_name = data.get("emoji_name")

        emoji = get(guild.emojis, id=_emoji_id) if _emoji_id else _emoji_name
        return cls(channel=channel, description=description, emoji=emoji)  # type: ignore


class WelcomeScreen:
    """Represents the welcome screen of a guild.

    .. versionadded:: 2.0

    Attributes
    ----------

    description: :class:`str`
        The description text displayed on the welcome screen.
    welcome_channels: List[:class:`WelcomeScreenChannel`]
        A list of channels displayed on welcome screen.
    """

    def __init__(self, data: WelcomeScreenPayload, guild: Guild):
        self._guild = guild
        self._update(data)

    def __repr__(self):
        return f"<WelcomeScreen description={self.description} welcome_channels={self.welcome_channels}"

    def _update(self, data: WelcomeScreenPayload):
        self.description: str = data.get("description")
        self.welcome_channels: list[WelcomeScreenChannel] = [
            WelcomeScreenChannel._from_dict(channel, self._guild)
            for channel in data.get("welcome_channels", [])
        ]

    @property
    def enabled(self) -> bool:
        """:class:`bool`: Indicates whether the welcome screen is enabled or not."""
        return "WELCOME_SCREEN_ENABLED" in self._guild.features

    @property
    def guild(self) -> Guild:
        """:class:`Guild`: The guild this welcome screen belongs to."""
        return self._guild

    @overload
    async def edit(
        self,
        *,
        description: str | None = ...,
        welcome_channels: list[WelcomeScreenChannel] | None = ...,
        enabled: bool | None = ...,
        reason: str | None = ...,
    ) -> None:
        ...

    @overload
    async def edit(self) -> None:
        ...

    async def edit(self, **options):
        """|coro|

        Edits the welcome screen.

        You must have the :attr:`~Permissions.manage_guild` permission in the
        guild to do this.

        Parameters
        ----------

        description: Optional[:class:`str`]
            The new description of welcome screen.
        welcome_channels: Optional[List[:class:`WelcomeScreenChannel`]]
            The welcome channels. The order of the channels would be same as the passed list order.
        enabled: Optional[:class:`bool`]
            Whether the welcome screen should be displayed.
        reason: Optional[:class:`str`]
            The reason that shows up on Audit log.

        Raises
        ------

        HTTPException
            Editing the welcome screen failed somehow.
        Forbidden
            You don't have permissions to edit the welcome screen.
        NotFound
            This welcome screen does not exist.

        Example
        -------
        .. code-block:: python3

            rules_channel = guild.get_channel(12345678)
            announcements_channel = guild.get_channel(87654321)
            custom_emoji = utils.get(guild.emojis, name='loudspeaker')
            await welcome_screen.edit(
                description='This is a very cool community server!',
                welcome_channels=[
                    WelcomeChannel(channel=rules_channel, description='Read the rules!', emoji='👨‍🏫'),
                    WelcomeChannel(channel=announcements_channel, description='Watch out for announcements!',
                                   emoji=custom_emoji),
                ]
            )

        .. note::
            Welcome channels can only accept custom emojis if :attr:`~Guild.premium_tier` is level 2 or above.
        """

        welcome_channels = options.get("welcome_channels", [])
        welcome_channels_data = []

        for channel in welcome_channels:
            if not isinstance(channel, WelcomeScreenChannel):
                raise TypeError(
                    "welcome_channels parameter must be a list of WelcomeScreenChannel."
                )

            welcome_channels_data.append(channel.to_dict())

        options["welcome_channels"] = welcome_channels_data

        if options:
            new = await self._guild._state.http.edit_welcome_screen(
                self._guild.id, options, reason=options.get("reason")
            )
            self._update(new)

        return self
