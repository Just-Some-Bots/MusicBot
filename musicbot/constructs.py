import json
import pydoc
import inspect
import logging

import discord

from enum import Enum
from discord.ext.commands.bot import _get_variable
from .utils import objdiff

log = logging.getLogger(__name__)

class BetterLogRecord(logging.LogRecord):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.relativeCreated /= 1000


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
    __slots__ = ['_content', 'reply', 'delete_after', 'codeblock', '_codeblock']

    def __init__(self, content, reply=False, delete_after=0, codeblock=None):
        self._content = content
        self.reply = reply
        self.delete_after = delete_after
        self.codeblock = codeblock
        self._codeblock = "```{!s}\n{{}}\n```".format('' if codeblock is True else codeblock)

    @property
    def content(self):
        if self.codeblock:
            return self._codeblock.format(self._content)
        else:
            return self._content

# Alright this is going to take some actual thinking through
class AnimatedResponse(Response):
    def __init__(self, content, *sequence, delete_after=0):
        super().__init__(content, delete_after=delete_after)
        self.sequence = sequence


class Serializer(json.JSONEncoder):
    def default(self, o):
        if hasattr(o, '__json__'):
            return o.__json__()

        return super().default(o)

    @classmethod
    def deserialize(cls, data):
        if all(x in data for x in Serializable._class_signature):
            # log.debug("Deserialization requested for %s", data)
            factory = pydoc.locate(data['__module__'] + '.' + data['__class__'])
            # log.debug("Found object %s", factory)
            if factory and issubclass(factory, Serializable):
                # log.debug("Deserializing %s object", factory)
                return factory._deserialize(data['data'], **cls._get_vars(factory._deserialize))

        return data

    @classmethod
    def _get_vars(cls, func):
        # log.debug("Getting vars for %s", func)
        params = inspect.signature(func).parameters.copy()
        args = {}
        # log.debug("Got %s", params)

        for name, param in params.items():
            # log.debug("Checking arg %s, type %s", name, param.kind)
            if param.kind is param.POSITIONAL_OR_KEYWORD and param.default is None:
                # log.debug("Using var %s", name)
                args[name] = _get_variable(name)
                # log.debug("Collected var for arg '%s': %s", name, args[name])

        return args


class Serializable:
    _class_signature = ('__class__', '__module__', 'data')

    def _enclose_json(self, data):
        return {
            '__class__': self.__class__.__qualname__,
            '__module__': self.__module__,
            'data': data
        }

    # Perhaps convert this into some sort of decorator
    @staticmethod
    def _bad(arg):
        raise TypeError('Argument "%s" must not be None' % arg)

    def serialize(self, *, cls=Serializer, **kwargs):
        return json.dumps(self, cls=cls, **kwargs)

    def __json__(self):
        raise NotImplementedError

    @classmethod
    def _deserialize(cls, raw_json, **kwargs):
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

    __slots__ = ['before', 'after', 'broken']

    def __init__(self, before: discord.Member, after: discord.Member):
        self.broken = False
        if not all([before, after]):
            self.broken = True
            return

        self.before = before
        self.after = after

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
        return all((
            self.my_voice_channel,
            any((
                self.new_voice_channel == self.my_voice_channel,
                self.old_voice_channel == self.my_voice_channel
            ))
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
            self.my_voice_channel,
            self.before.voice_channel != self.my_voice_channel,
            self.after.voice_channel == self.my_voice_channel
        ))

    @property
    def leaving(self):
        return all((
            self.my_voice_channel,
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

    @property
    def resuming(self):
        return all((
            not self.joining,
            self.is_about_me,
            not self.server.voice_client,
            not self.raw_change
        ))

    def empty(self, *, excluding_me=True, excluding_deaf=False, old_channel=False):
        def check(member):
            if excluding_me and member == self.me:
                return False

            if excluding_deaf and any([member.deaf, member.self_deaf]):
                return False

            return True

        channel = self.old_voice_channel if old_channel else self.voice_channel
        if not channel:
            return

        return not sum(1 for m in channel.voice_members if check(m))

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
