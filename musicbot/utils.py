import datetime
import inspect
import logging
import pathlib
import re
import unicodedata
from functools import wraps
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Set,
    TypeVar,
    Union,
)

from .constants import DISCORD_MSG_CHAR_LIMIT
from .exceptions import PermissionsError

if TYPE_CHECKING:
    from discord import Member, StageChannel, VoiceChannel

    from .bot import MusicBot

CmdFunc = TypeVar("CmdFunc", bound=Callable[..., Any])

log = logging.getLogger(__name__)


def load_file(
    filename: pathlib.Path, skip_commented_lines: bool = True, comment_char: str = "#"
) -> List[str]:
    """
    Read `filename` into list of strings but ignore lines starting
    with the given `comment_char` character.
    Default comment character is #
    """
    try:
        with open(filename, encoding="utf8") as f:
            results = []
            for line in f:
                line = line.strip()

                if line and not (
                    skip_commented_lines and line.startswith(comment_char)
                ):
                    results.append(line)

            return results

    except IOError as e:
        print("Error loading", filename, e)
        return []


def write_file(filename: pathlib.Path, contents: Iterable[str]) -> None:
    """
    Open the given `filename` for writing in utf8 and write each item in
    `contents` to the file as a single line.
    Shorthand function that is now outmoded by pathlib, and could/should be replaced.
    """
    with open(filename, "w", encoding="utf8") as f:
        for item in contents:
            f.write(str(item))
            f.write("\n")


def slugify(value: str, allow_unicode: bool = False) -> str:
    """
    Taken from https://github.com/django/django/blob/master/django/utils/text.py
    Convert to ASCII if 'allow_unicode' is False. Convert spaces or repeated
    dashes to single dashes. Remove characters that aren't letters, numbers,
    underscores, or hyphens. Convert to lowercase. Also strip leading and
    trailing spaces, dashes, and underscores.
    """
    value = str(value)
    if allow_unicode:
        value = unicodedata.normalize("NFKC", value)
    else:
        value = (
            unicodedata.normalize("NFKD", value)
            .encode("ascii", "ignore")
            .decode("ascii")
        )
    value = re.sub(r"[^\w\s-]", "", value.lower())
    return re.sub(r"[-\s]+", "-", value).strip("-_")


def paginate(
    content: Union[str, List[str]],
    *,
    length: int = DISCORD_MSG_CHAR_LIMIT,
    reserve: int = 0,
) -> List[str]:
    """
    Split up a large string or list of strings into chunks for sending to discord.
    """
    if isinstance(content, str):
        contentlist = content.split("\n")
    elif isinstance(content, list):
        contentlist = content
    else:
        raise ValueError(f"Content must be str or list, not {type(content)}")

    chunks = []
    currentchunk = ""

    for line in contentlist:
        if len(currentchunk) + len(line) < length - reserve:
            currentchunk += line + "\n"
        else:
            chunks.append(currentchunk)
            currentchunk = ""

    if currentchunk:
        chunks.append(currentchunk)

    return chunks


def _func_() -> str:
    """
    Gets the name of the calling frame code object.
    Emulates __func__ from C++
    """
    frame = inspect.currentframe()
    if not frame or not frame.f_back:
        raise RuntimeError(
            "Call to _func_() failed, may not be available in this context."
        )

    return frame.f_back.f_code.co_name


def _get_variable(name: str) -> Any:
    """
    Inspect each frame in the call stack for local variables with the
    `name` given then return that variable's value or None if not found.
    """
    stack = inspect.stack()
    try:
        for frames in stack:
            try:
                frame = frames[0]
                current_locals = frame.f_locals
                if name in current_locals:
                    return current_locals[name]
            finally:
                del frame
    finally:
        del stack

    return None


def owner_only(func: Callable[..., Any]) -> Any:
    """
    Decorator function that checks the invoking message author ID matches
    the Owner ID which MusicBot has determined either via Config or
    Discord AppInfo.
    """

    @wraps(func)
    async def wrapper(self: "MusicBot", *args: Any, **kwargs: Any) -> Any:
        # Only allow the owner to use these commands
        orig_msg = _get_variable("message")

        if not orig_msg or orig_msg.author.id == self.config.owner_id:
            return await func(self, *args, **kwargs)
        raise PermissionsError("Only the owner can use this command.")

    setattr(wrapper, "admin_only", True)
    return wrapper


def dev_only(func: Callable[..., Any]) -> Any:
    """
    Decorator function that sets `dev_cmd` as an attribute to the function
    it decorates.
    This is then checked in MusicBot.on_message to ensure the protected
    commands are not executed by non "dev" users.
    """

    @wraps(func)
    async def wrapper(self: "MusicBot", *args: Any, **kwargs: Any) -> Any:
        orig_msg = _get_variable("message")

        if orig_msg.author.id in self.config.dev_ids:
            return await func(self, *args, **kwargs)
        raise PermissionsError("Only dev users can use this command.")

    setattr(wrapper, "dev_cmd", True)
    return wrapper


