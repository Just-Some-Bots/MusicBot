import sys
import decimal
import aiohttp

from hashlib import md5
from .constants import DISCORD_MSG_CHAR_LIMIT



class Serializable:
    def serialize(self):
        raise NotImplementedError

    @classmethod
    def deserialize(cls, playlist, jsonstr):
        raise NotImplementedError




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


def sane_round_int(x):
    return int(decimal.Decimal(x).quantize(1, rounding=decimal.ROUND_HALF_UP))


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


def safe_print(content, *, end='\n', flush=True):
    sys.stdout.buffer.write((content + end).encode('utf-8', 'replace'))
    if flush: sys.stdout.flush()


def avg(i):
    return sum(i) / len(i)

def version_is_newer(current, version):
    """
    Returns True if the given string in the format 'x.x.x[_x]' is newer
    than the current version
    """
    if '_' in version:
        main_ver, hotfix_ver = version.split('_', 1)
    else:
        main_ver = version
        hotfix_ver = None

    if '_' in current:
        main_cur, hotfix_cur = current.split('_', 1)
    else:
        main_cur = current
        hotfix_cur = None

    major_ver, minor_ver, subminor_ver = main_ver.split('.', 2)
    major_cur, minor_cur, subminor_cur = main_cur.split('.', 2)

    if int(major_ver) > int(major_cur):
        return True
    elif int(minor_ver) > int(minor_cur):
        return True
    elif int(subminor_ver) > int(subminor_cur):
        return True
    
    # At this point, all three parts of ver is <= cur. We only compare hotfixes
    # if they are all equal
    if int(major_ver) == int(major_cur) and int(minor_ver) == int(minor_cur) and \
                    int(subminor_ver) == int(subminor_cur):
        if hotfix_ver and not hotfix_cur:
            return True
        elif not hotfix_ver and not hotfix_cur:
            return False
        else: 
            # Both have a hotfix number (it is not possible for there to be a 
            # hotfix number for the current version but not the one fetched from
            # online
            return int(hotfix_ver) > int(hotfix_cur)
    else:
        return False


    if hotfix_ver and not hotfix_cur:
        return True
    elif int(hotfix_ver) > int(hotfix_cur):
        return True

    return False