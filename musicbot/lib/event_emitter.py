import asyncio
import traceback
import collections


class EventEmitter:
    def __init__(self):
        self._events = collections.defaultdict(list)
        self.loop = asyncio.get_event_loop()

    def emit(self, event, *args, **kwargs):
        if event not in self._events:
            return

        for cb in self._events[event]:
            # noinspection PyBroadException
            try:
                if asyncio.iscoroutinefunction(cb):
                    asyncio.ensure_future(cb(*args, **kwargs), loop=self.loop)
                else:
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

    # TODO: add .once
