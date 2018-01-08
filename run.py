# coding=utf-8

from __future__ import print_function

import sys
import os
import subprocess
import logging
import tempfile
import traceback
import time
import argparse

try:
    import webbrowser
    import importlib.util
    import pathlib
except ImportError:  # py 2
    pass

REQUIRED_PY_VERSION = (3, 5)
FILL_CHAR = '─'

# Arguments
parser = argparse.ArgumentParser(description='The original MusicBot for Discord.')
parser.add_argument('--start', help='non-interactively starts the bot', action='store_true')
parser.add_argument('--update', help='updates the bot and dependencies', action='store_true')
parser.add_argument('--skip-checks', help='skips the bot\'s initial checks', action='store_true')
app_args = parser.parse_args()

# Logging
try:
    tmpfile = tempfile.TemporaryFile('w+', encoding='utf8')
except TypeError:
    tmpfile = tempfile.TemporaryFile('w+')
log = logging.getLogger('launcher')
log.setLevel(logging.DEBUG)

sh = logging.StreamHandler(stream=sys.stdout)
sh.setFormatter(logging.Formatter(
    fmt="[%(levelname)s] %(name)s: %(message)s"
))

sh.setLevel(logging.INFO)
log.addHandler(sh)

tfh = logging.StreamHandler(stream=tmpfile)
tfh.setFormatter(logging.Formatter(
    fmt="[%(relativeCreated).9f] %(asctime)s - %(levelname)s - %(name)s: %(message)s"
))
tfh.setLevel(logging.DEBUG)
log.addHandler(tfh)

def finalize_logging():
    if os.path.isfile("logs/musicbot.log"):
        log.info("Moving old log.")
        try:
            if os.path.isfile("logs/musicbot.log.last"):
                os.unlink("logs/musicbot.log.last")
            os.rename("logs/musicbot.log", "logs/musicbot.log.last")
        except Exception:
            pass

    with open("logs/musicbot.log", 'w', encoding='utf8') as f:
        tmpfile.seek(0)
        f.write(tmpfile.read())
        tmpfile.close()

    global tfh
    log.removeHandler(tfh)
    del tfh

    fh = logging.FileHandler("logs/musicbot.log", mode='a')
    fh.setFormatter(logging.Formatter(
        fmt="[%(relativeCreated).9f] %(name)s-%(levelname)s: %(message)s"
    ))
    fh.setLevel(logging.DEBUG)
    log.addHandler(fh)

    sh.setLevel(logging.INFO)

    dlog = logging.getLogger('discord')
    dlh = logging.StreamHandler(stream=sys.stdout)
    dlh.terminator = ''
    dlh.setFormatter(logging.Formatter('.'))
    dlog.addHandler(dlh)

def uinput(text=''):
    return input("{0}-> ".format(text)).lower().strip()

def run_sp(args, shell=True, check=True):
    """Runs a command using subprocess and handles logging"""
    try:
        r = subprocess.run(args, shell=shell, check=check, stdout=subprocess.PIPE, encoding='utf-8')
    except AttributeError:  # py2 bollocks
        try:
            r = subprocess.check_output(args, shell=shell)
        except Exception:
            raise
    except TypeError:  # py3.5 bollocks
        try:
            r = subprocess.run(args, shell=shell, check=check, stdout=subprocess.PIPE, universal_newlines=True)
        except Exception:
            raise
    except subprocess.CalledProcessError as e:
        log.debug(e.stdout)
        raise
    except Exception as e:
        log.debug(e)
        raise
    try:
        log.debug(r.stdout)
    except AttributeError:  # py2 bollocks
        log.debug(r)
    return r

def check_py():
    log.info('Running Python {0.major}.{0.minor}.'.format(sys.version_info))

    if not sys.version_info >= REQUIRED_PY_VERSION:
        # Try and find a working Python 3 executable
        log.warning('Using an incompatible Python version. Attempting to find an alternative.')
        pycom = None
        tests = ['py -3', 'python3', 'python3.5']
        for t in tests:
            log.debug('Trying {0}'.format(t))
            try:
                run_sp('{0} -c "exit()"'.format(t), shell=True)
                pycom = t
                break
            except subprocess.CalledProcessError:
                continue
            except (IOError, OSError):  # py2 bollocks is why this isn't a filenotfounderror
                continue

        if pycom:
            log.info('Relaunch this file using "{0} run.py"'.format(pycom))
            terminate()
        else:
            log.warning('Could not find a working executable. Please update Python to {0} or higher.'.format(REQUIRED_PY_VERSION))
            terminate()

def check_encoding():
    log.debug("Checking console encoding")

    if sys.platform.startswith('win') or sys.stdout.encoding.replace('-', '').lower() != 'utf8':
        log.info("Setting console encoding to UTF-8.")

        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf8', line_buffering=True)
        # only slightly evil
        sys.__stdout__ = sh.stream = sys.stdout

        if os.environ.get('PYCHARM_HOSTED', None) not in (None, '0'):
            log.info("Enabling colors in pycharm pseudoconsole")
            sys.stdout.isatty = lambda: True

def restart(pycom=None, quick=False, *args):
    pycom = pycom if pycom else sys.executable
    # Python 2 compatibility bullshit
    args = [pycom] + list(args) + list(sys.argv)
    if quick:
        args.append('--start')
    # Buggy on Windows: https://bugs.python.org/issue19124
    os.execv(pycom, args)

