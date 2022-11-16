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

import datetime
from typing import TYPE_CHECKING, Any, Callable, Iterable, Mapping, TypeVar, overload

import discord.abc

from . import utils
from .asset import Asset
from .enums import (
    ChannelType,
    EmbeddedActivity,
    InviteTarget,
    StagePrivacyLevel,
    VideoQualityMode,
    VoiceRegion,
    try_enum,
)
from .errors import ClientException, InvalidArgument
from .file import File
from .flags import ChannelFlags
from .invite import Invite
from .iterators import ArchivedThreadIterator
from .mixins import Hashable
from .object import Object
from .permissions import PermissionOverwrite, Permissions
from .stage_instance import StageInstance
from .threads import Thread
from .utils import MISSING

__all__ = (
    "TextChannel",
    "VoiceChannel",
    "StageChannel",
    "DMChannel",
    "CategoryChannel",
    "GroupChannel",
    "PartialMessageable",
    "ForumChannel",
)

if TYPE_CHECKING:
    from .abc import Snowflake, SnowflakeTime
    from .guild import Guild
    from .guild import GuildChannel as GuildChannelType
    from .member import Member, VoiceState
    from .message import Message, PartialMessage
    from .role import Role
    from .state import ConnectionState
    from .types.channel import CategoryChannel as CategoryChannelPayload
    from .types.channel import DMChannel as DMChannelPayload
    from .types.channel import ForumChannel as ForumChannelPayload
    from .types.channel import GroupDMChannel as GroupChannelPayload
    from .types.channel import StageChannel as StageChannelPayload
    from .types.channel import TextChannel as TextChannelPayload
    from .types.channel import VoiceChannel as VoiceChannelPayload
    from .types.snowflake import SnowflakeList
    from .types.threads import ThreadArchiveDuration
    from .user import BaseUser, ClientUser, User
    from .webhook import Webhook


