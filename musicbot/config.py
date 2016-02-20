import configparser


class ConfigDefaults:
    username = None
    password = None

    owner_id = None
    command_prefix = '!'
    bound_channels = set()

    default_volume = 0.15
    white_list_check = False
    skips_required = 4
    skip_ratio_required = 0.5
    save_videos = True
    now_playing_mentions = False
    auto_summon = True
    auto_playlist = True
    ignore_non_voice = True
    debug_mode = False

    options_file = 'config/options.ini'
    blacklist_file = 'config/blacklist.txt'
    whitelist_file = 'config/whitelist.txt'
    auto_playlist_file = 'config/autoplaylist.txt' # this will change when I add playlists


class Config:
    def __init__(self, config_file):
        self.config_file = config_file
        config = configparser.ConfigParser()
        config.read(config_file)

        # Maybe wrap these in a helper and change ConfigDefaults names to their config value

        self.username = config.get('Credentials', 'Username', fallback=ConfigDefaults.username)
        self.password = config.get('Credentials', 'Password', fallback=ConfigDefaults.password)

        self.owner_id = config.get('Permissions', 'OwnerID', fallback=ConfigDefaults.owner_id)
        self.command_prefix = config.get('Chat', 'CommandPrefix', fallback=ConfigDefaults.command_prefix)
        self.bound_channels = config.get('Chat', 'BindToChannels', fallback=ConfigDefaults.bound_channels)

        self.default_volume = config.getfloat('MusicBot', 'DefaultVolume', fallback=ConfigDefaults.default_volume)
        self.white_list_check = config.getboolean('MusicBot', 'WhiteListCheck', fallback=ConfigDefaults.white_list_check)
        self.skips_required = config.getint('MusicBot', 'SkipsRequired', fallback=ConfigDefaults.skips_required)
        self.skip_ratio_required = config.getfloat('MusicBot', 'SkipRatio', fallback=ConfigDefaults.skip_ratio_required)
        self.repeat = config.getboolean('MusicBot', 'Repeat', fallback=False)
        self.save_videos = config.getboolean('MusicBot', 'SaveVideos', fallback=ConfigDefaults.save_videos)
        self.now_playing_mentions = config.getboolean('MusicBot', 'NowPlayingMentions', fallback=ConfigDefaults.now_playing_mentions)
        self.auto_summon = config.getboolean('MusicBot', 'AutoSummon', fallback=ConfigDefaults.auto_summon)
        self.auto_playlist = config.getboolean('MusicBot', 'UseAutoPlaylist', fallback=ConfigDefaults.auto_playlist)
        self.ignore_non_voice = config.getboolean('MusicBot', 'IgnoreNonVoice', fallback=ConfigDefaults.ignore_non_voice)
        self.debug_mode = config.getboolean('MusicBot', 'DebugMode', fallback=ConfigDefaults.debug_mode)

        self.blacklist_file = config.get('Files', 'BlacklistFile', fallback=ConfigDefaults.blacklist_file)
        self.whitelist_file = config.get('Files', 'WhitelistFile', fallback=ConfigDefaults.whitelist_file)
        self.auto_playlist_file = config.get('Files', 'AutoPlaylistFile', fallback=ConfigDefaults.auto_playlist_file)

        # Validation logic for bot settings.
        if not self.username or not self.password:
            raise ValueError('A username or password was not specified in the configuration file.')

        if not self.owner_id:
            raise ValueError("An owner is not specified in the configuration file")

        if self.bound_channels:
            try:
                self.bound_channels = set(x for x in self.bound_channels.split() if x)
            except:
                print("[Warning] BindToChannels data invalid, will not bind to any channels")
                self.bound_channels = set()

    # TODO: Add save function for future editing of options with commands
    #       Maybe add warnings about fields missing from the config file

    def write_default_config(self, location):
        pass


# These two are going to be wrappers for the id lists, with add/remove/load/save functions
# and id/object conversion so types aren't an issue
class Blacklist:
    pass

class Whitelist:
    pass
