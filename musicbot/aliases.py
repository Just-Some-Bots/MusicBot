import json
import logging
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any, DefaultDict, Dict, List, Tuple

from .constants import DEFAULT_COMMAND_ALIAS_FILE, EXAMPLE_COMMAND_ALIAS_FILE
from .exceptions import HelpfulError

log = logging.getLogger(__name__)

RawAliasJSON = Dict[str, Any]
CommandTuple = Tuple[str, str]  # (cmd, args)
AliasTuple = Tuple[str, str]  # (alias, args)
AliasesDict = Dict[str, CommandTuple]  # {alias: (cmd, args)}
CommandDict = DefaultDict[str, List[AliasTuple]]  # {cmd: [(alias, args),]}


class Aliases:
    """
    Aliases class provides a method of duplicating commands under different names or
    providing reduction in keystrokes for multi-argument commands.
    Command alias with conflicting names will overload each other, it is up to
    the user to avoid configuring aliases with conflicts.
    """

    def __init__(self, aliases_file: Path, nat_cmds: List[str]) -> None:
        """
        Handle locating, initializing, loading, and validation of command aliases.
        If given `aliases_file` is not found, examples will be copied to the location.

        :raises: musicbot.exceptions.HelpfulError
            if loading fails in some known way.
        """
        # List of "natural" commands to allow.
        self.nat_cmds: List[str] = nat_cmds
        # File Path used to locate and load the alias json.
        self.aliases_file: Path = aliases_file
        # "raw" dict from json file.
        self.aliases_seed: RawAliasJSON = AliasesDefault.aliases_seed
        # Simple aliases
        self.aliases: AliasesDict = AliasesDefault.complex_aliases
        # Reverse lookup list generated when loading aliases.
        self.cmd_aliases: CommandDict = defaultdict(list)

        # find aliases file
        if not self.aliases_file.is_file():
            example_aliases = Path(EXAMPLE_COMMAND_ALIAS_FILE)
            if example_aliases.is_file():
                shutil.copy(str(example_aliases), str(self.aliases_file))
                log.warning("Aliases file not found, copying example_aliases.json")
            else:
                raise HelpfulError(
                    # fmt: off
                    "Error while loading aliases.\n"
                    "\n"
                    "Problem:\n"
                    "  Your aliases files (aliases.json & example_aliases.json) are missing.\n"
                    "\n"
                    "Solution:\n"
                    "  Replace the alias config file(s) or copy them from:\n"
                    "    https://github.com/Just-Some-Bots/MusicBot/",
                    # fmt: on
                )

        # parse json
        self.load()

    def load(self) -> None:
        """
        Attempt to load/decode JSON and determine which version of aliases we have.
        """
        # parse json
        try:
            with self.aliases_file.open() as f:
                self.aliases_seed = json.load(f)
        except OSError as e:
            log.error(
                "Failed to load aliases file:  %s",
                self.aliases_file,
                exc_info=e,
            )
            self.aliases_seed = AliasesDefault.aliases_seed
            return
        except json.JSONDecodeError as e:
            log.error(
                "Failed to parse aliases file:  %s\n"
                "Ensure the file contains valid JSON and restart the bot.",
                self.aliases_file,
                exc_info=e,
            )
            self.aliases_seed = AliasesDefault.aliases_seed
            return

        # clear aliases data
        self.aliases.clear()
        self.cmd_aliases.clear()

        # Create an alias-to-command map from the JSON.
        for cmd, aliases in self.aliases_seed.items():
            # ignore comments
            if cmd.lower() in ["--comment", "--comments"]:
                continue

            # check for spaces, and handle args in cmd alias if they exist.
            cmd_args = ""
            if " " in cmd:
                cmd_bits = cmd.split(" ", maxsplit=1)
                if len(cmd_bits) > 1:
                    cmd = cmd_bits[0]
                    cmd_args = cmd_bits[1].strip()
                cmd = cmd.strip()

            # ensure command name is valid.
            if self.nat_cmds and cmd not in self.nat_cmds:
                log.error(
                    "Aliases skipped for non-existent command:  %(command)s  ->  %(aliases)s",
                    {"command": cmd, "aliases": aliases},
                )
                continue

            # ensure alias data uses valid types.
            if not isinstance(cmd, str) or not isinstance(aliases, list):
                log.error(
                    "Alias(es) skipped for invalid alias data:  %(command)s  ->  %(aliases)s",
                    {"command": cmd, "aliases": aliases},
                )
                continue

            # Loop over given aliases and associate them.
            for alias in aliases:
                alias = alias.lower()
                if alias in self.aliases:
                    log.error(
                        "Alias `%(alias)s` skipped as already exists on command:  %(command)s",
                        {"alias": alias, "command": self.aliases[alias]},
                    )
                    continue

                self.aliases.update({alias: (cmd, cmd_args)})
                self.cmd_aliases[cmd].append((alias, cmd_args))

    def save(self) -> None:
        """
        Save the aliases in memory to the disk.

        :raises: OSError if open for write fails.
        :raises: RuntimeError if something fails to encode.
        """
        try:
            with self.aliases_file.open(mode="w") as f:
                json.dump(self.aliases_seed, f, indent=4, sort_keys=True)
        except (ValueError, TypeError, RecursionError) as e:
            raise RuntimeError("JSON could not be saved.") from e

    def from_alias(self, alias_name: str) -> Tuple[str, str]:
        """
        Get the command name the given `alias_name` refers to.
        Returns a two-member tuple containing the command name and any args for
        the command alias in the case of complex aliases.
        """
        cmd_name, cmd_args = self.aliases.get(alias_name, ("", ""))

        # If no alias at all, return nothing.
        if not cmd_name:
            return ("", "")

        return (cmd_name, cmd_args)

    def for_command(self, cmd_name: str) -> List[Tuple[str, str]]:
        """
        Get the aliases registered for a given command.
        Returns a list of two-member tuples containing the alias name, and any arguments.
        """
        if cmd_name in self.cmd_aliases:
            return self.cmd_aliases[cmd_name]
        return []

    def exists(self, alias_name: str) -> bool:
        """Test if the given alias exists."""
        if alias_name in ["--comment", "--comments"]:
            return True
        return alias_name in self.aliases

    def make_alias(self, alias_name: str, cmd_name: str, cmd_args: str = "") -> None:
        """
        Add or update an alias with the given command and args.
        """
        ct = (cmd_name, cmd_args)
        cmd_seed = " ".join(list(ct)).strip()

        if self.exists(alias_name):
            existing_seed = " ".join(list(self.aliases[alias_name])).strip()
            masks = list(self.aliases_seed[existing_seed])
            if len(masks) == 1:
                del self.aliases_seed[existing_seed]
            elif len(masks) > 1:
                self.aliases_seed[existing_seed].remove(alias_name)

        if cmd_seed in self.aliases_seed:
            self.aliases_seed[cmd_seed].append(alias_name)
        else:
            self.aliases_seed[cmd_seed] = [alias_name]

        self.aliases[alias_name] = ct
        self.cmd_aliases[cmd_name].append((alias_name, cmd_args))

    def remove_alias(self, alias_name: str) -> None:
        """
        Remove an alias if it exists. Not saved to disk.
        """
        if alias_name not in self.aliases:
            return

        # remove from command reverse lookup.
        cmd, args = self.aliases[alias_name]
        cmd_alias = (alias_name, args)
        if cmd in self.cmd_aliases:
            if cmd_alias in self.cmd_aliases[cmd]:
                self.cmd_aliases[cmd].remove(cmd_alias)

        # remove from alias seed data.
        if alias_name in self.aliases_seed:
            del self.aliases_seed[alias_name]
        del self.aliases[alias_name]


class AliasesDefault:
    aliases_file: Path = Path(DEFAULT_COMMAND_ALIAS_FILE)
    aliases_seed: RawAliasJSON = {}
    complex_aliases: AliasesDict = {}
