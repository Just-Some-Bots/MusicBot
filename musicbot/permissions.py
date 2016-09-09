import shutil
import traceback
import configparser

from discord import User as discord_User


class PermissionsDefaults:
    perms_file = 'config/permissions.ini'

    CommandWhiteList = set()
    CommandBlackList = set()
    IgnoreNonVoice = set()
    GrantToRoles = set()
    UserList = set()

    MaxSongs = 0
    MaxSongLength = 0
    MaxPlaylistLength = 0

    AllowPlaylists = True
    InstaSkip = False


class Permissions:
    def __init__(self, config_file, grant_all=None):
        self.config_file = config_file
        self.config = configparser.ConfigParser(interpolation=None)

        if not self.config.read(config_file, encoding='utf-8'):
            print('[permissions] Permissions file not found, copying example_permissions.ini')

            try:
                shutil.copy('config/example_permissions.ini', config_file)
                self.config.read(config_file, encoding='utf-8')

            except Exception as e:
                traceback.print_exc()
                raise RuntimeError("Unable to copy config/example_permissions.ini to %s: %s" % (config_file, e))

        self.default_group = PermissionGroup('Default', self.config['Default'])
        self.groups = set()

        for section in self.config.sections():
            self.groups.add(PermissionGroup(section, self.config[section]))

        # Create a fake section to fallback onto the permissive default values to grant to the owner
        # noinspection PyTypeChecker
        owner_group = PermissionGroup("Owner (auto)", configparser.SectionProxy(self.config, None))
        if hasattr(grant_all, '__iter__'):
            owner_group.user_list = set(grant_all)

        self.groups.add(owner_group)


    def save(self):
        with open(self.config_file, 'w') as f:
            self.config.write(f)

    def for_user(self, user):
        """
        Returns the first PermissionGroup a user belongs to
        :param user: A discord User or Member object
        """

        for group in self.groups:
            if user.id in group.user_list:
                return group

        # The only way I could search for roles is if I add a `server=None` param and pass that too
        if type(user) == discord_User:
            return self.default_group

        # We loop again so that we don't return a role based group before we find an assigned one
        for group in self.groups:
            for role in user.roles:
                if role.id in group.granted_to_roles:
                    return group

        return self.default_group

    def create_group(self, name, **kwargs):
        self.config.read_dict({name:kwargs})
        self.groups.add(PermissionGroup(name, self.config[name]))
        # TODO: Test this


class PermissionGroup:
    def __init__(self, name, section_data):
        self.name = name

        self.command_whitelist = section_data.get('CommandWhiteList', fallback=PermissionsDefaults.CommandWhiteList)
        self.command_blacklist = section_data.get('CommandBlackList', fallback=PermissionsDefaults.CommandBlackList)
        self.ignore_non_voice = section_data.get('IgnoreNonVoice', fallback=PermissionsDefaults.IgnoreNonVoice)
        self.granted_to_roles = section_data.get('GrantToRoles', fallback=PermissionsDefaults.GrantToRoles)
        self.user_list = section_data.get('UserList', fallback=PermissionsDefaults.UserList)

        self.max_songs = section_data.get('MaxSongs', fallback=PermissionsDefaults.MaxSongs)
        self.max_song_length = section_data.get('MaxSongLength', fallback=PermissionsDefaults.MaxSongLength)
        self.max_playlist_length = section_data.get('MaxPlaylistLength', fallback=PermissionsDefaults.MaxPlaylistLength)

        self.allow_playlists = section_data.get('AllowPlaylists', fallback=PermissionsDefaults.AllowPlaylists)
        self.instaskip = section_data.get('InstaSkip', fallback=PermissionsDefaults.InstaSkip)

        self.validate()

    def validate(self):
        if self.command_whitelist:
            self.command_whitelist = set(self.command_whitelist.lower().split())

        if self.command_blacklist:
            self.command_blacklist = set(self.command_blacklist.lower().split())

        if self.ignore_non_voice:
            self.ignore_non_voice = set(self.ignore_non_voice.lower().split())

        if self.granted_to_roles:
            self.granted_to_roles = set(self.granted_to_roles.split())

        if self.user_list:
            self.user_list = set(self.user_list.split())

        try:
            self.max_songs = max(0, int(self.max_songs))
        except:
            self.max_songs = PermissionsDefaults.MaxSongs

        try:
            self.max_song_length = max(0, int(self.max_song_length))
        except:
            self.max_song_length = PermissionsDefaults.MaxSongLength

        try:
            self.max_playlist_length = max(0, int(self.max_playlist_length))
        except:
            self.max_playlist_length = PermissionsDefaults.MaxPlaylistLength

        self.allow_playlists = configparser.RawConfigParser.BOOLEAN_STATES.get(
            self.allow_playlists, PermissionsDefaults.AllowPlaylists
        )

        self.instaskip = configparser.RawConfigParser.BOOLEAN_STATES.get(
            self.instaskip, PermissionsDefaults.InstaSkip
        )


    def add_user(self, uid):
        self.user_list.add(uid)

    def remove_user(self, uid):
        if uid in self.user_list:
            self.user_list.pop(uid)


    def __repr__(self):
        return "<PermissionGroup: %s>" % self.name

    def __str__(self):
        return "<PermissionGroup: %s: %s>" % (self.name, self.__dict__)
