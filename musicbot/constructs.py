import asyncio
import inspect
import json
import logging
import pydoc
from collections import defaultdict
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    DefaultDict,
    Dict,
    List,
    Optional,
    Set,
    Type,
    Union,
)

import discord

from .constants import DATA_GUILD_FILE_OPTIONS
from .json import Json
from .utils import _get_variable

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .autoplaylist import AutoPlaylist
    from .bot import MusicBot
    from .config import Config


class GuildAsyncEvent(asyncio.Event):
    """
    Simple extension of asyncio.Event() to provide a boolean flag for activity.
    """

    def __init__(self) -> None:
        """
        Create an event with an activity flag.
        """
        super().__init__()
        self._event_active: bool = False

    def is_active(self) -> bool:
        """Reports activity state"""
        return self._event_active

    def activate(self) -> None:
        """Sets the event's active flag."""
        self._event_active = True

    def deactivate(self) -> None:
        """Unset the event's active flag."""
        self._event_active = False


class GuildSpecificData:
    """
    A typed collection of data specific to each guild/discord server.
    """

    def __init__(self, bot: "MusicBot") -> None:
        """
        Initialize a managed server specific data set.
        """
        # Members for internal use only.
        self._ssd: DefaultDict[int, "GuildSpecificData"] = bot.server_data
        self._bot_config: "Config" = bot.config
        self._bot: "MusicBot" = bot
        self._guild_id: int = 0
        self._guild_name: str = ""
        self._command_prefix: str = ""
        self._prefix_history: Set[str] = set()
        self._events: DefaultDict[str, GuildAsyncEvent] = defaultdict(GuildAsyncEvent)
        self._file_lock: asyncio.Lock = asyncio.Lock()
        self._loading_lock: asyncio.Lock = asyncio.Lock()
        self._is_file_loaded: bool = False

        # Members below are available for public use.
        self.last_np_msg: Optional["discord.Message"] = None
        self.last_played_song_subject: str = ""
        self.follow_user: Optional["discord.Member"] = None
        self.auto_join_channel: Optional[
            Union["discord.VoiceChannel", "discord.StageChannel"]
        ] = None
        self.autoplaylist: "AutoPlaylist" = self._bot.playlist_mgr.get_default()
        self.current_playing_url: str = ""

        # create a task to load any persistent guild options.
        # in theory, this should work out fine.
        bot.create_task(self.load_guild_options_file(), name="MB_LoadGuildOptions")
        bot.create_task(self.autoplaylist.load(), name="MB_LoadAPL")

    def is_ready(self) -> bool:
        """A status indicator for fully loaded server data."""
        return self._is_file_loaded and self._guild_id != 0

    def _lookup_guild_id(self) -> int:
        """
        Looks up guild.id used to create this instance of GuildSpecificData
        Will return 0 if for some reason lookup fails.
        """
        for key, val in self._ssd.items():
            if val == self:
                guild = discord.utils.find(
                    lambda m: m.id == key,  # pylint: disable=cell-var-from-loop
                    self._bot.guilds,
                )
                if guild:
                    self._guild_name = guild.name
                return key
        return 0

    async def get_played_history(self) -> Optional["AutoPlaylist"]:
        """Get the history playlist for this guild, if enabled."""
        if not self._bot.config.enable_queue_history_guilds:
            return None

        if not self.is_ready():
            return None

        pl = self._bot.playlist_mgr.get_playlist(f"history-{self._guild_id}.txt")
        pl.create_file()
        if not pl.loaded:
            await pl.load()
        return pl

    @property
    def command_prefix(self) -> str:
        """
        If per-server prefix is enabled, and the server has a specific
        command prefix, it will be returned.
        Otherwise the default command prefix is returned from MusicBot config.
        """
        if self._bot_config.enable_options_per_guild:
            if self._command_prefix:
                return self._command_prefix
        return self._bot_config.command_prefix

    @command_prefix.setter
    def command_prefix(self, value: str) -> None:
        """Set the value of command_prefix"""
        if not value:
            raise ValueError("Cannot set an empty prefix.")

        # update prefix history
        if not self._command_prefix:
            self._prefix_history.add(self._bot_config.command_prefix)
        else:
            self._prefix_history.add(self._command_prefix)

        # set prefix value
        self._command_prefix = value

        # clean up history buffer if needed.
        if len(self._prefix_history) > 3:
            self._prefix_history.pop()

    @property
    def command_prefix_list(self) -> List[str]:
        """
        Get the prefix list for this guild.
        It includes a history of prefix changes since last restart as well.
        """
        history = list(self._prefix_history)

        # add self mention to invoke list.
        if self._bot_config.commands_via_mention and self._bot.user:
            history.append(f"<@{self._bot.user.id}>")

        # Add current prefix to list.
        if self._command_prefix:
            history = [self._command_prefix] + history
        else:
            history = [self._bot_config.command_prefix] + history

        return history

    def get_event(self, name: str) -> GuildAsyncEvent:
        """
        Gets an event by the given `name` or otherwise creates and stores one.
        """
        return self._events[name]

    async def load_guild_options_file(self) -> None:
        """
        Load a JSON file from the server's data directory that contains
        server-specific options intended to persist through shutdowns.
        This method only supports per-server command prefix currently.
        """
        if self._loading_lock.locked():
            return

        async with self._loading_lock:
            if self._guild_id == 0:
                self._guild_id = self._lookup_guild_id()
                if self._guild_id == 0:
                    log.error(
                        "Cannot load data for guild with ID 0. This is likely a bug in the code!"
                    )
                    return

            opt_file = self._bot_config.data_path.joinpath(
                str(self._guild_id), DATA_GUILD_FILE_OPTIONS
            )
            if not opt_file.is_file():
                log.debug("No file for guild %s/%s", self._guild_id, self._guild_name)
                self._is_file_loaded = True
                return

            async with self._file_lock:
                try:
                    log.debug(
                        "Loading guild data for guild with ID:  %s/%s",
                        self._guild_id,
                        self._guild_name,
                    )
                    options = Json(opt_file)
                    self._is_file_loaded = True
                except OSError:
                    log.exception(
                        "An OS error prevented reading guild data file:  %s",
                        opt_file,
                    )
                    return

            guild_prefix = options.get("command_prefix", None)
            if guild_prefix:
                self._command_prefix = guild_prefix
                log.info(
                    "Guild %s/%s has custom command prefix: %s",
                    self._guild_id,
                    self._guild_name,
                    self._command_prefix,
                )

            guild_playlist = options.get("auto_playlist", None)
            if guild_playlist:
                self.autoplaylist = self._bot.playlist_mgr.get_playlist(guild_playlist)
                await self.autoplaylist.load()

    async def save_guild_options_file(self) -> None:
        """
        Save server-specific options, like the command prefix, to a JSON
        file in the server's data directory.
        """
        if self._guild_id == 0:
            log.error(
                "Cannot save data for guild with ID 0. This is likely a bug in the code!"
            )
            return

        opt_file = self._bot_config.data_path.joinpath(
            str(self._guild_id), DATA_GUILD_FILE_OPTIONS
        )

        auto_playlist = None
        if self.autoplaylist is not None:
            auto_playlist = self.autoplaylist.filename

        # Prepare a dictionary to store our options.
        opt_dict = {
            "command_prefix": self._command_prefix,
            "auto_playlist": auto_playlist,
        }

        async with self._file_lock:
            try:
                with open(opt_file, "w", encoding="utf8") as fh:
                    fh.write(json.dumps(opt_dict))
            except OSError:
                log.exception("Could not save guild specific data due to OS Error.")
            except (TypeError, ValueError):
                log.exception(
                    "Failed to serialize guild specific data due to invalid data."
                )


