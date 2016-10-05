'''

If this is running then python is obviously installed, but we need to make sure that python3 is installed.

What we need to do:
    0. (optional) Check disk space
        0.1: The same env checks in run.py?
    1: Make sure this is python 3.5+
      1.1: If we installed python 3.5, restart using that
    2. Check for and install required programs:
      - brew (osx)
      - git
      - ffmpeg
      - libopus (non windows)
      - libffi (non windows)
      - libsodium (sometimes needed, might need to check after pynacl)
      - a compiler
    3: Ensure pip and update pip
    4: Git clone and clean out non arch related stuff (run scripts, bins/ on non-windows)
    5: Install requirements.txt packages (if everything is ok then no errors should occur)
    6. Copy configs and prompt the user for something (maybe)

The OSX specific steps might be a bit different so we just need to pay special attention to those steps
Remember to make sure the user knows the script might prompt for password
Print the command beforehand just so they know whats happening

When the script runs the user should be greeted with some text and a press [enter/whatever] to continue prompt
'''

from __future__ import print_function

import os
import re
import sys
import logging
import platform
import subprocess

try:
    import urllib.request
    from urllib.request import Request
except ImportError:
    pass
    # Doesn't matter, we'll be running python 3 by the time we use these
    # Unless we need to download python, in which case i'll figure that out later

# Logging setup goes here

PY_VERSION = sys.version_info # (3, 5, 1, ...)
SYS_PLATFORM = sys.platform   # 'win32', 'linux', 'darwin'
SYS_UNAME = platform.uname()
SYS_ARCH = ('32', '64')[SYS_UNAME.machine.endswith('64')]
SYS_PKGMANAGER = None # TODO: Figure this out

PLATFORMS = ['win32', 'linux', 'darwin']

MINIMUM_PY_VERSION = (3, 5)


if SYS_PLATFORM not in PLATFORMS:
    raise RuntimeError('Unsupported system "%s"' % SYS_PLATFORM)

# python2 compat bollocks
if PY_VERSION >= (3,):
    raw_input = input


def sudo_check_output(args, **kwargs):
    if not isinstance(args, (list, tuple)):
        args = args.split()

    return subprocess.check_output(('sudo',) + args, **kwargs)

def sudo_check_call(args, **kwargs):
    if not isinstance(args, (list, tuple)):
        args = args.split()

    return subprocess.check_call(('sudo',) + args, **kwargs)


###############################################################################


class SetupTask:

    def __getattribute__(self, item):
        try:
            # Check for platform variant of function first
            return object.__getattribute__(self, item + '_' + SYS_PLATFORM)
        except:
            pass

        if item.endswith('_dist'):
            try:
                # check for dist aliases, ex: setup_dist -> setup_win32
                return object.__getattribute__(self, item.rsplit('_', 1)[0] + '_' + SYS_PLATFORM)
            except:
                try:
                    # If there's no dist variant, try to fallback to the generic, ex: setup_dist -> setup
                    return object.__getattribute__(self, item.rsplit('_', 1)[0])
                except:
                    pass

        return object.__getattribute__(self, item)

    @classmethod
    def run(cls):
        self = cls()
        if not self.check():
            self.setup(self.download())

    def check(self):
        """
        Check to see if the component exists and works
        """
        pass

    def download(self):
        """
        Download the component
        """
        pass

    def setup(self, data):
        """
        Install the componenet and any other required tasks
        """
        pass


class EnsurePython(SetupTask):
    def check(self):
        if PY_VERSION >= MINIMUM_PY_VERSION:
            return True

        # try to find python 3.5 and rerun with it

    def download_win32(self):
        # https://www.python.org/ftp/python/3.5.2/python-3.5.2.exe
        pass

    def setup_win32(self, data):
        # There should be some sort of silent install option but I have to experiment with that
        pass

    def download_linux(self):
        # https://www.python.org/ftp/python/3.5.2/Python-3.5.2.tgz
        pass

    def setup_linux(self, data):
        # tar -xf data
        # do build process
        pass

    def download_darwin(self):
        # https://www.python.org/ftp/python/3.5.2/python-3.5.2-macosx10.6.pkg
        pass

    def setup_darwin(self, data):
        # idk maybe just execute it
        pass

    def _restart(self):
        pass # Restart with 3.5 if needed


