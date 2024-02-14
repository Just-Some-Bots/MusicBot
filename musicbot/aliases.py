import json
import logging
import shutil
from pathlib import Path
from typing import Any, Dict

from .constants import DEFAULT_COMMAND_ALIAS_FILE, EXAMPLE_COMMAND_ALIAS_FILE
from .exceptions import HelpfulError

log = logging.getLogger(__name__)


class Aliases:
    def __init__(self, aliases_file: Path) -> None:
        """
        Handle locating, initializing, loading, and validation of command aliases.
        If given `aliases_file` is not found, examples will be copied to the location.

        :raises: musicbot.exceptions.HelpfulError
            if loading fails in some known way.
        """
        self.aliases_file = aliases_file
        self.aliases_seed = AliasesDefault.aliases_seed
        self.aliases = AliasesDefault.aliases

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
        with self.aliases_file.open() as f:
            try:
                self.aliases_seed = json.load(f)
            except json.JSONDecodeError as e:
                raise HelpfulError(
                    f"Failed to parse aliases file:  {str(self.aliases_file)}",
                    "Ensure your alias file contains valid JSON and restart the bot.",
                ) from e

        # construct
        for cmd, aliases in self.aliases_seed.items():
            if not isinstance(cmd, str) or not isinstance(aliases, list):
                raise HelpfulError(
                    "Failed to load aliases file due to invalid format.",
                    "Make sure your aliases conform to the format given in the example file.",
                )
            self.aliases.update({alias.lower(): cmd.lower() for alias in aliases})

    def get(self, alias: str) -> str:
        """
        Return cmd name that given `alias` points to or an empty string.
        """
        return self.aliases.get(alias, "")


class AliasesDefault:
    aliases_file: Path = Path(DEFAULT_COMMAND_ALIAS_FILE)
    aliases_seed: Dict[str, Any] = {}
    aliases: Dict[str, str] = {}