class _TextChannel(discord.abc.GuildChannel, Hashable):
    __slots__ = (
        "name",
        "id",
        "guild",
        "topic",
        "_state",
        "nsfw",
        "category_id",
        "position",
        "slowmode_delay",
        "_overwrites",
        "_type",
        "last_message_id",
        "default_auto_archive_duration",
        "flags",
    )

    def __init__(
        self,
        *,
        state: ConnectionState,
        guild: Guild,
        data: TextChannelPayload | ForumChannelPayload,
    ):
        self._state: ConnectionState = state
        self.id: int = int(data["id"])
        self._update(guild, data)

    @property
    def _repr_attrs(self) -> tuple[str, ...]:
        return "id", "name", "position", "nsfw", "category_id"

    def __repr__(self) -> str:
        attrs = [(val, getattr(self, val)) for val in self._repr_attrs]
        joined = " ".join("%s=%r" % t for t in attrs)
        return f"<{self.__class__.__name__} {joined}>"

    def _update(
        self, guild: Guild, data: TextChannelPayload | ForumChannelPayload
    ) -> None:
        # This data will always exist
        self.guild: Guild = guild
        self.name: str = data["name"]
        self.category_id: int | None = utils._get_as_snowflake(data, "parent_id")
        self._type: int = data["type"]

        # This data may be missing depending on how this object is being created/updated
        if not data.pop("_invoke_flag", False):
            self.topic: str | None = data.get("topic")
            self.position: int = data.get("position")
            self.nsfw: bool = data.get("nsfw", False)
            # Does this need coercion into `int`? No idea yet.
            self.slowmode_delay: int = data.get("rate_limit_per_user", 0)
            self.default_auto_archive_duration: ThreadArchiveDuration = data.get(
                "default_auto_archive_duration", 1440
            )
            self.last_message_id: int | None = utils._get_as_snowflake(
                data, "last_message_id"
            )
            self.flags: ChannelFlags = ChannelFlags._from_value(data.get("flags", 0))
            self._fill_overwrites(data)

    @property
    def type(self) -> ChannelType:
        """:class:`ChannelType`: The channel's Discord type."""
        return try_enum(ChannelType, self._type)

    @property
    def _sorting_bucket(self) -> int:
        return ChannelType.text.value

    @utils.copy_doc(discord.abc.GuildChannel.permissions_for)
    def permissions_for(self, obj: Member | Role, /) -> Permissions:
        base = super().permissions_for(obj)

        # text channels do not have voice related permissions
        denied = Permissions.voice()
        base.value &= ~denied.value
        return base

    @property
    def members(self) -> list[Member]:
        """List[:class:`Member`]: Returns all members that can see this channel."""
        return [m for m in self.guild.members if self.permissions_for(m).read_messages]

    @property
    def threads(self) -> list[Thread]:
        """List[:class:`Thread`]: Returns all the threads that you can see.

        .. versionadded:: 2.0
        """
        return [
            thread
            for thread in self.guild._threads.values()
            if thread.parent_id == self.id
        ]

    def is_nsfw(self) -> bool:
        """:class:`bool`: Checks if the channel is NSFW."""
        return self.nsfw

    @property
    def last_message(self) -> Message | None:
        """Fetches the last message from this channel in cache.

        The message might not be valid or point to an existing message.

        .. admonition:: Reliable Fetching
            :class: helpful

            For a slightly more reliable method of fetching the
            last message, consider using either :meth:`history`
            or :meth:`fetch_message` with the :attr:`last_message_id`
            attribute.

        Returns
        -------
        Optional[:class:`Message`]
            The last message in this channel or ``None`` if not found.
        """
        return (
            self._state._get_message(self.last_message_id)
            if self.last_message_id
            else None
        )

    @overload
    async def edit(
        self,
        *,
        reason: str | None = ...,
        name: str = ...,
        topic: str = ...,
        position: int = ...,
        nsfw: bool = ...,
        sync_permissions: bool = ...,
        category: CategoryChannel | None = ...,
        slowmode_delay: int = ...,
        default_auto_archive_duration: ThreadArchiveDuration = ...,
        type: ChannelType = ...,
        overwrites: Mapping[Role | Member | Snowflake, PermissionOverwrite] = ...,
    ) -> TextChannel | None:
        ...

    @overload
    async def edit(self) -> TextChannel | None:
        ...

    async def edit(self, *, reason=None, **options):
        """|coro|

        Edits the channel.

        You must have the :attr:`~Permissions.manage_channels` permission to
        use this.

        .. versionchanged:: 1.3
            The ``overwrites`` keyword-only parameter was added.

        .. versionchanged:: 1.4
            The ``type`` keyword-only parameter was added.

        .. versionchanged:: 2.0
            Edits are no longer in-place, the newly edited channel is returned instead.

        Parameters
        ----------
        name: :class:`str`
            The new channel name.
        topic: :class:`str`
            The new channel's topic.
        position: :class:`int`
            The new channel's position.
        nsfw: :class:`bool`
            To mark the channel as NSFW or not.
        sync_permissions: :class:`bool`
            Whether to sync permissions with the channel's new or pre-existing
            category. Defaults to ``False``.
        category: Optional[:class:`CategoryChannel`]
            The new category for this channel. Can be ``None`` to remove the
            category.
        slowmode_delay: :class:`int`
            Specifies the slowmode rate limit for user in this channel, in seconds.
            A value of `0` disables slowmode. The maximum value possible is `21600`.
        type: :class:`ChannelType`
            Change the type of this text channel. Currently, only conversion between
            :attr:`ChannelType.text` and :attr:`ChannelType.news` is supported. This
            is only available to guilds that contain ``NEWS`` in :attr:`Guild.features`.
        reason: Optional[:class:`str`]
            The reason for editing this channel. Shows up on the audit log.
        overwrites: Dict[Union[:class:`Role`, :class:`Member`, :class:`~discord.abc.Snowflake`], :class:`PermissionOverwrite`]
            The overwrites to apply to channel permissions. Useful for creating secret channels.
        default_auto_archive_duration: :class:`int`
            The new default auto archive duration in minutes for threads created in this channel.
            Must be one of ``60``, ``1440``, ``4320``, or ``10080``.

        Returns
        -------
        Optional[:class:`.TextChannel`]
            The newly edited text channel. If the edit was only positional
            then ``None`` is returned instead.

        Raises
        ------
        InvalidArgument
            If position is less than 0 or greater than the number of channels, or if
            the permission overwrite information is not in proper form.
        Forbidden
            You do not have permissions to edit the channel.
        HTTPException
            Editing the channel failed.
        """

        payload = await self._edit(options, reason=reason)
        if payload is not None:
            # the payload will always be the proper channel payload
            return self.__class__(state=self._state, guild=self.guild, data=payload)  # type: ignore

    @utils.copy_doc(discord.abc.GuildChannel.clone)
    async def clone(
        self, *, name: str | None = None, reason: str | None = None
    ) -> TextChannel:
        return await self._clone_impl(
            {
                "topic": self.topic,
                "nsfw": self.nsfw,
                "rate_limit_per_user": self.slowmode_delay,
            },
            name=name,
            reason=reason,
        )

    async def delete_messages(
        self, messages: Iterable[Snowflake], *, reason: str | None = None
    ) -> None:
        """|coro|

        Deletes a list of messages. This is similar to :meth:`Message.delete`
        except it bulk deletes multiple messages.

        As a special case, if the number of messages is 0, then nothing
        is done. If the number of messages is 1 then single message
        delete is done. If it's more than two, then bulk delete is used.

        You cannot bulk delete more than 100 messages or messages that
        are older than 14 days old.

        You must have the :attr:`~Permissions.manage_messages` permission to
        use this.

        Parameters
        ----------
        messages: Iterable[:class:`abc.Snowflake`]
            An iterable of messages denoting which ones to bulk delete.
        reason: Optional[:class:`str`]
            The reason for deleting the messages. Shows up on the audit log.

        Raises
        ------
        ClientException
            The number of messages to delete was more than 100.
        Forbidden
            You do not have proper permissions to delete the messages.
        NotFound
            If single delete, then the message was already deleted.
        HTTPException
            Deleting the messages failed.
        """
        if not isinstance(messages, (list, tuple)):
            messages = list(messages)

        if len(messages) == 0:
            return  # do nothing

        if len(messages) == 1:
            message_id: int = messages[0].id
            await self._state.http.delete_message(self.id, message_id, reason=reason)
            return

        if len(messages) > 100:
            raise ClientException("Can only bulk delete messages up to 100 messages")

        message_ids: SnowflakeList = [m.id for m in messages]
        await self._state.http.delete_messages(self.id, message_ids, reason=reason)

    async def purge(
        self,
        *,
        limit: int | None = 100,
        check: Callable[[Message], bool] = MISSING,
        before: SnowflakeTime | None = None,
        after: SnowflakeTime | None = None,
        around: SnowflakeTime | None = None,
        oldest_first: bool | None = False,
        bulk: bool = True,
        reason: str | None = None,
    ) -> list[Message]:
        """|coro|

        Purges a list of messages that meet the criteria given by the predicate
        ``check``. If a ``check`` is not provided then all messages are deleted
        without discrimination.

        You must have the :attr:`~Permissions.manage_messages` permission to
        delete messages even if they are your own.
        The :attr:`~Permissions.read_message_history` permission is
        also needed to retrieve message history.

        Parameters
        ----------
        limit: Optional[:class:`int`]
            The number of messages to search through. This is not the number
            of messages that will be deleted, though it can be.
        check: Callable[[:class:`Message`], :class:`bool`]
            The function used to check if a message should be deleted.
            It must take a :class:`Message` as its sole parameter.
        before: Optional[Union[:class:`abc.Snowflake`, :class:`datetime.datetime`]]
            Same as ``before`` in :meth:`history`.
        after: Optional[Union[:class:`abc.Snowflake`, :class:`datetime.datetime`]]
            Same as ``after`` in :meth:`history`.
        around: Optional[Union[:class:`abc.Snowflake`, :class:`datetime.datetime`]]
            Same as ``around`` in :meth:`history`.
        oldest_first: Optional[:class:`bool`]
            Same as ``oldest_first`` in :meth:`history`.
        bulk: :class:`bool`
            If ``True``, use bulk delete. Setting this to ``False`` is useful for mass-deleting
            a bot's own messages without :attr:`Permissions.manage_messages`. When ``True``, will
            fall back to single delete if messages are older than two weeks.
        reason: Optional[:class:`str`]
            The reason for deleting the messages. Shows up on the audit log.

        Returns
        -------
        List[:class:`.Message`]
            The list of messages that were deleted.

        Raises
        ------
        Forbidden
            You do not have proper permissions to do the actions required.
        HTTPException
            Purging the messages failed.

        Examples
        --------

        Deleting bot's messages ::

            def is_me(m):
                return m.author == client.user

            deleted = await channel.purge(limit=100, check=is_me)
            await channel.send(f'Deleted {len(deleted)} message(s)')
        """
        return await discord.abc._purge_messages_helper(
            self,
            limit=limit,
            check=check,
            before=before,
            after=after,
            around=around,
            oldest_first=oldest_first,
            bulk=bulk,
            reason=reason,
        )

    async def webhooks(self) -> list[Webhook]:
        """|coro|

        Gets the list of webhooks from this channel.

        Requires :attr:`~.Permissions.manage_webhooks` permissions.

        Returns
        -------
        List[:class:`Webhook`]
            The webhooks for this channel.

        Raises
        ------
        Forbidden
            You don't have permissions to get the webhooks.
        """

        from .webhook import Webhook

        data = await self._state.http.channel_webhooks(self.id)
        return [Webhook.from_state(d, state=self._state) for d in data]

    async def create_webhook(
        self, *, name: str, avatar: bytes | None = None, reason: str | None = None
    ) -> Webhook:
        """|coro|

        Creates a webhook for this channel.

        Requires :attr:`~.Permissions.manage_webhooks` permissions.

        .. versionchanged:: 1.1
            Added the ``reason`` keyword-only parameter.

        Parameters
        ----------
        name: :class:`str`
            The webhook's name.
        avatar: Optional[:class:`bytes`]
            A :term:`py:bytes-like object` representing the webhook's default avatar.
            This operates similarly to :meth:`~ClientUser.edit`.
        reason: Optional[:class:`str`]
            The reason for creating this webhook. Shows up in the audit logs.

        Returns
        -------
        :class:`Webhook`
            The created webhook.

        Raises
        ------
        HTTPException
            Creating the webhook failed.
        Forbidden
            You do not have permissions to create a webhook.
        """

        from .webhook import Webhook

        if avatar is not None:
            avatar = utils._bytes_to_base64_data(avatar)  # type: ignore

        data = await self._state.http.create_webhook(
            self.id, name=str(name), avatar=avatar, reason=reason
        )
        return Webhook.from_state(data, state=self._state)

    async def follow(
        self, *, destination: TextChannel, reason: str | None = None
    ) -> Webhook:
        """
        Follows a channel using a webhook.

        Only news channels can be followed.

        .. note::

            The webhook returned will not provide a token to do webhook
            actions, as Discord does not provide it.

        .. versionadded:: 1.3

        Parameters
        ----------
        destination: :class:`TextChannel`
            The channel you would like to follow from.
        reason: Optional[:class:`str`]
            The reason for following the channel. Shows up on the destination guild's audit log.

            .. versionadded:: 1.4

        Returns
        -------
        :class:`Webhook`
            The created webhook.

        Raises
        ------
        HTTPException
            Following the channel failed.
        Forbidden
            You do not have the permissions to create a webhook.
        """

        if not self.is_news():
            raise ClientException("The channel must be a news channel.")

        if not isinstance(destination, TextChannel):
            raise InvalidArgument(
                f"Expected TextChannel received {destination.__class__.__name__}"
            )

        from .webhook import Webhook

        data = await self._state.http.follow_webhook(
            self.id, webhook_channel_id=destination.id, reason=reason
        )
        return Webhook._as_follower(data, channel=destination, user=self._state.user)

    def get_partial_message(self, message_id: int, /) -> PartialMessage:
        """Creates a :class:`PartialMessage` from the message ID.

        This is useful if you want to work with a message and only have its ID without
        doing an unnecessary API call.

        .. versionadded:: 1.6

        Parameters
        ----------
        message_id: :class:`int`
            The message ID to create a partial message for.

        Returns
        -------
        :class:`PartialMessage`
            The partial message.
        """

        from .message import PartialMessage

        return PartialMessage(channel=self, id=message_id)

    def get_thread(self, thread_id: int, /) -> Thread | None:
        """Returns a thread with the given ID.

        .. versionadded:: 2.0

        Parameters
        ----------
        thread_id: :class:`int`
            The ID to search for.

        Returns
        -------
        Optional[:class:`Thread`]
            The returned thread or ``None`` if not found.
        """
        return self.guild.get_thread(thread_id)

    def archived_threads(
        self,
        *,
        private: bool = False,
        joined: bool = False,
        limit: int | None = 50,
        before: Snowflake | datetime.datetime | None = None,
    ) -> ArchivedThreadIterator:
        """Returns an :class:`~discord.AsyncIterator` that iterates over all archived threads in the guild.

        You must have :attr:`~Permissions.read_message_history` to use this. If iterating over private threads
        then :attr:`~Permissions.manage_threads` is also required.

        .. versionadded:: 2.0

        Parameters
        ----------
        limit: Optional[:class:`bool`]
            The number of threads to retrieve.
            If ``None``, retrieves every archived thread in the channel. Note, however,
            that this would make it a slow operation.
        before: Optional[Union[:class:`abc.Snowflake`, :class:`datetime.datetime`]]
            Retrieve archived channels before the given date or ID.
        private: :class:`bool`
            Whether to retrieve private archived threads.
        joined: :class:`bool`
            Whether to retrieve private archived threads that you've joined.
            You cannot set ``joined`` to ``True`` and ``private`` to ``False``.

        Yields
        ------
        :class:`Thread`
            The archived threads.

        Raises
        ------
        Forbidden
            You do not have permissions to get archived threads.
        HTTPException
            The request to get the archived threads failed.
        """
        return ArchivedThreadIterator(
            self.id,
            self.guild,
            limit=limit,
            joined=joined,
            private=private,
            before=before,
        )


