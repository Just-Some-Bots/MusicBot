import configparser
import logging
import pathlib
import shutil
from typing import TYPE_CHECKING, Dict, List, Set, Tuple, Type, Union

import configupdater
import discord

from . import write_path
from .config import ConfigOption, ConfigOptionRegistry, ExtendedConfigParser, RegTypes
from .constants import (
    DEFAULT_OWNER_GROUP_NAME,
    DEFAULT_PERMS_FILE,
    DEFAULT_PERMS_GROUP_NAME,
    EXAMPLE_PERMS_FILE,
)
from .exceptions import HelpfulError, PermissionsError
from .i18n import _Dd

if TYPE_CHECKING:
    from .bot import MusicBot

log = logging.getLogger(__name__)

PERMS_ALLOW_ALL_EXTRACTOR_NAME: str = "__"


# Permissive class define the permissive value of each default permissions
class PermissionsDefaults:
    """
    Permissions system and PermissionGroup default values.
    Most values restrict access by default.
    """

    command_whitelist: Set[str] = set()
    command_blacklist: Set[str] = set()
    advanced_commandlists: bool = False
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
        "soundcloud",
        "Bandcamp",
        "spotify:musicbot",
    }

    # These defaults are not used per-group but rather for permissions system itself.
    perms_file: pathlib.Path = write_path(DEFAULT_PERMS_FILE)
    example_perms_file: pathlib.Path = write_path(EXAMPLE_PERMS_FILE)


