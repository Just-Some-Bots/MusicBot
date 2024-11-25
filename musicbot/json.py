import json
import logging
import pathlib
from typing import Any, Dict

log = logging.getLogger(__name__)


class Json:
    def __init__(self, json_file: pathlib.Path) -> None:
        """
        Managed JSON data, where some structure is expected.
        """
        log.debug("Loading JSON file: %s", json_file)
        self.file = json_file
        self.data = self.parse()

    def parse(self) -> Dict[str, Any]:
        """Parse the file as JSON"""
        parsed = {}
        with open(self.file, encoding="utf-8") as data:
            try:
                parsed = json.load(data)
                if not isinstance(parsed, dict):
                    raise TypeError("Parsed information must be of type Dict[str, Any]")
            except (json.JSONDecodeError, TypeError):
                log.error("Error parsing %s as JSON", self.file, exc_info=True)
                parsed = {}
        return parsed

    def get(self, item: str, fallback: Any = None) -> Any:
        """Gets an item from a JSON file"""
        try:
            data = self.data[item]
        except KeyError:
            log.warning("Could not grab data from JSON key: %s", item)
            data = fallback
        return data