class TextChannel(discord.abc.Messageable, _TextChannel):
    """Represents a Discord text channel.

    .. container:: operations

        .. describe:: x == y

            Checks if two channels are equal.

        .. describe:: x != y

            Checks if two channels are not equal.

        .. describe:: hash(x)

            Returns the channel's hash.

        .. describe:: str(x)

            Returns the channel's name.

    Attributes
    ----------
    name: :class:`str`
        The channel name.
    guild: :class:`Guild`
        The guild the channel belongs to.
    id: :class:`int`
        The channel ID.
    category_id: Optional[:class:`int`]
        The category channel ID this channel belongs to, if applicable.
    topic: Optional[:class:`str`]
        The channel's topic. ``None`` if it doesn't exist.
    position: Optional[:class:`int`]
        The position in the channel list. This is a number that starts at 0. e.g. the
        top channel is position 0. Can be ``None`` if the channel was received in an interaction.
    last_message_id: Optional[:class:`int`]
        The last message ID of the message sent to this channel. It may
        *not* point to an existing or valid message.
    slowmode_delay: :class:`int`
        The number of seconds a member must wait between sending messages
        in this channel. A value of `0` denotes that it is disabled.
        Bots and users with :attr:`~Permissions.manage_channels` or
        :attr:`~Permissions.manage_messages` bypass slowmode.
    nsfw: :class:`bool`
        If the channel is marked as "not safe for work".

        .. note::

            To check if the channel or the guild of that channel are marked as NSFW, consider :meth:`is_nsfw` instead.
    default_auto_archive_duration: :class:`int`
        The default auto archive duration in minutes for threads created in this channel.

        .. versionadded:: 2.0
    flags: :class:`ChannelFlags`
        Extra features of the channel.

        .. versionadded:: 2.0
    """

    def __init__(
        self, *, state: ConnectionState, guild: Guild, data: TextChannelPayload
    ):
        super().__init__(state=state, guild=guild, data=data)

    @property
    def _repr_attrs(self) -> tuple[str, ...]:
        return super()._repr_attrs + ("news",)

    def _update(self, guild: Guild, data: TextChannelPayload) -> None:
        super()._update(guild, data)

    async def _get_channel(self) -> "TextChannel":
        return self

    def is_news(self) -> bool:
        """:class:`bool`: Checks if the channel is a news/announcements channel."""
        return self._type == ChannelType.news.value

    @property
    def news(self) -> bool:
        """Equivalent to :meth:`is_news`."""
        return self.is_news()

    async def create_thread(
        self,
        *,
        name: str,
        message: Snowflake | None = None,
        auto_archive_duration: ThreadArchiveDuration = MISSING,
        type: ChannelType | None = None,
        reason: str | None = None,
    ) -> Thread:
        """|coro|

        Creates a thread in this text channel.

        To create a public thread, you must have :attr:`~discord.Permissions.create_public_threads`.
        For a private thread, :attr:`~discord.Permissions.create_private_threads` is needed instead.

        .. versionadded:: 2.0

        Parameters
        ----------
        name: :class:`str`
            The name of the thread.
        message: Optional[:class:`abc.Snowflake`]
            A snowflake representing the message to create the thread with.
            If ``None`` is passed then a private thread is created.
            Defaults to ``None``.
        auto_archive_duration: :class:`int`
            The duration in minutes before a thread is automatically archived for inactivity.
            If not provided, the channel's default auto archive duration is used.
        type: Optional[:class:`ChannelType`]
            The type of thread to create. If a ``message`` is passed then this parameter
            is ignored, as a thread created with a message is always a public thread.
            By default, this creates a private thread if this is ``None``.
        reason: :class:`str`
            The reason for creating a new thread. Shows up on the audit log.

        Returns
        -------
        :class:`Thread`
            The created thread

        Raises
        ------
        Forbidden
            You do not have permissions to create a thread.
        HTTPException
            Starting the thread failed.
        """

        if type is None:
            type = ChannelType.private_thread

        if message is None:
            data = await self._state.http.start_thread_without_message(
                self.id,
                name=name,
                auto_archive_duration=auto_archive_duration
                or self.default_auto_archive_duration,
                type=type.value,
                reason=reason,
            )
        else:
            data = await self._state.http.start_thread_with_message(
                self.id,
                message.id,
                name=name,
                auto_archive_duration=auto_archive_duration
                or self.default_auto_archive_duration,
                reason=reason,
            )

        return Thread(guild=self.guild, state=self._state, data=data)


class ForumChannel(_TextChannel):
    """Represents a Discord forum channel.

    .. container:: operations

        .. describe:: x == y

            Checks if two channels are equal.

        .. describe:: x != y

            Checks if two channels are not equal.

        .. describe:: hash(x)

            Returns the channel's hash.

        .. describe:: str(x)

            Returns the channel's name.

    Attributes
    ----------
    name: :class:`str`
        The channel name.
    guild: :class:`Guild`
        The guild the channel belongs to.
    id: :class:`int`
        The channel ID.
    category_id: Optional[:class:`int`]
        The category channel ID this channel belongs to, if applicable.
    topic: Optional[:class:`str`]
        The channel's topic. ``None`` if it doesn't exist.

        .. note::

            :attr:`guidelines` exists as an alternative to this attribute.
    position: Optional[:class:`int`]
        The position in the channel list. This is a number that starts at 0. e.g. the
        top channel is position 0. Can be ``None`` if the channel was received in an interaction.
    last_message_id: Optional[:class:`int`]
        The last message ID of the message sent to this channel. It may
        *not* point to an existing or valid message.
    slowmode_delay: :class:`int`
        The number of seconds a member must wait between sending messages
        in this channel. A value of `0` denotes that it is disabled.
        Bots and users with :attr:`~Permissions.manage_channels` or
        :attr:`~Permissions.manage_messages` bypass slowmode.
    nsfw: :class:`bool`
        If the channel is marked as "not safe for work".

        .. note::

            To check if the channel or the guild of that channel are marked as NSFW, consider :meth:`is_nsfw` instead.
    default_auto_archive_duration: :class:`int`
        The default auto archive duration in minutes for threads created in this channel.

        .. versionadded:: 2.0
    flags: :class:`ChannelFlags`
        Extra features of the channel.

        .. versionadded:: 2.0
    """

    def __init__(
        self, *, state: ConnectionState, guild: Guild, data: ForumChannelPayload
    ):
        super().__init__(state=state, guild=guild, data=data)

    def _update(self, guild: Guild, data: ForumChannelPayload) -> None:
        super()._update(guild, data)

    @property
    def guidelines(self) -> str | None:
        """Optional[:class:`str`]: The channel's guidelines. An alias of :attr:`topic`."""
        return self.topic

    async def create_thread(
        self,
        name: str,
        content=None,
        *,
        embed=None,
        embeds=None,
        file=None,
        files=None,
        stickers=None,
        delete_message_after=None,
        nonce=None,
        allowed_mentions=None,
        view=None,
        auto_archive_duration: ThreadArchiveDuration = MISSING,
        slowmode_delay: int = MISSING,
        reason: str | None = None,
    ) -> Thread:
        """|coro|

        Creates a thread in this forum channel.

        To create a public thread, you must have :attr:`~discord.Permissions.create_public_threads`.
        For a private thread, :attr:`~discord.Permissions.create_private_threads` is needed instead.

        .. versionadded:: 2.0

        Parameters
        ----------
        name: :class:`str`
            The name of the thread.
        content: :class:`str`
            The content of the message to send.
        embed: :class:`~discord.Embed`
            The rich embed for the content.
        embeds: List[:class:`~discord.Embed`]
            A list of embeds to upload. Must be a maximum of 10.
        file: :class:`~discord.File`
            The file to upload.
        files: List[:class:`~discord.File`]
            A list of files to upload. Must be a maximum of 10.
        stickers: Sequence[Union[:class:`~discord.GuildSticker`, :class:`~discord.StickerItem`]]
            A list of stickers to upload. Must be a maximum of 3.
        delete_message_after: :class:`int`
            The time to wait before deleting the thread.
        nonce: :class:`int`
            The nonce to use for sending this message. If the message was successfully sent,
            then the message will have a nonce with this value.
        allowed_mentions: :class:`~discord.AllowedMentions`
            Controls the mentions being processed in this message. If this is
            passed, then the object is merged with :attr:`~discord.Client.allowed_mentions`.
            The merging behaviour only overrides attributes that have been explicitly passed
            to the object, otherwise it uses the attributes set in :attr:`~discord.Client.allowed_mentions`.
            If no object is passed at all then the defaults given by :attr:`~discord.Client.allowed_mentions`
            are used instead.
        view: :class:`discord.ui.View`
            A Discord UI View to add to the message.
        auto_archive_duration: :class:`int`
            The duration in minutes before a thread is automatically archived for inactivity.
            If not provided, the channel's default auto archive duration is used.
        slowmode_delay: :class:`int`
            The number of seconds a member must wait between sending messages
            in the new thread. A value of `0` denotes that it is disabled.
            Bots and users with :attr:`~Permissions.manage_channels` or
            :attr:`~Permissions.manage_messages` bypass slowmode.
            If not provided, the forum channel's default slowmode is used.
        reason: :class:`str`
            The reason for creating a new thread. Shows up on the audit log.

        Returns
        -------
        :class:`Thread`
            The created thread

        Raises
        ------
        Forbidden
            You do not have permissions to create a thread.
        HTTPException
            Starting the thread failed.
        """
        state = self._state
        message_content = str(content) if content is not None else None

        if embed is not None and embeds is not None:
            raise InvalidArgument(
                "cannot pass both embed and embeds parameter to create_thread()"
            )

        if embed is not None:
            embed = embed.to_dict()

        elif embeds is not None:
            if len(embeds) > 10:
                raise InvalidArgument(
                    "embeds parameter must be a list of up to 10 elements"
                )
            embeds = [embed.to_dict() for embed in embeds]

        if stickers is not None:
            stickers = [sticker.id for sticker in stickers]

        if allowed_mentions is None:
            allowed_mentions = (
                state.allowed_mentions and state.allowed_mentions.to_dict()
            )
        elif state.allowed_mentions is not None:
            allowed_mentions = state.allowed_mentions.merge(allowed_mentions).to_dict()
        else:
            allowed_mentions = allowed_mentions.to_dict()

        if view:
            if not hasattr(view, "__discord_ui_view__"):
                raise InvalidArgument(
                    f"view parameter must be View not {view.__class__!r}"
                )

            components = view.to_components()
        else:
            components = None

        if file is not None and files is not None:
            raise InvalidArgument("cannot pass both file and files parameter to send()")

        if file is not None:
            if not isinstance(file, File):
                raise InvalidArgument("file parameter must be File")

            try:
                data = await state.http.send_files(
                    self.id,
                    files=[file],
                    allowed_mentions=allowed_mentions,
                    content=message_content,
                    embed=embed,
                    embeds=embeds,
                    nonce=nonce,
                    stickers=stickers,
                    components=components,
                )
            finally:
                file.close()

        elif files is not None:
            if len(files) > 10:
                raise InvalidArgument(
                    "files parameter must be a list of up to 10 elements"
                )
            elif not all(isinstance(file, File) for file in files):
                raise InvalidArgument("files parameter must be a list of File")

            try:
                data = await state.http.send_files(
                    self.id,
                    files=files,
                    content=message_content,
                    embed=embed,
                    embeds=embeds,
                    nonce=nonce,
                    allowed_mentions=allowed_mentions,
                    stickers=stickers,
                    components=components,
                )
            finally:
                for f in files:
                    f.close()
        else:
            data = await state.http.start_forum_thread(
                self.id,
                content=message_content,
                name=name,
                embed=embed,
                embeds=embeds,
                nonce=nonce,
                allowed_mentions=allowed_mentions,
                stickers=stickers,
                components=components,
                auto_archive_duration=auto_archive_duration
                or self.default_auto_archive_duration,
                rate_limit_per_user=slowmode_delay or self.slowmode_delay,
                reason=reason,
            )
        ret = Thread(guild=self.guild, state=self._state, data=data)
        msg = ret.get_partial_message(data["last_message_id"])
        if view:
            state.store_view(view, msg.id)

        if delete_message_after is not None:
            await msg.delete(delay=delete_message_after)
        return ret


