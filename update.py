#!/usr/bin/env python3

import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from typing import Any, List, Optional, Tuple
from urllib.request import urlopen


def yes_or_no_input(question: str) -> bool:
    """
    Prompt the user for a yes or no response to given `question`
    As many times as it takes to get yes or no.
    """
    while True:
        ri = input(f"{question} (y/n): ")

        if ri.lower() in ["yes", "y"]:
            return True

        if ri.lower() in ["no", "n"]:
            return False


def run_or_raise_error(cmd: List[str], message: str, **kws: Any) -> None:
    """
    Wrapper for subprocess.check_call that avoids shell=True

    :raises: RuntimeError  with given `message` as exception text.
    """
    try:
        subprocess.check_call(cmd, **kws)
    except (  # pylint: disable=duplicate-code
        OSError,
        PermissionError,
        FileNotFoundError,
        subprocess.CalledProcessError,
    ) as e:
        raise RuntimeError(message) from e


def get_bot_version(git_bin: str) -> str:
    """
    Gets the bot current version as reported by git, without loading constants.
    """
    try:
        ver = (
            subprocess.check_output(
                [git_bin, "describe", "--tags", "--always", "--dirty"]
            )
            .decode("ascii")
            .strip()
        )

    except (subprocess.SubprocessError, OSError, ValueError) as e:
        print(f"Failed getting version due to:  {str(e)}")
        ver = "unknown"

    print(f"Current version:  {ver}")
    return ver


def get_bot_branch(git_bin: str) -> str:
    """Uses git to find the current branch name."""
    try:
        branch = (
            subprocess.check_output([git_bin, "rev-parse", "--abbrev-ref", "HEAD"])
            .decode("ascii")
            .strip()
        )
    except (subprocess.SubprocessError, OSError, ValueError) as e:
        print(f"Failed getting branch name due to:  {str(e)}")
        branch = ""
    return branch


def get_bot_remote_url(git_bin: str) -> str:
    """Uses git to find the current repo's remote URL."""
    try:
        url = (
            subprocess.check_output([git_bin, "ls-remote", "--get-url"])
            .decode("ascii")
            .strip()
        )
    except (subprocess.SubprocessError, OSError, ValueError) as e:
        print(f"Failed getting repo URL due to:  {str(e)}")
        url = ""
    return url


def check_bot_updates(git_bin: str, branch_name: str) -> Optional[Tuple[str, str]]:
    """Attempt a dry-run with git fetch to detect updates on remote."""
    try:
        updates = (
            subprocess.check_output([git_bin, "fetch", "--dry-run"])
            .decode("utf8")
            .split("\n")
        )
        for line in updates:
            parts = line.split()
            if branch_name in parts:
                commits = line.strip().split(" ", maxsplit=1)[0]
                commit_at, commit_to = commits.split("..")
                return (commit_at, commit_to)

        return None
    except (subprocess.SubprocessError, OSError, ValueError) as e:
        print(f"Failed checking for updates due to:  {str(e)}")
    return None


def update_deps() -> None:
    """
    Tries to upgrade MusicBot dependencies using pip module.
    This will use the same exe/bin as is running this code without version checks.
    """
    print("Attempting to update dependencies...")

    run_or_raise_error(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-warn-script-location",
            "--user",
            "-U",
            "-r",
            "requirements.txt",
        ],
        "Could not update dependencies. You need to update manually. "
        f"Run:  {sys.executable} -m pip install -U -r requirements.txt",
    )


def get_local_ffmpeg_version(ffmpeg_bin: str) -> str:
    """
    Finds and runs ffmpeg to extract its version.
    Note: this function is windows-only.
    """
    try:
        ver = (
            subprocess.check_output([ffmpeg_bin, "-version"]).decode("utf8").split("\n")
        )
        for line in ver:
            if "ffmpeg version" in line.lower():
                return line

        return "unknown"
    except (subprocess.SubprocessError, OSError, ValueError) as e:
        print(f"Failed checking for updates due to:  {str(e)}")
    return "unknown"


