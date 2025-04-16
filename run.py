#!/usr/bin/env python3

import argparse
import asyncio
import importlib.util
import json
import logging
import os
import pathlib
import shutil
import signal
import ssl
import subprocess
import sys
import time
from typing import Any, Callable, Coroutine, Dict, List, Optional, Tuple, Union

import musicbot.logs
from musicbot import get_write_base, parse_write_base_arg, write_path
from musicbot.constants import (
    DEFAULT_AUDIO_CACHE_DIR,
    DEFAULT_DATA_DIR,
    DEFAULT_I18N_LANG,
    DEFAULT_LOGS_KEPT,
    DEFAULT_LOGS_ROTATE_FORMAT,
    DEFAULT_MEDIA_FILE_DIR,
    DEFAULT_OPTIONS_FILE,
    EXAMPLE_OPTIONS_FILE,
    EXAMPLE_PERMS_FILE,
    MAXIMUM_LOGS_LIMIT,
)
from musicbot.constants import VERSION as BOTVERSION
from musicbot.exceptions import (
    HelpfulError,
    RestartCode,
    RestartSignal,
    TerminateSignal,
)
from musicbot.i18n import _L, I18n
from musicbot.logs import (
    rotate_log_files,
    set_logging_level,
    set_logging_max_kept_logs,
    set_logging_rotate_date_format,
    setup_loggers,
    shutdown_loggers,
)

# protect dependency import from stopping the launcher
try:
    # This has been available for 7+ years. So it should be OK to do this...
    from aiohttp.client_exceptions import ClientConnectorCertificateError
except ImportError:
    # prevent NameError while handling exceptions later, if import fails.
    class ClientConnectorCertificateError(Exception):  # type: ignore[no-redef]
        pass


I18n()
parse_write_base_arg()
musicbot.logs.install_logger()
log = logging.getLogger("musicbot.launcher")


class GIT:
    @classmethod
    def works(cls, raise_instead: bool = False) -> bool:
        """
        Checks for output from git --version to verify git can be run.

        :param: raise_instead:  Return True on success but raise Runtime error otherwise.

        :raises:  RuntimeError  if `raise_instead` is set True.
        """
        try:
            git_bin = shutil.which("git")
            if not git_bin:
                if raise_instead:
                    raise RuntimeError(
                        "Cannot locate `git` executable in environment path."
                    )
                return False
            return bool(subprocess.check_output([git_bin, "--version"]))
        except (
            OSError,
            ValueError,
            PermissionError,
            FileNotFoundError,
            subprocess.CalledProcessError,
        ) as e:
            if raise_instead:
                raise RuntimeError(
                    f"Cannot execute `git` commands due to an error:  {str(e)}"
                ) from e
            return False

    @classmethod
    def show_branch(cls) -> str:
        """
        Runs `git rev-parse --abbrev-ref HEAD` to get the current branch name.
        Will return an empty string if running the command fails.
        """
        try:
            git_bin = shutil.which("git")
            if not git_bin:
                log.warning("Could not find git executable.")
                return ""

            gitbytes = subprocess.check_output(
                [git_bin, "rev-parse", "--abbrev-ref", "HEAD"],
                stderr=subprocess.STDOUT,
            )
            branch = gitbytes.decode("utf8").strip()

            return branch
        except (OSError, ValueError, subprocess.CalledProcessError):
            return ""

    @classmethod
    def check_updates(cls) -> Tuple[str, str]:
        """
        Runs `git fetch --dry-run` and extracts the commit IDs.
        If the command fails or no commit IDs are found, this
        will return empty strings rather than raise errors.
        """
        branch = cls.show_branch()
        if not branch:
            return ("", "")

        try:
            commit_at = ""
            commit_to = ""
            git_bin = shutil.which("git")
            if not git_bin:
                return ("", "")

            gitbytes = subprocess.check_output([git_bin, "fetch", "--dry-run"])
            lines = gitbytes.decode("utf8").split("\n")
            for line in lines:
                parts = line.split()
                if branch in parts:
                    commits = line.strip().split(" ", maxsplit=1)[0]
                    commit_at, commit_to = commits.split("..")
                    break

            return (commit_at, commit_to)
        except (OSError, ValueError, subprocess.CalledProcessError):
            return ("", "")

    @classmethod
    def run_upgrade_pull(cls) -> None:
        """Runs `git pull` in the current working directory."""
        cls.works(raise_instead=True)

        log.info("Attempting to upgrade with `git pull` on current path.")
        try:
            git_bin = shutil.which("git")
            if not git_bin:
                raise FileNotFoundError("Could not locate `git` executable on path.")
            raw_data = subprocess.check_output([git_bin, "pull"])
            git_data = raw_data.decode("utf8").strip()
            log.info("Result of git pull:  %s", git_data)
        except (
            OSError,
            UnicodeError,
            PermissionError,
            FileNotFoundError,
            subprocess.CalledProcessError,
        ):
            log.exception("Upgrade failed, you need to run `git pull` manually.")


