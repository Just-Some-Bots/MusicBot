import asyncio
import logging
import pathlib
import shutil
import time
from collections import UserList
from typing import TYPE_CHECKING, Dict, List, Optional, Set

from . import write_path
from .constants import (
    APL_FILE_APLCOPY,
    APL_FILE_DEFAULT,
    APL_FILE_HISTORY,
    OLD_BUNDLED_AUTOPLAYLIST_FILE,
    OLD_DEFAULT_AUTOPLAYLIST_FILE,
)
from .exceptions import MusicbotException

if TYPE_CHECKING:
    from .bot import MusicBot

    StrUserList = UserList[str]
else:
    StrUserList = UserList

log = logging.getLogger(__name__)


class AutoPlaylist(StrUserList):
    def __init__(self, filename: pathlib.Path, bot: "MusicBot") -> None:
        super().__init__()

        self._bot: MusicBot = bot
        self._file: pathlib.Path = filename
        self._removed_file = filename.with_name(f"{filename.stem}.removed.log")

        self._update_lock: asyncio.Lock = asyncio.Lock()
        self._file_lock: asyncio.Lock = asyncio.Lock()
        self._is_loaded: bool = False

    @property
    def filename(self) -> str:
        """The base file name of this playlist."""
        return self._file.name

    @property
    def loaded(self) -> bool:
        """
        Returns the load status of this playlist.
        When False, no playlist data will be available.
        """
        return self._is_loaded

    @property
    def rmlog_file(self) -> pathlib.Path:
        """Returns the generated removal log file name."""
        return self._removed_file

    def create_file(self) -> None:
        """Creates the playlist file if it does not exist."""
        if not self._file.is_file():
            self._file.touch(exist_ok=True)

    async def load(self, force: bool = False) -> None:
        """
        Loads the playlist file if it has not been loaded.
        """
        # ignore loaded lists unless forced.
        if (self._is_loaded or self._file_lock.locked()) and not force:
            return

        # Load the actual playlist file.
        async with self._file_lock:
            try:
                self.data = self._read_playlist()
            except OSError:
                log.warning("Error loading auto playlist file:  %s", self._file)
                self.data = []
                self._is_loaded = False
                return
            self._is_loaded = True

    def _read_playlist(self) -> List[str]:
        """
        Read and parse the playlist file for track entries.
        """
        # Comments in apl files are only handled based on start-of-line.
        # Inline comments are not supported due to supporting non-URL entries.
        comment_char = "#"

        # Read in the file and add non-comments to the playlist.
        playlist: List[str] = []
        with open(self._file, "r", encoding="utf8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith(comment_char):
                    continue
                playlist.append(line)
        return playlist

    async def clear_all_tracks(self, log_msg: str) -> None:
        """
        Remove all tracks from the current playlist.
        Functions much like remove_track but does all the I/O stuff in bulk.

        :param: log_msg:  A reason for clearing, usually states the user.
        """
        async with self._update_lock:
            all_tracks = list(self.data)
            song_subject = "[Removed all tracks]"

            for track in all_tracks:
                self.data.remove(track)

            if not self._removed_file.is_file():
                self._removed_file.touch(exist_ok=True)

            try:
                with open(self._removed_file, "a", encoding="utf8") as f:
                    ctime = time.ctime()
                    # add 10 spaces to line up with # Reason:
                    e_str = log_msg.replace("\n", "\n#" + " " * 10)
                    sep = "#" * 32
                    f.write(
                        f"# Entry removed {ctime}\n"
                        f"# Track:  {song_subject}\n"
                        f"# Reason: {e_str}\n"
                        f"\n{sep}\n\n"
                    )
            except (OSError, PermissionError, FileNotFoundError, IsADirectoryError):
                log.exception(
                    "Could not log information about the playlist URL removal."
                )

            log.info("Updating playlist file...")

            def _filter_replace(line: str, url: str) -> str:
                target = line.strip()
                if target == url:
                    return f"# Removed # {url}"
                return line

            # read the original file in and update lines with the URL.
            # this is done to preserve the comments and formatting.
            try:
                data = self._file.read_text(encoding="utf8").split("\n")
                last_track = len(all_tracks) - 1
                self._bot.filecache.cachemap_defer_write = True
                for idx, track in enumerate(all_tracks):
                    data = [_filter_replace(x, track) for x in data]
                    if idx == last_track:
                        self._bot.filecache.cachemap_defer_write = False
                    self._bot.filecache.remove_autoplay_cachemap_entry_by_url(track)

                text = "\n".join(data)
                self._file.write_text(text, encoding="utf8")
            except (OSError, PermissionError, FileNotFoundError):
                log.exception("Failed to save playlist file:  %s", self._file)

    async def remove_track(
        self,
        song_subject: str,
        *,
        ex: Optional[Exception] = None,
        delete_from_ap: bool = False,
    ) -> None:
        """
        Handle clearing the given `song_subject` from the autoplaylist queue,
        and optionally from the configured autoplaylist file.

        :param: ex:  an exception that is given as the reason for removal.
        :param: delete_from_ap:  should the configured list file be updated?
        """
        if song_subject not in self.data:
            return

        async with self._update_lock:
            self.data.remove(song_subject)
            if ex and not isinstance(ex, UserWarning):
                log.info(
                    "Removing unplayable song from playlist, %(playlist)s: %(track)s",
                    {"playlist": self._file.name, "track": song_subject},
                )
            else:
                log.info(
                    "Removing song from playlist, %(playlist)s: %(track)s",
                    {"playlist": self._file.name, "track": song_subject},
                )

            if not self._removed_file.is_file():
                self._removed_file.touch(exist_ok=True)

            try:
                with open(self._removed_file, "a", encoding="utf8") as f:
                    ctime = time.ctime()
                    if isinstance(ex, MusicbotException):
                        error = ex.message % ex.fmt_args
                    else:
                        error = str(ex)
                    # add 10 spaces to line up with # Reason:
                    e_str = error.replace("\n", "\n#" + " " * 10)
                    sep = "#" * 32
                    f.write(
                        f"# Entry removed {ctime}\n"
                        f"# Track:  {song_subject}\n"
                        f"# Reason: {e_str}\n"
                        f"\n{sep}\n\n"
                    )
            except (OSError, PermissionError, FileNotFoundError, IsADirectoryError):
                log.exception(
                    "Could not log information about the playlist URL removal."
                )

            if delete_from_ap:
                log.info("Updating playlist file...")

                def _filter_replace(line: str, url: str) -> str:
                    target = line.strip()
                    if target == url:
                        return f"# Removed # {url}"
                    return line

                # read the original file in and update lines with the URL.
                # this is done to preserve the comments and formatting.
                try:
                    data = self._file.read_text(encoding="utf8").split("\n")
                    data = [_filter_replace(x, song_subject) for x in data]
                    text = "\n".join(data)
                    self._file.write_text(text, encoding="utf8")
                except (OSError, PermissionError, FileNotFoundError):
                    log.exception("Failed to save playlist file:  %s", self._file)
                self._bot.filecache.remove_autoplay_cachemap_entry_by_url(song_subject)

    async def add_track(self, song_subject: str) -> None:
        """
        Add the given `song_subject` to the auto playlist file and in-memory
        list.  Does not update the player's current autoplaylist queue.
        """
        if song_subject in self.data:
            log.debug("URL already in playlist %s, ignoring", self._file.name)
            return

        async with self._update_lock:
            # Note, this does not update the player's copy of the list.
            self.data.append(song_subject)
            log.info(
                "Adding new URL to playlist, %(playlist)s: %(track)s",
                {"playlist": self._file.name, "track": song_subject},
            )

            try:
                # make sure the file exists.
                if not self._file.is_file():
                    self._file.touch(exist_ok=True)

                # append to the file to preserve its formatting.
                with open(self._file, "r+", encoding="utf8") as fh:
                    lines = fh.readlines()
                    if not lines:
                        lines.append("# MusicBot Auto Playlist\n")
                    if lines[-1].endswith("\n"):
                        lines.append(f"{song_subject}\n")
                    else:
                        lines.append(f"\n{song_subject}\n")
                    fh.seek(0)
                    fh.writelines(lines)
            except (OSError, PermissionError, FileNotFoundError):
                log.exception("Failed to save playlist file:  %s", self._file)


class AutoPlaylistManager:
    """Manager class that facilitates multiple playlists."""

    def __init__(self, bot: "MusicBot") -> None:
        """
        Initialize the manager, checking the file system for usable playlists.
        """
        self._bot: MusicBot = bot
        self._apl_dir: pathlib.Path = bot.config.auto_playlist_dir
        self._apl_file_default = self._apl_dir.joinpath(APL_FILE_DEFAULT)
        self._apl_file_history = self._apl_dir.joinpath(APL_FILE_HISTORY)
        self._apl_file_usercopy = self._apl_dir.joinpath(APL_FILE_APLCOPY)

        self._playlists: Dict[str, AutoPlaylist] = {}

        self.setup_autoplaylist()

    def setup_autoplaylist(self) -> None:
        """
        Ensure directories for auto playlists are available and that historic
        playlist files are copied.
        """
        if not self._apl_dir.is_dir():
            self._apl_dir.mkdir(parents=True, exist_ok=True)

        # Files from previous versions of MusicBot
        old_usercopy = write_path(OLD_DEFAULT_AUTOPLAYLIST_FILE)
        old_bundle = write_path(OLD_BUNDLED_AUTOPLAYLIST_FILE)

        # Copy or rename the old auto-playlist files if new files don't exist yet.
        if old_usercopy.is_file() and not self._apl_file_usercopy.is_file():
            # rename the old autoplaylist.txt into the new playlist directory.
            old_usercopy.rename(self._apl_file_usercopy)
        if old_bundle.is_file() and not self._apl_file_default.is_file():
            # copy the bundled playlist into the default, shared playlist.
            shutil.copy(old_bundle, self._apl_file_default)

        if (
            not self._apl_file_history.is_file()
            and self._bot.config.enable_queue_history_global
        ):
            self._apl_file_history.touch(exist_ok=True)

        self.discover_playlists()

    @property
    def _default_pl(self) -> AutoPlaylist:
        """Returns the default playlist, even if the file is deleted."""
        if self._apl_file_default.stem in self._playlists:
            return self._playlists[self._apl_file_default.stem]

        self._playlists[self._apl_file_default.stem] = AutoPlaylist(
            filename=self._apl_file_default,
            bot=self._bot,
        )
        return self._playlists[self._apl_file_default.stem]

    @property
    def _usercopy_pl(self) -> Optional[AutoPlaylist]:
        """Returns the copied autoplaylist.txt playlist if it exists."""
        # return mapped copy if possible.
        if self._apl_file_usercopy.stem in self._playlists:
            return self._playlists[self._apl_file_usercopy.stem]

        # if no mapped copy, check if file exists and map it.
        if self._apl_file_usercopy.is_file():
            self._playlists[self._apl_file_usercopy.stem] = AutoPlaylist(
                filename=self._apl_file_usercopy,
                bot=self._bot,
            )

        return self._playlists.get(self._apl_file_usercopy.stem, None)

    @property
    def global_history(self) -> AutoPlaylist:
        """Returns the MusicBot global history file."""
        if self._apl_file_history.stem in self._playlists:
            return self._playlists[self._apl_file_history.stem]

        self._playlists[self._apl_file_history.stem] = AutoPlaylist(
            filename=self._apl_file_history,
            bot=self._bot,
        )
        return self._playlists[self._apl_file_history.stem]

    @property
    def playlist_names(self) -> List[str]:
        """Returns all discovered playlist names."""
        return list(self._playlists.keys())

    @property
    def loaded_playlists(self) -> List[AutoPlaylist]:
        """Returns all loaded AutoPlaylist objects."""
        return [pl for pl in self._playlists.values() if pl.loaded]

    @property
    def loaded_tracks(self) -> List[str]:
        """
        Contains a list of all unique playlist entries, from each loaded playlist.
        """
        tracks: Set[str] = set()
        for pl in self._playlists.values():
            if pl.loaded:
                tracks = tracks.union(set(pl))
        return list(tracks)

    def discover_playlists(self) -> None:
        """
        Look for available playlist files but do not load them into memory yet.
        This method makes playlists available for display or selection.
        """
        for pfile in self._apl_dir.iterdir():
            # only process .txt files
            if pfile.suffix.lower() == ".txt":
                # ignore already discovered playlists.
                if pfile.stem in self._playlists:
                    continue

                pl = AutoPlaylist(pfile, self._bot)
                self._playlists[pfile.stem] = pl

    def get_default(self) -> AutoPlaylist:
        """
        Gets the appropriate default playlist based on which files exist.
        """
        # If the old autoplaylist.txt was copied, use it.
        if self._usercopy_pl is not None:
            return self._usercopy_pl
        return self._default_pl

    def get_playlist(self, filename: str) -> AutoPlaylist:
        """Get or create a playlist with the given filename."""
        # using pathlib .name here prevents directory traversal attack.
        pl_file = self._apl_dir.joinpath(pathlib.Path(filename).name)

        # Return the existing instance if we have one.
        if pl_file.stem in self._playlists:
            return self._playlists[pl_file.stem]

        # otherwise, make a new instance with this filename
        self._playlists[pl_file.stem] = AutoPlaylist(pl_file, self._bot)
        return self._playlists[pl_file.stem]

    def playlist_exists(self, filename: str) -> bool:
        """Check for the existence of the given playlist file."""
        # using pathlib .name prevents directory traversal attack.
        return self._apl_dir.joinpath(pathlib.Path(filename).name).is_file()
