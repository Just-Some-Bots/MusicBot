import sys
import logging
import aiohttp
import inspect

from hashlib import md5
from .constants import DISCORD_MSG_CHAR_LIMIT

log = logging.getLogger(__name__)


def load_file(filename, skip_commented_lines=True, comment_char='#'):
    try:
        with open(filename, encoding='utf8') as f:
            results = []
            for line in f:
                line = line.strip()

                if line and not (skip_commented_lines and line.startswith(comment_char)):
                    results.append(line)

            return results

    except IOError as e:
        print("Error loading", filename, e)
        return []


def write_file(filename, contents):
    with open(filename, 'w', encoding='utf8') as f:
        for item in contents:
            f.write(str(item))
            f.write('\n')

def paginate(content, *, length=DISCORD_MSG_CHAR_LIMIT, reserve=0):
    """
    Split up a large string or list of strings into chunks for sending to discord.
    """
    if type(content) == str:
        contentlist = content.split('\n')
    elif type(content) == list:
        contentlist = content
    else:
        raise ValueError("Content must be str or list, not %s" % type(content))

    chunks = []
    currentchunk = ''

    for line in contentlist:
        if len(currentchunk) + len(line) < length - reserve:
            currentchunk += line + '\n'
        else:
            chunks.append(currentchunk)
            currentchunk = ''

    if currentchunk:
        chunks.append(currentchunk)

    return chunks


async def get_header(session, url, headerfield=None, *, timeout=5):
    with aiohttp.Timeout(timeout):
        async with session.head(url) as response:
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
    return ('{:.%sf}' % dp).format(x).rstrip('0').rstrip('.')


def ftimedelta(td):
    p1, p2 = str(td).rsplit(':', 1)
    return ':'.join([p1, '{:02d}'.format(int(float(p2)))])


def safe_print(content, *, end='\n', flush=True):
    sys.stdout.buffer.write((content + end).encode('utf-8', 'replace'))
    if flush: sys.stdout.flush()


def avg(i):
    return sum(i) / len(i)


def objdiff(obj1, obj2, *, access_attr=None, depth=0):
    changes = {}

    if access_attr is None:
        attrdir = lambda x: x

    elif access_attr == 'auto':
        if hasattr(obj1, '__slots__') and hasattr(obj2, '__slots__'):
            attrdir = lambda x: getattr(x, '__slots__')

        elif hasattr(obj1, '__dict__') and hasattr(obj2, '__dict__'):
            attrdir = lambda x: getattr(x, '__dict__')

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
                idiff = objdiff(iobj1, iobj2, access_attr='auto', depth=depth - 1)
                if idiff:
                    changes[item] = idiff

            elif iobj1 is not iobj2:
                changes[item] = (iobj1, iobj2)
                # log.everything("{1}.{0} ({3}) is not {2}.{0} ({4}) ".format(item, repr(obj1), repr(obj2), iobj1, iobj2))

            else:
                pass
                # log.everything("{obj1}.{item} is {obj2}.{item} ({val1} and {val2})".format(obj1=obj1, obj2=obj2, item=item, val1=iobj1, val2=iobj2))

        except Exception as e:
            # log.everything("Error checking {o1}/{o2}.{item}".format(o1=obj1, o2=obj2, item=item), exc_info=e)
            continue

    return changes

def color_supported():
    return hasattr(sys.stderr, "isatty") and sys.stderr.isatty()

def _func_():
    # emulate __func__ from C++
    return inspect.currentframe().f_back.f_code.co_name
