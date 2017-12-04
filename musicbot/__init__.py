import sys
import inspect
import logging

from textwrap import dedent
from discord.ext.commands.bot import _get_variable

from .exceptions import HelpfulError

class Yikes:
    def find_module(self, fullname, path=None):
        if fullname == 'requests':
            return self
        return None

    def _get_import_chain(self, *, until=None):
        stack = inspect.stack()[2:]
        try:
            for frameinfo in stack:
                try:
                    if not frameinfo.code_context:
                        continue

                    data = dedent(''.join(frameinfo.code_context))
                    if data.strip() == until:
                        raise StopIteration

                    yield frameinfo.filename, frameinfo.lineno, data.strip()
                    del data
                finally:
                    del frameinfo
        finally:
            del stack

    def _format_import_chain(self, chain, *, message=None):
        lines = []
        for line in chain:
            lines.append("In %s, line %s:\n    %s" % line)

        if message:
            lines.append(message)

        return '\n'.join(lines)

    def load_module(self, name):
        if _get_variable('allow_requests'):
            sys.meta_path.pop(0)
            return __import__('requests')

        import_chain = tuple(self._get_import_chain(until='from .bot import MusicBot'))
        import_tb = self._format_import_chain(import_chain)

        raise HelpfulError(
            "You are attempting to import requests, or import a module that uses requests.  "
            "Requests (or any module that uses requests) should not be used in this code.  "
            "See %s for why requests is not suitable for this code."
            % "[https://discordpy.readthedocs.io/en/latest/faq.html#what-does-blocking-mean]",

            "Don't use requests, use aiohttp instead.  The api is very similar to requests "
            "when using session objects. [http://aiohttp.readthedocs.io/en/stable/]  If "
            "a module you're trying to use depends on requests, see if you can find a similar "
            "module compatable with asyncio.  If you can't find one, learn how to avoid blocking "
            "in coroutines.  If you're new to programming, consider learning more about how "
            "asynchronous code and coroutines work.  Blocking calls (notably HTTP requests) can take "
            "a long time, during which the bot is unable to do anything but wait for it.  "
            "If you're sure you know what you're doing, simply add `allow_requests = True` above your "
            "import statement, that being `import requests` or whatever requests dependent module.",

            footnote="Import traceback (most recent call last):\n" + import_tb
        )

sys.meta_path.insert(0, Yikes())

from .bot import MusicBot
from .constructs import BetterLogRecord

__all__ = ['MusicBot']

logging.setLogRecordFactory(BetterLogRecord)

_func_prototype = "def {logger_func_name}(self, message, *args, **kwargs):\n" \
                  "    if self.isEnabledFor({levelname}):\n" \
                  "        self._log({levelname}, message, args, **kwargs)"

def _add_logger_level(levelname, level, *, func_name = None):
    """

    :type levelname: str
        The reference name of the level, e.g. DEBUG, WARNING, etc
    :type level: int
        Numeric logging level
    :type func_name: str
        The name of the logger function to log to a level, e.g. "info" for log.info(...)
    """

    func_name = func_name or levelname.lower()

    setattr(logging, levelname, level)
    logging.addLevelName(level, levelname)

    exec(_func_prototype.format(logger_func_name=func_name, levelname=levelname), logging.__dict__, locals())
    setattr(logging.Logger, func_name, eval(func_name))


_add_logger_level('EVERYTHING', 1)
_add_logger_level('NOISY', 4, func_name='noise')
_add_logger_level('FFMPEG', 5)
_add_logger_level('VOICEDEBUG', 6)

log = logging.getLogger(__name__)
log.setLevel(logging.EVERYTHING)

fhandler = logging.FileHandler(filename='logs/musicbot.log', encoding='utf-8', mode='a')
fhandler.setFormatter(logging.Formatter(
    "[{relativeCreated:.16f}] {asctime} - {levelname} - {name} | "
    "In {filename}::{threadName}({thread}), line {lineno} in {funcName}: {message}",
    style='{'
))
log.addHandler(fhandler)

del _func_prototype
del _add_logger_level
del fhandler
