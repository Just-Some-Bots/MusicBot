class CommandError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__()


class ExtractionError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__()
