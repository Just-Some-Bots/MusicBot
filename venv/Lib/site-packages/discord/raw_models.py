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
from typing import TYPE_CHECKING, List, Optional, Set

from .automod import AutoModAction
from .enums import ChannelType, try_enum

if TYPE_CHECKING:
    from .abc import MessageableChannel
    from .guild import Guild
    from .member import Member
    from .message import Message
    from .partial_emoji import PartialEmoji
    from .state import ConnectionState
    from .threads import Thread
    from .types.raw_models import (
        AutoModActionExecutionEvent as AutoModActionExecution,
        BulkMessageDeleteEvent,
        IntegrationDeleteEvent,
        MessageDeleteEvent,
        MessageUpdateEvent,
        ReactionActionEvent,
        ReactionClearEmojiEvent,
        ReactionClearEvent,
        ScheduledEventSubscription,
        ThreadDeleteEvent,
        TypingEvent,
    )


__all__ = (
    "RawMessageDeleteEvent",
    "RawBulkMessageDeleteEvent",
    "RawMessageUpdateEvent",
    "RawReactionActionEvent",
    "RawReactionClearEvent",
    "RawReactionClearEmojiEvent",
    "RawIntegrationDeleteEvent",
    "RawThreadDeleteEvent",
    "RawTypingEvent",
    "RawScheduledEventSubscription",
    "AutoModActionExecutionEvent",
)


class _RawReprMixin:
    def __repr__(self) -> str:
        value = " ".join(f"{attr}={getattr(self, attr)!r}" for attr in self.__slots__)
        return f"<{self.__class__.__name__} {value}>"


class RawMessageDeleteEvent(_RawReprMixin):
    """Represents the event payload for a :func:`on_raw_message_delete` event.

    Attributes
    ------------
    channel_id: :class:`int`
        The channel ID where the deletion took place.
    guild_id: Optional[:class:`int`]
        The guild ID where the deletion took place, if applicable.
    message_id: :class:`int`
        The message ID that got deleted.
    cached_message: Optional[:class:`Message`]
        The cached message, if found in the internal message cache.
    """

    __slots__ = ("message_id", "channel_id", "guild_id", "cached_message")

    def __init__(self, data: MessageDeleteEvent) -> None:
        self.message_id: int = int(data["id"])
        self.channel_id: int = int(data["channel_id"])
        self.cached_message: Optional[Message] = None
        try:
            self.guild_id: Optional[int] = int(data["guild_id"])
        except KeyError:
            self.guild_id: Optional[int] = None


class RawBulkMessageDeleteEvent(_RawReprMixin):
    """Represents the event payload for a :func:`on_raw_bulk_message_delete` event.

    Attributes
    -----------
    message_ids: Set[:class:`int`]
        A :class:`set` of the message IDs that were deleted.
    channel_id: :class:`int`
        The channel ID where the message got deleted.
    guild_id: Optional[:class:`int`]
        The guild ID where the message got deleted, if applicable.
    cached_messages: List[:class:`Message`]
        The cached messages, if found in the internal message cache.
    """

    __slots__ = ("message_ids", "channel_id", "guild_id", "cached_messages")

    def __init__(self, data: BulkMessageDeleteEvent) -> None:
        self.message_ids: Set[int] = {int(x) for x in data.get("ids", [])}
        self.channel_id: int = int(data["channel_id"])
        self.cached_messages: List[Message] = []

        try:
            self.guild_id: Optional[int] = int(data["guild_id"])
        except KeyError:
            self.guild_id: Optional[int] = None


