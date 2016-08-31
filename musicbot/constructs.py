import sys
import discord

from .utils import objdiff
from logging import StreamHandler


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
    def __init__(self, before: discord.Member, after: discord.Member):
        self.before = before
        self.after = after

        self.broken = False

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

    def empty(self, *, excluding_me=True, excluding_deaf=False):
        def check(member):
            if excluding_me and member == self.me:
                return False

            if excluding_deaf and any([member.deaf, member.self_deaf]):
                return False

            return True

        return not sum(1 for m in self.voice_channel.voice_members if check(m))

    @property
    def change(self):
        return objdiff(self.before.voice, self.after.voice, access_attr='__slots__')


class Serializable:
    def serialize(self):
        raise NotImplementedError

    @classmethod
    def deserialize(cls, playlist, jsonstr):
        raise NotImplementedError


class SafeStreamHandler(StreamHandler):
    def __init__(self, stderr=False):
        super().__init__(sys.stderr if stderr else sys.stdout)

    def emit(self, record):
        try:
            msg = self.format(record)
            stream = self.stream.buffer
            stream.write(msg.encode('utf-8', 'replace'))
            stream.write(self.terminator.encode('utf-8'))
            self.flush()
        except Exception:
            self.handleError(record)
