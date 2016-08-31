import logging

from .bot import MusicBot

__all__ = ['MusicBot']

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

fhandler = logging.FileHandler(filename='logs/musicbot.log', encoding='utf-8', mode='w')
fhandler.setFormatter(logging.Formatter('{asctime}:{levelname}:{name}: {message}', style='{'))
log.addHandler(fhandler)
