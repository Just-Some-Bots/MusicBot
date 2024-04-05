import configparser
import logging
import pathlib
import shutil
from typing import TYPE_CHECKING, Dict, Set, Tuple, Type, Union

import configupdater
import discord

from .config import ConfigOption, ConfigOptionRegistry, ExtendedConfigParser, RegTypes
from .constants import (
    DEFAULT_OWNER_GROUP_NAME,
    DEFAULT_PERMS_FILE,
    DEFAULT_PERMS_GROUP_NAME,
    EXAMPLE_PERMS_FILE,
)
from .exceptions import HelpfulError, PermissionsError

if TYPE_CHECKING:
    from .bot import MusicBot

log = logging.getLogger(__name__)


# Permissive class define the permissive value of each permissions


class PermissionsDefaults:
    """
    Permissions system and PermissionGroup default values.
    Most values restrict access by default.
    """

    command_whitelist: Set[str] = set()
    command_blacklist: Set[str] = set()
    ignore_non_voice: Set[str] = set()
    grant_to_roles: Set[int] = set()
    user_list: Set[int] = set()

    max_songs: int = 8
    max_song_length: int = 210
    max_playlist_length: int = 0
    max_search_items: int = 10

    allow_playlists: bool = True
    insta_skip: bool = False
    skip_looped: bool = False
    remove: bool = False
    skip_when_absent: bool = True
    bypass_karaoke_mode: bool = False

    summon_no_voice: bool = False

    # allow at least the extractors that the bot normally needs.
    # an empty set here allows all.
    extractors: Set[str] = {
        "generic",
        "youtube",
        "youtube:tab",
        "youtube:search",
        "youtube:playlist",
        "spotify:musicbot",
    }

    # These defaults are not used per-group but rather for permissions system itself.
    perms_file: pathlib.Path = pathlib.Path(DEFAULT_PERMS_FILE)
    example_perms_file: pathlib.Path = pathlib.Path(EXAMPLE_PERMS_FILE)


class PermissiveDefaults(PermissionsDefaults):
    """
    The maxiumum allowed version of defaults.
    Most values grant access or remove limits by default.
    """

    command_whitelist: Set[str] = set()
    command_blacklist: Set[str] = set()
    ignore_non_voice: Set[str] = set()
    grant_to_roles: Set[int] = set()
    user_list: Set[int] = set()

    max_songs: int = 0
    max_song_length: int = 0
    max_playlist_length: int = 0
    max_search_items: int = 10

    allow_playlists: bool = True
    insta_skip: bool = True
    skip_looped: bool = True
    remove: bool = True
    skip_when_absent: bool = False
    bypass_karaoke_mode: bool = True

    summon_no_voice: bool = True

    # an empty set here allows all.
    extractors: Set[str] = set()


