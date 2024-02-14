import configparser
import logging
import pathlib
import shutil
from typing import TYPE_CHECKING, Any, Dict, List, Set, Union

import discord

from .config import ExtendedConfigParser
from .constants import DEFAULT_PERMS_FILE, EXAMPLE_PERMS_FILE

if TYPE_CHECKING:
    from .bot import MusicBot

log = logging.getLogger(__name__)

# Permissive class define the permissive value of each permissions


class PermissionsDefaults:
    """
    Permissions system and PermissionGroup default values.
    Most values restrict access by default.
    """

    perms_file: pathlib.Path = pathlib.Path(DEFAULT_PERMS_FILE)
    example_perms_file: pathlib.Path = pathlib.Path(EXAMPLE_PERMS_FILE)

    CommandWhiteList: Set[str] = set()
    CommandBlackList: Set[str] = set()
    IgnoreNonVoice: Set[str] = set()
    GrantToRoles: Set[int] = set()
    UserList: Set[int] = set()

    MaxSongs: int = 8
    MaxSongLength: int = 210
    MaxPlaylistLength: int = 0
    MaxSearchItems: int = 10

    AllowPlaylists: bool = True
    InstaSkip: bool = False
    SkipLooped: bool = False
    Remove: bool = False
    SkipWhenAbsent: bool = True
    BypassKaraokeMode: bool = False

    SummonNoVoice: bool = False

    # allow at least the extractors that the bot normally needs.
    # an empty set here allows all.
    Extractors: Set[str] = {
        "generic",
        "youtube",
        "youtube:tab",
        "youtube:search",
        "youtube:playlist",
        "spotify:musicbot",
    }


class Permissive:
    CommandWhiteList: Set[str] = set()
    CommandBlackList: Set[str] = set()
    IgnoreNonVoice: Set[str] = set()
    GrantToRoles: Set[int] = set()
    UserList: Set[int] = set()

    MaxSongs: int = 0
    MaxSongLength: int = 0
    MaxPlaylistLength: int = 0
    MaxSearchItems: int = 10

    AllowPlaylists: bool = True
    InstaSkip: bool = True
    SkipLooped: bool = True
    Remove: bool = True
    SkipWhenAbsent: bool = False
    BypassKaraokeMode: bool = True

    SummonNoVoice: bool = True

    Extractors: Set[str] = set()


class Permissions:
    def __init__(self, perms_file: pathlib.Path, grant_all: List[int]) -> None:
        """
        Handles locating, initializing defaults, loading, and validating
        permissions config from the given `perms_file` path.

        :param: grant_all:  a list of discord User IDs to grant permissive defaults.
        """
        self.perms_file = perms_file
        self.config = ExtendedConfigParser(interpolation=None)

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

        self.default_group = PermissionGroup("Default", self.config["Default"])
        self.groups = set()

        for section in self.config.sections():
            if section != "Owner (auto)":
                self.groups.add(PermissionGroup(section, self.config[section]))

        if self.config.has_section("Owner (auto)"):
            owner_group = PermissionGroup(
                "Owner (auto)", self.config["Owner (auto)"], fallback=Permissive
            )

        else:
            log.info(
                "[Owner (auto)] section not found, falling back to permissive default"
            )
            # Create a fake section to fallback onto the default permissive values to grant to the owner
            owner_group = PermissionGroup(
                "Owner (auto)",
                configparser.SectionProxy(self.config, "Owner (auto)"),
                fallback=Permissive,
            )

        if hasattr(grant_all, "__iter__"):
            owner_group.user_list = set(grant_all)

        self.groups.add(owner_group)

    async def async_validate(self, bot: "MusicBot") -> None:
        """
        Handle validation of permissions data that depends on async services.
        """
        log.debug("Validating permissions...")

        og = discord.utils.get(self.groups, name="Owner (auto)")
        if not og:
            raise RuntimeError("Owner permissions group is missing!")

        if 0 in og.user_list:
            log.debug("Fixing automatic owner group")
            og.user_list = {bot.config.owner_id}

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

        for group in self.groups:
            if user.id in group.user_list:
                return group

        # The only way I could search for roles is if I add a `server=None` param and pass that too
        if isinstance(user, discord.User):
            return self.default_group

        # We loop again so that we don't return a role based group before we find an assigned one
        for group in self.groups:
            for role in user.roles:
                if role.id in group.granted_to_roles:
                    return group

        return self.default_group

    def create_group(self, name: str, **kwargs: Dict[str, Any]) -> None:
        """
        Currently unused, intended to create a permission group that could
        then be saved back to the permissions config file.
        """
        # TODO: Test this.  and implement the rest of permissions editing...
        self.config.read_dict({name: kwargs})
        self.groups.add(PermissionGroup(name, self.config[name]))


class PermissionGroup:
    def __init__(
        self,
        name: str,
        section_data: configparser.SectionProxy,
        fallback: Any = PermissionsDefaults,
    ) -> None:
        """
        Create a PermissionGroup object from a ConfigParser section.

        :param: name:  the name of the group
        :param: section_data:  a config SectionProxy that describes a group
        :param: fallback:  Typically a PermissionsDefaults class
        """
        self.name = name

        self.command_whitelist = section_data.getstrset(
            "CommandWhiteList", fallback=fallback.CommandWhiteList
        )
        self.command_blacklist = section_data.getstrset(
            "CommandBlackList", fallback=fallback.CommandBlackList
        )
        self.ignore_non_voice = section_data.getstrset(
            "IgnoreNonVoice", fallback=fallback.IgnoreNonVoice
        )
        self.granted_to_roles = section_data.getidset(
            "GrantToRoles", fallback=fallback.GrantToRoles
        )
        self.user_list = section_data.getidset("UserList", fallback=fallback.UserList)

        self.max_songs = section_data.getint("MaxSongs", fallback=fallback.MaxSongs)
        self.max_song_length = section_data.getint(
            "MaxSongLength", fallback=fallback.MaxSongLength
        )
        self.max_playlist_length = section_data.getint(
            "MaxPlaylistLength", fallback=fallback.MaxPlaylistLength
        )
        self.max_search_items = section_data.getint(
            "MaxSearchItems", fallback=fallback.MaxSearchItems
        )

        self.allow_playlists = section_data.getboolean(
            "AllowPlaylists", fallback=fallback.AllowPlaylists
        )
        self.instaskip = section_data.getboolean(
            "InstaSkip", fallback=fallback.InstaSkip
        )
        self.skiplooped = section_data.getboolean(
            "SkipLooped", fallback=fallback.SkipLooped
        )
        self.remove = section_data.getboolean("Remove", fallback=fallback.Remove)
        self.skip_when_absent = section_data.getboolean(
            "SkipWhenAbsent", fallback=fallback.SkipWhenAbsent
        )
        self.bypass_karaoke_mode = section_data.getboolean(
            "BypassKaraokeMode", fallback=fallback.BypassKaraokeMode
        )

        self.summonplay = section_data.getboolean(
            "SummonNoVoice", fallback=fallback.SummonNoVoice
        )

        self.extractors = section_data.getstrset(
            "Extractors", fallback=fallback.Extractors
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

    def __repr__(self) -> str:
        return f"<PermissionGroup: {self.name}>"

    def __str__(self) -> str:
        return f"<PermissionGroup: {self.name}: {self.__dict__}>"