def command_helper(
    usage: Optional[List[str]] = None,
    desc: str = "",
    remap_subs: Optional[Dict[str, str]] = None,
    allow_dm: bool = False,
) -> Callable[[CmdFunc], CmdFunc]:
    """
    Decorator which enables command help to be translated and retires the doc-block.
    The usage strings are filtered and will replace "{cmd}" with "{prefix}cmd_name" where
    {prefix} is replaced only while formatting help for display.
    Filtered usage should reduce typos when writing usage strings. :)

    Usage command parameters should adhear to these rules:
    1. All literal parameters must be lower case and alphanumeric.
    2. All placeholder parameters must be upper case and alphanumeric.
    3. < > denotes a required parameter.
    4. [ ] denotes an optional parameter.
    5.  |  denotes multiple choices for the parameter.
    6. Literal terms may appear without parameter marks.

    :param: usage:  A list of usage patterns with descriptions.
                    If omitted, will default to the prefix and command name alone.
                    Set to an empty list if you want no usage examples.

    :param: desc:   A general description of the command.

    :param: remap_subs:  A dictionary for normalizing alternate sub-commands into a standard sub-command.
                         This allows users to simplify permissions for these commands.
                         It should be avoided for all new commands, deprecated and reserved for backwards compat.
                         Ex:  {"alt": "standard"}

    :param: allow_dm:  Allow the command to be used in DM.
                       This wont work for commands that need guild data.
    """
    if usage is None:
        usage = ["{cmd}"]

    def remap_subcommands(args: List[str]) -> List[str]:
        """Remaps the first argument in the list according to an external map."""
        if not remap_subs or not args:
            return args
        if args[0] in remap_subs.keys():
            args[0] = remap_subs[args[0]]
            return args
        return args

    def deco(func: Callable[..., Any]) -> Any:
        u = [
            u.replace("{cmd}", f"{{prefix}}{func.__name__.replace('cmd_', '')}")
            for u in usage
        ]

        @wraps(func)
        async def wrapper(self: "MusicBot", *args: Any, **kwargs: Any) -> Any:
            return await func(self, *args, **kwargs)

        setattr(wrapper, "help_usage", u)
        setattr(wrapper, "help_desc", desc)
        setattr(wrapper, "remap_subcommands", remap_subcommands)
        setattr(wrapper, "cmd_in_dm", allow_dm)
        return wrapper

    return deco


def is_empty_voice_channel(  # pylint: disable=dangerous-default-value
    voice_channel: Union["VoiceChannel", "StageChannel", None],
    *,
    exclude_me: bool = True,
    exclude_deaf: bool = True,
    include_bots: Set[int] = set(),
) -> bool:
    """
    Check if the given `voice_channel` is figuratively or literally empty.

    :param: `exclude_me`: Exclude our bot instance, the default.
    :param: `exclude_deaf`: Excludes members who are self-deaf or server-deaf.
    :param: `include_bots`: A list of bot IDs to include if they are present.
    """
    if not voice_channel:
        log.debug("Cannot count members when voice_channel is None.")
        return True

    def _check(member: "Member") -> bool:
        if exclude_me and member == voice_channel.guild.me:
            return False

        if (
            member.voice
            and exclude_deaf
            and any([member.voice.deaf, member.voice.self_deaf])
        ):
            return False

        if member.bot and member.id not in include_bots:
            return False

        return True

    return not sum(1 for m in voice_channel.members if _check(m))


def count_members_in_voice(  # pylint: disable=dangerous-default-value
    voice_channel: Union["VoiceChannel", "StageChannel", None],
    include_only: Iterable[int] = [],
    include_bots: Iterable[int] = [],
    exclude_ids: Iterable[int] = [],
    exclude_me: bool = True,
    exclude_deaf: bool = True,
) -> int:
    """
    Counts the number of members in given voice channel.
    By default it excludes all deaf users, all bots, and the MusicBot client itself.

    :param: voice_channel:  A VoiceChannel to inspect.
    :param: include_only:  A list of Member IDs to check for, only members in this list are counted if present.
    :param: include_bots:  A list of Bot Member IDs to include.  By default all bots are excluded.
    :param: exclude_ids:  A list of Member IDs to exclude from the count.
    :param: exclude_me:  A switch to, by default, exclude the bot ClientUser.
    :param: exclude_deaf:  A switch to, by default, exclude members who are deaf.
    """
    if not voice_channel:
        log.debug("Cannot count members when voice_channel is None.")
        return 0

    num_voice = 0
    for member in voice_channel.members:
        if not member:
            continue

        if member.bot and member.id not in include_bots:
            continue

        if exclude_me and member == voice_channel.guild.me:
            continue

        if exclude_ids and member.id in exclude_ids:
            continue

        voice = member.voice
        if not voice:
            continue

        if exclude_deaf and (voice.deaf or voice.self_deaf):
            continue

        if include_only and member.id not in include_only:
            continue

        num_voice += 1
    return num_voice