class PIP:
    @classmethod
    def run(cls, command: str, check_output: bool = False) -> Union[bytes, int]:
        """Runs a pip command using `sys.exectutable -m pip` through subprocess.
        Given `command` is split before it is passed, so quoted items will not work.
        """
        if not cls.works():
            raise RuntimeError(_L("Cannot execute pip."))

        try:
            return cls.run_python_m(command.split(), check_output=check_output)
        except subprocess.CalledProcessError as e:
            return e.returncode
        except (OSError, PermissionError, FileNotFoundError):
            log.exception("Error using -m method")
        return 0

    @classmethod
    def run_python_m(
        cls, args: List[str], check_output: bool = False, quiet: bool = True
    ) -> Union[bytes, int]:
        """
        Use subprocess check_call or check_output to run a pip module
        command using the `args` as additional arguments to pip.
        The returned value of the call is returned from this method.

        :param: check_output:  Use check_output rather than check_call.
        """
        cmd_args = [sys.executable, "-m", "pip"] + args
        if check_output:
            if quiet:
                return subprocess.check_output(cmd_args, stderr=subprocess.DEVNULL)
            return subprocess.check_output(cmd_args)
        if quiet:
            return subprocess.check_call(cmd_args, stdout=subprocess.DEVNULL)
        return subprocess.check_call(cmd_args)

    @classmethod
    def run_install(
        cls, cmd: str, quiet: bool = False, check_output: bool = False
    ) -> Union[bytes, int]:
        """
        Runs pip install command and returns the command exist status.

        :param: cmd:  a string of arguments passed to `pip install`.
        :param: quiet:  attempt to silence output using -q command flag.
        :param: check_output:  return command output instead of exit code.
        """
        q_flag = "-q " if quiet else ""
        return cls.run(f"install {q_flag}{cmd}", check_output)

    @classmethod
    def works(cls) -> bool:
        """Checks for output from pip --version to verify pip can be run."""
        try:
            rcode = cls.run_python_m(["--version"])
            if rcode == 0:
                return True
            return False
        except subprocess.CalledProcessError:
            log.exception("PIP failed while calling sub-process.")
            return False
        except PermissionError:
            log.exception("PIP failed due to Permission Error.")
            return False
        except FileNotFoundError:
            log.exception(
                "PIP failed due to missing Python executable?  (%s)",
                sys.executable,
            )
            return False
        except OSError:
            log.exception("PIP failed due to OSError.")
            return False

    @classmethod
    def check_updates(cls) -> List[Dict[str, Any]]:
        """
        Runs `pip install -U -r ./requirements.txt --quiet --dry-run --report -`
        and returns the number of packages that could be updated.
        """
        updata = cls.run_install(
            "-U -r ./requirements.txt --quiet --dry-run --report -",
            check_output=True,
        )
        try:
            if isinstance(updata, bytes):
                pip_data = json.loads(updata.decode(errors="ignore"))
                ilist = pip_data.get("install", [])
                if not isinstance(ilist, list):
                    return []
                return ilist
        except json.JSONDecodeError:
            log.warning("Could not decode pip update report JSON.")

        return []

    @classmethod
    def run_upgrade_requirements(
        cls,
        get_output: bool = False,
        quiet: bool = True,
    ) -> Union[str, int]:
        """
        Uses a subprocess call to run python using sys.executable.
        Runs `pip install --no-warn-script-location --no-input -U -r ./requirements.txt`
        This method attempts to catch all exceptions and ensure a return value.

        :param: get_output:  Return the process output rather than its exit code.
            If set True, and an exception is caught, this will return the string "[[ProcessException]]"
            If set False and an exception is caught, this will return int -255

        :returns:  process exit code, where 0 is assumed success.
        """
        if not cls.works():
            raise RuntimeError(_L("Cannot locate or execute python -m pip"))

        log.info(
            "Attempting to upgrade with `%s` on current path...",
            "pip install --upgrade -r requirements.txt",
        )
        try:
            raw_data = cls.run_python_m(
                [
                    "install",
                    "--no-warn-script-location",
                    "--no-input",
                    "-U",
                    "-r",
                    "requirements.txt",
                ],
                check_output=get_output,
                quiet=quiet,
            )
            if isinstance(raw_data, bytes):
                pip_data = raw_data.decode("utf8").strip()
                log.info("Result of pip upgrade:\n%s", pip_data)
                if get_output:
                    return pip_data

            if isinstance(raw_data, int):
                log.info("Result exit code from pip upgrade: %s", raw_data)
                return raw_data

            # if somehow raw_data is not int or bytes.
            if get_output:
                return "[[OutputTypeException]]"
            return -255
        except (
            PermissionError,
            FileNotFoundError,
            OSError,
            UnicodeError,
            subprocess.CalledProcessError,
        ):
            log.exception(
                "Upgrade failed to execute or we could not understand the output"
            )
            log.warning(
                "You may need to run `%s` manually.",
                "pip install --upgrade -r requirements.txt",
            )

            if get_output:
                return "[[ProcessException]]"
            return -255