class VocalGuildChannel(discord.abc.Connectable, discord.abc.GuildChannel, Hashable):
    __slots__ = (
        "name",
        "id",
        "guild",
        "bitrate",
        "user_limit",
        "_state",
        "position",
        "_overwrites",
        "category_id",
        "rtc_region",
        "video_quality_mode",
        "last_message_id",
        "flags",
    )

    def __init__(
        self,
        *,
        state: ConnectionState,
        guild: Guild,
        data: VoiceChannelPayload | StageChannelPayload,
    ):
        self._state: ConnectionState = state
        self.id: int = int(data["id"])
        self._update(guild, data)

    def _get_voice_client_key(self) -> tuple[int, str]:
        return self.guild.id, "guild_id"

    def _get_voice_state_pair(self) -> tuple[int, int]:
        return self.guild.id, self.id

    def _update(
        self, guild: Guild, data: VoiceChannelPayload | StageChannelPayload
    ) -> None:
        # This data will always exist
        self.guild = guild
        self.name: str = data["name"]
        self.category_id: int | None = utils._get_as_snowflake(data, "parent_id")

        # This data may be missing depending on how this object is being created/updated
        if not data.pop("_invoke_flag", False):
            rtc = data.get("rtc_region")
            self.rtc_region: VoiceRegion | None = (
                try_enum(VoiceRegion, rtc) if rtc is not None else None
            )
            self.video_quality_mode: VideoQualityMode = try_enum(
                VideoQualityMode, data.get("video_quality_mode", 1)
            )
            self.last_message_id: int | None = utils._get_as_snowflake(
                data, "last_message_id"
            )
            self.position: int = data.get("position")
            self.bitrate: int = data.get("bitrate")
            self.user_limit: int = data.get("user_limit")
            self.flags: ChannelFlags = ChannelFlags._from_value(data.get("flags", 0))
            self._fill_overwrites(data)

    @property
    def _sorting_bucket(self) -> int:
        return ChannelType.voice.value

    @property
    def members(self) -> list[Member]:
        """List[:class:`Member`]: Returns all members that are currently inside this voice channel."""
        ret = []
        for user_id, state in self.guild._voice_states.items():
            if state.channel and state.channel.id == self.id:
                member = self.guild.get_member(user_id)
                if member is not None:
                    ret.append(member)
        return ret

    @property
    def voice_states(self) -> dict[int, VoiceState]:
        """Returns a mapping of member IDs who have voice states in this channel.

        .. versionadded:: 1.3

        .. note::

            This function is intentionally low level to replace :attr:`members`
            when the member cache is unavailable.

        Returns
        -------
        Mapping[:class:`int`, :class:`VoiceState`]
            The mapping of member ID to a voice state.
        """
        return {
            key: value
            for key, value in self.guild._voice_states.items()
            if value.channel and value.channel.id == self.id
        }

    @utils.copy_doc(discord.abc.GuildChannel.permissions_for)
    def permissions_for(self, obj: Member | Role, /) -> Permissions:
        base = super().permissions_for(obj)

        # Voice channels cannot be edited by people who can't connect to them.
        # It also implicitly denies all other voice perms
        if not base.connect:
            denied = Permissions.voice()
            denied.update(manage_channels=True, manage_roles=True)
            base.value &= ~denied.value
        return base