def format_song_duration(seconds: Union[int, float, datetime.timedelta]) -> str:
    """
    Take in the given `seconds` and format it as a compact timedelta string.
    If input `seconds` is an int or float, it will be converted to a timedelta.
    If the input has partial seconds, those are quietly removed without rounding.
    """
    if isinstance(seconds, (int, float)):
        seconds = datetime.timedelta(seconds=seconds)

    if not isinstance(seconds, datetime.timedelta):
        raise TypeError(
            "Can only format a duration that is int, float, or timedelta object."
        )

    # Simply remove any microseconds from the delta.
    time_delta = str(seconds).split(".", maxsplit=1)[0]
    t_hours = seconds.seconds / 3600

    # if hours is 0 remove it.
    if seconds.days == 0 and t_hours < 1:
        duration_array = time_delta.split(":")
        return ":".join(duration_array[1:])
    return time_delta


def format_size_from_bytes(size_bytes: int) -> str:
    """
    Format a given `size_bytes` into an approximate short-hand notation.
    """
    suffix = {0: "", 1: "Ki", 2: "Mi", 3: "Gi", 4: "Ti"}
    power = 1024
    size = float(size_bytes)
    i = 0
    while size > power:
        size /= power
        i += 1
    return f"{size:.3f} {suffix[i]}B"


def format_size_to_bytes(size_str: str, strict_si: bool = False) -> int:
    """
    Convert human-friendly data-size notation into integer.
    Note: this function is not intended to convert Bits notation.

    :param: size_str:  A size notation like: 20MB or "12.3 kb"
    :param: strict_si:  Toggles use of 1000 rather than 1024 for SI suffixes.
    """
    if not size_str:
        return 0

    si_units = 1024
    if strict_si:
        si_units = 1000
    suffix_list = {
        "kilobyte": si_units,
        "megabyte": si_units**2,
        "gigabyte": si_units**3,
        "terabyte": si_units**4,
        "petabyte": si_units**5,
        "exabyte": si_units**6,
        "zetabyte": si_units**7,
        "yottabyte": si_units**8,
        "kb": si_units,
        "mb": si_units**2,
        "gb": si_units**3,
        "tb": si_units**4,
        "pb": si_units**5,
        "eb": si_units**6,
        "zb": si_units**7,
        "yb": si_units**8,
        "kibibyte": 1024,
        "mebibyte": 1024**2,
        "gibibyte": 1024**3,
        "tebibyte": 1024**4,
        "pebibyte": 1024**5,
        "exbibyte": 1024**6,
        "zebibyte": 1024**7,
        "yobibyte": 1024**8,
        "kib": 1024,
        "mib": 1024**2,
        "gib": 1024**3,
        "tib": 1024**4,
        "pib": 1024**5,
        "eib": 1024**6,
        "zib": 1024**7,
        "yib": 1024**8,
    }
    size_str = size_str.lower().strip().strip("s")
    for suffix, conversion in suffix_list.items():
        if size_str.endswith(suffix):
            return int(float(size_str[0 : -len(suffix)]) * conversion)

    if size_str.endswith("b"):
        size_str = size_str[0:-1]
    elif size_str.endswith("byte"):
        size_str = size_str[0:-4]

    return int(float(size_str))


def format_time_to_seconds(time_str: Union[str, int]) -> int:
    """
    Convert a phrase containing time duration(s) to seconds as int
    This function allows for interesting/sloppy time notations like:
    - 1yearand2seconds  = 31556954
    - 8s 1d             = 86408
    - .5 hours          = 1800
    - 99 + 1            = 100
    - 3600              = 3600
    Only partial seconds are not supported, thus ".5s + 1.5s" will be 1 not 2.

    :param: time_str:  is assumed to contain a time duration as str or int.

    :returns:  0 if no time value is recognized, rather than raise a ValueError.
    """
    if isinstance(time_str, int):
        return time_str

    # support HH:MM:SS notations like those from timedelta.__str__
    hms_total = 0
    if ":" in time_str:
        parts = time_str.split()
        for part in parts:
            bits = part.split(":")
            part_sec = 0
            try:
                # format is MM:SS
                if len(bits) == 2:
                    m = int(bits[0])
                    s = int(bits[1])
                    part_sec += (m * 60) + s
                # format is HH:MM:SS
                elif len(bits) == 3:
                    h = int(bits[0] or 0)
                    m = int(bits[1])
                    s = int(bits[2] or 0)
                    part_sec += (h * 3600) + (m * 60) + s
                # format is not supported.
                else:
                    continue
                hms_total += part_sec
                time_str = time_str.replace(part, "")
            except (ValueError, TypeError):
                continue

    # TODO: find a good way to make this i18n friendly.
    time_lex = re.compile(r"(\d*\.?\d+)\s*(y|d|h|m|s)?", re.I)
    unit_seconds = {
        "y": 31556952,
        "d": 86400,
        "h": 3600,
        "m": 60,
        "s": 1,
    }
    total_sec = hms_total
    for value, unit in time_lex.findall(time_str):
        if not unit:
            unit = "s"
        else:
            unit = unit[0].lower().strip()
        total_sec += int(float(value) * unit_seconds[unit])
    return total_sec


def check_extractor(target: str, contains: str) -> bool:
    """Tests extractor string for containing the given extractor parts."""
    parts = contains.split(":")
    return all(p in target for p in parts)
