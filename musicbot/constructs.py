import logging
import discord

from enum import Enum
from .utils import objdiff


class BetterLogRecord(logging.LogRecord):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.relativeCreated = round(self.relativeCreated, 5)


class SkipState:
    __slots__ = ['skippers', 'skip_msgs']

    def __init__(self):
        self.skippers = set()
        self.skip_msgs = set()

    @property
    def skip_count(self):
        return len(self.skippers)

    def reset(self):
        self.skippers.clear()
        self.skip_msgs.clear()

    def add_skipper(self, skipper, msg):
        self.skippers.add(skipper)
        self.skip_msgs.add(msg)
        return self.skip_count


class Response:
    # TODO: Add slots and make sure there isn't any random attr setting anywhere

    def __init__(self, content, reply=False, delete_after=0):
        self.content = content
        self.reply = reply
        self.delete_after = delete_after

# Alright this is going to take some actual thinking through
class AnimatedResponse(Response):
    def __init__(self, content, *sequence, delete_after=0):
        super().__init__(content, delete_after=delete_after)



class Serializable:
    def serialize(self):
        raise NotImplementedError

    @classmethod
    def deserialize(cls, playlist, jsonstr):
        raise NotImplementedError


class VoiceStateUpdate:
    class Change(Enum):
        RESUME     = 0   # Reconnect to an existing voice session
        JOIN       = 1   # User has joined the bot's voice channel
        LEAVE      = 2   # User has left the bot's voice channel
        MOVE       = 3   # User has moved voice channels on this server
        CONNECT    = 4   # User has connected to voice chat on this server
        DISCONNECT = 5   # User has disconnected from voice chat on this server
        MUTE       = 6   # User is now mute
        UNMUTE     = 7   # User is no longer mute
        DEAFEN     = 8   # User is now deaf
        UNDEAFEN   = 9   # User is no longer deaf
        AFK        = 10  # User has gone afk
        UNAFK      = 11  # User has come back from afk

        def __repr__(self):
            return self.name

    __slots__ = ['before', 'after', 'broken', 'resuming']

    def __init__(self, before: discord.Member, after: discord.Member):
        self.broken = False
        if not all([before, after]):
            self.broken = True
            return

        self.before = before
        self.after = after

        self.resuming = None

    @property
    def me(self) -> discord.Member:
        return self.after.server.me

    @property
    def is_about_me(self):
        return self.after == self.me

    @property
    def my_voice_channel(self) -> discord.Channel:
        return self.me.voice_channel

    @property
    def is_about_my_voice_channel(self):
        return any((
            self.joining,
            self.leaving,
            self.voice_channel == self.my_voice_channel
        ))

    @property
    def voice_channel(self) -> discord.Channel:
        return self.new_voice_channel or self.old_voice_channel

    @property
    def old_voice_channel(self) -> discord.Channel:
        return self.before.voice_channel

    @property
    def new_voice_channel(self) -> discord.Channel:
        return self.after.voice_channel

    @property
    def server(self) -> discord.Server:
        return self.after.server or self.before.server

    @property
    def member(self) -> discord.Member:
        return self.after or self.before

    @property
    def joining(self):
        return all((
            self.before.voice_channel != self.my_voice_channel,
            self.after.voice_channel == self.my_voice_channel
        ))

    @property
    def leaving(self):
        return all((
            self.before.voice_channel == self.my_voice_channel,
            self.after.voice_channel != self.my_voice_channel
        ))

    @property
    def moving(self):
        return all((
            self.before.voice_channel,
            self.after.voice_channel,
            self.before.voice_channel != self.after.voice_channel,
        ))

    @property
    def connecting(self):
        return all((
            not self.before.voice_channel or self.resuming,
            self.after.voice_channel
        ))

    @property
    def disconnecting(self):
        return all((
            self.before.voice_channel,
            not self.after.voice_channel
        ))

    def empty(self, *, excluding_me=True, excluding_deaf=False):
        def check(member):
            if excluding_me and member == self.me:
                return False

            if excluding_deaf and any([member.deaf, member.self_deaf]):
                return False

            return True

        return not sum(1 for m in self.voice_channel.voice_members if check(m))

    @property
    def raw_change(self) -> dict:
        return objdiff(self.before.voice, self.after.voice, access_attr='__slots__')

    @property
    def changes(self):
        changes = []
        rchange = self.raw_change

        if 'voice_channel' in rchange:
            if self.joining:
                changes.append(self.Change.JOIN)

            if self.leaving:
                changes.append(self.Change.LEAVE)

            if self.moving:
                changes.append(self.Change.MOVE)

        if self.resuming:
            changes.append(self.Change.RESUME)

        if self.connecting:
            changes.append(self.Change.CONNECT)

        elif self.disconnecting:
            changes.append(self.Change.DISCONNECT)

        if any(s in rchange for s in ['mute', 'self_mute']):
            m = rchange.get('mute', None) or rchange.get('self_mute')
            changes.append(self.Change.MUTE if m[1] else self.Change.UNMUTE)

        if any(s in rchange for s in ['deaf', 'self_deaf']):
            d = rchange.get('deaf', None) or rchange.get('self_deaf')
            changes.append(self.Change.DEAFEN if d[1] else self.Change.UNDEAFEN)

        if 'is_afk' in rchange:
            changes.append(self.Change.MUTE if rchange['is_afk'][1] else self.Change.UNMUTE)

        return changes
