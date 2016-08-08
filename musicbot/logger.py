import os
import configparser
from datetime import datetime
from .exceptions import HelpfulError
from .utils import safe_print


class LoggerConfig:
    """
    Controls the configuration aspect of the logger
    """
    def __init__(self, config_file, log_file):
        self.config_file = config_file
        self.log_file = log_file

        config = configparser.ConfigParser(interpolation=None)
        if not config.read(self.config_file, encoding='utf-8'):
            raise HelpfulError("Logging configuration file {} wasn't found.".format(self.config_file),
                "You are missing important files. Redownload the bot from the repo.")

        self.file = config.getboolean('General', 'File', fallback=LoggerDefaults.file)
        self.discord = config.getboolean('General', 'Discord', fallback=LoggerDefaults.discord)

        self.timeformat = config.get('Advanced', 'TimeFormat', fallback=LoggerDefaults.timeformat)


class Logger:
    def __init__(self):
        self.config = LoggerConfig(LoggerDefaults.config_file, LoggerDefaults.log_file)

        dt = datetime.now()
        with open(self.config.log_file, 'w') as f:
            f.write('{} - Script started'.format(dt.strftime(self.config.timeformat)))

    async def log(self, msg, log_to_file=True, log_to_discord=True, print=False):
        """
        Primary function for logging a message
        """
        if print:
            safe_print(msg)
        if msg.startswith('\r'):
            msg = msg.replace('\r', '')
        if self.config.file and log_to_file:
            await self._log_file(msg)
        if self.config.discord and log_to_discord:
            await self._log_discord(msg)

    async def _log_file(self, msg):
        dt = datetime.now()
        with open(self.config.log_file, 'a') as f:
            f.write('\n{} - {}'.format(dt.strftime(self.config.timeformat), msg))

    async def _log_discord(self, msg):
        pass


class LoggerDefaults:
    """
    All of the default values for the logger
    """
    config_file = "config/logging.ini"
    log_file = "bot.log"

    file = False
    discord = True

    timeformat = '%Y/%m/%d %H:%M:%S'