class RawMessageUpdateEvent(_RawReprMixin):
    """Represents the payload for a :func:`on_raw_message_edit` event.

    Attributes
    -----------
    message_id: :class:`int`
        The message ID that got updated.
    channel_id: :class:`int`
        The channel ID where the update took place.

        .. versionadded:: 1.3
    guild_id: Optional[:class:`int`]
        The guild ID where the message got updated, if applicable.

        .. versionadded:: 1.7

    data: :class:`dict`
        The raw data given by the `gateway <https://discord.com/developers/docs/topics/gateway#message-update>`_
    cached_message: Optional[:class:`Message`]
        The cached message, if found in the internal message cache. Represents the message before
        it is modified by the data in :attr:`RawMessageUpdateEvent.data`.
    """

    __slots__ = ("message_id", "channel_id", "guild_id", "data", "cached_message")

    def __init__(self, data: MessageUpdateEvent) -> None:
        self.message_id: int = int(data["id"])
        self.channel_id: int = int(data["channel_id"])
        self.data: MessageUpdateEvent = data
        self.cached_message: Optional[Message] = None

        try:
            self.guild_id: Optional[int] = int(data["guild_id"])
        except KeyError:
            self.guild_id: Optional[int] = None


class RawReactionActionEvent(_RawReprMixin):
    """Represents the payload for a :func:`on_raw_reaction_add` or
    :func:`on_raw_reaction_remove` event.

    Attributes
    -----------
    message_id: :class:`int`
        The message ID that got or lost a reaction.
    user_id: :class:`int`
        The user ID who added the reaction or whose reaction was removed.
    channel_id: :class:`int`
        The channel ID where the reaction got added or removed.
    guild_id: Optional[:class:`int`]
        The guild ID where the reaction got added or removed, if applicable.
    emoji: :class:`PartialEmoji`
        The custom or unicode emoji being used.
    member: Optional[:class:`Member`]
        The member who added the reaction. Only available if `event_type` is `REACTION_ADD` and the reaction is inside a guild.

        .. versionadded:: 1.3

    event_type: :class:`str`
        The event type that triggered this action. Can be
        ``REACTION_ADD`` for reaction addition or
        ``REACTION_REMOVE`` for reaction removal.

        .. versionadded:: 1.3
    """

    __slots__ = (
        "message_id",
        "user_id",
        "channel_id",
        "guild_id",
        "emoji",
        "event_type",
        "member",
    )

    def __init__(self, data: ReactionActionEvent, emoji: PartialEmoji, event_type: str) -> None:
        self.message_id: int = int(data["message_id"])
        self.channel_id: int = int(data["channel_id"])
        self.user_id: int = int(data["user_id"])
        self.emoji: PartialEmoji = emoji
        self.event_type: str = event_type
        self.member: Optional[Member] = None

        try:
            self.guild_id: Optional[int] = int(data["guild_id"])
        except KeyError:
            self.guild_id: Optional[int] = None


class RawReactionClearEvent(_RawReprMixin):
    """Represents the payload for a :func:`on_raw_reaction_clear` event.

    Attributes
    -----------
    message_id: :class:`int`
        The message ID that got its reactions cleared.
    channel_id: :class:`int`
        The channel ID where the reactions got cleared.
    guild_id: Optional[:class:`int`]
        The guild ID where the reactions got cleared.
    """

    __slots__ = ("message_id", "channel_id", "guild_id")

    def __init__(self, data: ReactionClearEvent) -> None:
        self.message_id: int = int(data["message_id"])
        self.channel_id: int = int(data["channel_id"])

        try:
            self.guild_id: Optional[int] = int(data["guild_id"])
        except KeyError:
            self.guild_id: Optional[int] = None


class RawReactionClearEmojiEvent(_RawReprMixin):
    """Represents the payload for a :func:`on_raw_reaction_clear_emoji` event.

    .. versionadded:: 1.3

    Attributes
    -----------
    message_id: :class:`int`
        The message ID that got its reactions cleared.
    channel_id: :class:`int`
        The channel ID where the reactions got cleared.
    guild_id: Optional[:class:`int`]
        The guild ID where the reactions got cleared.
    emoji: :class:`PartialEmoji`
        The custom or unicode emoji being removed.
    """

    __slots__ = ("message_id", "channel_id", "guild_id", "emoji")

    def __init__(self, data: ReactionClearEmojiEvent, emoji: PartialEmoji) -> None:
        self.emoji: PartialEmoji = emoji
        self.message_id: int = int(data["message_id"])
        self.channel_id: int = int(data["channel_id"])

        try:
            self.guild_id: Optional[int] = int(data["guild_id"])
        except KeyError:
            self.guild_id: Optional[int] = None


