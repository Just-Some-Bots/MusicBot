import json
import logging
import shutil
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .constants import DEFAULT_COMMAND_ALIAS_FILE, EXAMPLE_COMMAND_ALIAS_FILE
from .exceptions import HelpfulError

log = logging.getLogger(__name__)

RawAliasJSON = Dict[str, Any]
ComplexAliases = Dict[str, Tuple[str, str]]


class Aliases:
    """
    Aliases class provides a method of duplicating commands under different names or
    providing reduction in keystrokes for multi-argument commands.
    Command alias with conflicting names will overload each other, it is up to
    the user to avoid configuring aliases with conflicts.
    """

    # TODO: add a method to query aliases a natural command has.

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
        self.aliases: ComplexAliases = AliasesDefault.complex_aliases

        # find aliases file
        if not self.aliases_file.is_file():
            example_aliases = Path(EXAMPLE_COMMAND_ALIAS_FILE)
            if example_aliases.is_file():
                shutil.copy(str(example_aliases), str(self.aliases_file))
                log.warning("Aliases file not found, copying example_aliases.json")
            else:
                raise HelpfulError(
                    "Your aliases files are missing. Neither aliases.json nor example_aliases.json were found.",
                    "Grab the files back from the archive or remake them yourself and copy paste the content "
                    "from the repo. Stop removing important files!",
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
            if cmd not in self.nat_cmds:
                log.error(
                    "Aliases skipped for non-existent command:  %s  ->  %s",
                    cmd,
                    aliases,
                )
                continue

            # ensure alias data uses valid types.
            if not isinstance(cmd, str) or not isinstance(aliases, list):
                log.error(
                    "Alias(es) skipped for invalid alias data:  %s  ->  %s",
                    cmd,
                    aliases,
                )
                continue

            # Loop over given aliases and associate them.
            for alias in aliases:
                alias = alias.lower()
                if alias in self.aliases:
                    log.error(
                        "Alias `%s` skipped as already exists on command:  %s",
                        alias,
                        self.aliases[alias],
                    )
                    continue

                self.aliases.update({alias: (cmd, cmd_args)})

    def get(self, alias_name: str) -> Tuple[str, str]:
        """
        Get the command name the given `aliase_name` refers to.
        Returns a two-member tuple containing the command name and any args for
        the command alias in the case of complex aliases.
        """
        cmd_name, cmd_args = self.aliases.get(alias_name, ("", ""))

        # If no alias at all, return nothing.
        if not cmd_name:
            return ("", "")

        return (cmd_name, cmd_args)


class AliasesDefault:
    aliases_file: Path = Path(DEFAULT_COMMAND_ALIAS_FILE)
    aliases_seed: RawAliasJSON = {}
    complex_aliases: ComplexAliases = {}