def bugger_off(msg: str = _L("Press enter to continue . . ."), code: int = 1) -> None:
    """Make the console wait for the user to press enter/return."""
    input(msg)
    sys.exit(code)


def sanity_checks(args: argparse.Namespace) -> None:
    """
    Run a collection of pre-startup checks to either automatically correct
    issues or inform the user of how to correct them.

    :param: optional:  Toggle optional start up checks.
    """
    log.info("Starting sanity checks")
    """Required Checks"""
    # Make sure we're on Python 3.9+
    req_ensure_py3()

    # Make sure we're in a writable env
    req_ensure_env()

    # For rewrite only
    req_check_deps()

    log.info("Required checks passed.")

    """Optional Checks"""
    if not args.do_start_checks:
        return

    # Check disk usage
    opt_check_disk_space()

    # Display an update check, if enabled.
    if not args.no_update_check:
        opt_check_updates()
    else:
        log.info("Skipped checking for updates.")

    log.info("Optional checks passed.")


def req_ensure_py3() -> None:
    """
    Verify the current running version of Python and attempt to find a
    suitable minimum version in the system if the running version is too old.
    """
    log.info("Checking for Python 3.9+")

    if sys.version_info < (3, 9):
        log.warning(
            "Python 3.9+ is required. This version is %s", sys.version.split()[0]
        )
        log.warning("Attempting to locate Python 3.9...")
        # Should we look for other versions than min-ver?

        pycom = None

        if sys.platform.startswith("win"):
            pycom = shutil.which("py.exe")
            if not pycom:
                log.warning("Could not locate py.exe")

            try:
                subprocess.check_output([pycom, "-3.9", '-c "exit()"'])
                pycom = f"{pycom} -3.9"
            except (
                OSError,
                PermissionError,
                FileNotFoundError,
                subprocess.CalledProcessError,
            ):
                log.warning("Could not execute `py.exe -3.9` ")
                pycom = None

            if pycom:
                log.info("Python 3 found.  Launching bot...")
                os.system(f"start cmd /k {pycom} run.py")
                sys.exit(0)

        else:
            log.info('Trying "python3.9"')
            pycom = shutil.which("python3.9")
            if not pycom:
                log.warning("Could not locate python3.9 on path.")

            try:
                subprocess.check_output([pycom, '-c "exit()"'])
            except (
                OSError,
                PermissionError,
                FileNotFoundError,
                subprocess.CalledProcessError,
            ):
                pycom = None

            if pycom:
                log.info(
                    "\nPython 3.9 found.  Re-launching bot using: %s run.py\n", pycom
                )
                os.execlp(pycom, pycom, "run.py")

        log.critical(
            "Could not find Python 3.9 or higher.  Please run the bot using Python version 3.9 to 3.13"
        )
        bugger_off()


def req_check_deps() -> None:
    """
    Check that we have the required dependency modules at the right versions.
    """
    try:
        import discord  # pylint: disable=import-outside-toplevel

        if discord.version_info.major < 2:
            log.critical(
                (
                    "This version of MusicBot requires a newer version of discord.py. "
                    "Your version is %s. Try running the update.py script."
                ),
                discord.__version__,
            )
            bugger_off()
    except ImportError:
        # if we can't import discord.py, an error will be thrown later down the line anyway
        pass
    except AttributeError:
        # if the user has a library like dpytest installed but discord.py is missing somehow.
        pass