class SkipState:
    __slots__ = ["skippers", "skip_msgs"]

    def __init__(self) -> None:
        """
        Manage voters and their ballots for fair MusicBot track skipping.
        This creates a set of discord.Message and a set of member IDs to
        enable counting votes for skipping a song.
        """
        self.skippers: Set[int] = set()
        self.skip_msgs: Set["discord.Message"] = set()

    @property
    def skip_count(self) -> int:
        """
        Get the number of authors who requested skip.
        """
        return len(self.skippers)

    def reset(self) -> None:
        """
        Clear the vote counting sets.
        """
        self.skippers.clear()
        self.skip_msgs.clear()

    def add_skipper(self, skipper_id: int, msg: "discord.Message") -> int:
        """
        Add a message and the author's ID to the skip vote.
        """
        self.skippers.add(skipper_id)
        self.skip_msgs.add(msg)
        return self.skip_count


class Response:
    __slots__ = ["_content", "reply", "delete_after", "codeblock", "_codeblock"]

    def __init__(
        self,
        content: Union[str, "discord.Embed"],
        reply: bool = False,
        delete_after: int = 0,
        codeblock: str = "",
    ) -> None:
        """
        Helper class intended to be used by command functions in MusicBot.
        Simple commands should return a Response rather than calling to send
        messages on their own.

        :param: content:  the text message or an Embed object to be sent.
        :param: reply:  if this response should reply to the original author.
        :param: delete_after:  how long to wait before deleting the message created by this Response.
            Set to 0 to never delete.
        :param: codeblock:  format a code block with this value as the language used for syntax highlights.
        """
        self._content = content
        self.reply = reply
        self.delete_after = delete_after
        self.codeblock = codeblock
        self._codeblock = f"```{codeblock}\n{{}}\n```"

    @property
    def content(self) -> Union[str, "discord.Embed"]:
        """
        Get the Response content, but quietly format a code block if needed.
        """
        if self.codeblock:
            return self._codeblock.format(self._content)
        return self._content