def start_bot():
    import asyncio

    tried_requirementstxt = False
    retry = True
    loops = 0
    max_wait_time = 60

    while retry:
        # Maybe I need to try to import stuff first, then actually import stuff
        # It'd save me a lot of pain with all that awful exception type checking

        m = None
        print()
        try:
            from musicbot import MusicBot
            m = MusicBot()

            sh.terminator = ''
            log.info("Connecting")
            sh.terminator = '\n'

            m.run()
        except SyntaxError:
            log.exception("Syntax error (this is a bug, not your fault)")
            break
        except ImportError:
            log.exception("Could not import a module.")
            if not tried_requirementstxt:
                tried_requirementstxt = True
                update_deps()
            else:
                break
        except Exception as e:
            if hasattr(e, '__module__') and e.__module__ == 'musicbot.exceptions':
                if e.__class__.__name__ == 'HelpfulError':
                    log.info(e.message)
                    break
                elif e.__class__.__name__ == "TerminateSignal":
                    break
                elif e.__class__.__name__ == "RestartSignal":
                    restart(quick=True)
            else:
                log.exception("Error starting the bot.")
        finally:
            if not m or not m.init_ok:
                if any(sys.exc_info()):
                    # How to log this without redundant messages...
                    traceback.print_exc()
                break

            asyncio.set_event_loop(asyncio.new_event_loop())
            loops += 1

        sleeptime = min(loops * 2, max_wait_time)
        if sleeptime:
            log.info("Restarting in {} seconds...".format(loops * 2))
            time.sleep(sleeptime)

    print()
    terminate()

def terminate(msg="Press enter to continue...", code=1, with_msg=True):
    if with_msg:
        input(msg)
    sys.exit(code)

def check_env():
    try:
        assert os.path.isdir('config'), 'could not find "config" folder'
        assert os.path.isdir('musicbot'), 'could not find "musicbot" folder'
        assert os.path.isdir('.git'), 'bot was not installed using Git'
        assert os.path.isfile('musicbot/__init__.py'), 'could not load the bot\'s Python module'
        assert importlib.util.find_spec('musicbot'), "could not import the bot\'s Python module"
    except AssertionError as e:
        log.critical('Failed check: {0}. Please visit http://bit.ly/dmbguide for official install steps.'.format(e))
        terminate()
    log.info('Installation is ok.')

def check_version():
    log.debug('Doing Git version checks...')
    try:
        import git
    except ImportError:
        update_deps()
        import git

    try:
        repo = git.Repo(os.getcwd())
        assert not repo.is_dirty(), 'local changes have been made'
        assert not repo.bare, 'repository is bare'
        remote = repo.remote(name='origin')
        remote.fetch()
    except git.exc.InvalidGitRepositoryError:  # shouldn't happen, we already checked for .git
        log.warning('The folder is not a valid Git repository. Aborting.')
        terminate()
    except AssertionError as e:
        log.warning('Can\'t check for bot updates: {0}.'.format(e))
        return
    except ValueError:
        log.warning('Could not find a Git remote linked to this repo.')
        return

    behind = list(repo.iter_commits('{0}..origin/{0}'.format(repo.active_branch.name)))
    if behind:
        log.warning('Your repo is behind by {0} commits.'.format(len(behind)))
        while True:
            print()
            print(' An update is available '.center(50, FILL_CHAR))
            print('It is recommended that you keep your bot up to date to ensure you have the latest'
                  '\nbug fixes and feature updates. For information about the changes, see'
                  '\nhttps://github.com/Just-Some-Bots/MusicBot/releases')
            print()
            r = uinput('Update now? [y/n] ')
            if r == 'y':
                try:
                    remote.pull()
                    return True
                except git.exc.GitCommandError as e:
                    log.error('Could not update the bot: {0}'.format(e))
            elif r == 'n':
                return
    else:
        log.info('Bot is up to date. [{0.summary} (by {0.author.name})]'.format(repo.head.commit))

def open_browser(url):
    if not sys.platform.startswith('linux'):  # I'd rather not run a non-GUI browser lol
        try:
            webbrowser.open(url)
        except Exception:
            pass
    log.info('Visit {0} for help.'.format(url))

def update_deps():
    log.info('Updating dependencies...')
    run_sp([sys.executable, '-m', 'pip', 'install', '-U', 'pip'], shell=False)
    res = run_sp([sys.executable, '-m', 'pip', 'install', '-U', '-r', 'requirements.txt'], shell=False)
    out = res.stdout.lower()
    if 'failed with' in out:
        print(res.stdout)
        log.error('Could not install a dependency. You may need to run this as an admin/sudo.')
        return
    log.info('Updated dependencies.')

def ensure_folders():
    pathlib.Path('logs').mkdir(exist_ok=True)
    pathlib.Path('data').mkdir(exist_ok=True)

def main():
    if not app_args.skip_checks:
        check_py()
        check_encoding()
        check_env()

    ensure_folders()
    finalize_logging()
    up = check_version()
    if up is True:
        restart()

    if app_args.start:
        start_bot()
    elif app_args.update:
        check_version()
        update_deps()
    else:
        try:
            from musicbot.constants import VERSION
        except Exception:
            VERSION = '(unknown ver)'

        while True:
            print()
            print(' MusicBot {0} '.format(VERSION).center(50, FILL_CHAR))
            print('[1] Start - starts the bot (--start)'
                  '\n[2] Update - updates the bot and its dependencies (--update)'
                  '\n[3] Help - provides information and help for the bot'
                  '\n[q] Quit')
            print()
            r = uinput('Choose an option ')
            if r == '1':
                start_bot()
            elif r == '2':
                check_version()
                update_deps()
                restart()
            elif r == '3':
                url = 'https://github.com/Just-Some-Bots/MusicBot/wiki'
                open_browser(url)
            elif r == 'q':
                break

if __name__ == '__main__':
    main()