def req_ensure_env() -> None:
    """
    Inspect the environment variables, validating and updating values where needed.
    """
    log.info("Ensuring we're in the right environment")

    if os.environ.get("APP_ENV") != "docker" and not os.path.isdir(".git"):
        # NOTICE:
        # if you feel like removing this check to "make it work"
        # be aware this project depends on git for version information
        # as well as ease of updating the bot.
        log.critical(
            "MusicBot was not installed using Git.\n"
            "Check the documentation for install guides:\n"
            "  https://just-some-bots.github.io/MusicBot/"
        )
        bugger_off()

    # Make sure musicbot exists and test if it can be imported.
    try:
        if not os.path.isdir("musicbot"):
            raise RuntimeError(_L('folder "musicbot" not found'))

        if not os.path.isfile("musicbot/__init__.py"):
            raise RuntimeError(_L("musicbot folder is not a Python module"))

        if not importlib.util.find_spec("musicbot"):
            raise RuntimeError(_L("musicbot module is not importable"))
    except RuntimeError as e:
        log.critical("Failed environment check, %s", e)
        bugger_off()

    # test we have permissions to write files.
    # if so, make all our write-enabled directories if needed.
    test_path: pathlib.Path = write_path("musicbot-test-folder")
    try:
        os.mkdir(test_path)
        # Make our write-enabled folders if needed.
        write_path(DEFAULT_DATA_DIR).mkdir(parents=True, exist_ok=True)
        write_path(DEFAULT_OPTIONS_FILE).parent.mkdir(parents=True, exist_ok=True)
        write_path(DEFAULT_MEDIA_FILE_DIR).mkdir(parents=True, exist_ok=True)
        write_path(DEFAULT_AUDIO_CACHE_DIR).mkdir(parents=True, exist_ok=True)
    except (
        OSError,
        FileExistsError,
        PermissionError,
        IsADirectoryError,
    ):
        basedir = get_write_base()
        if not basedir:
            basedir = os.getcwd()

        log.critical(
            "MusicBot could not write files in the following directory:\n%(dir)s",
            {"dir": basedir},
        )
        log.critical(
            "Please make sure MusicBot can read and write in the above directory."
        )
        bugger_off()
    finally:
        try:
            shutil.rmtree(test_path, ignore_errors=True)
        except Exception:  # pylint: disable=broad-exception-caught
            log.exception("Failed to clean up write-test path.")

    # this actually does an access check as well.
    ffmpeg_bin = shutil.which("ffmpeg")
    if sys.platform.startswith("win"):
        if ffmpeg_bin:
            log.info("Detected FFmpeg is installed at:  %s", ffmpeg_bin)
        else:
            log.info("Adding local bins/ folder environment PATH for bundled ffmpeg...")
            os.environ["PATH"] += ";" + os.path.abspath("bin/")
            sys.path.append(os.path.abspath("bin/"))  # might as well
            # try to get the local bin path again.
            ffmpeg_bin = shutil.which("ffmpeg")

    # make sure ffmpeg is available.
    if not ffmpeg_bin:
        log.critical(
            "MusicBot could not locate FFmpeg binary in your environment.\n"
            "Please install FFmpeg so it is available in your environment PATH variable."
        )
        if sys.platform.startswith("win"):
            log.info(
                "On Windows, you can add a pre-compiled EXE to the MusicBot `bin` folder,\n"
                "or you can install FFmpeg system-wide using WinGet or by running the install.bat file."
            )
        elif sys.platform.startswith("darwin"):
            log.info(
                "On MacOS, you may be able to install FFmpeg via homebrew.\n"
                "Otherwise, check the official FFmpeg site for build or install steps."
            )
        else:
            log.info(
                "On Linux, many distros make FFmpeg available via system package managers.\n"
                "Check for ffmpeg with your system package manager or build from sources."
            )
        bugger_off()


def opt_check_disk_space(warnlimit_mb: int = 200) -> None:
    """
    Performs and optional check of system disk storage space to warn the
    user if the bot might gobble that remaining space with downloads later.
    """
    if shutil.disk_usage(".").free < warnlimit_mb * 1024 * 2:
        log.warning(
            "Less than %sMB of free space remains on this device",
            warnlimit_mb,
        )


def opt_check_updates() -> None:
    """
    Runs a collection of git and pip commands and logs if updates are available.
    """
    log.info("\nChecking for updates to MusicBot or dependencies...")
    needs_update = False
    if GIT.works():
        git_branch = GIT.show_branch()
        commit_at, commit_to = GIT.check_updates()
        if commit_at and commit_to:
            log.warning(
                (
                    "MusicBot updates are available through `git` command.\n"
                    "Your current branch is:  %s\n"
                    "The latest commit ID is:  %s"
                ),
                git_branch,
                commit_to,
            )
            needs_update = True
        else:
            log.info("No MusicBot updates available via `git` command.")
    else:
        log.warning(
            "Could not check for updates using `git` commands.  You should check manually."
        )

    if PIP.works():
        install_pkgs = PIP.check_updates()
        package_count = len(install_pkgs)
        if package_count:
            pkg_list = _L("The following packages can be updated:\n")
            for pkg in install_pkgs:
                pkg_meta = pkg.get("metadata", {})
                pkg_name = pkg_meta.get("name", "")
                pkg_ver = pkg_meta.get("version", "")
                if pkg_name:
                    pkg_list += _L("  %s  to version:  %s\n") % (pkg_name, pkg_ver)
            log.warning(
                (
                    "There may be updates for dependency packages. "
                    "PIP reports %s package(s) could be installed.\n%s"
                ),
                package_count,
                pkg_list,
            )
            needs_update = True
        else:
            log.info("No dependency updates available via `pip` command.")
    else:
        log.warning(
            "Could not check for updates using `pip` commands.  You should check manually."
        )
    if needs_update:
        log.info(
            "You can run a guided update by using the command:\n    %s ./update.py",
            sys.executable,
        )