def get_remote_ffmpeg_version() -> Optional[Tuple[str, str]]:
    """Fetch the latest version info for essential release build."""
    with urlopen(
        "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip.ver"
    ) as req:
        fver = req.read().decode("utf8")
        lmod = req.info()["last-modified"]
        return (fver, lmod)
    return None


def dl_windows_ffmpeg() -> None:
    """Handle fetching and extracting ffmpeg binaries."""
    bins_path = os.path.abspath("bin")
    lp_ffmpeg = os.path.join(bins_path, "ffmpeg.exe")
    lp_ffprobe = os.path.join(bins_path, "ffprobe.exe")
    print(
        "Downloading ffmpeg release essentials build from:\n"
        "  https://www.gyan.dev/ffmpeg/builds/\n"
        "Extracting exe files to the following directory:\n"
        f"  {bins_path}\n\n"
        "If you need full codec support, you can manually download the full build instead."
    )
    fd, tmp_ffmpeg_path = tempfile.mkstemp(suffix="zip", prefix="tmp-ffmpeg")
    os.close(fd)

    print("Downloading zip file to temporary location, please wait...")
    with urlopen(
        "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
    ) as zipdl:
        with open(tmp_ffmpeg_path, "wb") as tmp:
            tmp.write(zipdl.read())
            tmp.close()

    print("Starting extraction of ffmpeg and ffprobe executables...")
    with zipfile.ZipFile(tmp_ffmpeg_path) as xip:
        for f in xip.namelist():
            if f.lower().endswith("ffmpeg.exe"):
                with open(lp_ffmpeg, "wb") as f1:
                    f1.write(xip.read(f))
                    f1.close()
                    print(f"Extracted ffmpeg.exe to:  {lp_ffmpeg}")
            if f.lower().endswith("ffprobe.exe"):
                with open(lp_ffprobe, "wb") as f2:
                    f2.write(xip.read(f))
                    f2.close()
                    print(f"Extracted ffprobe.exe to:  {lp_ffprobe}")
        xip.close()
    del xip

    # clean up the temp file.
    if os.path.isfile(tmp_ffmpeg_path):
        os.unlink(tmp_ffmpeg_path)


def update_ffmpeg() -> None:
    """
    Handles checking for new versions of ffmpeg and requesting update.
    """
    if not sys.platform.startswith("win"):
        print(
            "Skipping ffmpeg checks for non-Windows OS. "
            "You should use a package manager to install/update ffmpeg instead."
        )
        return

    print("Checking for ffmpeg versions...")

    bundle_ffmpeg_bin = os.path.join(os.path.abspath("bin"), "ffmpeg.exe")
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        print("Could not locate ffmpeg in your environment.")
    else:
        localver = get_local_ffmpeg_version(ffmpeg_bin)
        print(f"Found FFmpeg EXE at:  {ffmpeg_bin}")
        print(f"Current {localver}")

    # TODO: query winget for updates if winget is detected.
    # only query remote version if we are updating bundled exe.
    if ffmpeg_bin.lower() == bundle_ffmpeg_bin.lower():
        remotever = get_remote_ffmpeg_version()
        print(f"Available version:  {remotever[0]}")
        print(f"Available since:  {remotever[1]}")

    print("")

    if (
        ffmpeg_bin.lower() != bundle_ffmpeg_bin.lower()
        and "winget" in ffmpeg_bin.lower()
    ):
        winget_bin = shutil.which("winget")
        if not winget_bin:
            print(
                "We detected FFmpeg was installed via winget tool, but could not locate winget in your path."
            )
            print("You will need to manually update FFmpeg instead.")
            return

        do_upgrade = yes_or_no_input("Should we upgrade FFmpeg using winget? [Y/n]")
        if do_upgrade:
            run_or_raise_error(
                [
                    winget_bin,
                    "upgrade",
                    "Gyan.FFmpeg",
                ],
                "Could not update ffmpeg. You need to update it manually."
                "Try running:  winget upgrade Gyan.FFmpeg",
            )
            return

    elif ffmpeg_bin.lower() == bundle_ffmpeg_bin.lower():
        do_dl = yes_or_no_input(
            "Should we update the MusicBot bundled ffmpeg executables? [Y/n]"
        )
        if do_dl:
            dl_windows_ffmpeg()
            newver = get_local_ffmpeg_version(ffmpeg_bin)
            print(f"Updated ffmpeg to  {newver}")

    else:
        print(
            "We detected FFmpeg installed but it is not the exe bundled with MusicBot.\n"
            "You will need to update your FFmpeg install manually."
        )


