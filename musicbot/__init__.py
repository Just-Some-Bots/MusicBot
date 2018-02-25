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
            lines.append("%sでは、行%s:\n%s" % line)

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
            "要求をインポートしようとしているか、要求を使用しているモジュールをインポートしようとしています。  "
            "要求（または要求を使用するモジュール）は、このコードでは使用しないでください。  "
            "このコードに対して要求が適切でない理由については、%sを参照してください。"
            % "[https://discordpy.readthedocs.io/en/latest/faq.html#what-does-blocking-mean]",

            "リクエストを使用しないで、代わりにaiohttpを使用してください。 APIはリクエストと非常に似ています"
            "セッションオブジェクトを使用する場合[http://aiohttp.readthedocs.io/en/stable/] "
            "あなたが使用しようとしているモジュールはリクエストに依存しています。 "
            "モジュールasyncioと互換性があります。見つけられない場合は、ブロックを回避する方法を学んでください"
            "コルーチンでプログラミングに慣れていない場合は、 "
            "非同期コードとコルーチンが機能します。ブロッキングコール（特にHTTPリクエスト）は、"
            "長い間、ボットは何もすることができないが、それを待つ。"
            "あなたが何をしているのか分かっているなら、あなたの上に `allow_requests = True`を追加するだけです "
            "importステートメント、それは `import requests`または何らかの要求依存モジュールです。",

            footnote="トレースバックをインポートする(直近の最後のコール):\n" + import_tb
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
