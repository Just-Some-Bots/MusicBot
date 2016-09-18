"""
Hi im logman. I take care of logging history of played tracks. I also help
remembering queued songs in case of restart.
"""

import datetime
import pymongo
import atexit

from pymongo.errors import OperationFailure, ServerSelectionTimeoutError


class Logman():

    def __init__(self, mongodb_uri):
        self.connection = pymongo.MongoClient(mongodb_uri)
        self.db = self.connection.get_default_database()
        self.history = self.db['history']
        atexit.register(self._disconnect)

    def _disconnect(self):
        self.connection.close()

    def log_song(self, entry):
        """Use this to log a song history."""
        time = str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        song = {
            'date': time,
            'title': entry.title,
            'url': entry.url
        }

        try:
            self.history.insert(song)

        except (OperationFailure, ServerSelectionTimeoutError):
            print("[Logman] \"im hev trouble comunicating with mongodb. "
                  "Cud be wrong login info or bad uri :<\"")