def finalize() -> None:
    """Attempt to fetch the bot version constant and print it."""
    try:
        from musicbot.constants import (  # pylint: disable=import-outside-toplevel
            VERSION,
        )

        print(f"The current MusicBot version is:  {VERSION}")
    except ImportError:
        print(
            "There was a problem fetching your current bot version. "
            "The installation may not have completed correctly."
        )

    print("Done!")


def main() -> None:
    """
    Runs several checks, starting with making sure there is a .git folder
    in the current working path.
    Attempt to detect a git executable and use it to run git pull.
    Later, we try to use pip module to upgrade dependency modules.
    """
    print("Starting update checks...")

    if sys.platform.startswith("win"):
        bin_path = os.path.abspath("bin/")
        print(
            f"Adding MusicBot bin folder to environment path for this run:  {bin_path}",
        )
        os.environ["PATH"] += ";" + bin_path
        sys.path.append(bin_path)  # might as well

    # Make sure that we're in a Git repository
    if not os.path.isdir(".git"):
        raise EnvironmentError(
            "This isn't a Git repository.  Are you running in the correct directory?\n"
            "You must use `git clone` to install the bot or update checking cannot continue."
        )

    git_bin = shutil.which("git")
    if not git_bin:
        raise EnvironmentError(
            "Could not locate `git` executable.  Auto-update may not be possible.\n"
            "Check that `git` is installed and available in your environment path."
        )

    print(f"Found git executable at:  {git_bin}")

    # Make sure that we can actually use Git on the command line
    # because some people install Git Bash without allowing access to Windows CMD
    run_or_raise_error(
        [git_bin, "--version"],
        "Could not use the `git` command. You will need to run `git pull` manually.",
        stdout=subprocess.DEVNULL,
    )

    print("Checking for current bot version and local changes...")
    get_bot_version(git_bin)

    # Check that the current working directory is clean
    status_unclean = subprocess.check_output(
        [git_bin, "status", "--porcelain"], universal_newlines=True
    )
    if status_unclean:
        hard_reset = yes_or_no_input(
            "You have modified files that are tracked by Git (e.g the bot's source files).\n"
            "Should we try to hard reset the repo? You will lose local modifications."
        )
        if hard_reset:
            run_or_raise_error(
                [git_bin, "reset", "--hard"],
                "Could not hard reset the directory to a clean state.\n"
                "You will need to run `git pull` manually.",
            )
        else:
            do_deps = yes_or_no_input(
                "OK, skipping bot update. Do you still want to update dependencies?"
            )
            if do_deps:
                update_deps()

            update_ffmpeg()
            finalize()
            return

    # List some branch info.
    branch_name = get_bot_branch(git_bin)
    repo_url = get_bot_remote_url(git_bin)
    if branch_name:
        print(f"Current git branch name:  {branch_name}")
    if repo_url:
        print(f"Current git repo URL:  {repo_url}")

    # Check for updates.
    print("Checking remote repo for bot updates...")
    updates = check_bot_updates(git_bin, branch_name)
    if not updates:
        print("No updates found for bot source code.")
    else:
        print(f"Updates are available, latest commit ID is:  {updates[1]}")
        do_bot_upgrade = yes_or_no_input("Would you like to update?")
        if do_bot_upgrade:
            run_or_raise_error(
                [git_bin, "pull"],
                "Could not update the bot. You will need to run 'git pull' manually.",
            )

    update_deps()
    update_ffmpeg()
    finalize()


if __name__ == "__main__":
    main()
