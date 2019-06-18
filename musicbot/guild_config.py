from .constructs import Serializable
from . import exceptions

class GuildConfig(Serializable):
    def __init__(self, bot):
        self.auto_mode = bot.config.auto_mode

    def __json__(self):
        return self._enclose_json({
            'version': 1,
            'auto_mode': self.auto_mode
        })

    @classmethod
    def _deserialize(cls, data, bot=None):
        assert bot is not None, cls._bad('bot')

        if 'version' not in data or data['version'] < 0:
            raise exceptions.VersionError('data version needs to be higher than 0')

        config = cls(bot)

        config.auto_mode = data['auto_mode']

        return config