def parse_cli_args() -> argparse.Namespace:
    """
    Parse command line arguments and do reasonable checks and assignments.

    :returns:  Command line arguments parsed via argparse.
    """

    # define a few custom arg validators.
    def kept_logs_int(value: str) -> int:
        """Validator for log rotation limits."""
        try:
            val = int(value)
            if val > MAXIMUM_LOGS_LIMIT:
                raise ValueError(_L("Value is above the maximum limit."))
            if val <= -1:
                raise ValueError(_L("Value must not be negative."))
            return val
        except (TypeError, ValueError) as e:
            raise argparse.ArgumentTypeError(
                _L("Value for Max Logs Kept must be a number from 0 to %s")
                % (MAXIMUM_LOGS_LIMIT),
            ) from e

    def log_levels_int(level_name: str) -> int:
        """Validator for log level name to existing level int."""
        level_name = level_name.upper()
        try:
            val = getattr(logging, level_name, None)
            if not isinstance(val, int):
                raise TypeError(_L("Log level '%s' is not available.") % (level_name))
            return val
        except (TypeError, ValueError) as e:
            raise argparse.ArgumentTypeError(
                _L("Log Level must be one of:  %s")
                % (
                    "CRITICAL, ERROR, WARNING, INFO, DEBUG, VOICEDEBUG, FFMPEG, NOISY, EVERYTHING"
                ),
            ) from e

    ap = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            _L(
                "Launch a music playing discord bot built using discord.py, youtubeDL, and ffmpeg."
            )
            + "\n"
            + _L("Available via Github:")
            + "\n  https://github.com/Just-Some-Bots/MusicBot"
        ),
        epilog=(
            _L("For more help and support with this bot, join our discord:")
            + "\n  https://discord.gg/bots\n\n"
            + _L("This software is provided under the MIT License.")
            + "\n"
            + _L("See the `LICENSE` text file for complete details.")
        ),
    )

    # Allow language settings for logs and discord default.
    # Both domains in one
    ap.add_argument(
        "--lang",
        dest="lang_both",
        default=DEFAULT_I18N_LANG,
        metavar="LOCALE",
        type=str,
        help=_L(
            "Override the default / system detected language for all text in MusicBot."
        ),
    )
    # Lang in log domain.
    ap.add_argument(
        "--log_lang",
        dest="lang_logs",
        default=DEFAULT_I18N_LANG,
        metavar="LOCALE",
        type=str,
        help=_L("Use this language for all server-side log messages from MusicBot."),
    )
    # Lang in discord message domain.
    ap.add_argument(
        "--msg_lang",
        dest="lang_msgs",
        default=DEFAULT_I18N_LANG,
        metavar="LOCALE",
        type=str,
        help=_L(
            "Use this language for all messages sent to discord from MusicBot.\n"
            "This does not prevent per-guild language selection."
        ),
    )

    # Show Version and exit option.
    ap.add_argument(
        "-V",
        "--version",
        dest="show_version",
        action="store_true",
        help=_L("Print the MusicBot version information and exit."),
    )

    # No Startup Checks option.
    ap.add_argument(
        "--no-checks",
        dest="do_start_checks",
        action="store_false",
        help=_L("Skip all optional startup checks, including the update check."),
    )

    # Skip disk checks option.
    ap.add_argument(
        "--no-disk-check",
        dest="no_disk_check",
        action="store_true",
        help=_L("Skip only the disk space check at startup."),
    )

    # Skip update checks option.
    ap.add_argument(
        "--no-update-check",
        dest="no_update_check",
        action="store_true",
        help=_L("Skip only the update check at startup."),
    )

    # Disable dependency install on error option.
    ap.add_argument(
        "--no-install-deps",
        dest="no_install_deps",
        action="store_true",
        help=_L(
            "Disable MusicBot from trying to install dependencies when it cannot import them."
        ),
    )

    # Log related options.
    ap.add_argument(
        "--logs-kept",
        dest="keep_n_logs",
        default=DEFAULT_LOGS_KEPT,
        metavar="NUMBER",
        type=kept_logs_int,
        help=_L(
            "Specify how many log files to keep, between 0 and %s inclusive."
            " (Default: %s)"
        )
        % (MAXIMUM_LOGS_LIMIT, DEFAULT_LOGS_KEPT),
    )
    ap.add_argument(
        "--log-level",
        dest="log_level",
        default="NOTSET",
        metavar="LEVEL",
        type=log_levels_int,
        help=_L("Override the log level settings set in config. Must be one of: %s")
        % (
            "CRITICAL, ERROR, WARNING, INFO, DEBUG, VOICEDEBUG, FFMPEG, NOISY, EVERYTHING"
        ),
    )
    ap.add_argument(
        "--log-rotate-fmt",
        dest="old_log_fmt",
        default=DEFAULT_LOGS_ROTATE_FORMAT,
        metavar="FORMAT",
        type=str,
        help=_L(
            "Override the default date format used when rotating log files. "
            "This should contain values compatible with strftime().  "
            "(Default:  '%s')"
        )
        % (DEFAULT_LOGS_ROTATE_FORMAT.replace("%", "%%")),
    )

    ap.add_argument(
        "--write-dir",
        dest="global_writes_basedir",
        default="",
        metavar="PATH",
        type=str,
        help=_L(
            "Supply a directory where MusicBot can store all mutable files.\n"
            "Essentially treats the install directory as read-only.\n"
            "MusicBot must have permission to create this directory.\n"
        ),
    )

    ap.add_argument(
        "--mk-examples",
        dest="make_examples",
        action="store_true",
        help="Update or create example config files and then exit. Useful if code is changed or examples are out-of-date for some reason.",
    )

    args = ap.parse_args()

    # Show version and exit.
    if args.show_version:
        print("Just-Some-Bots/MusicBot\n" + _L("Version:  %s") % (BOTVERSION) + "\n")
        sys.exit(0)

    if -1 < args.keep_n_logs <= MAXIMUM_LOGS_LIMIT:
        set_logging_max_kept_logs(args.keep_n_logs)

    if args.log_level != logging.NOTSET:
        set_logging_level(args.log_level, override=True)

    if args.old_log_fmt != DEFAULT_LOGS_ROTATE_FORMAT:
        set_logging_rotate_date_format(args.old_log_fmt)

    return args