class RawIntegrationDeleteEvent(_RawReprMixin):
    """Represents the payload for a :func:`on_raw_integration_delete` event.

    .. versionadded:: 2.0

    Attributes
    -----------
    integration_id: :class:`int`
        The ID of the integration that got deleted.
    application_id: Optional[:class:`int`]
        The ID of the bot/OAuth2 application for this deleted integration.
    guild_id: :class:`int`
        The guild ID where the integration got deleted.
    """

    __slots__ = ("integration_id", "application_id", "guild_id")

    def __init__(self, data: IntegrationDeleteEvent) -> None:
        self.integration_id: int = int(data["id"])
        self.guild_id: int = int(data["guild_id"])

        try:
            self.application_id: Optional[int] = int(data["application_id"])
        except KeyError:
            self.application_id: Optional[int] = None


class RawThreadDeleteEvent(_RawReprMixin):
    """Represents the payload for :func:`on_raw_thread_delete` event.

    .. versionadded:: 2.0

    Attributes
    ----------

    thread_id: :class:`int`
        The ID of the thread that was deleted.
    thread_type: :class:`discord.ChannelType`
        The channel type of the deleted thread.
    guild_id: :class:`int`
        The ID of the guild the deleted thread belonged to.
    parent_id: :class:`int`
        The ID of the channel the thread belonged to.
    thread: Optional[:class:`discord.Thread`]
        The thread that was deleted. This may be ``None`` if deleted thread is not found in internal cache.
    """

    __slots__ = ("thread_id", "thread_type", "guild_id", "parent_id", "thread")

    def __init__(self, data: ThreadDeleteEvent) -> None:
        self.thread_id: int = int(data["id"])
        self.thread_type: ChannelType = try_enum(ChannelType, int(data["type"]))
        self.guild_id: int = int(data["guild_id"])
        self.parent_id: int = int(data["parent_id"])
        self.thread: Optional[Thread] = None


class RawTypingEvent(_RawReprMixin):
    """Represents the payload for a :func:`on_raw_typing` event.

    .. versionadded:: 2.0

    Attributes
    -----------
    channel_id: :class:`int`
        The channel ID where the typing originated from.
    user_id: :class:`int`
        The ID of the user that started typing.
    when: :class:`datetime.datetime`
        When the typing started as an aware datetime in UTC.
    guild_id: Optional[:class:`int`]
        The guild ID where the typing originated from, if applicable.
    member: Optional[:class:`Member`]
        The member who started typing. Only available if the member started typing in a guild.
    """

    __slots__ = ("channel_id", "user_id", "when", "guild_id", "member")

    def __init__(self, data: TypingEvent) -> None:
        self.channel_id: int = int(data["channel_id"])
        self.user_id: int = int(data["user_id"])
        self.when: datetime.datetime = datetime.datetime.fromtimestamp(data.get("timestamp"), tz=datetime.timezone.utc)
        self.member: Optional[Member] = None

        try:
            self.guild_id: Optional[int] = int(data["guild_id"])
        except KeyError:
            self.guild_id: Optional[int] = None


class RawScheduledEventSubscription(_RawReprMixin):
    """Represents the payload for a :func:`raw_scheduled_event_user_add` or
    :func:`raw_scheduled_event_user_remove` event.

    .. versionadded:: 2.0

    Attributes
    -----------
    event_id: :class:`int`
        The event ID where the typing originated from.
    user_id: :class:`int`
        The ID of the user that subscribed/unsubscribed.
    guild: Optional[:class:`Guild`]
        The guild where the subscription/unsubscription happened.
    event_type: :class:`str`
        Can be either ``USER_ADD`` or ``USER_REMOVE`` depending on
        the event called.
    """

    __slots__ = ("event_id", "guild", "user_id", "event_type")

    def __init__(self, data: ScheduledEventSubscription, event_type: str):
        self.event_id: int = int(data["guild_scheduled_event_id"])
        self.user_id: int = int(data["user_id"])
        self.guild: Guild = None
        self.event_type: str = event_type