class Serializer(json.JSONEncoder):
    def default(self, o: "Serializable") -> Any:
        """
        Default method used by JSONEncoder to return serializable data for
        the given object or Serializable in `o`
        """
        if hasattr(o, "__json__"):
            return o.__json__()

        return super().default(o)

    @classmethod
    def deserialize(cls, data: Dict[str, Any]) -> Any:
        """
        Read a simple JSON dict for a valid class signature, and pass the
        simple dict on to a _deserialize function in the signed class.
        """
        if all(x in data for x in Serializable.CLASS_SIGNATURE):
            # log.debug("Deserialization requested for %s", data)
            factory = pydoc.locate(data["__module__"] + "." + data["__class__"])
            # log.debug("Found object %s", factory)
            if factory and issubclass(factory, Serializable):  # type: ignore[arg-type]
                # log.debug("Deserializing %s object", factory)
                return factory._deserialize(  # type: ignore[attr-defined]
                    data["data"], **cls._get_vars(factory._deserialize)  # type: ignore[attr-defined]
                )

        return data

    @classmethod
    def _get_vars(cls, func: Callable[..., Any]) -> Dict[str, Any]:
        """
        Inspect argument specification for given callable `func` and attempt
        to inject it's named parameters by inspecting the calling frames for
        locals which match the parameter names.
        """
        # log.debug("Getting vars for %s", func)
        params = inspect.signature(func).parameters.copy()
        args = {}
        # log.debug("Got %s", params)

        for name, param in params.items():
            # log.debug("Checking arg %s, type %s", name, param.kind)
            if param.kind is param.POSITIONAL_OR_KEYWORD and param.default is None:
                # log.debug("Using var %s", name)
                args[name] = _get_variable(name)
                # log.debug("Collected var for arg '%s': %s", name, args[name])

        return args


class Serializable:
    CLASS_SIGNATURE = ("__class__", "__module__", "data")

    def _enclose_json(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Helper used by child instances of Serializable that includes class signature
        for the Serializable object.
        Intended to be called from __json__ methods of child instances.
        """
        return {
            "__class__": self.__class__.__qualname__,
            "__module__": self.__module__,
            "data": data,
        }

    # Perhaps convert this into some sort of decorator
    @staticmethod
    def _bad(arg: str) -> None:
        """
        Wrapper used by assertions in Serializable classes to enforce required arguments.

        :param: arg:  the parameter name being enforced.

        :raises: TypeError  when given `arg` is None in calling frame.
        """
        raise TypeError(f"Argument '{arg}' must not be None")

    def serialize(self, *, cls: Type[Serializer] = Serializer, **kwargs: Any) -> str:
        """
        Simple wrapper for json.dumps with Serializer instance support.
        """
        return json.dumps(self, cls=cls, **kwargs)

    def __json__(self) -> Optional[Dict[str, Any]]:
        """
        Serialization method to be implemented by derived classes.
        Should return a simple dictionary representing the Serializable
        class and its data/state, using only built-in types.
        """
        raise NotImplementedError

    @classmethod
    def _deserialize(
        cls: Type["Serializable"], raw_json: Dict[str, Any], **kwargs: Any
    ) -> Any:
        """
        Deserialization handler, to be implemented by derived classes.
        Should construct and return a valid Serializable child instance or None.

        :param: raw_json:  data from json.loads() using built-in types only.
        """
        raise NotImplementedError
