
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