class VoiceChannel(discord.abc.Messageable, VocalGuildChannel):
    """Represents a Discord guild voice channel.

    .. container:: operations

        .. describe:: x == y

            Checks if two channels are equal.

        .. describe:: x != y

            Checks if two channels are not equal.

        .. describe:: hash(x)

            Returns the channel's hash.

        .. describe:: str(x)

            Returns the channel's name.

    Attributes
    ----------
    name: :class:`str`
        The channel name.
    guild: :class:`Guild`
        The guild the channel belongs to.
    id: :class:`int`
        The channel ID.
    category_id: Optional[:class:`int`]
        The category channel ID this channel belongs to, if applicable.
    position: Optional[:class:`int`]
        The position in the channel list. This is a number that starts at 0. e.g. the
        top channel is position 0. Can be ``None`` if the channel was received in an interaction.
    bitrate: :class:`int`
        The channel's preferred audio bitrate in bits per second.
    user_limit: :class:`int`
        The channel's limit for number of members that can be in a voice channel.
    rtc_region: Optional[:class:`VoiceRegion`]
        The region for the voice channel's voice communication.
        A value of ``None`` indicates automatic voice region detection.

        .. versionadded:: 1.7
    video_quality_mode: :class:`VideoQualityMode`
        The camera video quality for the voice channel's participants.

        .. versionadded:: 2.0
    last_message_id: Optional[:class:`int`]
        The ID of the last message sent to this channel. It may not always point to an existing or valid message.

        .. versionadded:: 2.0
    flags: :class:`ChannelFlags`
        Extra features of the channel.

        .. versionadded:: 2.0
    """

    __slots__ = "nsfw"

    def _update(self, guild: Guild, data: VoiceChannelPayload):
        super()._update(guild, data)
        self.nsfw: bool = data.get("nsfw", False)

    def __repr__(self) -> str:
        attrs = [
            ("id", self.id),
            ("name", self.name),
            ("rtc_region", self.rtc_region),
            ("position", self.position),
            ("bitrate", self.bitrate),
            ("video_quality_mode", self.video_quality_mode),
            ("user_limit", self.user_limit),
            ("category_id", self.category_id),
        ]
        joined = " ".join("%s=%r" % t for t in attrs)
        return f"<{self.__class__.__name__} {joined}>"

    async def _get_channel(self):
        return self

    def is_nsfw(self) -> bool:
        """:class:`bool`: Checks if the channel is NSFW."""
        return self.nsfw

    @property
    def last_message(self) -> Message | None:
        """Fetches the last message from this channel in cache.

        The message might not be valid or point to an existing message.

        .. admonition:: Reliable Fetching
            :class: helpful

            For a slightly more reliable method of fetching the
            last message, consider using either :meth:`history`
            or :meth:`fetch_message` with the :attr:`last_message_id`
            attribute.

        Returns
        -------
        Optional[:class:`Message`]
            The last message in this channel or ``None`` if not found.
        """
        return (
            self._state._get_message(self.last_message_id)
            if self.last_message_id
            else None
        )

    def get_partial_message(self, message_id: int, /) -> PartialMessage:
        """Creates a :class:`PartialMessage` from the message ID.

        This is useful if you want to work with a message and only have its ID without
        doing an unnecessary API call.

        .. versionadded:: 1.6

        Parameters
        ----------
        message_id: :class:`int`
            The message ID to create a partial message for.

        Returns
        -------
        :class:`PartialMessage`
            The partial message.
        """

        from .message import PartialMessage

        return PartialMessage(channel=self, id=message_id)

    async def delete_messages(
        self, messages: Iterable[Snowflake], *, reason: str | None = None
    ) -> None:
        """|coro|

        Deletes a list of messages. This is similar to :meth:`Message.delete`
        except it bulk deletes multiple messages.

        As a special case, if the number of messages is 0, then nothing
        is done. If the number of messages is 1 then single message
        delete is done. If it's more than two, then bulk delete is used.

        You cannot bulk delete more than 100 messages or messages that
        are older than 14 days old.

        You must have the :attr:`~Permissions.manage_messages` permission to
        use this.

        Parameters
        ----------
        messages: Iterable[:class:`abc.Snowflake`]
            An iterable of messages denoting which ones to bulk delete.
        reason: Optional[:class:`str`]
            The reason for deleting the messages. Shows up on the audit log.

        Raises
        ------
        ClientException
            The number of messages to delete was more than 100.
        Forbidden
            You do not have proper permissions to delete the messages.
        NotFound
            If single delete, then the message was already deleted.
        HTTPException
            Deleting the messages failed.
        """
        if not isinstance(messages, (list, tuple)):
            messages = list(messages)

        if len(messages) == 0:
            return  # do nothing

        if len(messages) == 1:
            message_id: int = messages[0].id
            await self._state.http.delete_message(self.id, message_id, reason=reason)
            return

        if len(messages) > 100:
            raise ClientException("Can only bulk delete messages up to 100 messages")

        message_ids: SnowflakeList = [m.id for m in messages]
        await self._state.http.delete_messages(self.id, message_ids, reason=reason)

    async def purge(
        self,
        *,
        limit: int | None = 100,
        check: Callable[[Message], bool] = MISSING,
        before: SnowflakeTime | None = None,
        after: SnowflakeTime | None = None,
        around: SnowflakeTime | None = None,
        oldest_first: bool | None = False,
        bulk: bool = True,
        reason: str | None = None,
    ) -> list[Message]:
        """|coro|

        Purges a list of messages that meet the criteria given by the predicate
        ``check``. If a ``check`` is not provided then all messages are deleted
        without discrimination.

        You must have the :attr:`~Permissions.manage_messages` permission to
        delete messages even if they are your own.
        The :attr:`~Permissions.read_message_history` permission is
        also needed to retrieve message history.

        Parameters
        ----------
        limit: Optional[:class:`int`]
            The number of messages to search through. This is not the number
            of messages that will be deleted, though it can be.
        check: Callable[[:class:`Message`], :class:`bool`]
            The function used to check if a message should be deleted.
            It must take a :class:`Message` as its sole parameter.
        before: Optional[Union[:class:`abc.Snowflake`, :class:`datetime.datetime`]]
            Same as ``before`` in :meth:`history`.
        after: Optional[Union[:class:`abc.Snowflake`, :class:`datetime.datetime`]]
            Same as ``after`` in :meth:`history`.
        around: Optional[Union[:class:`abc.Snowflake`, :class:`datetime.datetime`]]
            Same as ``around`` in :meth:`history`.
        oldest_first: Optional[:class:`bool`]
            Same as ``oldest_first`` in :meth:`history`.
        bulk: :class:`bool`
            If ``True``, use bulk delete. Setting this to ``False`` is useful for mass-deleting
            a bot's own messages without :attr:`Permissions.manage_messages`. When ``True``, will
            fall back to single delete if messages are older than two weeks.
        reason: Optional[:class:`str`]
            The reason for deleting the messages. Shows up on the audit log.

        Returns
        -------
        List[:class:`.Message`]
            The list of messages that were deleted.

        Raises
        ------
        Forbidden
            You do not have proper permissions to do the actions required.
        HTTPException
            Purging the messages failed.

        Examples
        --------

        Deleting bot's messages ::

            def is_me(m):
                return m.author == client.user

            deleted = await channel.purge(limit=100, check=is_me)
            await channel.send(f'Deleted {len(deleted)} message(s)')
        """
        return await discord.abc._purge_messages_helper(
            self,
            limit=limit,
            check=check,
            before=before,
            after=after,
            around=around,
            oldest_first=oldest_first,
            bulk=bulk,
            reason=reason,
        )

    async def webhooks(self) -> list[Webhook]:
        """|coro|

        Gets the list of webhooks from this channel.

        Requires :attr:`~.Permissions.manage_webhooks` permissions.

        Returns
        -------
        List[:class:`Webhook`]
            The webhooks for this channel.

        Raises
        ------
        Forbidden
            You don't have permissions to get the webhooks.
        """

        from .webhook import Webhook

        data = await self._state.http.channel_webhooks(self.id)
        return [Webhook.from_state(d, state=self._state) for d in data]

    async def create_webhook(
        self, *, name: str, avatar: bytes | None = None, reason: str | None = None
    ) -> Webhook:
        """|coro|

        Creates a webhook for this channel.

        Requires :attr:`~.Permissions.manage_webhooks` permissions.

        .. versionchanged:: 1.1
            Added the ``reason`` keyword-only parameter.

        Parameters
        ----------
        name: :class:`str`
            The webhook's name.
        avatar: Optional[:class:`bytes`]
            A :term:`py:bytes-like object` representing the webhook's default avatar.
            This operates similarly to :meth:`~ClientUser.edit`.
        reason: Optional[:class:`str`]
            The reason for creating this webhook. Shows up in the audit logs.

        Returns
        -------
        :class:`Webhook`
            The created webhook.

        Raises
        ------
        HTTPException
            Creating the webhook failed.
        Forbidden
            You do not have permissions to create a webhook.
        """

        from .webhook import Webhook

        if avatar is not None:
            avatar = utils._bytes_to_base64_data(avatar)  # type: ignore

        data = await self._state.http.create_webhook(
            self.id, name=str(name), avatar=avatar, reason=reason
        )
        return Webhook.from_state(data, state=self._state)

    @property
    def type(self) -> ChannelType:
        """:class:`ChannelType`: The channel's Discord type."""
        return ChannelType.voice

    @utils.copy_doc(discord.abc.GuildChannel.clone)
    async def clone(
        self, *, name: str | None = None, reason: str | None = None
    ) -> VoiceChannel:
        return await self._clone_impl(
            {"bitrate": self.bitrate, "user_limit": self.user_limit},
            name=name,
            reason=reason,
        )

    @overload
    async def edit(
        self,
        *,
        name: str = ...,
        bitrate: int = ...,
        user_limit: int = ...,
        position: int = ...,
        sync_permissions: int = ...,
        category: CategoryChannel | None = ...,
        overwrites: Mapping[Role | Member, PermissionOverwrite] = ...,
        rtc_region: VoiceRegion | None = ...,
        video_quality_mode: VideoQualityMode = ...,
        reason: str | None = ...,
    ) -> VoiceChannel | None:
        ...

    @overload
    async def edit(self) -> VoiceChannel | None:
        ...

    async def edit(self, *, reason=None, **options):
        """|coro|

        Edits the channel.

        You must have the :attr:`~Permissions.manage_channels` permission to
        use this.

        .. versionchanged:: 1.3
            The ``overwrites`` keyword-only parameter was added.

        .. versionchanged:: 2.0
            Edits are no longer in-place, the newly edited channel is returned instead.

        Parameters
        ----------
        name: :class:`str`
            The new channel's name.
        bitrate: :class:`int`
            The new channel's bitrate.
        user_limit: :class:`int`
            The new channel's user limit.
        position: :class:`int`
            The new channel's position.
        sync_permissions: :class:`bool`
            Whether to sync permissions with the channel's new or pre-existing
            category. Defaults to ``False``.
        category: Optional[:class:`CategoryChannel`]
            The new category for this channel. Can be ``None`` to remove the
            category.
        reason: Optional[:class:`str`]
            The reason for editing this channel. Shows up on the audit log.
        overwrites: Dict[Union[:class:`Role`, :class:`Member`, :class:`~discord.abc.Snowflake`], :class:`PermissionOverwrite`]
            The overwrites to apply to channel permissions. Useful for creating secret channels.
        rtc_region: Optional[:class:`VoiceRegion`]
            The new region for the voice channel's voice communication.
            A value of ``None`` indicates automatic voice region detection.

            .. versionadded:: 1.7
        video_quality_mode: :class:`VideoQualityMode`
            The camera video quality for the voice channel's participants.

            .. versionadded:: 2.0

        Returns
        -------
        Optional[:class:`.VoiceChannel`]
            The newly edited voice channel. If the edit was only positional
            then ``None`` is returned instead.

        Raises
        ------
        InvalidArgument
            If the permission overwrite information is not in proper form.
        Forbidden
            You do not have permissions to edit the channel.
        HTTPException
            Editing the channel failed.
        """

        payload = await self._edit(options, reason=reason)
        if payload is not None:
            # the payload will always be the proper channel payload
            return self.__class__(state=self._state, guild=self.guild, data=payload)  # type: ignore

    async def create_activity_invite(
        self, activity: EmbeddedActivity | int, **kwargs
    ) -> Invite:
        """|coro|

        A shortcut method that creates an instant activity invite.

        You must have the :attr:`~discord.Permissions.start_embedded_activities` permission to
        do this.

        Parameters
        ----------
        activity: Union[:class:`discord.EmbeddedActivity`, :class:`int`]
            The activity to create an invite for which can be an application id as well.
        max_age: :class:`int`
            How long the invite should last in seconds. If it's 0 then the invite
            doesn't expire. Defaults to ``0``.
        max_uses: :class:`int`
            How many uses the invite could be used for. If it's 0 then there
            are unlimited uses. Defaults to ``0``.
        temporary: :class:`bool`
            Denotes that the invite grants temporary membership
            (i.e. they get kicked after they disconnect). Defaults to ``False``.
        unique: :class:`bool`
            Indicates if a unique invite URL should be created. Defaults to True.
            If this is set to ``False`` then it will return a previously created
            invite.
        reason: Optional[:class:`str`]
            The reason for creating this invite. Shows up on the audit log.

        Returns
        -------
        :class:`~discord.Invite`
            The invite that was created.

        Raises
        ------
        TypeError
            If the activity is not a valid activity or application id.
        ~discord.HTTPException
            Invite creation failed.
        """

        if isinstance(activity, EmbeddedActivity):
            activity = activity.value

        elif not isinstance(activity, int):
            raise TypeError("Invalid type provided for the activity.")

        return await self.create_invite(
            target_type=InviteTarget.embedded_application,
            target_application_id=activity,
            **kwargs,
        )


