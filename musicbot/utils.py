import re
import sys
import logging
import aiohttp
import inspect
import unicodedata
from typing import TYPE_CHECKING, Union, List

from .constants import DISCORD_MSG_CHAR_LIMIT

if TYPE_CHECKING:
    from discord import VoiceChannel

log = logging.getLogger(__name__)


def load_file(filename, skip_commented_lines=True, comment_char="#"):
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


def write_file(filename, contents):
    with open(filename, "w", encoding="utf8") as f:
        for item in contents:
            f.write(str(item))
            f.write("\n")


def slugify(value, allow_unicode=False):
    """
    Taken from https://github.com/django/django/blob/master/django/utils/text.py
    Convert to ASCII if 'allow_unicode' is False. Convert spaces or repeated
    dashes to single dashes. Remove characters that aren't alphanumerics,
    underscores, or hyphens. Convert to lowercase. Also strip leading and
    trailing whitespace, dashes, and underscores.
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


def paginate(content, *, length=DISCORD_MSG_CHAR_LIMIT, reserve=0):
    """
    Split up a large string or list of strings into chunks for sending to discord.
    """
    if isinstance(content, str):
        contentlist = content.split("\n")
    elif isinstance(content, list):
        contentlist = content
    else:
        raise ValueError("Content must be str or list, not %s" % type(content))

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


async def get_header(
    session, url, headerfield=None, *, timeout=5, allow_redirects=True
):
    req_timeout = aiohttp.ClientTimeout(total=timeout)
    async with session.head(
        url, timeout=req_timeout, allow_redirects=allow_redirects
    ) as response:
        if headerfield:
            return response.headers.get(headerfield)
        else:
            return response.headers


def fixg(x, dp=2):
    return ("{:.%sf}" % dp).format(x).rstrip("0").rstrip(".")


def ftimedelta(td):
    p1, p2 = str(td).rsplit(":", 1)
    return ":".join([p1, "{:02d}".format(int(float(p2)))])


def safe_print(content, *, end="\n", flush=True):
    sys.stdout.buffer.write((content + end).encode("utf-8", "replace"))
    if flush:
        sys.stdout.flush()


def objdiff(obj1, obj2, *, access_attr=None, depth=0):
    changes = {}

    if access_attr is None:
        attrdir = lambda x: x  # noqa: E731

    elif access_attr == "auto":
        if hasattr(obj1, "__slots__") and hasattr(obj2, "__slots__"):
            attrdir = lambda x: getattr(x, "__slots__")  # noqa: E731

        elif hasattr(obj1, "__dict__") and hasattr(obj2, "__dict__"):
            attrdir = lambda x: getattr(x, "__dict__")  # noqa: E731

        else:
            attrdir = dir

    elif isinstance(access_attr, str):
        attrdir = lambda x: list(getattr(x, access_attr))  # noqa: E731

    else:
        attrdir = dir

    for item in set(attrdir(obj1) + attrdir(obj2)):
        try:
            iobj1 = getattr(obj1, item, AttributeError("No such attr " + item))
            iobj2 = getattr(obj2, item, AttributeError("No such attr " + item))

            if depth:
                idiff = objdiff(iobj1, iobj2, access_attr="auto", depth=depth - 1)
                if idiff:
                    changes[item] = idiff

            elif iobj1 is not iobj2:
                changes[item] = (iobj1, iobj2)

            else:
                pass

        except Exception:
            continue

    return changes


def color_supported():
    return hasattr(sys.stderr, "isatty") and sys.stderr.isatty()


def _func_():
    # emulate __func__ from C++
    return inspect.currentframe().f_back.f_code.co_name


def _get_variable(name):
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


def is_empty_voice_channel(
    voice_channel: "VoiceChannel",
    *,
    exclude_me: bool = True,
    exclude_deaf: bool = True,
    include_bots: List[int] = [],
) -> bool:
    """
    Check if the given `voice_channel` is figuratively or literally empty.

    :param: `exclude_me`: Exclude our bot instance, the default.
    :param: `exclude_deaf`: Excludes members who are self-deaf or server-deaf.
    :param: `include_bots`: A list of bot IDs to include if they are present.
    """

    def _check(member):
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


def format_song_duration(ftd):
    duration_array = ftd.split(":")
    return (
        ftd
        if int(duration_array[0]) > 0
        else "{0}:{1}".format(duration_array[1], duration_array[2])
    )


def format_size_from_bytes(size: int):
    suffix = {0: "", 1: "Ki", 2: "Mi", 3: "Gi", 4: "Ti"}
    power = 1024
    i = 0
    while size > power:
        size /= power
        i += 1
    return f"{size:.3f} {suffix[i]}B"


def format_size_to_bytes(size_str: str, strict_si=False) -> int:
    """Convert human-friendly *bytes notation into integer.
    Note: this function is not intended to convert Bits notation.

    Option `strict_si` will use 1000 rather than 1024 for SI suffixes.
    """
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
    for suffix in suffix_list:
        if size_str.endswith(suffix):
            return int(float(size_str[0 : -len(suffix)]) * suffix_list[suffix])
    else:
        if size_str.endswith("b"):
            size_str = size_str[0:-1]
        elif size_str.endswith("byte"):
            size_str = size_str[0:-4]
    return int(size_str)


def format_time_to_seconds(time_str: Union[str, int]) -> int:
    """Convert a phrase containing time duration(s) to seconds as int
    This function allows for intresting/sloppy time notations like:
    - 1yearand2seconds  = 31556954
    - 8s 1d             = 86408
    - .5 hours          = 1800
    - 99 + 1            = 100
    - 3600              = 3600
    Only partial seconds are not supported, thus ".5s + 1.5s" will be 1 not 2.

    Param `time_str` is assumed to contain a time duration as str or int.
    Returns 0 if no time value is recognised, rather than raise a ValueError.
    """
    if isinstance(time_str, int):
        return time_str

    # TODO: find a good way to make this i18n friendly.
    time_lex = re.compile(r"(\d*\.?\d+)\s*(y|d|h|m|s)?", re.I)
    unit_seconds = {
        "y": 31556952,
        "d": 86400,
        "h": 3600,
        "m": 60,
        "s": 1,
    }
    total_sec = 0
    for value, unit in time_lex.findall(time_str):
        if not unit:
            unit = "s"
        else:
            unit = unit[0].lower().strip()
        total_sec += int(float(value) * unit_seconds[unit])
    return total_sec