class PermissiveDefaults(PermissionsDefaults):
    """
    The maximum allowed version of defaults.
    Most values grant access or remove limits by default.
    """

    command_whitelist: Set[str] = set()
    command_blacklist: Set[str] = set()
    advanced_commandlists: bool = False
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
        self.groups: Dict[str, PermissionGroup] = {}

        if not self.config.read(self.perms_file, encoding="utf-8"):
            example_file = PermissionsDefaults.example_perms_file
            if example_file.is_file():
                log.warning(
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
            else:
                log.error(
                    "Could not locate config permissions or example permissions files.\n"
                    "MusicBot will generate the config files at the location:\n"
                    "  %(perms_file)s",
                    {"perms_file": self.perms_file.parent},
                )

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

        if not self.perms_file.is_file():
            log.info("Generating new config permissions files...")
            try:
                ex_file = PermissionsDefaults.example_perms_file
                self.register.write_default_ini(ex_file)
                shutil.copy(ex_file, self.perms_file)
                self.config.read(self.perms_file, encoding="utf-8")
            except OSError as e:
                raise HelpfulError(
                    # fmt: off
                    "Error creating default config permissions file.\n"
                    "\n"
                    "Problem:\n"
                    "  MusicBot attempted to generate the config files but failed due to an error:\n"
                    "  %(raw_error)s\n"
                    "\n"
                    "Solution:\n"
                    "  Make sure MusicBot can read and write to your config files.\n",
                    # fmt: on
                    fmt_args={"raw_error": e},
                ) from e

    def _generate_default_group(self, name: str) -> "PermissionGroup":
        """Generate a group with `name` using PermissionDefaults."""
        return PermissionGroup(name, self, PermissionsDefaults)

    def _generate_permissive_group(self, name: str) -> "PermissionGroup":
        """Generate a group with `name` using PermissiveDefaults. Typically owner group."""
        return PermissionGroup(name, self, PermissiveDefaults)

    def set_owner_id(self, owner_id: int) -> None:
        """Sets the given id as the owner ID in the owner permission group."""
        if owner_id == 0:
            log.debug("Config 'OwnerID' is set auto, will set correctly later.")
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
            log.debug("Setting auto 'OwnerID' for owner permissions group.")
            self.owner_group.user_list = {bot.config.owner_id}

    def for_user(self, user: Union[discord.Member, discord.User]) -> "PermissionGroup":
        """
        Returns the first PermissionGroup a user belongs to
        :param user: A discord User or Member object
        """
        # Only ever put Owner in the Owner group.
        if user.id in self.owner_group.user_list:
            return self.owner_group

        # TODO: Maybe we should validate to prevent users in multiple groups...
        # Or complicate things more by merging groups into virtual groups......

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
        Should multi-line values be needed, maybe use ConfigUpdater package instead.
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
                    log.debug("Updating group in permissions file:  %s", group)
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
    _BuiltIn: List[str] = [DEFAULT_PERMS_GROUP_NAME, DEFAULT_OWNER_GROUP_NAME]

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
            option="CommandWhitelist",
            dest="command_whitelist",
            getter="getstrset",
            default=defaults.command_whitelist,
            comment=_Dd(
                "List of command names allowed for use, separated by spaces.\n"
                "Sub-command access can be controlled by adding _ and the sub-command name.\n"
                "That is `config_set` grants only the `set` sub-command of the config command.\n"
                "This option overrides CommandBlacklist if set.\n"
            ),
            empty_display_val="(All allowed)",
        )
        self.command_blacklist = self._mgr.register.init_option(
            section=name,
            option="CommandBlacklist",
            dest="command_blacklist",
            default=defaults.command_blacklist,
            getter="getstrset",
            comment=_Dd(
                "List of command names denied from use, separated by spaces.\n"
                "Will not work if CommandWhitelist is set!"
            ),
            empty_display_val="(None denied)",
        )
        self.advanced_commandlists = self._mgr.register.init_option(
            section=name,
            option="AdvancedCommandLists",
            dest="advanced_commandlists",
            getter="getboolean",
            default=defaults.advanced_commandlists,
            comment=_Dd(
                "When enabled, CommandBlacklist and CommandWhitelist are used together.\n"
                "Only commands in the whitelist are allowed, however sub-commands may be denied by the blacklist.\n"
            ),
        )
        self.ignore_non_voice = self._mgr.register.init_option(
            section=name,
            option="IgnoreNonVoice",
            dest="ignore_non_voice",
            getter="getstrset",
            default=defaults.ignore_non_voice,
            comment=_Dd(
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
            comment=_Dd(
                "List of Discord server role IDs that are granted this permission group.\n"
                "This option is ignored if UserList is set."
            ),
            invisible=True,
        )
        self.user_list = self._mgr.register.init_option(
            section=name,
            option="UserList",
            dest="user_list",
            getter="getidset",
            default=defaults.user_list,
            comment=_Dd(
                "List of Discord member IDs that are granted permissions in this group.\n"
                "This option overrides GrantToRoles."
            ),
            invisible=True,
        )
        self.max_songs = self._mgr.register.init_option(
            section=name,
            option="MaxSongs",
            dest="max_songs",
            getter="getint",
            default=defaults.max_songs,
            comment=_Dd(
                "Maximum number of songs a user is allowed to queue.\n"
                "A value of 0 means unlimited."
            ),
            empty_display_val="(Unlimited)",
        )
        self.max_song_length = self._mgr.register.init_option(
            section=name,
            option="MaxSongLength",
            dest="max_song_length",
            getter="getint",
            default=defaults.max_song_length,
            comment=_Dd(
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
            comment=_Dd(
                "Maximum number of songs a playlist is allowed to have when queued.\n"
                "A value of 0 means unlimited."
            ),
            empty_display_val="(Unlimited)",
        )
        self.max_search_items = self._mgr.register.init_option(
            section=name,
            option="MaxSearchItems",
            dest="max_search_items",
            getter="getint",
            default=defaults.max_search_items,
            comment=_Dd(
                "The maximum number of items that can be returned in a search."
            ),
        )
        self.allow_playlists = self._mgr.register.init_option(
            section=name,
            option="AllowPlaylists",
            dest="allow_playlists",
            getter="getboolean",
            default=defaults.allow_playlists,
            comment=_Dd("Allow users to queue playlists, or multiple songs at once."),
        )
        self.instaskip = self._mgr.register.init_option(
            section=name,
            option="InstaSkip",
            dest="instaskip",
            getter="getboolean",
            default=defaults.insta_skip,
            comment=_Dd(
                "Allow users to skip without voting, if LegacySkip config option is enabled."
            ),
        )
        self.skip_looped = self._mgr.register.init_option(
            section=name,
            option="SkipLooped",
            dest="skip_looped",
            getter="getboolean",
            default=defaults.skip_looped,
            comment=_Dd("Allows the user to skip a looped song."),
        )
        self.remove = self._mgr.register.init_option(
            section=name,
            option="Remove",
            dest="remove",
            getter="getboolean",
            default=defaults.remove,
            comment=_Dd(
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
            comment=_Dd(
                "Skip songs added by users who are not in voice when their song is played."
            ),
        )
        self.bypass_karaoke_mode = self._mgr.register.init_option(
            section=name,
            option="BypassKaraokeMode",
            dest="bypass_karaoke_mode",
            getter="getboolean",
            default=defaults.bypass_karaoke_mode,
            comment=_Dd(
                "Allows the user to add songs to the queue when Karaoke Mode is enabled."
            ),
        )
        self.summonplay = self._mgr.register.init_option(
            section=name,
            option="SummonNoVoice",
            dest="summonplay",
            getter="getboolean",
            default=defaults.summon_no_voice,
            comment=_Dd(
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
            comment=_Dd(
                "Specify yt-dlp extractor names, separated by spaces, that are allowed to be used.\n"
                "When empty, hard-coded defaults are used. The defaults are displayed above, but may change between versions.\n"
                "To allow all extractors, add `%(allow_all)s` without quotes to the list.\n"
                "\n"
                "Services/extractors supported by yt-dlp are listed here:\n"
                "  https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md \n"
                "\n"
                "MusicBot also provides one custom service `spotify:musicbot` to enable or disable Spotify API extraction.\n"
                "NOTICE: MusicBot might not support all services available to yt-dlp!\n"
            ),
            comment_args={"allow_all": PERMS_ALLOW_ALL_EXTRACTOR_NAME},
            empty_display_val="(All allowed)",
        )

        self.validate()
        self._mgr.register.update_missing_config()

    def validate(self) -> None:
        """Validate permission values are within acceptable limits"""
        if self.max_search_items > 100:
            log.warning("Max search items can't be larger than 100. Setting to 100.")
            self.max_search_items = 100

        # if extractors contains the all marker, blank out the list to allow all.
        if PERMS_ALLOW_ALL_EXTRACTOR_NAME in self.extractors:
            self.extractors = set()

        # Make sure to clear the UserList and GrantToRoles options of built-ins.
        if self.name in PermissionGroup._BuiltIn:
            self.user_list.clear()
            self.granted_to_roles.clear()

    def add_user(self, uid: int) -> None:
        """Add given discord User ID to the user list."""
        self.user_list.add(uid)

    def remove_user(self, uid: int) -> None:
        """Remove given discord User ID from the user list."""
        if uid in self.user_list:
            self.user_list.remove(uid)

    def can_use_command(self, command: str, sub: str = "") -> bool:
        """
        Test if the group can use the given command or sub-command.

        :param: command:  The command name to test.
        :param: sub:      The sub-command argument of the command being tested.

        :returns:  boolean:  False if not allowed, True otherwise.
        """
        csub = f"{command}_{sub}"
        terms = [command]
        if sub:
            terms.append(csub)

        if not self.advanced_commandlists:
            if self.command_whitelist and all(
                c not in self.command_whitelist for c in terms
            ):
                return False

            if self.command_blacklist and any(
                c in self.command_blacklist for c in terms
            ):
                return False

        else:
            if self.command_whitelist and all(
                x not in self.command_whitelist for x in terms
            ):
                return False

            if (
                sub
                and command in self.command_whitelist
                and csub in self.command_blacklist
            ):
                return False

            if any(
                c in self.command_blacklist and c in self.command_whitelist
                for c in terms
            ):
                return False
        return True

    def can_use_extractor(self, extractor: str) -> None:
        """
        Test if this group / user can use the given extractor.

        :raises:  PermissionsError  if extractor is not allowed.
        """
        # empty extractor list will allow all extractors.
        if not self.extractors:
            return

        # check the list for any partial matches.
        for allowed in self.extractors:
            if extractor.startswith(allowed):
                return

        # the extractor is not allowed.
        raise PermissionsError(
            "You do not have permission to play the requested media.\n"
            "The yt-dlp extractor `%(extractor)s` is not permitted in your group.",
            fmt_args={"extractor": extractor},
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
        if not config_value and opt.empty_display_val:
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
        # apply a sort to the extractors.
        if option.option == "Extractors":
            conf_value = sorted(list(conf_value))  # type: ignore[arg-type,type-var,assignment]
        return self._value_to_ini(conf_value, option.getter)

    def write_default_ini(self, filename: pathlib.Path) -> bool:
        """Uses registry to generate an example_permissions.ini file."""
        if not isinstance(self._config, Permissions):
            raise RuntimeError("Dev bug, Permissions object expcted.")

        if DEFAULT_OWNER_GROUP_NAME not in self._config.groups:
            self._config.groups[DEFAULT_OWNER_GROUP_NAME] = (
                self._config._generate_permissive_group(  # pylint: disable=protected-access
                    DEFAULT_OWNER_GROUP_NAME
                )
            )
        if DEFAULT_PERMS_GROUP_NAME not in self._config.groups:
            self._config.add_group(DEFAULT_PERMS_GROUP_NAME)

        try:
            cu = configupdater.ConfigUpdater()
            cu.optionxform = str  # type: ignore

            # add the default sections.
            cu.add_section(DEFAULT_OWNER_GROUP_NAME)
            cu.add_section(DEFAULT_PERMS_GROUP_NAME)

            # create the comment documentation and fill in defaults for each section.
            docs = ""
            for opt in self.option_list:
                if opt.section not in [
                    DEFAULT_OWNER_GROUP_NAME,
                    DEFAULT_PERMS_GROUP_NAME,
                ]:
                    continue
                dval = self.to_ini(opt, use_default=True)
                cu[opt.section][opt.option] = dval
                if opt.section == DEFAULT_PERMS_GROUP_NAME:
                    if opt.comment_args:
                        comment = opt.comment % opt.comment_args
                    else:
                        comment = opt.comment
                    comment = "".join(
                        f"    {c}\n" for c in comment.split("\n")
                    ).rstrip()
                    docs += f" {opt.option} = {dval}\n{comment}\n\n"

            # add comments to head of file.
            adder = cu[DEFAULT_OWNER_GROUP_NAME].add_before
            head_comment = (
                "This is the permissions file for MusicBot. Do not edit this file using Notepad.\n"
                "Use Notepad++ or a code editor like Visual Studio Code.\n"
                "For help, see: https://just-some-bots.github.io/MusicBot/ \n"
                "\n"
                "This file was generated by MusicBot, it contains all options set to their default values.\n"
                "\n"
                "Basics:\n"
                "- Lines starting with semicolons (;) are comments, and are ignored.\n"
                "- Words in square brackets [ ] are permission group names.\n"
                "- Group names must be unique, and cannot be duplicated.\n"
                "- Each group must have at least one permission option defined.\n"
                "- [Default] is a reserved section. Users without a specific group assigned will use it.\n"
                "- [Owner (auto)] is a reserved section that cannot be removed, used by the Owner user.\n"
                "\nAvailable Options:\n"
                f"{docs}"
            ).strip()
            for line in head_comment.split("\n"):
                adder.comment(line, comment_prefix=";")
            adder.space()
            adder.space()

            # add owner section comment
            owner_comment = (
                "This permission group is used by the Owner only, it cannot be deleted or renamed.\n"
                "It's options only apply to Owner user set in the 'OwnerID' config option.\n"
                "You cannot set the UserList or GrantToRoles options in this group.\n"
                "This group does not control access to owner-only commands."
            )
            for line in owner_comment.split("\n"):
                adder.comment(line, comment_prefix=";")

            # add default section comment
            default_comment = (
                "This is the default permission group. It cannot be deleted or renamed.\n"
                "All users without explicit group assignment will be placed in this group.\n"
                "The options GrantToRoles and UserList are effectively ignored in this group.\n"
                "If you want to use the above options, add a new [Group] to the file."
            )
            adder = cu[DEFAULT_PERMS_GROUP_NAME].add_before
            adder.space()
            adder.space()
            for line in default_comment.split("\n"):
                adder.comment(line, comment_prefix=";")

            with open(filename, "w", encoding="utf8") as fp:
                cu.write(fp)

            return True
        except (
            configparser.DuplicateSectionError,
            configparser.ParsingError,
            OSError,
            AttributeError,
        ):
            log.exception("Failed to save default INI file at:  %s", filename)
            return False
