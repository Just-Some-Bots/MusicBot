import configparser


class PermissionsDefaults:
    perms_file = 'config/permissions.ini'

    CommandWhiteList = set()
    CommandBlackList = set()
    IgnoreNonVoice = set()
    GrantToRoles = set()
    UserList = set()

    MaxSongLength = 0
    MaxSongs = 0

    AllowPlaylists = True


class Permissions:
    def __init__(self, config_file):
        self.config_file = config_file
        self.config = configparser.ConfigParser(default_section='Default')
        self.config.read(config_file)

        self.default_group = PermissionGroup('Default', self.config[self.config.default_section])
        self.groups = set()

        for section in self.config.sections():
            self.groups.add(PermissionGroup(section, self.config[section]))

    def save(self):
        with open(self.config_file, 'w') as f:
            self.config.write(f)

    def for_user(self, user):
        '''
        Returns the first PermissionGroup a user belongs to
        :param user: A discord User or Member object
        '''

        for group in self.groups:
            if user.id in group.user_list:
                return group

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

        self.max_song_length = max(0, section_data.getint('MaxSongLength', fallback=PermissionsDefaults.MaxSongLength))
        self.max_songs = max(0, section_data.getint('MaxSongs', fallback=PermissionsDefaults.MaxSongs))

        self.allow_playlists = section_data.getboolean('AllowPlaylists', fallback=PermissionsDefaults.AllowPlaylists)

        self.verify()

    def verify(self):
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

    def add_user(self, uid):
        self.user_list.add(uid)

    def remove_user(self, uid):
        if uid in self.user_list:
            self.user_list.pop(uid)


    def __repr__(self):
        return "<PermissionGroup: %s>" % self.name

    def __str__(self):
        return "<PermissionGroup: %s: %s>" % (self.name, self.__dict__)