class StageChannel(VocalGuildChannel):
    """Represents a Discord guild stage channel.

    .. versionadded:: 1.7

    .. container:: operations

        .. describe:: x == y

            Checks if two channels are equal.

        .. describe:: x != y

            Checks if two channels are not equal.

        .. describe:: hash(x)

            Returns the channel's hash.

        .. describe:: str(x)

            Returns the channel's name.

    Attributes
    ----------
    name: :class:`str`
        The channel name.
    guild: :class:`Guild`
        The guild the channel belongs to.
    id: :class:`int`
        The channel ID.
    topic: Optional[:class:`str`]
        The channel's topic. ``None`` if it isn't set.
    category_id: Optional[:class:`int`]
        The category channel ID this channel belongs to, if applicable.
    position: Optional[:class:`int`]
        The position in the channel list. This is a number that starts at 0. e.g. the
        top channel is position 0. Can be ``None`` if the channel was received in an interaction.
    bitrate: :class:`int`
        The channel's preferred audio bitrate in bits per second.
    user_limit: :class:`int`
        The channel's limit for number of members that can be in a stage channel.
    rtc_region: Optional[:class:`VoiceRegion`]
        The region for the stage channel's voice communication.
        A value of ``None`` indicates automatic voice region detection.
    video_quality_mode: :class:`VideoQualityMode`
        The camera video quality for the stage channel's participants.

        .. versionadded:: 2.0
    flags: :class:`ChannelFlags`
        Extra features of the channel.

        .. versionadded:: 2.0
    """

    __slots__ = ("topic",)

    def __repr__(self) -> str:
        attrs = [
            ("id", self.id),
            ("name", self.name),
            ("topic", self.topic),
            ("rtc_region", self.rtc_region),
            ("position", self.position),
            ("bitrate", self.bitrate),
            ("video_quality_mode", self.video_quality_mode),
            ("user_limit", self.user_limit),
            ("category_id", self.category_id),
        ]
        joined = " ".join("%s=%r" % t for t in attrs)
        return f"<{self.__class__.__name__} {joined}>"

    def _update(self, guild: Guild, data: StageChannelPayload) -> None:
        super()._update(guild, data)
        self.topic = data.get("topic")

    @property
    def requesting_to_speak(self) -> list[Member]:
        """List[:class:`Member`]: A list of members who are requesting to speak in the stage channel."""
        return [
            member
            for member in self.members
            if member.voice and member.voice.requested_to_speak_at is not None
        ]

    @property
    def speakers(self) -> list[Member]:
        """List[:class:`Member`]: A list of members who have been permitted to speak in the stage channel.

        .. versionadded:: 2.0
        """
        return [
            member
            for member in self.members
            if member.voice
            and not member.voice.suppress
            and member.voice.requested_to_speak_at is None
        ]

    @property
    def listeners(self) -> list[Member]:
        """List[:class:`Member`]: A list of members who are listening in the stage channel.

        .. versionadded:: 2.0
        """
        return [
            member for member in self.members if member.voice and member.voice.suppress
        ]

    @property
    def moderators(self) -> list[Member]:
        """List[:class:`Member`]: A list of members who are moderating the stage channel.

        .. versionadded:: 2.0
        """
        required_permissions = Permissions.stage_moderator()
        return [
            member
            for member in self.members
            if self.permissions_for(member) >= required_permissions
        ]

    @property
    def type(self) -> ChannelType:
        """:class:`ChannelType`: The channel's Discord type."""
        return ChannelType.stage_voice

    @utils.copy_doc(discord.abc.GuildChannel.clone)
    async def clone(
        self, *, name: str | None = None, reason: str | None = None
    ) -> StageChannel:
        return await self._clone_impl({}, name=name, reason=reason)

    @property
    def instance(self) -> StageInstance | None:
        """Optional[:class:`StageInstance`]: The running stage instance of the stage channel.

        .. versionadded:: 2.0
        """
        return utils.get(self.guild.stage_instances, channel_id=self.id)

    async def create_instance(
        self,
        *,
        topic: str,
        privacy_level: StagePrivacyLevel = MISSING,
        reason: str | None = None,
        send_notification: bool | None = False,
    ) -> StageInstance:
        """|coro|

        Create a stage instance.

        You must have the :attr:`~Permissions.manage_channels` permission to
        use this.

        .. versionadded:: 2.0

        Parameters
        ----------
        topic: :class:`str`
            The stage instance's topic.
        privacy_level: :class:`StagePrivacyLevel`
            The stage instance's privacy level. Defaults to :attr:`StagePrivacyLevel.guild_only`.
        reason: :class:`str`
            The reason the stage instance was created. Shows up on the audit log.
        send_notification: :class:`bool`
            Send a notification to everyone in the server that the stage instance has started.
            Defaults to ``False``. Requires the ``mention_everyone`` permission.

        Returns
        -------
        :class:`StageInstance`
            The newly created stage instance.

        Raises
        ------
        InvalidArgument
            If the ``privacy_level`` parameter is not the proper type.
        Forbidden
            You do not have permissions to create a stage instance.
        HTTPException
            Creating a stage instance failed.
        """

        payload: dict[str, Any] = {
            "channel_id": self.id,
            "topic": topic,
            "send_start_notification": send_notification,
        }

        if privacy_level is not MISSING:
            if not isinstance(privacy_level, StagePrivacyLevel):
                raise InvalidArgument(
                    "privacy_level field must be of type PrivacyLevel"
                )

            payload["privacy_level"] = privacy_level.value

        data = await self._state.http.create_stage_instance(**payload, reason=reason)
        return StageInstance(guild=self.guild, state=self._state, data=data)

    async def fetch_instance(self) -> StageInstance:
        """|coro|

        Gets the running :class:`StageInstance`.

        .. versionadded:: 2.0

        Returns
        -------
        :class:`StageInstance`
            The stage instance.

        Raises
        ------
        NotFound
            The stage instance or channel could not be found.
        HTTPException
            Getting the stage instance failed.
        """
        data = await self._state.http.get_stage_instance(self.id)
        return StageInstance(guild=self.guild, state=self._state, data=data)

    @overload
    async def edit(
        self,
        *,
        name: str = ...,
        topic: str | None = ...,
        position: int = ...,
        sync_permissions: int = ...,
        category: CategoryChannel | None = ...,
        overwrites: Mapping[Role | Member, PermissionOverwrite] = ...,
        rtc_region: VoiceRegion | None = ...,
        video_quality_mode: VideoQualityMode = ...,
        reason: str | None = ...,
    ) -> StageChannel | None:
        ...

    @overload
    async def edit(self) -> StageChannel | None:
        ...

    async def edit(self, *, reason=None, **options):
        """|coro|

        Edits the channel.

        You must have the :attr:`~Permissions.manage_channels` permission to
        use this.

        .. versionchanged:: 2.0
            The ``topic`` parameter must now be set via :attr:`create_instance`.

        .. versionchanged:: 2.0
            Edits are no longer in-place, the newly edited channel is returned instead.

        Parameters
        ----------
        name: :class:`str`
            The new channel's name.
        position: :class:`int`
            The new channel's position.
        sync_permissions: :class:`bool`
            Whether to sync permissions with the channel's new or pre-existing
            category. Defaults to ``False``.
        category: Optional[:class:`CategoryChannel`]
            The new category for this channel. Can be ``None`` to remove the
            category.
        reason: Optional[:class:`str`]
            The reason for editing this channel. Shows up on the audit log.
        overwrites: Dict[Union[:class:`Role`, :class:`Member`, :class:`~discord.abc.Snowflake`], :class:`PermissionOverwrite`]
            The overwrites to apply to channel permissions. Useful for creating secret channels.
        rtc_region: Optional[:class:`VoiceRegion`]
            The new region for the stage channel's voice communication.
            A value of ``None`` indicates automatic voice region detection.
        video_quality_mode: :class:`VideoQualityMode`
            The camera video quality for the stage channel's participants.

            .. versionadded:: 2.0

        Returns
        -------
        Optional[:class:`.StageChannel`]
            The newly edited stage channel. If the edit was only positional
            then ``None`` is returned instead.

        Raises
        ------
        InvalidArgument
            If the permission overwrite information is not in proper form.
        Forbidden
            You do not have permissions to edit the channel.
        HTTPException
            Editing the channel failed.
        """

        payload = await self._edit(options, reason=reason)
        if payload is not None:
            # the payload will always be the proper channel payload
            return self.__class__(state=self._state, guild=self.guild, data=payload)  # type: ignore