class Permissions:
    def __init__(self, perms_file: pathlib.Path) -> None:
        """
        Handles locating, initializing defaults, loading, and validating
        permissions config from the given `perms_file` path.

        :param: grant_all:  a list of discord User IDs to grant permissive defaults.
        """
        self.perms_file = perms_file
        self.config = ExtendedConfigParser()
        self.register = PermissionOptionRegistry(self, self.config)
        self.groups: Dict[str, "PermissionGroup"] = {}

        if not self.config.read(self.perms_file, encoding="utf-8"):
            example_file = PermissionsDefaults.example_perms_file
            log.info(
                "Permissions file not found, copying from:  %s",
                example_file,
            )

            try:
                shutil.copy(example_file, self.perms_file)
                self.config.read(self.perms_file, encoding="utf-8")

            except Exception as e:
                log.exception(
                    "Error copying example permissions file:  %s", example_file
                )
                raise RuntimeError(
                    f"Unable to copy {example_file} to {self.perms_file}:  {str(e)}"
                ) from e

        for section in self.config.sections():
            if section == DEFAULT_OWNER_GROUP_NAME:
                self.groups[section] = self._generate_permissive_group(section)
            else:
                self.groups[section] = self._generate_default_group(section)

        # in case the permissions don't have a default group, make one.
        if not self.config.has_section(DEFAULT_PERMS_GROUP_NAME):
            self.groups[DEFAULT_PERMS_GROUP_NAME] = self._generate_default_group(
                DEFAULT_PERMS_GROUP_NAME
            )

        # in case the permissions don't have an owner group, create a virtual one.
        if not self.config.has_section(DEFAULT_OWNER_GROUP_NAME):
            self.groups[DEFAULT_OWNER_GROUP_NAME] = self._generate_permissive_group(
                DEFAULT_OWNER_GROUP_NAME
            )

        self.register.validate_register_destinations()

    def _generate_default_group(self, name: str) -> "PermissionGroup":
        """Generate a group with `name` using PermissionDefaults."""
        return PermissionGroup(name, self, PermissionsDefaults)

    def _generate_permissive_group(self, name: str) -> "PermissionGroup":
        """Generate a group with `name` using PermissiveDefaults. Typically owner group."""
        return PermissionGroup(name, self, PermissiveDefaults)

    def set_owner_id(self, owner_id: int) -> None:
        """Sets the given id as the owner ID in the owner permission group."""
        if owner_id == 0:
            log.debug("OwnerID is set auto, will set correctly later.")
        self.groups[DEFAULT_OWNER_GROUP_NAME].user_list = set([owner_id])

    @property
    def owner_group(self) -> "PermissionGroup":
        """Always returns the owner group"""
        return self.groups[DEFAULT_OWNER_GROUP_NAME]

    @property
    def default_group(self) -> "PermissionGroup":
        """Always returns the default group"""
        return self.groups[DEFAULT_PERMS_GROUP_NAME]

    async def async_validate(self, bot: "MusicBot") -> None:
        """
        Handle validation of permissions data that depends on async services.
        """
        log.debug("Validating permissions...")
        if 0 in self.owner_group.user_list:
            log.debug("Setting auto OwnerID for owner permissions group.")
            self.owner_group.user_list = {bot.config.owner_id}

    def save(self) -> None:
        """
        Currently unused function intended to write permissions back to
        its configuration file.
        """
        with open(self.perms_file, "w", encoding="utf8") as f:
            self.config.write(f)

    def for_user(self, user: Union[discord.Member, discord.User]) -> "PermissionGroup":
        """
        Returns the first PermissionGroup a user belongs to
        :param user: A discord User or Member object
        """

        # Search for the first group a member ID shows up in.
        for group in self.groups.values():
            if user.id in group.user_list:
                return group

        # In case this is not a Member and has no roles, use default.
        if isinstance(user, discord.User):
            return self.default_group

        # Search groups again and associate the member by role IDs.
        for group in self.groups.values():
            for role in user.roles:
                if role.id in group.granted_to_roles:
                    return group

        # Or just assign default role.
        return self.default_group

    def add_group(self, name: str) -> None:
        """
        Creates a permission group, but does nothing to the parser.
        """
        self.groups[name] = self._generate_default_group(name)

    def remove_group(self, name: str) -> None:
        """Removes a permission group but does nothing to the parser."""
        del self.groups[name]
        self.register.unregister_group(name)

    def save_group(self, group: str) -> bool:
        """
        Converts the current Permission Group value into an INI file value as needed.
        Note: ConfigParser must not use multi-line values. This will break them.
        Should multiline values be needed, maybe use ConfigUpdater package instead.
        """
        try:
            cu = configupdater.ConfigUpdater()
            cu.optionxform = str  # type: ignore
            cu.read(self.perms_file, encoding="utf8")

            opts = self.register.get_option_dict(group)
            # update/delete existing
            if group in set(cu.keys()):
                # update
                if group in self.groups:
                    log.debug("Updating group in permssions file:  %s", group)
                    for option in set(cu[group].keys()):
                        cu[group][option].value = self.register.to_ini(opts[option])

                # delete
                else:
                    log.debug("Deleting group from permissions file:  %s", group)
                    cu.remove_section(group)

            # add new
            elif group in self.groups:
                log.debug("Adding new group to permissions file:  %s", group)
                options = ""
                for _, opt in opts.items():
                    c_bits = opt.comment.split("\n")
                    if len(c_bits) > 1:
                        comments = "".join([f"# {x}\n" for x in c_bits])
                    else:
                        comments = f"# {opt.comment.strip()}\n"
                    ini_val = self.register.to_ini(opt)
                    options += f"{comments}{opt.option} = {ini_val}\n\n"
                new_section = configupdater.ConfigUpdater()
                new_section.optionxform = str  # type: ignore
                new_section.read_string(f"[{group}]\n{options}\n")
                cu.add_section(new_section[group].detach())

            log.debug("Saving permissions file now.")
            cu.update_file()
            return True

        # except configparser.MissingSectionHeaderError:
        except configparser.ParsingError:
            log.exception("ConfigUpdater could not parse the permissions file!")
        except configparser.DuplicateSectionError:
            log.exception("You have a duplicate section, fix your Permissions file!")
        except OSError:
            log.exception("Failed to save permissions group:  %s", group)

        return False

    def update_option(self, option: ConfigOption, value: str) -> bool:
        """
        Uses option data to parse the given value and update its associated permission.
        No data is saved to file however.
        """
        tparser = ExtendedConfigParser()
        tparser.read_dict({option.section: {option.option: value}})

        try:
            get = getattr(tparser, option.getter, None)
            if not get:
                log.critical("Dev Bug! Permission has getter that is not available.")
                return False
            new_conf_val = get(option.section, option.option, fallback=option.default)
            if not isinstance(new_conf_val, type(option.default)):
                log.error(
                    "Dev Bug! Permission has invalid type, getter and default must be the same type."
                )
                return False
            setattr(self.groups[option.section], option.dest, new_conf_val)
            return True
        except (HelpfulError, ValueError, TypeError):
            return False


