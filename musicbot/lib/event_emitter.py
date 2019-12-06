import asyncio
import traceback
import collections
from functools import partial

class EventEmitter:
    def __init__(self):
        self._events = collections.defaultdict(list)
        self.loop = asyncio.get_event_loop()
        self.log = None
        
        for item in dir(self):
            iteminst = getattr(self, item)
            if isinstance(iteminst, _MarkOn):
                self.on(iteminst.event, partial(iteminst.func, self))

    def emit(self, event, *args, **kwargs):
        if event not in self._events:
            return

        for cb in list(self._events[event]):
            # noinspection PyBroadException
            try:
                if asyncio.iscoroutinefunction(cb):
                    asyncio.ensure_future(cb(*args, **kwargs), loop=self.loop)
                else:
                    cb(*args, **kwargs)

            except:
                if not self.log:
                    traceback.print_exc()
                else:
                    self.log.error(traceback.format_exc())

    def on(self, event, cb):
        self._events[event].append(cb)
        return self

    def off(self, event, cb):
        self._events[event].remove(cb)

        if not self._events[event]:
            del self._events[event]

        return self

    def once(self, event, cb):
        def callback(*args, **kwargs):
            self.off(event, callback)
            return cb(*args, **kwargs)

        return self.on(event, callback)

class _MarkOn:
    def __init__(self, event, func):
        self.event = event
        self.func = func

def on(event):
    def on_ev(func):
        return _MarkOn(event, func)
    return on_ev

on_event = on

class EmitterToggler:

    current_value = None
    _emit = None
    _eventmap = dict()

    def _call(self, event, value):
        self.current_value = value

    def __init__(self, emitter):
        self._emit = emitter
        self._emit.on('toggler', lambda key: self._call(key, self._eventmap[key]))

    def add(self, eventmap):
        self._eventmap.update(eventmap)

    def once(self, when, event):
        self._emit.once(when, lambda **_: self._emit.emit('toggler', key=event))
