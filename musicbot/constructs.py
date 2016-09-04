import sys
import logging
import discord

from enum import Enum
from .utils import objdiff


class SkipState:
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
    def __init__(self, content, reply=False, delete_after=0):
        self.content = content
        self.reply = reply
        self.delete_after = delete_after

# Alright this is going to take some actual thinking through
class AnimatedResponse(Response):
    def __init__(self, content, *sequence, delete_after=0):
        super().__init__(content, delete_after=delete_after)




class VoiceStateUpdate:
    class Change(Enum):
        RESUME = 0
        JOIN = 1
        LEAVE = 2
        MUTE = 3
        UNMUTE = 4
        DEAFEN = 5
        UNDEAFEN = 6
        AFK = 7
        UNAFK = 8

        def __repr__(self):
            return self.name

    __slots__ = ['before', 'after', 'broken', 'joining', 'resuming', 'old_voice_channel', 'new_voice_channel']

    def __init__(self, before: discord.Member, after: discord.Member):
        self.before = before
        self.after = after

        self.broken = False
        self.resuming = None

        if not all([before, after]):
            self.broken = True
            return

        self.old_voice_channel = before.voice_channel
        self.new_voice_channel = after.voice_channel

        if before.voice_channel == self.voice_channel:
            self.joining = False
        elif after.voice_channel == self.voice_channel:
            self.joining = True
        else:
            self.joining = None

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
        return self.voice_channel == self.my_voice_channel

    @property
    def voice_channel(self) -> discord.Channel:
        return self.new_voice_channel or self.old_voice_channel

    @property
    def server(self) -> discord.Server:
        return self.after.server or self.before.server

    @property
    def member(self) -> discord.Member:
        return self.after or self.before

    def empty(self, *, excluding_me=True, excluding_deaf=False):
        def check(member):
            if excluding_me and member == self.me:
                return False

            if excluding_deaf and any([member.deaf, member.self_deaf]):
                return False

            return True

        return not sum(1 for m in self.voice_channel.voice_members if check(m))

    @property
    def raw_change(self):
        return objdiff(self.before.voice, self.after.voice, access_attr='__slots__')

    @property
    def change(self):
        changes = []
        rchange = self.raw_change

        if 'voice_channel' in rchange:
            changes.append(self.Change.JOIN if self.joining else self.Change.LEAVE)

        if self.resuming or self.joining is None:
            changes.append(self.Change.RESUME)

        if any(s in rchange for s in ['mute', 'self_mute']):
            m = rchange.get('mute', None) or rchange.get('self_mute')
            changes.append(self.Change.MUTE if m[1] else self.Change.UNMUTE)

        if any(s in rchange for s in ['deaf', 'self_deaf']):
            d = rchange.get('deaf', None) or rchange.get('self_deaf')
            changes.append(self.Change.DEAFEN if d[1] else self.Change.UNDEAFEN)

        if 'is_afk' in rchange:
            changes.append(self.Change.MUTE if rchange['is_afk'][1] else self.Change.UNMUTE)

        return changes


class Serializable:
    def serialize(self):
        raise NotImplementedError

    @classmethod
    def deserialize(cls, playlist, jsonstr):
        raise NotImplementedError
