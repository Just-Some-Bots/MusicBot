import json
import pathlib
import logging

log = logging.get_logger(__name__)


class AudioFileCache:
    """
    This class provides methods to manage the audio file cache and get info about it.
    """

    def __init__(self, bot):
        self.bot = bot
        self.config = bot.config
        self.cache_path = pathlib.Path(bot.config.audio_cache_path)

        self.size_bytes = 0
        self.file_count = 0

        # Stores filenames without extension associated to a playlist URL.
        self.auto_playlist_cachemap = {}

    def cache_dir_exists(self):
        return self.cache_path.is_dir()

    def get_cache_size(self):
        """
        Returns AudioFileCache size as a two member tuple containing size_bytes and file_count.
        """
        return (self.size_bytes, self.file_count)

    def scan_audio_cache(self):
        """
        Scan the audio cache directory and return a tuple with info.
        Returns (size_in_bytes:int, number_of_files:int)
        """
        cached_bytes = 0
        cached_files = 0
        if os.path.isdir(self.cache_path):
            for cache_file in pathlib.Path(self.cache_path).iterdir():
                cached_files += 1
                cached_bytes += os.path.getsize(cache_file)
        self.size_bytes = cached_bytes
        self.file_count = cached_files

        return self.get_cache_size()

    def _delete_cache_file(self, path: pathlib.Path):
        try:
            path.unlink(missing_ok=True)
            return True
        except Exception:
            log.exception(f"Failed to delete cache file:  {path}")
            return False

    def delete_old_audiocache(self, remove_dir=False):
        """
        Handle deletion of cache data according to settings and return bool status.
        Param `remove_dir` is intened only to be used in bot-startup.
        """

        if not os.path.isdir(self.cache_path):
            log.debug("Audio cache directory is missing, nothing to delete.")
            return False

        if self.config.save_videos:
            # Sort cache by access or creation time and delete any that are older than set limit.
            # Accumulate file sizes until a set limit is reached and purge remaining files.
            if (
                self.config.storage_limit_bytes == 0
                and self.config.storage_limit_days == 0
            ):
                log.debug("Audio cache has no limits set, nothing to delete.")
                return False

            if os.name == "nt":
                # On Windows, creation time (ctime) is the only reliable way to do this.
                # mtime is usually older than download time. atime is changed on multiple files by some part of the player.
                # To make this consistent everywhere, we need to store last-played times for songs on our own.
                cached_files = sorted(
                    pathlib.Path(self.cache_path).iterdir(),
                    key=os.path.getctime,
                    reverse=True,
                )
            else:
                cached_files = sorted(
                    pathlib.Path(self.cache_path).iterdir(),
                    key=os.path.getatime,
                    reverse=True,
                )

            max_age = time.time() - (86400 * self.config.storage_limit_days)
            cached_size = 0
            removed_count = 0
            removed_size = 0
            retained_count = 0
            retained_size = 0
            for cache_file in cached_files:
                file_size = os.path.getsize(cache_file)

                # Do not purge files from autoplaylist if retention is enabled.
                if self._check_autoplay_cachemap(cache_file):
                    retained_count += 1
                    retained_size += file_size
                    continue

                # get file access/creation time.
                if os.name == "nt":
                    file_time = os.path.getctime(cache_file)
                else:
                    file_time = os.path.getatime(cache_file)

                # enforce size limit before time limit.
                if (
                    self.config.storage_limit_bytes
                    and self.config.storage_limit_bytes <= (cached_size + file_size)
                ):
                    self._delete_cache_file(cache_file)
                    removed_count += 1
                    removed_size += file_size
                    continue

                if self.config.storage_limit_days:
                    if file_time < max_age:
                        self._delete_cache_file(cache_file)
                        removed_count += 1
                        removed_size += file_size
                        continue

                cached_size += file_size

            if removed_count:
                log.debug(
                    "Audio cache deleted {} file{}, total of {} removed.".format(
                        removed_count,
                        "" if removed_count == 1 else "s",
                        format_size_from_bytes(removed_size),
                    )
                )
            if retained_count:
                log.debug(
                    "Audio cached retained {} files from autoplaylist, total of {} retained.".format(
                        retained_count,
                        format_size_from_bytes(retained_size),
                        "" if retained_count == 1 else "s",
                    )
                )
            self.file_count = len(cached_files) - removed_count
            self.size_bytes = cached_size + retained_size
            log.debug(
                "Audio cache is now {} over {} file{}.".format(
                    format_size_from_bytes(self.size_bytes),
                    self.file_count,
                    "" if self.file_count == 1 else "s",
                )
            )
        elif remove_dir:
            try:
                shutil.rmtree(path)
                self.cached_audio_bytes = 0
                log.debug("Audio cache directory has been removed.")
                return True
            except Exception:
                try:
                    os.rename(path, path + "__")
                except Exception:
                    log.debug("Audio cache directory could not be removed or renamed.")
                    return False
                try:
                    shutil.rmtree(path)
                except Exception:
                    os.rename(path + "__", path)
                    log.debug("Audio cache directory could not be removed.")
                    return False

        return True

    def handle_new_cache_entry(self, entry):
        # ignore partial downloads
        if entry.cache_busted:
            return

        if entry.url in self.bot.autoplaylist:
            self.add_autoplay_cachemap_entry(entry)

        if self.config.save_videos and self.config.storage_limit_bytes:
            # TODO: Improve this so it isn't called every song when cache is full.
            #  idealy a second option for keeping cache between min and max.
            self.size_bytes = self.size_bytes + entry.downloaded_bytes
            if self.size_bytes > self.config.storage_limit_bytes:
                log.debug(
                    f"Cache level requires cleanup. {format_size_from_bytes(self.size_bytes)}"
                )
                self.delete_old_audiocache()

    def load_autoplay_cachemap(self):
        """
        Load cachemap file if it exists and settings are enabled.
        Cachemap file path is generated in Config using the auto playlist file name.
        The cache map is a dict with filename keys for playlist url values.
        Filenames are stored without their extension due to ytdl potentially getting a different format.
        """
        if (
            not self.config.storage_retain_autoplay
            or not self.config.auto_playlist
            or not self.config.save_videos
        ):
            self.auto_playlist_cachemap = {}
            return

        if not os.path.isfile(self.config.auto_playlist_cachemap_file):
            log.debug("Auto playlist has no cache map, moving on.")
            self.auto_playlist_cachemap = {}
            return

        with open(self.config.auto_playlist_cachemap_file, "r") as fh:
            try:
                self.auto_playlist_cachemap = json.load(fh)
                log.info(
                    f"Loaded auto playlist cache map with {len(self.auto_playlist_cachemap)} entries."
                )
            except Exception:
                log.exception("Failed to load auto playlist cache map.")
                self.auto_playlist_cachemap = {}

    async def save_autoplay_cachemap(self):
        if (
            not self.config.storage_retain_autoplay
            or not self.config.auto_playlist
            or not self.config.save_videos
        ):
            return

        async with self.aiolocks[_func_()]:
            try:
                with open(self.config.auto_playlist_cachemap_file, "w") as fh:
                    json.dump(self.auto_playlist_cachemap, fh)
                    log.info(
                        f"Saved auto playlist cache map with {len(self.auto_playlist_cachemap)} entries."
                    )
            except Exception:
                log.exception("Failed to save auto playlist cache map.")

    def add_autoplay_cachemap_entry(self, entry):
        if (
            not self.config.storage_retain_autoplay
            or not self.config.auto_playlist
            or not self.config.save_videos
        ):
            return

        filename = pathlib.Path(entry.filename).stem
        if filename in self.auto_playlist_cachemap:
            if self.auto_playlist_cachemap[filename] != entry.url:
                log.warning(
                    "Auto playlist cache map conflict on Key: {}  Old: {}  New: {}".format(
                        filename,
                        self.auto_playlist_cachemap[filename],
                        entry.url,
                    )
                )
        self.auto_playlist_cachemap[filename] = entry.url

    def remove_autoplay_cachemap_entry(self, entry):
        if (
            not self.config.storage_retain_autoplay
            or not self.config.auto_playlist
            or not self.config.save_videos
        ):
            return

        filename = pathlib.Path(entry.filename).stem
        if filename in self.auto_playlist_cachemap:
            del self.auto_playlist_cachemap[filename]

    def remove_autoplay_cachemap_entry_by_url(self, url):
        if (
            not self.config.storage_retain_autoplay
            or not self.config.auto_playlist
            or not self.config.save_videos
        ):
            return

        to_remove = set()
        for map_key, map_url in self.auto_playlist_cachemap.items():
            if map_url == url:
                to_remove.add(map_key)
        for key in to_remove:
            del self.auto_playlist_cachemap[key]

    def _check_autoplay_cachemap(self, filename: pathlib.Path) -> bool:
        """
        Test if filename is a valid autoplaylist file still.
        Returns True if map entry URL is still in autoplaylist.
        If settings are disabled for cache retention this will also return false.
        """
        if (
            not self.config.storage_retain_autoplay
            or not self.config.auto_playlist
            or not self.config.save_videos
        ):
            return False

        if filename.stem in self.auto_playlist_cachemap:
            cached_url = self.auto_playlist_cachemap[filename.stem]
            if cached_url in self.bot.autoplaylist:
                return True

        return False