class PermissionGroup:
    def __init__(
        self,
        name: str,
        manager: Permissions,
        defaults: Type[PermissionsDefaults],
    ) -> None:
        """
        Create a PermissionGroup object from a ConfigParser section.

        :param: name:  the name of the group
        :param: section_data:  a config SectionProxy that describes a group
        :param: fallback:  Typically a PermissionsDefaults class
        """
        self._mgr = manager

        self.name = name

        self.command_whitelist = self._mgr.register.init_option(
            section=name,
            option="CommandWhiteList",
            dest="command_whitelist",
            getter="getstrset",
            default=defaults.command_whitelist,
            comment="List of command names allowed for use, separated by spaces. Overrides CommandBlackList is set.",
            empty_display_val="(All allowed)",
        )
        self.command_blacklist = self._mgr.register.init_option(
            section=name,
            option="CommandBlackList",
            dest="command_blacklist",
            default=defaults.command_blacklist,
            getter="getstrset",
            comment="List of command names denied from use, separated by spaces. Will not work if CommandWhiteList is set!",
            empty_display_val="(None denied)",
        )
        self.ignore_non_voice = self._mgr.register.init_option(
            section=name,
            option="IgnoreNonVoice",
            dest="ignore_non_voice",
            getter="getstrset",
            default=defaults.ignore_non_voice,
            comment=(
                "List of command names that can only be used while in the same voice channel as MusicBot.\n"
                "Some commands will always require the user to be in voice, regardless of this list.\n"
                "Command names should be separated by spaces."
            ),
            empty_display_val="(No commands listed)",
        )
        self.granted_to_roles = self._mgr.register.init_option(
            section=name,
            option="GrantToRoles",
            dest="granted_to_roles",
            getter="getidset",
            default=defaults.grant_to_roles,
            comment="List of Discord server role IDs that are granted this permission group. This option is ignored if UserList is set.",
            invisible=True,
        )
        self.user_list = self._mgr.register.init_option(
            section=name,
            option="UserList",
            dest="user_list",
            getter="getidset",
            default=defaults.user_list,
            comment="List of Discord member IDs that are granted permissions in this group. This option overrides GrantToRoles.",
            invisible=True,
        )
        self.max_songs = self._mgr.register.init_option(
            section=name,
            option="MaxSongs",
            dest="max_songs",
            getter="getint",
            default=defaults.max_songs,
            comment="Maximum number of songs a user is allowed to queue. A value of 0 means unlimited.",
            empty_display_val="(Unlimited)",
        )
        self.max_song_length = self._mgr.register.init_option(
            section=name,
            option="MaxSongLength",
            dest="max_song_length",
            getter="getint",
            default=defaults.max_song_length,
            comment=(
                "Maximum length of a song in seconds. A value of 0 means unlimited.\n"
                "This permission may not be enforced if song duration is not available."
            ),
            empty_display_val="(Unlimited)",
        )
        self.max_playlist_length = self._mgr.register.init_option(
            section=name,
            option="MaxPlaylistLength",
            dest="max_playlist_length",
            getter="getint",
            default=defaults.max_playlist_length,
            comment="Maximum number of songs a playlist is allowed to have to be queued. A value of 0 means unlimited.",
            empty_display_val="(Unlimited)",
        )
        self.max_search_items = self._mgr.register.init_option(
            section=name,
            option="MaxSearchItems",
            dest="max_search_items",
            getter="getint",
            default=defaults.max_search_items,
            comment="The maximum number of items that can be returned in a search.",
        )
        self.allow_playlists = self._mgr.register.init_option(
            section=name,
            option="AllowPlaylists",
            dest="allow_playlists",
            getter="getboolean",
            default=defaults.allow_playlists,
            comment="Allow users to queue playlists, or multiple songs at once.",
        )
        self.instaskip = self._mgr.register.init_option(
            section=name,
            option="InstaSkip",
            dest="instaskip",
            getter="getboolean",
            default=defaults.insta_skip,
            comment="Allow users to skip without voting, if LegacySkip config option is enabled.",
        )
        self.skip_looped = self._mgr.register.init_option(
            section=name,
            option="SkipLooped",
            dest="skip_looped",
            getter="getboolean",
            default=defaults.skip_looped,
            comment="Allows the user to skip a looped song.",
        )
        self.remove = self._mgr.register.init_option(
            section=name,
            option="Remove",
            dest="remove",
            getter="getboolean",
            default=defaults.remove,
            comment=(
                "Allows the user to remove any song from the queue.\n"
                "Does not remove or skip currently playing songs."
            ),
        )
        self.skip_when_absent = self._mgr.register.init_option(
            section=name,
            option="SkipWhenAbsent",
            dest="skip_when_absent",
            getter="getboolean",
            default=defaults.skip_when_absent,
            comment="Skip songs added by users who are not in voice when their song is played.",
        )
        self.bypass_karaoke_mode = self._mgr.register.init_option(
            section=name,
            option="BypassKaraokeMode",
            dest="bypass_karaoke_mode",
            getter="getboolean",
            default=defaults.bypass_karaoke_mode,
            comment="Allows the user to add songs to the queue when Karaoke Mode is enabled.",
        )
        self.summonplay = self._mgr.register.init_option(
            section=name,
            option="SummonNoVoice",
            dest="summonplay",
            getter="getboolean",
            default=defaults.summon_no_voice,
            comment=(
                "Auto summon to user voice channel when using play commands, if bot isn't in voice already.\n"
                "The summon command must still be allowed for this group!"
            ),
        )
        self.extractors = self._mgr.register.init_option(
            section=name,
            option="Extractors",
            dest="extractors",
            getter="getstrset",
            default=defaults.extractors,
            comment=(
                "List of yt_dlp extractor keys, separated by spaces, that are allowed to be used.\n"
                "Services supported by yt_dlp shown here:  https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md \n"
                "MusicBot also provides one custom service `spotify:musicbot` to enable or disable spotify API extraction.\n"
                "NOTICE: MusicBot might not support all services available to yt_dlp!\n"
            ),
            empty_display_val="(All allowed)",
        )

        self.validate()

    def validate(self) -> None:
        """Validate permission values are within acceptable limits"""
        if self.max_search_items > 100:
            log.warning("Max search items can't be larger than 100. Setting to 100.")
            self.max_search_items = 100

    def add_user(self, uid: int) -> None:
        """Add given discord User ID to the user list."""
        self.user_list.add(uid)

    def remove_user(self, uid: int) -> None:
        """Remove given discord User ID from the user list."""
        if uid in self.user_list:
            self.user_list.remove(uid)

    def can_use_command(self, command: str) -> None:
        """
        Test if command is enabled in this permission group.

        :raises:  PermissionsError  if command is denied from use.
        """
        if self.command_whitelist and command not in self.command_whitelist:
            raise PermissionsError(
                f"This command is not enabled for your group ({self.name}).",
                expire_in=20,
            )

        if self.command_blacklist and command in self.command_blacklist:
            raise PermissionsError(
                f"This command is disabled for your group ({self.name}).",
                expire_in=20,
            )

    def format(self, for_user: bool = False) -> str:
        """
        Format the current group values into INI-like text.

        :param: for_user:  Present values for display, instead of literal values.
        """
        perms = f"Permission group name:  {self.name}\n"
        for opt in self._mgr.register.option_list:
            if opt.section != self.name:
                continue
            if opt.invisible and for_user:
                continue
            val = self._mgr.register.to_ini(opt)
            if not val and opt.empty_display_val:
                val = opt.empty_display_val
            perms += f"{opt.option} = {val}\n"
        return perms

    def __repr__(self) -> str:
        return f"<PermissionGroup: {self.name}>"

    def __str__(self) -> str:
        return f"<PermissionGroup: {self.name}: {self.__dict__}>"


