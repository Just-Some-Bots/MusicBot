import shutil
import textwrap


class CommandError(Exception):
    def __init__(self, message, *, expire_in=0):
        self.message = message
        self.expire_in = expire_in

class ExtractionError(Exception):
    def __init__(self, message):
        self.message = message

class PermissionsError(CommandError):
    def __init__(self, reason, *, expire_in=0):
        self.reason = reason
        self.expire_in = expire_in
        self.message = "You don't have permission to use that command.\nReason: " + reason

class HelpfulError(Exception):
    def __init__(self, issue, solution, *, preface="An error has occured:\n", expire_in=0):
        self.issue = issue
        self.solution = solution
        self.preface = preface
        self.expire_in = expire_in
        self.message = self._construct_msg()

    def _construct_msg(self):
        return ("\n{}\n{}\n{}\n").format(
            self.preface,
            self._pretty_wrap(self.issue,    "  Problem:  "),
            self._pretty_wrap(self.solution, "  Solution: "))

    def _pretty_wrap(self, text, pretext):
        w = shutil.get_terminal_size().columns
        l1, *lx = textwrap.wrap(text, width=w - 1 - len(pretext))

        lx = [((' ' * len(pretext)) + l).rstrip().ljust(w) for l in lx]
        l1 = (pretext + l1).ljust(w)

        return ''.join([l1, *lx])

# signal to restart the bot
class RestartSignal(Exception):
    pass

# signal to end the bot "gracefully"
class TerminateSignal(Exception):
    pass