def setup_signal_handlers(
    loop: asyncio.AbstractEventLoop,
    callback: Callable[
        [signal.Signals, asyncio.AbstractEventLoop], Coroutine[Any, Any, None]
    ],
) -> None:
    """
    This function registers signal handlers with the event loop to help it close
    with more grace when various OS signals are sent to this process.
    """
    if os.name == "nt":
        return

    def handle_signal(sig: signal.Signals, loop: asyncio.AbstractEventLoop) -> None:
        """Creates and asyncio task to handle the signal on the event loop."""
        asyncio.create_task(callback(sig, loop), name=f"Signal_{sig.name}")

    # Linux/Unix signals we should clean up for.
    sigs = [signal.SIGTERM, signal.SIGINT, signal.SIGHUP]

    for sig in sigs:
        loop.add_signal_handler(sig, handle_signal, sig, loop)

    # set a flag to prevent adding more of the same handlers on soft restart.
    setattr(loop, "_sig_handler_set", True)


def respawn_bot_process() -> None:
    """
    Use a platform dependent method to restart the bot process, without
    an external process/service manager.
    This uses the sys.executable and sys.argv to restart the bot.

    This function attempts to make sure all buffers are flushed and logging
    is shut down before restarting the new process.

    On Linux/Unix-style OS this will use sys.execlp to replace the process
    while keeping the existing PID.

    On Windows OS this will use subprocess.Popen to create a new console
    where the new bot is started, with a new PID, and exit this instance.
    """
    exec_args = [sys.executable] + sys.argv

    shutdown_loggers()
    rotate_log_files()

    sys.stdout.flush()
    sys.stderr.flush()
    logging.shutdown()

    if os.name == "nt":
        # On Windows, this creates a new process window that dies when the script exits.
        # Seemed like the best way to avoid a pile of processes While keeping clean output in the shell.
        # There is seemingly no way to get the same effect as os.exec* on unix here in windows land.
        # The moment we end our existing instance, control is returned to the starting shell.
        subprocess.Popen(  # pylint: disable=consider-using-with
            exec_args,
            creationflags=subprocess.CREATE_NEW_CONSOLE,  # type: ignore[attr-defined]
        )
        print(_L("Opened a new MusicBot instance. This terminal can be safely closed!"))
        sys.exit(0)
    else:
        # On Unix/Linux/Mac this should immediately replace the current program.
        # No new PID, and the babies all get thrown out with the bath.  Kinda dangerous...
        # We need to make sure files and things are closed before we do this.
        os.execlp(exec_args[0], *exec_args)


def set_console_title() -> None:
    """
    Attempts to set the console window title using the current version string.
    On windows, this method will try to enable ANSI Escape codes by enabling
    virtual terminal processing or by calling an empty sub-shell.
    """
    # On windows, if colorlog isn't loaded already, ANSI escape codes probably
    # wont work like we expect them to.
    # This code attempts to solve that using ctypes and cursed windows-isms.
    # or if that fails (it shouldn't) it falls back to another cursed trick.
    if os.name == "nt":
        try:
            # if colorama fails to import we can assume setup_logs didn't load it.
            import colorama

            # this is only available in colorama version 0.4.6+
            # which as it happens isn't required by colorlog.
            colorama.just_fix_windows_console()
        except (ImportError, AttributeError):
            # This might only work for Win 10+
            from ctypes import windll  # type: ignore[attr-defined]

            k32 = windll.kernel32
            # For info on SetConsoleMode, see:
            #   https://learn.microsoft.com/en-us/windows/console/setconsolemode
            # For info on GetStdHandle, see:
            #   https://learn.microsoft.com/en-us/windows/console/getstdhandle
            try:
                k32.SetConsoleMode(k32.GetStdHandle(-11), 7)
            except Exception:  # pylint: disable=broad-exception-caught
                # If it didn't work, fall back to this cursed trick...
                # Since console -does- support ANSI escapes, but turns them off,
                # This sort of beats the current console buffer over the head with
                # the sub-shell's and then cannot disable the mode in parent shell.
                try:
                    # No version info for this, testing needed.
                    os.system("")
                except Exception:  # pylint: disable=broad-exception-caught
                    # if this failed too, we're just out of luck.
                    pass

    # Update the console title, ignore if it fails.
    try:
        sys.stdout.write(f"\x1b]2;MusicBot {BOTVERSION}\x07")
    except (TypeError, OSError):
        pass


