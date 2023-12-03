import re
import sys
import logging
import aiohttp
import inspect

from hashlib import md5
from .constants import DISCORD_MSG_CHAR_LIMIT

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


def paginate(content, *, length=DISCORD_MSG_CHAR_LIMIT, reserve=0):
    """
    Split up a large string or list of strings into chunks for sending to discord.
    """
    if type(content) == str:
        contentlist = content.split("\n")
    elif type(content) == list:
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


async def get_header(session, url, headerfield=None, *, timeout=5):
    req_timeout = aiohttp.ClientTimeout(total=timeout)
    async with session.head(url, timeout=req_timeout) as response:
        if headerfield:
            return response.headers.get(headerfield)
        else:
            return response.headers


def md5sum(filename, limit=0):
    fhash = md5()
    with open(filename, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            fhash.update(chunk)
    return fhash.hexdigest()[-limit:]


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
        attrdir = lambda x: x

    elif access_attr == "auto":
        if hasattr(obj1, "__slots__") and hasattr(obj2, "__slots__"):
            attrdir = lambda x: getattr(x, "__slots__")

        elif hasattr(obj1, "__dict__") and hasattr(obj2, "__dict__"):
            attrdir = lambda x: getattr(x, "__dict__")

        else:
            # log.everything("{}{} or {} has no slots or dict".format('-' * (depth+1), repr(obj1), repr(obj2)))
            attrdir = dir

    elif isinstance(access_attr, str):
        attrdir = lambda x: list(getattr(x, access_attr))

    else:
        attrdir = dir

    # log.everything("Diffing {o1} and {o2} with {attr}".format(o1=obj1, o2=obj2, attr=access_attr))

    for item in set(attrdir(obj1) + attrdir(obj2)):
        try:
            iobj1 = getattr(obj1, item, AttributeError("No such attr " + item))
            iobj2 = getattr(obj2, item, AttributeError("No such attr " + item))

            # log.everything("Checking {o1}.{attr} and {o2}.{attr}".format(attr=item, o1=repr(obj1), o2=repr(obj2)))

            if depth:
                # log.everything("Inspecting level {}".format(depth))
                idiff = objdiff(iobj1, iobj2, access_attr="auto", depth=depth - 1)
                if idiff:
                    changes[item] = idiff

            elif iobj1 is not iobj2:
                changes[item] = (iobj1, iobj2)
                # log.everything("{1}.{0} ({3}) is not {2}.{0} ({4}) ".format(item, repr(obj1), repr(obj2), iobj1, iobj2))

            else:
                pass
                # log.everything("{obj1}.{item} is {obj2}.{item} ({val1} and {val2})".format(obj1=obj1, obj2=obj2, item=item, val1=iobj1, val2=iobj2))

        except Exception:
            # log.everything("Error checking {o1}/{o2}.{item}".format(o1=obj1, o2=obj2, item=item), exc_info=e)
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


def format_time_to_seconds(time_str: str) -> int:
    """Convert a phrase containing time duration(s) to seconds as int
    This function allows for intresting/sloppy time notations like:
    - 1yearand2seconds  = 31556954
    - 8s 1d             = 86408
    - .5 hours          = 1800
    - 99 + 1            = 100
    - 3600              = 3600
    Only partial seconds are not supported, thus ".5s + 1.5s" will be 1 not 2.

    Param `time_str` is assumed to contain a time duration.
    Returns 0 if no time value is recognised, rather than raise a ValueError.
    """
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
        print(value, unit)
        if not unit:
            unit = "s"
        else:
            unit = unit[0].lower().strip()
        total_sec += int(float(value) * unit_seconds[unit])
    return total_sec
