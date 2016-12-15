import os
import shutil
import configparser

from .exceptions import HelpfulError
# [MBM] Multi-Language support
# required for language support
import importlib
# ===== END =====


class Config:
    def __init__(self, config_file):
        self.config_file = config_file
# [MBM] Multi-Language support
        language = self.config.language
        if language == "":
            language = "english"
            # print("No language detected, using english by default!")
        f = self.config.languages_location + language
        self.lang = importlib.import_module(f)
# ===== END =====
        config = configparser.ConfigParser()

        if not config.read(config_file, encoding='utf-8'):
            print(self.lang.config_file_not_found)

            try:
                shutil.copy('config/example_options.ini', config_file)

                # load the config again and check to see if the user edited that one
                c = configparser.ConfigParser()
                c.read(config_file, encoding='utf-8')

                if not int(c.get('Permissions', 'OwnerID', fallback=0)):  # jake pls no flame
                    print(self.lang.config_please_configure, flush=True)
                    os._exit(1)

            except FileNotFoundError as e:
                raise HelpfulError(self.lang.config_files_missing)

            except ValueError:  # Config id value was changed but its not valid
                print(self.lang.config_invalid_ownerid)
                # TODO: HelpfulError
                os._exit(4)

            except Exception as e:
                print(e)
                print(self.lang.config_cannot_copy_example % config_file, flush=True)
                os._exit(2)

        config = configparser.ConfigParser(interpolation=None)
        config.read(config_file, encoding='utf-8')

        confsections = {"Credentials", "Permissions", "Chat", "MusicBot"}.difference(config.sections())
        if confsections:
            raise HelpfulError(self.lang.config_section_missing.format(
                               ', '.join(['[%s]' % s for s in confsections])), preface=self.lang.config_error_parsing)

        self._email = config.get('Credentials', 'Email', fallback=ConfigDefaults.email)
        self._password = config.get('Credentials', 'Password', fallback=ConfigDefaults.password)
        self._login_token = config.get('Credentials', 'Token', fallback=ConfigDefaults.token)

        self.auth = None

        self.owner_id = config.get('Permissions', 'OwnerID', fallback=ConfigDefaults.owner_id)
        self.command_prefix = config.get('Chat', 'CommandPrefix', fallback=ConfigDefaults.command_prefix)
        self.bound_channels = config.get('Chat', 'BindToChannels', fallback=ConfigDefaults.bound_channels)
        self.autojoin_channels = config.get('Chat', 'AutojoinChannels', fallback=ConfigDefaults.autojoin_channels)

        self.default_volume = config.getfloat('MusicBot', 'DefaultVolume', fallback=ConfigDefaults.default_volume)
        self.skips_required = config.getint('MusicBot', 'SkipsRequired', fallback=ConfigDefaults.skips_required)
        self.skip_ratio_required = config.getfloat('MusicBot', 'SkipRatio', fallback=ConfigDefaults.skip_ratio_required)
        self.save_videos = config.getboolean('MusicBot', 'SaveVideos', fallback=ConfigDefaults.save_videos)
        self.now_playing_mentions = config.getboolean('MusicBot', 'NowPlayingMentions', fallback=ConfigDefaults.now_playing_mentions)
        self.auto_summon = config.getboolean('MusicBot', 'AutoSummon', fallback=ConfigDefaults.auto_summon)
        self.auto_playlist = config.getboolean('MusicBot', 'UseAutoPlaylist', fallback=ConfigDefaults.auto_playlist)
        self.auto_pause = config.getboolean('MusicBot', 'AutoPause', fallback=ConfigDefaults.auto_pause)
        self.delete_messages = config.getboolean('MusicBot', 'DeleteMessages', fallback=ConfigDefaults.delete_messages)
        self.delete_invoking = config.getboolean('MusicBot', 'DeleteInvoking', fallback=ConfigDefaults.delete_invoking)
        self.debug_mode = config.getboolean('MusicBot', 'DebugMode', fallback=ConfigDefaults.debug_mode)

        self.blacklist_file = config.get('Files', 'BlacklistFile', fallback=ConfigDefaults.blacklist_file)
        self.auto_playlist_file = config.get('Files', 'AutoPlaylistFile', fallback=ConfigDefaults.auto_playlist_file)

# [MBM] Multi-Language support
        self.language = config.get('MusicBot', 'Language', fallback=ConfigDefaults.language)
        self.languages_location = config.get('Files', 'LanguagesFile', fallback=ConfigDefaults.languages_location)
# ===== END =====

        self.run_checks()

    def run_checks(self):
        self.lang.config_validation_error
        confpreface = self.lang.config_error_reading

        if self._email or self._password:
            if not self._email:
                raise HelpfulError(self.lang.config_login_no_email, preface=confpreface)

            if not self._password:
                raise HelpfulError(self.lang.config_login_no_password, preface=confpreface)

            self.auth = (self._email, self._password)

        elif not self._login_token:
            raise HelpfulError(self.lang.config_login_no_token, preface=confpreface)

        else:
            self.auth = (self._login_token,)

        if self.owner_id and self.owner_id.isdigit():
            if int(self.owner_id) < 10000:
                raise HelpfulError(self.lang.config_ownerid_not_set % self.command_prefix, preface=confpreface)

        else:
            raise HelpfulError(self.lang.config_invalid_ownerid_set % (self.command_prefix, self.owner_id), preface=confpreface)

        if self.bound_channels:
            try:
                self.bound_channels = set(x for x in self.bound_channels.split() if x)
            except:
                print(self.lang.config_invalid_boundto)
                self.bound_channels = set()

        if self.autojoin_channels:
            try:
                self.autojoin_channels = set(x for x in self.autojoin_channels.split() if x)
            except:
                print(self.lang.config_invalid_autojoin)
                self.autojoin_channels = set()

        self.delete_invoking = self.delete_invoking and self.delete_messages

        self.bound_channels = set(item.replace(',', ' ').strip() for item in self.bound_channels)

        self.autojoin_channels = set(item.replace(',', ' ').strip() for item in self.autojoin_channels)

    # TODO: Add save function for future editing of options with commands
    #       Maybe add warnings about fields missing from the config file

    def write_default_config(self, location):
        pass


class ConfigDefaults:
    email = None    #
    password = None  # This is not where you put your login info, go away.
    token = None    #

    owner_id = None
    command_prefix = '!'
    bound_channels = set()
    autojoin_channels = set()

    default_volume = 0.15
    skips_required = 4
    skip_ratio_required = 0.5
    save_videos = True
    now_playing_mentions = False
    auto_summon = True
    auto_playlist = True
    auto_pause = True
    delete_messages = True
    delete_invoking = False
    debug_mode = False

    options_file = 'config/options.ini'
    blacklist_file = 'config/blacklist.txt'
    auto_playlist_file = 'config/autoplaylist.txt'  # this will change when I add playlists

# [MBM] Multi-Language support
    languages_location = "languages."
    language = "english"
# ===== END =====


# These two are going to be wrappers for the id lists, with add/remove/load/save functions
# and id/object conversion so types aren't an issue
class Blacklist:
    pass


class Whitelist:
    pass