def main() -> None:
    """
    All of the MusicBot starts here.
    """
    # Attempt to set console title.
    set_console_title()

    # take care of loggers right away
    setup_loggers()

    # parse arguments before any logs, so --help does not make an empty log.
    cli_args = parse_cli_args()

    # Log file creation is deferred until this first write.
    log.info("Loading MusicBot version:  %s", BOTVERSION)
    log.info("Log opened:  %s", time.ctime())
    log.info("Python version:  %s", sys.version)

    # Check if run.py is in the current working directory.
    run_py_dir = os.path.dirname(os.path.realpath(__file__))
    if run_py_dir != os.getcwd():
        # if not, verify musicbot and .git folders exists and change directory.
        run_mb_dir = pathlib.Path(run_py_dir).joinpath("musicbot")
        run_git_dir = pathlib.Path(run_py_dir).joinpath(".git")
        if run_mb_dir.is_dir() and run_git_dir.is_dir():
            log.warning("Changing working directory to:  %s", run_py_dir)
            os.chdir(run_py_dir)
        else:
            log.critical(
                "Cannot start the bot!  You started `run.py` in the wrong directory"
                " and we could not locate `musicbot` and `.git` folders to verify"
                " a new directory location."
            )
            log.error(
                "For best results, start `run.py` from the same folder you cloned MusicBot into.\n"
                "If you did not use git to clone the repository, you are strongly urged to."
            )
            time.sleep(3)  # make sure they see the message.
            sys.exit(127)

    # Handle startup checks, if they haven't been skipped.
    sanity_checks(cli_args)

    # Make sure Config doesn't wig out when no config exists but we still want to generate examples.
    if cli_args.make_examples and "MUSICBOT_TOKEN" not in os.environ:
        os.environ["MUSICBOT_TOKEN"] = "Your Token Here"

    exit_signal: Union[RestartSignal, TerminateSignal, None] = None
    event_loop: Optional[asyncio.AbstractEventLoop] = None
    tried_requirementstxt: bool = False
    use_certifi: bool = False
    retries: int = 0
    max_wait_time: int = 60

    while True:
        # Maybe I need to try to import stuff first, then actually import stuff
        # It'd save me a lot of pain with all that awful exception type checking

        m = None
        try:
            # Prevent re-import of MusicBot
            if "MusicBot" not in dir():
                from musicbot.bot import (  # pylint: disable=import-outside-toplevel
                    MusicBot,
                )

            # py3.8 made ProactorEventLoop default on windows.
            # py3.12 deprecated using get_event_loop(), we need new_event_loop().
            event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(event_loop)

            # init some of bot, but don't run it yet.
            m = MusicBot(  # pylint: disable=possibly-used-before-assignment
                use_certifi=use_certifi
            )

            # Update example options / permissions as needed.
            if cli_args.make_examples:
                log.info("Updating example config files...")
                m.config.register.write_default_ini(write_path(EXAMPLE_OPTIONS_FILE))
                m.permissions.register.write_default_ini(write_path(EXAMPLE_PERMS_FILE))
                raise TerminateSignal()

            # register system signal handlers with the event loop.
            if not getattr(event_loop, "_sig_handler_set", False):
                setup_signal_handlers(event_loop, m.on_os_signal)

            # let the MusicBot run free!
            event_loop.run_until_complete(m.run_musicbot())
            retries = 0

        except (ssl.SSLCertVerificationError, ClientConnectorCertificateError) as e:
            # For aiohttp, we need to look at the cause.
            if isinstance(e, ClientConnectorCertificateError) and isinstance(
                e.__cause__, ssl.SSLCertVerificationError
            ):
                e = e.__cause__
            else:
                log.critical(
                    "Certificate error is not a verification error, not trying certifi and exiting."
                )
                log.exception("Here is the exact error, it could be a bug.")
                break

            # In case the local trust store does not have the cert locally, we can try certifi.
            # We don't want to patch working systems with a third-party trust chain outright.
            # These verify_code values come from OpenSSL:  https://www.openssl.org/docs/man1.0.2/man1/verify.html
            if e.verify_code == 20:  # X509_V_ERR_UNABLE_TO_GET_ISSUER_CERT_LOCALLY
                if use_certifi:  # already tried it.
                    log.exception(
                        (
                            "Could not get Issuer Certificate even with certifi!\n"
                            "Try running:  %s -m pip install --upgrade certifi "
                        ),
                        sys.executable,
                    )
                    log.warning(
                        "To easily add a certificate to Windows trust store, \n"
                        "you can open the failing site in Microsoft Edge or IE...\n"
                    )
                    break

                log.warning(
                    "Could not get Issuer Certificate from default trust store, trying certifi instead."
                )
                use_certifi = True
                retries += 1
                continue

        except SyntaxError:
            if "-modded" in BOTVERSION:
                log.exception(
                    "Syntax error (modification detected, did you edit the code?)"
                )
            else:
                log.exception("Syntax error (this is a bug, not your fault)")
            break

        except (AttributeError, ImportError, ModuleNotFoundError) as e:
            # In case a discord extension is installed but discord.py isn't.
            if isinstance(e, AttributeError):
                if "module 'discord'" not in str(e):
                    raise

            if cli_args.no_install_deps:
                log.error(
                    # fmt: off
                    "Cannot start MusicBot due to an error!\n"
                    "\n"
                    "Problem:\n"
                    "  There was an error importing MusicBot or a dependency package.\n"
                    "\n"
                    "Solution:\n"
                    "  You need to manually install pip packages for MusicBot\n"
                    "  or launch without `--no-install-deps` and MusicBot will try to install them for you."
                    # fmt: on
                )
                break

            if not PIP.works():
                log.critical(
                    (
                        "MusicBot could not import dependency modules and we cannot run `pip` automatically!\n"
                        "You will need to manually install `pip` package for your version of python.\n"
                    )
                )
                log.warning(
                    (
                        "If you already installed `pip` but still get this error:\n"
                        " - Check that you installed it for this python version: %s\n"
                        " - Check installed packages are accessible to the user running MusicBot"
                    ),
                    sys.version.split(maxsplit=1)[0],
                )
                break

            if not tried_requirementstxt:
                tried_requirementstxt = True

                log.info(
                    "Attempting to install MusicBot dependency packages automatically...\n"
                )
                pip_exit_code = PIP.run_upgrade_requirements(quiet=False)

                # If pip ran without issue, it should return 0 status code.
                if pip_exit_code:
                    print()
                    log.critical(
                        # fmt: off
                        "MusicBot dependencies may not be installed!\n"
                        "\n"
                        "Problem:\n"
                        "  The pip install process ended with a possible error.\n"
                        "  Some or all of the the dependencies may be missing.\n"
                        "\n"
                        "Solution:\n"
                        "  You must manually install dependency packages.\n"
                        "  Open a CMD prompt / terminal to the MusicBot directory.\n"
                        "  You can try using the update scripts install packages.\n"
                        "  Or try this manual command:\n"
                        "    %(py_bin)s -m pip install -U -r ./requirements.txt\n"
                        "\n"
                        "You can also ask for help in MusicBot's support discord:\n"
                        "  https://discord.gg/bots",
                        # fmt: on
                        {"py_bin": sys.executable}
                    )
                    break

                print()
                log.info("OK, lets hope installing dependencies worked!")
                print()

                retries += 1
                continue

            if tried_requirementstxt and retries >= 1:
                exit_signal = RestartSignal(RestartCode.RESTART_FULL)
                retries += 1
                break

            log.error(
                "MusicBot got an ImportError after trying to install packages. MusicBot must exit..."
            )
            log.exception("The exception which caused the above error: ")
            retries = 0
            exit_signal = TerminateSignal(exit_code=1)
            break

        except HelpfulError as e:
            if e.fmt_args:
                log.error(_L(e.message), e.fmt_args)
            else:
                log.error(_L(e.message))
            break

        except TerminateSignal as e:
            exit_signal = e
            retries = 0
            break

        except RestartSignal as e:
            if e.get_name() == "RESTART_SOFT":
                log.info("MusicBot is doing a soft restart...")
                retries = 1
                continue

            log.info("MusicBot is doing a full process restart...")
            exit_signal = e
            retries = 1
            break

        except Exception:  # pylint: disable=broad-exception-caught
            log.exception("Error starting bot")
            break

        finally:
            if event_loop:
                log.debug("Closing event loop.")
                event_loop.close()

            sleeptime = min(retries * 2, max_wait_time)
            if sleeptime:
                log.info("Restarting in %s seconds...", sleeptime)
                time.sleep(sleeptime)

    print()
    log.info("All done.")

    shutdown_loggers()
    rotate_log_files()

    print()

    if exit_signal:
        if isinstance(exit_signal, RestartSignal):
            if exit_signal.get_name() == "RESTART_FULL":
                respawn_bot_process()
            elif exit_signal.get_name() == "RESTART_UPGRADE_ALL":
                PIP.run_upgrade_requirements()
                GIT.run_upgrade_pull()
                respawn_bot_process()
            elif exit_signal.get_name() == "RESTART_UPGRADE_PIP":
                PIP.run_upgrade_requirements()
                respawn_bot_process()
            elif exit_signal.get_name() == "RESTART_UPGRADE_GIT":
                GIT.run_upgrade_pull()
                respawn_bot_process()
        elif isinstance(exit_signal, TerminateSignal):
            sys.exit(exit_signal.exit_code)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(_L("OK, we're closing!"))
        shutdown_loggers()
        rotate_log_files()

    sys.exit(0)
