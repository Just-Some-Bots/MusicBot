class CommandError(Exception):
    def __init__(self, message):
        super().__init__(message)


class ExtractionError(Exception):
    def __init__(self, message):
        super().__init__(message)

class HelpfulError(Exception):
    def __init__(self, issue, solution):
        self.issue = issue
        self.solution = solution
        super().__init__(self._construct_msg())

    def _construct_msg(self):
        return ("\n"
            "An error has occured.\n"
            "  Cause: {}\n"
            "  Solution: {}\n"
            ).format(self.issue, self.solution)
