import json
import pydoc
import inspect
import logging

import discord

from enum import Enum
from .utils import objdiff, _get_variable

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
