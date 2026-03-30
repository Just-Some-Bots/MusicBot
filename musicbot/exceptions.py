from enum import Enum
from typing import Any, Dict, Optional, Union


class MusicbotException(Exception):
    """
    MusicbotException is a base exception for all exceptions raised by MusicBot.
    It allows translation of messages into log and UI contexts at display time, not before.
    Thus, all messages passed to this and child exceptions must use placeholders for
    variable message segments, and abide best practices for translated messages.

    :param: message:  The untranslated string used as the exception message.
    :param: fmt_args:  A mapping for variable substitution in messages.
    :param: delete_after:  Optional timeout period to override the short delay.
                           Used only when deletion options allow it.
    """

    def __init__(
        self,
        message: str,
        *,
        delete_after: Union[None, float, int] = None,
        fmt_args: Optional[Dict[str, Any]] = None,
    ) -> None:
        # This sets base exception args to the message.
        # So str() will produce the raw, untranslated message only.
        if fmt_args:
            super().__init__(message, fmt_args)
        else:
            super().__init__(message)

        self._message = message
        self._fmt_args = fmt_args if fmt_args is not None else {}
        self.delete_after = delete_after

    @property
    def message(self) -> str:
        """Get raw message text, this has not been translated."""
        return self._message

    @property
    def fmt_args(self) -> Dict[str, Any]:
        """Get any arguments that should be formatted into the message."""
        return self._fmt_args


# Something went wrong during the processing of a command
class CommandError(MusicbotException):
    pass


# Something went wrong during the processing of a song/ytdl stuff
class ExtractionError(MusicbotException):
    pass


# Something is wrong about data
class InvalidDataError(MusicbotException):
    pass


# The no processing entry type failed and an entry was a playlist/vice versa
class WrongEntryTypeError(ExtractionError):
    pass


# FFmpeg complained about something
class FFmpegError(MusicbotException):
    pass


# FFmpeg complained about something but we don't care
class FFmpegWarning(MusicbotException):
    pass


# Some issue retrieving something from Spotify's API or processing it.
class SpotifyError(ExtractionError):
    pass


# The user doesn't have permission to use a command
class PermissionsError(CommandError):
    pass


# Error with pretty formatting for hand-holding users through various errors
class HelpfulError(MusicbotException):
    pass


class HelpfulWarning(HelpfulError):
    pass


# simple exception used to signal that initial config load should retry.
class RetryConfigException(Exception):
    pass


# Signal codes used in RestartSignal
class RestartCode(Enum):
    RESTART_SOFT = 0
    RESTART_FULL = 1
    RESTART_UPGRADE_ALL = 2
    RESTART_UPGRADE_PIP = 3
    RESTART_UPGRADE_GIT = 4


# Base class for control signals
class Signal(Exception):
    pass


# signal to restart or reload the bot
class RestartSignal(Signal):
    def __init__(self, code: RestartCode = RestartCode.RESTART_SOFT):
        self.restart_code = code

    def get_code(self) -> int:
        """Get the int value of the code contained in this signal"""
        return self.restart_code.value

    def get_name(self) -> str:
        """Get the name of the restart code contained in this signal"""
        return self.restart_code.name


# signal to end the bot "gracefully"
class TerminateSignal(Signal):
    def __init__(self, exit_code: int = 0):
        self.exit_code: int = exit_code
