from .constructs import Serializable
from . import exceptions

class GuildConfig(Serializable):
    def __init__(self, bot):
        self.auto_mode = bot.config.auto_mode
        self.auto_random = False

    def __json__(self):
        return self._enclose_json({
            'version': 2,
            'auto_mode': self.auto_mode,
            'auto_random': self.auto_random
        })

    @classmethod
    def _deserialize(cls, data, bot=None):
        assert bot is not None, cls._bad('bot')

        if 'version' not in data or data['version'] < 0:
            raise exceptions.VersionError('data version needs to be higher than 0')

        config = cls(bot)

        config.auto_mode = data['auto_mode']
        if 'version' not in data or data['version'] >= 2:
            config.auto_random = data['auto_random']

        return config