class PermissionOptionRegistry(ConfigOptionRegistry):
    def __init__(self, config: Permissions, parser: ExtendedConfigParser) -> None:
        super().__init__(config, parser)

    def validate_register_destinations(self) -> None:
        """Check all configured options for matching destination definitions."""
        if not isinstance(self._config, Permissions):
            raise RuntimeError(
                "Dev Bug! Somehow this is Config when it should be Permissions."
            )

        errors = []
        for opt in self._option_list:
            if not hasattr(self._config.groups[opt.section], opt.dest):
                errors.append(
                    f"Permission `{opt}` has an missing destination named:  {opt.dest}"
                )
        if errors:
            msg = "Dev Bug!  Some permissions failed validation.\n"
            msg += "\n".join(errors)
            raise RuntimeError(msg)

    @property
    def distinct_options(self) -> Set[str]:
        """Unique Permission names for Permission groups."""
        return self._distinct_options

    def get_option_dict(self, group: str) -> Dict[str, ConfigOption]:
        """Get only ConfigOptions for the group, in a dict by option name."""
        return {opt.option: opt for opt in self.option_list if opt.section == group}

    def unregister_group(self, group: str) -> None:
        """Removes all registered options for group."""
        new_opts = []
        for opt in self.option_list:
            if opt.section == group:
                continue
            new_opts.append(opt)
        self._option_list = new_opts

    def get_values(self, opt: ConfigOption) -> Tuple[RegTypes, str, str]:
        """
        Get the values in PermissionGroup and *ConfigParser for this option.
        Returned tuple contains parsed value, ini-string, and a display string
        for the parsed config value if applicable.
        Display string may be empty if not used.
        """
        if not isinstance(self._config, Permissions):
            raise RuntimeError(
                "Dev Bug! Somehow this is Config when it should be Permissions."
            )

        if not opt.editable:
            return ("", "", "")

        if opt.section not in self._config.groups:
            raise ValueError(
                f"Dev Bug! PermissionGroup named `{opt.section}` does not exist."
            )

        if not hasattr(self._config.groups[opt.section], opt.dest):
            raise AttributeError(
                f"Dev Bug! Attribute `PermissionGroup.{opt.dest}` does not exist."
            )

        if not hasattr(self._parser, opt.getter):
            raise AttributeError(
                f"Dev Bug! Method `*ConfigParser.{opt.getter}` does not exist."
            )

        parser_get = getattr(self._parser, opt.getter)
        config_value = getattr(self._config.groups[opt.section], opt.dest)
        parser_value = parser_get(opt.section, opt.option, fallback=opt.default)

        display_config_value = ""
        if not display_config_value and opt.empty_display_val:
            display_config_value = opt.empty_display_val

        return (config_value, parser_value, display_config_value)

    def get_parser_value(self, opt: ConfigOption) -> RegTypes:
        """returns the parser's parsed value for the given option."""
        getter = getattr(self._parser, opt.getter, None)
        if getter is None:
            raise AttributeError(
                f"Dev Bug! Attribute *ConfigParser.{opt.getter} does not exist."
            )

        val: RegTypes = getter(opt.section, opt.option, fallback=opt.default)
        if not isinstance(val, type(opt.default)):
            raise TypeError("Dev Bug!  Type from parser does not match default type.")
        return val

    def to_ini(self, option: ConfigOption, use_default: bool = False) -> str:
        """
        Convert the parsed permission value into an INI value.
        This method does not perform validation, simply converts the value.

        :param: use_default:  return the default value instead of current config.
        """
        if not isinstance(self._config, Permissions):
            raise RuntimeError(
                "Dev Bug! Registry does not have Permissions config object."
            )

        if use_default:
            conf_value = option.default
        else:
            if option.section not in self._config.groups:
                raise ValueError(f"No PermissionGroup by the name `{option.section}`")

            group = self._config.groups[option.section]
            if not hasattr(group, option.dest):
                raise AttributeError(
                    f"Dev Bug! Attribute `PermissionGroup.{option.dest}` does not exist."
                )

            conf_value = getattr(group, option.dest)
        return self._value_to_ini(conf_value, option.getter)
