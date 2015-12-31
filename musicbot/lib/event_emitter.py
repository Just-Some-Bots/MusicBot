import collections
import traceback


class EventEmitter(object):
    def __init__(self):
        self._events = collections.defaultdict(list)

    def emit(self, event, *args, **kwargs):
        if event not in self._events:
            return

        for cb in self._events[event]:
            # noinspection PyBroadException
            try:
                cb(*args, **kwargs)

            except:
                traceback.print_exc()

    def on(self, event, cb):
        self._events[event].append(cb)
        return self

    def off(self, event, cb):
        self._events[event].remove(cb)

        if not self._events[event]:
            del self._events[event]

        return self