class CategoryChannel(discord.abc.GuildChannel, Hashable):
    """Represents a Discord channel category.

    These are useful to group channels to logical compartments.

    .. container:: operations

        .. describe:: x == y

            Checks if two channels are equal.

        .. describe:: x != y

            Checks if two channels are not equal.

        .. describe:: hash(x)

            Returns the category's hash.

        .. describe:: str(x)

            Returns the category's name.

    Attributes
    ----------
    name: :class:`str`
        The category name.
    guild: :class:`Guild`
        The guild the category belongs to.
    id: :class:`int`
        The category channel ID.
    position: Optional[:class:`int`]
        The position in the category list. This is a number that starts at 0. e.g. the
        top category is position 0. Can be ``None`` if the channel was received in an interaction.
    nsfw: :class:`bool`
        If the channel is marked as "not safe for work".

        .. note::

            To check if the channel or the guild of that channel are marked as NSFW, consider :meth:`is_nsfw` instead.
    flags: :class:`ChannelFlags`
        Extra features of the channel.

        .. versionadded:: 2.0
    """

    __slots__ = (
        "name",
        "id",
        "guild",
        "nsfw",
        "_state",
        "position",
        "_overwrites",
        "category_id",
        "flags",
    )

    def __init__(
        self, *, state: ConnectionState, guild: Guild, data: CategoryChannelPayload
    ):
        self._state: ConnectionState = state
        self.id: int = int(data["id"])
        self._update(guild, data)

    def __repr__(self) -> str:
        return f"<CategoryChannel id={self.id} name={self.name!r} position={self.position} nsfw={self.nsfw}>"

    def _update(self, guild: Guild, data: CategoryChannelPayload) -> None:
        # This data will always exist
        self.guild: Guild = guild
        self.name: str = data["name"]
        self.category_id: int | None = utils._get_as_snowflake(data, "parent_id")

        # This data may be missing depending on how this object is being created/updated
        if not data.pop("_invoke_flag", False):
            self.nsfw: bool = data.get("nsfw", False)
            self.position: int = data.get("position")
            self.flags: ChannelFlags = ChannelFlags._from_value(data.get("flags", 0))
            self._fill_overwrites(data)

    @property
    def _sorting_bucket(self) -> int:
        return ChannelType.category.value

    @property
    def type(self) -> ChannelType:
        """:class:`ChannelType`: The channel's Discord type."""
        return ChannelType.category

    def is_nsfw(self) -> bool:
        """:class:`bool`: Checks if the category is NSFW."""
        return self.nsfw

    @utils.copy_doc(discord.abc.GuildChannel.clone)
    async def clone(
        self, *, name: str | None = None, reason: str | None = None
    ) -> CategoryChannel:
        return await self._clone_impl({"nsfw": self.nsfw}, name=name, reason=reason)

    @overload
    async def edit(
        self,
        *,
        name: str = ...,
        position: int = ...,
        nsfw: bool = ...,
        overwrites: Mapping[Role | Member, PermissionOverwrite] = ...,
        reason: str | None = ...,
    ) -> CategoryChannel | None:
        ...

    @overload
    async def edit(self) -> CategoryChannel | None:
        ...

    async def edit(self, *, reason=None, **options):
        """|coro|

        Edits the channel.

        You must have the :attr:`~Permissions.manage_channels` permission to
        use this.

        .. versionchanged:: 1.3
            The ``overwrites`` keyword-only parameter was added.

        .. versionchanged:: 2.0
            Edits are no longer in-place, the newly edited channel is returned instead.

        Parameters
        ----------
        name: :class:`str`
            The new category's name.
        position: :class:`int`
            The new category's position.
        nsfw: :class:`bool`
            To mark the category as NSFW or not.
        reason: Optional[:class:`str`]
            The reason for editing this category. Shows up on the audit log.
        overwrites: Dict[Union[:class:`Role`, :class:`Member`, :class:`~discord.abc.Snowflake`], :class:`PermissionOverwrite`]
            The overwrites to apply to channel permissions. Useful for creating secret channels.

        Returns
        -------
        Optional[:class:`.CategoryChannel`]
            The newly edited category channel. If the edit was only positional
            then ``None`` is returned instead.

        Raises
        ------
        InvalidArgument
            If position is less than 0 or greater than the number of categories.
        Forbidden
            You do not have permissions to edit the category.
        HTTPException
            Editing the category failed.
        """

        payload = await self._edit(options, reason=reason)
        if payload is not None:
            # the payload will always be the proper channel payload
            return self.__class__(state=self._state, guild=self.guild, data=payload)  # type: ignore

    @utils.copy_doc(discord.abc.GuildChannel.move)
    async def move(self, **kwargs):
        kwargs.pop("category", None)
        await super().move(**kwargs)

    @property
    def channels(self) -> list[GuildChannelType]:
        """List[:class:`abc.GuildChannel`]: Returns the channels that are under this category.

        These are sorted by the official Discord UI, which places voice channels below the text channels.
        """

        def comparator(channel):
            return not isinstance(channel, _TextChannel), (channel.position or -1)

        ret = [c for c in self.guild.channels if c.category_id == self.id]
        ret.sort(key=comparator)
        return ret

    @property
    def text_channels(self) -> list[TextChannel]:
        """List[:class:`TextChannel`]: Returns the text channels that are under this category."""
        ret = [
            c
            for c in self.guild.channels
            if c.category_id == self.id and isinstance(c, TextChannel)
        ]
        ret.sort(key=lambda c: (c.position or -1, c.id))
        return ret

    @property
    def voice_channels(self) -> list[VoiceChannel]:
        """List[:class:`VoiceChannel`]: Returns the voice channels that are under this category."""
        ret = [
            c
            for c in self.guild.channels
            if c.category_id == self.id and isinstance(c, VoiceChannel)
        ]
        ret.sort(key=lambda c: (c.position or -1, c.id))
        return ret

    @property
    def stage_channels(self) -> list[StageChannel]:
        """List[:class:`StageChannel`]: Returns the stage channels that are under this category.

        .. versionadded:: 1.7
        """
        ret = [
            c
            for c in self.guild.channels
            if c.category_id == self.id and isinstance(c, StageChannel)
        ]
        ret.sort(key=lambda c: (c.position or -1, c.id))
        return ret

    @property
    def forum_channels(self) -> list[ForumChannel]:
        """List[:class:`ForumChannel`]: Returns the forum channels that are under this category.

        .. versionadded:: 2.0
        """
        ret = [
            c
            for c in self.guild.channels
            if c.category_id == self.id and isinstance(c, ForumChannel)
        ]
        ret.sort(key=lambda c: (c.position or -1, c.id))
        return ret

    async def create_text_channel(self, name: str, **options: Any) -> TextChannel:
        """|coro|

        A shortcut method to :meth:`Guild.create_text_channel` to create a :class:`TextChannel` in the category.

        Returns
        -------
        :class:`TextChannel`
            The channel that was just created.
        """
        return await self.guild.create_text_channel(name, category=self, **options)

    async def create_voice_channel(self, name: str, **options: Any) -> VoiceChannel:
        """|coro|

        A shortcut method to :meth:`Guild.create_voice_channel` to create a :class:`VoiceChannel` in the category.

        Returns
        -------
        :class:`VoiceChannel`
            The channel that was just created.
        """
        return await self.guild.create_voice_channel(name, category=self, **options)

    async def create_stage_channel(self, name: str, **options: Any) -> StageChannel:
        """|coro|

        A shortcut method to :meth:`Guild.create_stage_channel` to create a :class:`StageChannel` in the category.

        .. versionadded:: 1.7

        Returns
        -------
        :class:`StageChannel`
            The channel that was just created.
        """
        return await self.guild.create_stage_channel(name, category=self, **options)

    async def create_forum_channel(self, name: str, **options: Any) -> ForumChannel:
        """|coro|

        A shortcut method to :meth:`Guild.create_forum_channel` to create a :class:`ForumChannel` in the category.

        .. versionadded:: 2.0

        Returns
        -------
        :class:`ForumChannel`
            The channel that was just created.
        """
        return await self.guild.create_forum_channel(name, category=self, **options)


DMC = TypeVar("DMC", bound="DMChannel")


