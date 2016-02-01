import configparser


class Config(object):
    def __init__(self, config_file):
        config = configparser.ConfigParser()
        config.read(config_file)

        self.username = config.get('Credentials', 'Username', fallback=None)
        self.password = config.get('Credentials', 'Password', fallback=None)

        self.owner_id = config.get('Permissions', 'OwnerID', fallback=None)
        self.command_prefix = config.get('Chat', 'CommandPrefix', fallback='!')

        self.days_active = config.getint('MusicBot', 'DaysActive', fallback=0)
        self.white_list_check = config.getboolean('MusicBot', 'WhiteListCheck', fallback=False)
        self.skips_required = config.getint('MusicBot', 'SkipsRequired', fallback=7)
        self.skip_ratio_required = config.getfloat('MusicBot', 'SkipRatio', fallback=0.5)
        self.save_videos = config.getboolean('MusicBot', 'SaveVideos', fallback=True)
        self.now_playing_mentions = config.getboolean('MusicBot', 'NowPlayingMentions', fallback=True)
        self.auto_summon = config.getboolean('MusicBot', 'AutoSummon', fallback=True)
        self.auto_playlist = config.getboolean('MusicBot', 'UseAutoPlaylist', fallback=True)
        self.auto_delete = config.getboolean('MusicBot', 'AutoDelete', fallback=True)
        self.report_errors = config.getboolean('MusicBot', 'ReportErrors', fallback=True)

        self.config_file = config.get('Files', 'ConfigFile', fallback='config/config.json')
        self.backup_playlist_file = config.get('Files', 'BlackupPlaylistFile', fallback='config/backuplist.txt')

        # Validation logic for bot settings.
        if not self.username or not self.password:
            raise ValueError('A username or password was not specified in the configuration file.')

        if not self.owner_id:
            raise ValueError("An owner is not specified in the configuration file")

    # TODO: Add save function for future editing of options with commands
    #       Maybe add warnings about fields missing from the config file
