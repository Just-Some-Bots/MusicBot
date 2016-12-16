import shutil
import textwrap

# [MBM] Multi-Language support
# required for language support
from musicbot.config import Config, ConfigDefaults
import importlib
# ===== END =====

# Base class for exceptions
class MusicbotException(Exception):
    def __init__(self, config_file=ConfigDefaults.options_file, message, *, expire_in=0):
        self._message = message
        self.expire_in = expire_in

# [MBM] Multi-Language support
        self.config = Config(config_file)
        language = self.config.language
        f = self.config.languages_location + language
        self.lang = importlib.import_module(f)
# ===== END =====
    @property
    def message(self):
        return self._message

    @property
    def message_no_format(self):
        return self._message


# Something went wrong during the processing of a command
class CommandError(MusicbotException):
    pass


# Something went wrong during the processing of a song/ytdl stuff
class ExtractionError(MusicbotException):
    pass


# The no processing entry type failed and an entry was a playlist/vice versa
class WrongEntryTypeError(ExtractionError):
    def __init__(self, message, is_playlist, use_url):
        super().__init__(message)
        self.is_playlist = is_playlist
        self.use_url = use_url


# The user doesn't have permission to use a command
class PermissionsError(CommandError):
    @property
    def message(self):
        return self.lang.exceptions_no_permission + self._message


# Error with pretty formatting for hand-holding users through various errors
class HelpfulError(MusicbotException):
    def __init__(self, issue, solution, *, preface=self.lang.exceptions_error_occured, expire_in=0):
        self.issue = issue
        self.solution = solution
        self.preface = preface
        self.expire_in = expire_in

    @property
    def message(self):
        return ("\n{}\n{}\n{}\n").format(
            self.preface,
            self._pretty_wrap(self.issue, self.lang.exceptions_problem),
            self._pretty_wrap(self.solution, self.lang.exceptions_solution))

    @property
    def message_no_format(self):
        return "\n{}\n{}\n{}\n".format(
            self.preface,
            self._pretty_wrap(self.issue, self.lang.exceptions_problem, width=None),
            self._pretty_wrap(self.solution, self.lang.exceptions_solution, width=None))

    @staticmethod
    def _pretty_wrap(text, pretext, *, width=-1):
        if width is None:
            return pretext + text
        elif width == -1:
            width = shutil.get_terminal_size().columns

        l1, *lx = textwrap.wrap(text, width=width - 1 - len(pretext))

        lx = [((' ' * len(pretext)) + l).rstrip().ljust(width) for l in lx]
        l1 = (pretext + l1).ljust(width)

        return ''.join([l1, *lx])


class HelpfulWarning(HelpfulError):
    pass


# Base class for control signals
class Signal(Exception):
    pass


# signal to restart the bot
class RestartSignal(Signal):
    pass


# signal to end the bot "gracefully"
class TerminateSignal(Signal):
    pass