class DMChannel(discord.abc.Messageable, Hashable):
    """Represents a Discord direct message channel.

    .. container:: operations

        .. describe:: x == y

            Checks if two channels are equal.

        .. describe:: x != y

            Checks if two channels are not equal.

        .. describe:: hash(x)

            Returns the channel's hash.

        .. describe:: str(x)

            Returns a string representation of the channel

    Attributes
    ----------
    recipient: Optional[:class:`User`]
        The user you are participating with in the direct message channel.
        If this channel is received through the gateway, the recipient information
        may not be always available.
    me: :class:`ClientUser`
        The user presenting yourself.
    id: :class:`int`
        The direct message channel ID.
    """

    __slots__ = ("id", "recipient", "me", "_state")

    def __init__(
        self, *, me: ClientUser, state: ConnectionState, data: DMChannelPayload
    ):
        self._state: ConnectionState = state
        self.recipient: User | None = state.store_user(data["recipients"][0])
        self.me: ClientUser = me
        self.id: int = int(data["id"])

    async def _get_channel(self):
        return self

    def __str__(self) -> str:
        if self.recipient:
            return f"Direct Message with {self.recipient}"
        return "Direct Message with Unknown User"

    def __repr__(self) -> str:
        return f"<DMChannel id={self.id} recipient={self.recipient!r}>"

    @classmethod
    def _from_message(cls: type[DMC], state: ConnectionState, channel_id: int) -> DMC:
        self: DMC = cls.__new__(cls)
        self._state = state
        self.id = channel_id
        self.recipient = None
        # state.user won't be None here
        self.me = state.user  # type: ignore
        return self

    @property
    def type(self) -> ChannelType:
        """:class:`ChannelType`: The channel's Discord type."""
        return ChannelType.private

    @property
    def jump_url(self) -> str:
        """:class:`str`: Returns a URL that allows the client to jump to the channel.

        .. versionadded:: 2.0
        """
        return f"https://discord.com/channels/@me/{self.id}"

    @property
    def created_at(self) -> datetime.datetime:
        """:class:`datetime.datetime`: Returns the direct message channel's creation time in UTC."""
        return utils.snowflake_time(self.id)

    def permissions_for(self, obj: Any = None, /) -> Permissions:
        """Handles permission resolution for a :class:`User`.

        This function is there for compatibility with other channel types.

        Actual direct messages do not really have the concept of permissions.

        This returns all the Text related permissions set to ``True`` except:

        - :attr:`~Permissions.send_tts_messages`: You cannot send TTS messages in a DM.
        - :attr:`~Permissions.manage_messages`: You cannot delete others messages in a DM.

        Parameters
        ----------
        obj: :class:`User`
            The user to check permissions for. This parameter is ignored
            but kept for compatibility with other ``permissions_for`` methods.

        Returns
        -------
        :class:`Permissions`
            The resolved permissions.
        """

        base = Permissions.text()
        base.read_messages = True
        base.send_tts_messages = False
        base.manage_messages = False
        return base

    def get_partial_message(self, message_id: int, /) -> PartialMessage:
        """Creates a :class:`PartialMessage` from the message ID.

        This is useful if you want to work with a message and only have its ID without
        doing an unnecessary API call.

        .. versionadded:: 1.6

        Parameters
        ----------
        message_id: :class:`int`
            The message ID to create a partial message for.

        Returns
        -------
        :class:`PartialMessage`
            The partial message.
        """

        from .message import PartialMessage

        return PartialMessage(channel=self, id=message_id)


class GroupChannel(discord.abc.Messageable, Hashable):
    """Represents a Discord group channel.

    .. container:: operations

        .. describe:: x == y

            Checks if two channels are equal.

        .. describe:: x != y

            Checks if two channels are not equal.

        .. describe:: hash(x)

            Returns the channel's hash.

        .. describe:: str(x)

            Returns a string representation of the channel

    Attributes
    ----------
    recipients: List[:class:`User`]
        The users you are participating with in the group channel.
    me: :class:`ClientUser`
        The user presenting yourself.
    id: :class:`int`
        The group channel ID.
    owner: Optional[:class:`User`]
        The user that owns the group channel.
    owner_id: :class:`int`
        The owner ID that owns the group channel.

        .. versionadded:: 2.0
    name: Optional[:class:`str`]
        The group channel's name if provided.
    """

    __slots__ = (
        "id",
        "recipients",
        "owner_id",
        "owner",
        "_icon",
        "name",
        "me",
        "_state",
    )

    def __init__(
        self, *, me: ClientUser, state: ConnectionState, data: GroupChannelPayload
    ):
        self._state: ConnectionState = state
        self.id: int = int(data["id"])
        self.me: ClientUser = me
        self._update_group(data)

    def _update_group(self, data: GroupChannelPayload) -> None:
        self.owner_id: int | None = utils._get_as_snowflake(data, "owner_id")
        self._icon: str | None = data.get("icon")
        self.name: str | None = data.get("name")
        self.recipients: list[User] = [
            self._state.store_user(u) for u in data.get("recipients", [])
        ]

        self.owner: BaseUser | None
        if self.owner_id == self.me.id:
            self.owner = self.me
        else:
            self.owner = utils.find(lambda u: u.id == self.owner_id, self.recipients)

    async def _get_channel(self):
        return self

    def __str__(self) -> str:
        if self.name:
            return self.name

        if len(self.recipients) == 0:
            return "Unnamed"

        return ", ".join(map(lambda x: x.name, self.recipients))

    def __repr__(self) -> str:
        return f"<GroupChannel id={self.id} name={self.name!r}>"

    @property
    def type(self) -> ChannelType:
        """:class:`ChannelType`: The channel's Discord type."""
        return ChannelType.group

    @property
    def icon(self) -> Asset | None:
        """Optional[:class:`Asset`]: Returns the channel's icon asset if available."""
        if self._icon is None:
            return None
        return Asset._from_icon(self._state, self.id, self._icon, path="channel")

    @property
    def created_at(self) -> datetime.datetime:
        """:class:`datetime.datetime`: Returns the channel's creation time in UTC."""
        return utils.snowflake_time(self.id)

    @property
    def jump_url(self) -> str:
        """:class:`str`: Returns a URL that allows the client to jump to the channel.

        .. versionadded:: 2.0
        """
        return f"https://discord.com/channels/@me/{self.id}"

    def permissions_for(self, obj: Snowflake, /) -> Permissions:
        """Handles permission resolution for a :class:`User`.

        This function is there for compatibility with other channel types.

        Actual direct messages do not really have the concept of permissions.

        This returns all the Text related permissions set to ``True`` except:

        - :attr:`~Permissions.send_tts_messages`: You cannot send TTS messages in a DM.
        - :attr:`~Permissions.manage_messages`: You cannot delete others messages in a DM.

        This also checks the kick_members permission if the user is the owner.

        Parameters
        ----------
        obj: :class:`~discord.abc.Snowflake`
            The user to check permissions for.

        Returns
        -------
        :class:`Permissions`
            The resolved permissions for the user.
        """

        base = Permissions.text()
        base.read_messages = True
        base.send_tts_messages = False
        base.manage_messages = False
        base.mention_everyone = True

        if obj.id == self.owner_id:
            base.kick_members = True

        return base

    async def leave(self) -> None:
        """|coro|

        Leave the group.

        If you are the only one in the group, this deletes it as well.

        Raises
        ------
        HTTPException
            Leaving the group failed.
        """

        await self._state.http.leave_group(self.id)


class PartialMessageable(discord.abc.Messageable, Hashable):
    """Represents a partial messageable to aid with working messageable channels when
    only a channel ID are present.

    The only way to construct this class is through :meth:`Client.get_partial_messageable`.

    Note that this class is trimmed down and has no rich attributes.

    .. versionadded:: 2.0

    .. container:: operations

        .. describe:: x == y

            Checks if two partial messageables are equal.

        .. describe:: x != y

            Checks if two partial messageables are not equal.

        .. describe:: hash(x)

            Returns the partial messageable's hash.

    Attributes
    ----------
    id: :class:`int`
        The channel ID associated with this partial messageable.
    type: Optional[:class:`ChannelType`]
        The channel type associated with this partial messageable, if given.
    """

    def __init__(
        self, state: ConnectionState, id: int, type: ChannelType | None = None
    ):
        self._state: ConnectionState = state
        self._channel: Object = Object(id=id)
        self.id: int = id
        self.type: ChannelType | None = type

    async def _get_channel(self) -> Object:
        return self._channel

    def get_partial_message(self, message_id: int, /) -> PartialMessage:
        """Creates a :class:`PartialMessage` from the message ID.

        This is useful if you want to work with a message and only have its ID without
        doing an unnecessary API call.

        Parameters
        ----------
        message_id: :class:`int`
            The message ID to create a partial message for.

        Returns
        -------
        :class:`PartialMessage`
            The partial message.
        """

        from .message import PartialMessage

        return PartialMessage(channel=self, id=message_id)


def _guild_channel_factory(channel_type: int):
    value = try_enum(ChannelType, channel_type)
    if value is ChannelType.text:
        return TextChannel, value
    elif value is ChannelType.voice:
        return VoiceChannel, value
    elif value is ChannelType.category:
        return CategoryChannel, value
    elif value is ChannelType.news:
        return TextChannel, value
    elif value is ChannelType.stage_voice:
        return StageChannel, value
    elif value is ChannelType.forum:
        return ForumChannel, value
    else:
        return None, value


def _channel_factory(channel_type: int):
    cls, value = _guild_channel_factory(channel_type)
    if value is ChannelType.private:
        return DMChannel, value
    elif value is ChannelType.group:
        return GroupChannel, value
    else:
        return cls, value


def _threaded_channel_factory(channel_type: int):
    cls, value = _channel_factory(channel_type)
    if value in (
        ChannelType.private_thread,
        ChannelType.public_thread,
        ChannelType.news_thread,
    ):
        return Thread, value
    return cls, value


def _threaded_guild_channel_factory(channel_type: int):
    cls, value = _guild_channel_factory(channel_type)
    if value in (
        ChannelType.private_thread,
        ChannelType.public_thread,
        ChannelType.news_thread,
    ):
        return Thread, value
    return cls, value
