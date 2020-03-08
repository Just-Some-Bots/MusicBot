import sys
import logging
import aiohttp
import asyncio
import inspect
import io
import os
from collections import defaultdict
from hashlib import md5
from typing import Any, Callable, Optional, TypeVar, AnyStr, List, Set, Tuple, Iterable
from copy import deepcopy

from .constants import DISCORD_MSG_CHAR_LIMIT
from .exceptions import AsyncCalledProcessError

log = logging.getLogger(__name__)

T = TypeVar('T')

def callback_dummy_future(cb: Callable[[], T]) -> T:
    def _dummy(future):
        cb()
    return _dummy

def isiterable(x):
    try:
        iter(x)
    except TypeError:
        return False
    else:
        return True

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
    req_timeout = aiohttp.ClientTimeout(total = timeout)
    async with session.head(url, timeout = req_timeout) as response:
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

async def _run_process(*popenargs, **kwargs):
    ILLEGAL_KEY = {'bufsize', 'encoding', 'errors', 'text', 'universal_newlines'}
    if any([fkey in kwargs.keys() for fkey in ILLEGAL_KEY]):
        raise ValueError('illegal keyword in utils.check_call call'
                         'keyword should not be {}'.format(', '.join(ILLEGAL_KEY)))

    shell = kwargs.pop('shell', False)
    if shell:
        if len(popenargs) != 1:
            popenargs = ((' ' if isinstance(popenargs[0], str) else b' ').join(popenargs), )
        runner = asyncio.create_subprocess_shell
    else:
        if len(popenargs) == 1:
            popenargs = tuple(popenargs[0].split(' ' if isinstance(popenargs[0], str) else b' '))        
        runner = asyncio.create_subprocess_exec

    popenargs = (' '.join(popenargs),) if shell and not any([isinstance(arg, bytes) for arg in popenargs]) else popenargs
    process = await runner(*popenargs, **kwargs)
    await process.wait()
    return process

async def check_call(*popenargs, **kwargs):
    process = await _run_process(*popenargs, **kwargs)
    retcode = process.returncode
    if retcode:
        cmd = kwargs.get("args")
        if cmd is None:
            cmd = popenargs[0]
        raise AsyncCalledProcessError(retcode, cmd)

async def check_output(*popenargs, **kwargs):
    encoding = kwargs.pop('encoding', None)
    errors = kwargs.pop('errors', None)
    text = kwargs.pop('text', False)
    universal_newlines = kwargs.pop('universal_newlines', False)
    text_mode = encoding or errors or text or universal_newlines

    kwargs.setdefault('stdout', asyncio.subprocess.PIPE)

    process = await _run_process(*popenargs, **kwargs)
    _out, _err = await process.communicate()
    return io.BytesIO(_out) if not text_mode else io.TextIOWrapper(io.BytesIO(_out), encoding=encoding, errors=errors)

class DependencyResolver:
    def __init__(self):
        self.dependents = defaultdict(set)
        self.dependencies = dict()

    def add_item(self, name, dependencies: Optional[Set] = set()):
        for dep in dependencies:
            self.dependents[dep].add(name)
        self.dependencies[name] = dependencies.copy()

    def remove_item(self, name):
        for dep in self.dependencies[name]:
            self.dependents[dep].remove(name)
        del self.dependencies[name]

    def get_state(self) -> Tuple[List, Set]:
        """
        return list of item with dependencies satisfied and set of item that does not.
        """
        available_items = set(self.dependencies.keys())
        # known_good is a list of items that is known to have all dependency available
        # which is sorted in the order that dependents will come after dependencies
        known_good = [item for item, deps in self.dependencies.items() if not deps]
        unconsidered_known_good = set(known_good)

        unmet_dependencies = deepcopy(self.dependencies)
        while unconsidered_known_good:
            good = unconsidered_known_good.pop()
            for item in self.dependents[good]:
                unmet_dependencies[item].remove(good)
                if not unmet_dependencies[item]:
                    known_good.append(item)
                    unconsidered_known_good.add(item)

        faulty = available_items - set(known_good)

        return (known_good, faulty)

    def get_dependents(self, name) -> List:
        """
        return dependents of specified name.
        NOTE: dependency of every dependents returned will appear after the dependents.
        """
        dependents = list(self.dependents[name])
        unconsidered_dependents = self.dependents[name].copy()

        while unconsidered_dependents:
            dep = unconsidered_dependents.pop()
            for item in self.dependents[dep]:
                if item not in dependents and item != name:
                    dependents.append(item)
                    unconsidered_dependents.add(item)

        dependents.reverse()

        return dependents

    def get_dependents_multiple(self, names: Iterable, include_given = True) -> List:
        dependents = list()
        unordered_dependents = set()
        for name in names:
            if name not in unordered_dependents:
                new_items = self.get_dependents(name)
                if include_given:
                    new_items.append(name)
                for item in new_items:
                    if item not in unordered_dependents:
                        dependents.append(item)
                        unordered_dependents.add(item)
        return dependents

async def run_command(cmd, log=None):
    p = await asyncio.create_subprocess_shell(cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    if log:
        log.debug('Starting asyncio subprocess ({0}) with command: {1}'.format(p, cmd))
    stdout, stderr = await p.communicate()
    return stdout + stderr

def get_command(program):
    def is_exe(fpath):
        found = os.path.isfile(fpath) and os.access(fpath, os.X_OK)
        if not found and sys.platform == 'win32':
            fpath = fpath + ".exe"
            found = os.path.isfile(fpath) and os.access(fpath, os.X_OK)
        return found

    fpath, __ = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            path = path.strip('"')
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file

    return None

def check_restricted(command, perms):
    _whitelist = perms._command_whitelist
    whitelist = perms.command_whitelist
    _blacklist = perms._command_blacklist
    blacklist = perms.command_blacklist

    if not isiterable(command):
        command = set([command])

    unrestricted = set()

    for this_cmd in command:
        cmd = this_cmd
        while cmd:
            if _blacklist and cmd.callback in blacklist:
                break

            elif _whitelist and not cmd.callback in whitelist:
                break

            cmd = cmd.parent
        if not cmd:
            unrestricted.add(this_cmd)

    return unrestricted