class AutoModActionExecutionEvent:
    """Represents the payload for a :func:`auto_moderation_action_execution`
    
    .. versionadded:: 2.0
    
    Attributes
    -----------
    action: :class:`AutoModAction`
        The action that was executed.
    rule_id: :class:`int`
        The ID of the rule that the action belongs to.
    guild_id: :class:`int`
        The ID of the guild that the action was executed in.
    guild: Optional[:class:`Guild`]
        The guild that the action was executed in, if cached.
    user_id: :class:`int`
        The ID of the user that triggered the action.
    member: Optional[:class:`Member`]
        The member that triggered the action, if cached.
    channel_id: Optional[:class:`int`]
        The ID of the channel in which the member's content was posted.
    channel: Optional[Union[:class:`TextChannel`, :class:`Thread`, :class:`VoiceChannel`]]
        The channel in which the member's content was posted, if cached.
    message_id: Optional[:class:`int`]
        The ID of the message that triggered the action. This is only available if the 
        message was not blocked.
    message: Optional[:class:`Message`]
        The message that triggered the action, if cached.
    alert_system_message_id: Optional[:class:`int`]
        The ID of the system auto moderation message that was posted as a result
        of the action. 
    alert_system_message: Optional[:class:`Message`]
        The system auto moderation message that was posted as a result of the action,
        if cached.
    content: :class:`str`
        The content of the message that triggered the action.
    matched_keyword: :class:`str`
        The word or phrase configured that was matched in the content.
    matched_content: :class:`str`
        The substring in the content that was matched.
    """

    __slots__ = (
        "action",
        "rule_id",
        "guild_id",
        "guild",
        "user_id",
        "member",
        "content",
        "matched_keyword",
        "matched_content",
        "channel_id",
        "channel",
        "message_id",
        "message",
        "alert_system_message_id",
        "alert_system_message",
    )

    def __init__(self, state: ConnectionState, data: AutoModActionExecution) -> None:
        self.action: AutoModAction = AutoModAction.from_dict(data["action"])
        self.rule_id: int = int(data["rule_id"])
        self.guild_id: int = int(data["guild_id"])
        self.guild: Optional[Guild] = state._get_guild(self.guild_id)
        self.user_id: int = int(data["user_id"])
        self.content: str = data["content"]
        self.matched_keyword: str = data["matched_keyword"]
        self.matched_content: str = data["matched_content"]
        
        if self.guild:
            self.member: Optional[Member] = self.guild.get_member(self.user_id)
        else:
            self.member: Optional[Member] = None
        
        try:
            # I don't see why this would be optional, but it's documented as such
            # so we should treat it that way
            self.channel_id: Optional[int] = int(data["channel_id"])
            self.channel: Optional[MessageableChannel] = self.guild.get_channel_or_thread(self.channel_id)
        except KeyError:
            self.channel_id: Optional[int] = None
            self.channel: Optional[MessageableChannel] = None
            
        try:
            self.message_id: Optional[int] = int(data["message_id"])
            self.message: Optional[Message] = state._get_message(self.message_id)
        except KeyError:
            self.message_id: Optional[int] = None
            self.message: Optional[Message] = None
            
        try:
            self.alert_system_message_id: Optional[int] = int(data["alert_system_message_id"])
            self.alert_system_message: Optional[Message] = state._get_message(self.alert_system_message_id)
        except KeyError:
            self.alert_system_message_id: Optional[int] = None
            self.alert_system_message: Optional[Message] = None
            
    def __repr__(self) -> str:
        return (
            f"<AutoModActionExecutionEvent action={self.action!r} "
            f"rule_id={self.rule_id!r} guild_id={self.guild_id!r} "
            f"user_id={self.user_id!r}>"
        )