class EnsureEnv(SetupTask):
    pass # basically the important checks from run.py


class EnsureBrew(SetupTask):
    def check(self):
        if SYS_PLATFORM == 'darwin':
            try:
                subprocess.check_output(['brew'])
            except FileNotFoundError:
                return False
            except subprocess.CalledProcessError:
                pass

        return True

    def download(self):
        cmd = '/usr/bin/ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"'
        subprocess.check_call(cmd, shell=True)

    def setup(self, data):
        subprocess.check_call('brew update'.split())


class EnsureGit(SetupTask):
    def check(self):
        try:
            subprocess.check_output(['git', '--version'])
        except FileNotFoundError:
            return False

        return True

    @staticmethod
    def _get_latest_win_git_version():
        version = ('2.10.1', 'v2.10.1.windows.1')
        try:
            url = "https://github.com/git-for-windows/git/releases/latest"
            req = Request(url, method='HEAD')

            with urllib.request.urlopen(req) as resp:
                full_ver = os.path.basename(resp.url)

            match = re.match(r'v(\d+\.\d+\.\d+)', full_ver)
            return match.groups()[0], full_ver
        except:
            return version

    @classmethod
    def _get_latest_win_get_download(cls):
        dist_ver, full_ver = cls._get_latest_win_git_version()
        url = "https://github.com/git-for-windows/git/releases/download/{fullver}/Git-{ver}-{arch}-bit.exe"

        return url.format(full_ver=full_ver, ver=dist_ver, arch=SYS_ARCH)

    def download_win32(self):
        result = urllib.request.urlretrieve(self._get_latest_win_get_download(), 'tmp/git-setup.exe')
        return result[0]

    def setup_win32(self, data):
        pass # if I can't figure out silent setup i'll just run it via os.system or something

    def download_linux(self):
        pass # need package manager abstraction

    def setup_linux(self, data):
        pass # nothing really needed, I don't think setting any git options is necessary

    def download_darwin(self):
        pass # brew install git

    def setup_darwin(self, data):
        pass # same as linux, probably can just delete these stubs


class EnsureFFmpeg(SetupTask):
    pass

class EnsureOpus(SetupTask):
    """
    See below for check strat, alternatively locate libopus.so.0
    """
    pass

class EnsureFFI(SetupTask):
    """
    Check strategies include:
        linux subprocess.check_output("find /usr[/local]/include -iname 'ffi.h'", shell=True) (find /usr/include /usr/local/include ...?)
        gcc -lffi (Fail: cannot find -lffi) vs (Success: ...  undefined reference to `main')
        "echo | gcc -xc++ -E -v -" and parse
    """
    pass

class EnsureSodium(SetupTask):
    pass # This one is going to be weird since sometimes its not needed (check python import)

class EnsureCompiler(SetupTask):
    pass

class EnsurePip(SetupTask):
    pass

class GitCloneMusicbot(SetupTask):
    pass

class PipInstallRequirements(SetupTask):
    pass

class SetupMusicbot(SetupTask):
    pass


###############################################################################


def preface():
    print("This is where the text goes")
    raw_input("Press enter to begin. ")

def main():
    EnsurePython.run()
    EnsureBrew.run()
    EnsureGit.run()
    EnsureFFmpeg.run()
    EnsureOpus.run()
    EnsureFFI.run()
    EnsureSodium.run()
    EnsureCompiler.run()
    EnsurePip.run()
    GitCloneMusicbot.run()
    PipInstallRequirements.run()
    SetupMusicbot.run()


if __name__ == '__main__':
    main()

