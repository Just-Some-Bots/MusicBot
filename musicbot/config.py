import configparser


class ConfigDefaults(object):
    username = None
    password = None

    owner_id = None
    command_prefix = '!'

    days_active = 0 # I might remove this entirely, it seems kinda dumb now that there's server verification levels
    white_list_check = False
    skips_required = 5
    skip_ratio_required = 0.5
    save_videos = True
    now_playing_mentions = False
    auto_summon = True
    auto_playlist = True

    blacklist_file = 'config/blacklist.txt'
    whitelist_file = 'config/whitelist.txt'
    backup_playlist_file = 'config/backuplist.txt' # this will change when I add playlists


class Config(object):
    def __init__(self, config_file):
        config = configparser.ConfigParser()
        config.read(config_file)

        # Maybe wrap these in a helper and change ConfigDefaults names to their config value

        self.username = config.get('Credentials', 'Username', fallback=ConfigDefaults.username)
        self.password = config.get('Credentials', 'Password', fallback=ConfigDefaults.password)

        self.owner_id = config.get('Permissions', 'OwnerID', fallback=ConfigDefaults.owner_id)
        self.command_prefix = config.get('Chat', 'CommandPrefix', fallback=ConfigDefaults.command_prefix)

        self.days_active = config.getint('MusicBot', 'DaysActive', fallback=ConfigDefaults.days_active)
        self.white_list_check = config.getboolean('MusicBot', 'WhiteListCheck', fallback=ConfigDefaults.white_list_check)
        self.skips_required = config.getint('MusicBot', 'SkipsRequired', fallback=ConfigDefaults.skips_required)
        self.skip_ratio_required = config.getfloat('MusicBot', 'SkipRatio', fallback=ConfigDefaults.skip_ratio_required)
        self.save_videos = config.getboolean('MusicBot', 'SaveVideos', fallback=ConfigDefaults.save_videos)
        self.now_playing_mentions = config.getboolean('MusicBot', 'NowPlayingMentions', fallback=ConfigDefaults.now_playing_mentions)
        self.auto_summon = config.getboolean('MusicBot', 'AutoSummon', fallback=ConfigDefaults.auto_summon)
        self.auto_playlist = config.getboolean('MusicBot', 'UseAutoPlaylist', fallback=ConfigDefaults.auto_playlist)

        self.blacklist_file = config.get('Files', 'BlacklistFile', fallback=ConfigDefaults.blacklist_file)
        self.whitelist_file = config.get('Files', 'WhitelistFile', fallback=ConfigDefaults.whitelist_file)
        self.backup_playlist_file = config.get('Files', 'BlackupPlaylistFile', fallback=ConfigDefaults.backup_playlist_file)


        # Validation logic for bot settings.
        if not self.username or not self.password:
            raise ValueError('A username or password was not specified in the configuration file.')

        if not self.owner_id:
            raise ValueError("An owner is not specified in the configuration file")

    # TODO: Add save function for future editing of options with commands
    #       Maybe add warnings about fields missing from the config file
