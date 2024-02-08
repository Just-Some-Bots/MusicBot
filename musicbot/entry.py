import os
import asyncio
import logging
import re
import sys

from discord.abc import GuildChannel
from typing import TYPE_CHECKING, Any, List, Dict, Optional, Callable
from yt_dlp.utils import ContentTooShortError  # type: ignore

from .constructs import Serializable
from .exceptions import ExtractionError, InvalidDataError
from .spotify import Spotify
from .downloader import YtdlpResponseDict

if TYPE_CHECKING:
    from .playlist import Playlist
    from .filecache import AudioFileCache
    from .downloader import Downloader

log = logging.getLogger(__name__)

# optionally using pymediainfo instead of ffprobe if presents
try:
    import pymediainfo  # type: ignore
except ImportError:
    log.debug("module 'pymediainfo' not found, will fall back to ffprobe.")
    pymediainfo = None


class BasePlaylistEntry(Serializable):
    def __init__(self) -> None:
        self.filename: str = ""
        self.downloaded_bytes: int = 0
        self.cache_busted: bool = False
        self._is_downloading: bool = False
        self._is_downloaded: bool = False
        self._waiting_futures: List[asyncio.Future] = []

    @property
    def url(self) -> str:
        raise NotImplementedError

    @property
    def title(self) -> str:
        raise NotImplementedError

    @property
    def is_downloaded(self) -> bool:
        if self._is_downloading:
            return False

        return bool(self.filename) and self._is_downloaded

    async def _download(self) -> None:
        raise NotImplementedError

    def get_ready_future(self) -> asyncio.Future:
        """
        Returns a future that will fire when the song is ready to be played.
        The future will either fire with the result (being the entry) or an exception
        as to why the song download failed.
        """
        future = asyncio.Future()  # type: asyncio.Future
        if self.is_downloaded:
            # In the event that we're downloaded, we're already ready for playback.
            future.set_result(self)

        else:
            # If we request a ready future, let's ensure that it'll actually resolve at one point.
            self._waiting_futures.append(future)
            asyncio.ensure_future(self._download())

        name = self.title or self.filename or self.url
        log.debug("Created future for {0}".format(name))
        return future

    def _for_each_future(self, cb: Callable) -> None:
        """
        Calls `cb` for each future that is not cancelled. Absorbs and logs any errors that may have occurred.
        """
        futures = self._waiting_futures
        self._waiting_futures = []

        for future in futures:
            if future.cancelled():
                continue

            try:
                cb(future)

            except Exception:
                log.exception("Unhandled exception in _for_each_future callback.")

    def __eq__(self, other) -> bool:
        return self is other

    def __hash__(self) -> int:
        return id(self)


async def run_command(cmd: str) -> bytes:
    p = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    log.debug("Starting asyncio subprocess ({0}) with command: {1}".format(p, cmd))
    stdout, stderr = await p.communicate()
    return stdout + stderr


def get(program: str) -> Optional[str]:
    def is_exe(file_path):
        found = os.path.isfile(file_path) and os.access(file_path, os.X_OK)
        if not found and sys.platform == "win32":
            file_path = file_path + ".exe"
            found = os.path.isfile(file_path) and os.access(file_path, os.X_OK)
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


class URLPlaylistEntry(BasePlaylistEntry):
    SERIAL_VERSION: int = 2  # version for serial data checks.

    def __init__(
        self,
        playlist: "Playlist",
        info: YtdlpResponseDict,
        **meta: Dict[str, Any],
    ) -> None:
        super().__init__()

        self.playlist: "Playlist" = playlist
        self.downloader: "Downloader" = playlist.bot.downloader
        self.filecache: "AudioFileCache" = playlist.bot.filecache

        self.info: YtdlpResponseDict = info

        if self.duration is None:
            log.info(
                "Cannot extract duration of the entry. This does not affect the ability of the bot. "
                "However, estimated time for this entry will not be unavailable and estimated time "
                "of the queue will also not be available until this entry got downloaded.\n"
                "entry name: {}".format(self.title)
            )

        self.meta: Dict[str, Any] = meta
        self.aoptions: str = "-vn"

    @property
    def url(self) -> str:
        """Gets a playable URL from this entries info."""
        return self.info.get_playable_url()

    @property
    def title(self) -> str:
        """Gets a title string from entry info or 'Unknown'"""
        # TODO: i18n for this at some point.
        return self.info.title or "Unknown"

    @property
    def duration(self) -> Optional[float]:
        """Gets available duration data or None"""
        # duration can be 0, if so we make sure it returns None instead.
        return self.info.get("duration", None) or None

    @duration.setter
    def duration(self, value: float) -> None:
        self.info["duration"] = value

    @property
    def thumbnail_url(self) -> str:
        """Get available thumbnail from info or an empty string"""
        return self.info.thumbnail_url

    @property
    def expected_filename(self) -> Optional[str]:
        """Get the expected filename from info if available or None"""
        return self.info.get("__expected_filename", None)

    def __json__(self) -> Dict[str, Any]:
        """
        Handles representing this object as JSON.
        """
        # WARNING:  if you change data or keys here, you must increase SERIAL_VERSION.
        return self._enclose_json(
            {
                "version": URLPlaylistEntry.SERIAL_VERSION,
                "info": self.info.data,
                "downloaded": self.is_downloaded,
                "filename": self.filename,
                "meta": {
                    name: {
                        "type": obj.__class__.__name__,
                        "id": obj.id,
                        "name": obj.name,
                    }
                    for name, obj in self.meta.items()
                    if obj
                },
                "aoptions": self.aoptions,
            }
        )

    @classmethod
    def _deserialize(
        cls, raw_json: Dict[str, Any], playlist: Optional["Playlist"] = None, **kwargs
    ) -> Optional["URLPlaylistEntry"]:
        """
        Handles converting from JSON to URLPlaylistEntry.
        """
        # WARNING:  if you change data or keys here, you must increase SERIAL_VERSION.

        # yes this is an Optional that is, in fact, not Optional. :)
        assert playlist is not None, cls._bad("playlist")

        vernum: Optional[int] = raw_json.get("version", None)
        if not vernum:
            raise InvalidDataError("Entry data is missing version number.")
        elif vernum != URLPlaylistEntry.SERIAL_VERSION:
            raise InvalidDataError("Entry data has the wrong version number.")

        try:
            info = YtdlpResponseDict(raw_json["info"])
            downloaded = (
                raw_json["downloaded"] if playlist.bot.config.save_videos else False
            )
            filename = raw_json["filename"] if downloaded else None
            meta: Dict[str, Any] = {}

            # TODO: Better [name] fallbacks
            if "channel" in raw_json["meta"]:
                # int() it because persistent queue from pre-rewrite days saved ids as strings
                meta["channel"] = playlist.bot.get_channel(
                    int(raw_json["meta"]["channel"]["id"])
                )
                if not meta["channel"]:
                    log.warning(
                        "Cannot find channel in an entry loaded from persistent queue. Chennel id: {}".format(
                            raw_json["meta"]["channel"]["id"]
                        )
                    )
                    meta.pop("channel")
                elif "author" in raw_json["meta"] and isinstance(
                    meta["channel"], GuildChannel
                ):
                    # int() it because persistent queue from pre-rewrite days saved ids as strings
                    meta["author"] = meta["channel"].guild.get_member(
                        int(raw_json["meta"]["author"]["id"])
                    )
                    if not meta["author"]:
                        log.warning(
                            "Cannot find author in an entry loaded from persistent queue. Author id: {}".format(
                                raw_json["meta"]["author"]["id"]
                            )
                        )
                        meta.pop("author")

            entry = cls(playlist, info, **meta)
            entry.filename = filename

            return entry
        except Exception as e:
            log.error("Could not load {}".format(cls.__name__), exc_info=e)

        return None

    async def _ensure_entry_info(self) -> None:
        """helper to ensure this entry object has critical information"""

        # handle some extra extraction here so we can allow spotify links in the queue.
        if "open.spotify.com" in self.url.lower() and Spotify.is_url_supported(
            self.url
        ):
            info = await self.downloader.extract_info(self.url, download=False)
            if info.ytdl_type == "url":
                self.info = info
            else:
                raise Exception(
                    "Cannot download spotify links, these should be extracted before now."
                )

        # if this isn't set this entry is probably from a playlist and needs more info.
        if not self.expected_filename:
            new_info = await self.downloader.extract_info(self.url, download=False)
            self.info.data = {**self.info.data, **new_info.data}

    async def _download(self) -> None:
        if self._is_downloading:
            return
        log.debug("URLPlaylistEntry is now checking download status.")

        self._is_downloading = True
        try:
            # Ensure any late-extraction links, like Spotify tracks, get processed.
            await self._ensure_entry_info()

            # Ensure the folder that we're going to move into exists.
            self.filecache.ensure_cache_dir_exists()

            # check and see if the expected file already exists in cache.
            if self.expected_filename:
                # get an existing cache path if we have one.
                file_cache_path = self.filecache.get_if_cached(self.expected_filename)

                # win a cookie if cache worked but extension was different.
                if file_cache_path and self.expected_filename != file_cache_path:
                    log.warning("Download cached with different extension...")

                # check if cache size matches remote, basic validation.
                if file_cache_path:
                    local_size = os.path.getsize(file_cache_path)
                    remote_size = int(self.info.http_header("CONTENT-LENGTH", 0))

                    if local_size != remote_size:
                        log.debug(
                            "Local size different from remote size. Re-downloading..."
                        )
                        await self._really_download()
                    else:
                        log.debug(f"Download already cached at:  {file_cache_path}")
                        self.filename = file_cache_path
                        self._is_downloaded = True

                # nothing cached, time to download for real.
                else:
                    await self._really_download()

            if self.duration is None:
                if pymediainfo:
                    try:
                        mediainfo = pymediainfo.MediaInfo.parse(self.filename)
                        self.duration = mediainfo.tracks[0].duration / 1000
                    except Exception:
                        self.duration = None

                else:
                    args = [
                        "ffprobe",
                        "-i",
                        self.filename,
                        "-show_entries",
                        "format=duration",
                        "-v",
                        "quiet",
                        "-of",
                        'csv="p=0"',
                    ]

                    raw_output = await run_command(" ".join(args))
                    output = raw_output.decode("utf-8")

                    try:
                        self.duration = float(output)
                    except ValueError:
                        # @TheerapakG: If somehow it is not string of float
                        self.duration = None

                if not self.duration:
                    log.error(
                        "Cannot extract duration of downloaded entry, invalid output from ffprobe or pymediainfo. "
                        "This does not affect the ability of the bot. However, estimated time for this entry "
                        "will not be unavailable and estimated time of the queue will also not be available "
                        "until this entry got removed.\n"
                        "entry file: {}".format(self.filename)
                    )
                else:
                    log.debug(
                        "Get duration of {} as {} seconds by inspecting it directly".format(
                            self.filename, self.duration
                        )
                    )

            if self.playlist.bot.config.use_experimental_equalization:
                try:
                    aoptions = await self.get_mean_volume(self.filename)
                except Exception:
                    log.error(
                        "There as a problem with working out EQ, likely caused by a strange installation of FFmpeg. "
                        "This has not impacted the ability for the bot to work, but will mean your tracks will not be equalised."
                    )
                    aoptions = "-vn"
            else:
                aoptions = "-vn"

            self.aoptions = aoptions

            # Trigger ready callbacks.
            self._for_each_future(lambda future: future.set_result(self))

        # Flake8 thinks 'e' is never used, and later undefined. Maybe the lambda is too much.
        except Exception as e:  # noqa: F841
            log.exception("Exception while checking entry data.")
            self._for_each_future(lambda future: future.set_exception(e))  # noqa: F821

        finally:
            self._is_downloading = False

    async def get_mean_volume(self, input_file: str) -> str:
        log.debug("Calculating mean volume of {0}".format(input_file))
        exe = get("ffmpeg")
        args = "-af loudnorm=I=-24.0:LRA=7.0:TP=-2.0:linear=true:print_format=json -f null /dev/null"

        raw_output = await run_command(f'"{exe}" -i "{input_file}" {args}')
        output = raw_output.decode("utf-8")
        log.debug(f"Experimental Mean Volume Output:  {output}")

        i_matches = re.findall(r'"input_i" : "(-?([0-9]*\.[0-9]+))",', output)
        if i_matches:
            log.debug("i_matches={}".format(i_matches[0][0]))
            IVAL = float(i_matches[0][0])
        else:
            log.debug("Could not parse I in normalise json.")
            IVAL = float(0)

        lra_matches = re.findall(r'"input_lra" : "(-?([0-9]*\.[0-9]+))",', output)
        if lra_matches:
            log.debug("lra_matches={}".format(lra_matches[0][0]))
            LRA = float(lra_matches[0][0])
        else:
            log.debug("Could not parse LRA in normalise json.")
            LRA = float(0)

        tp_matches = re.findall(r'"input_tp" : "(-?([0-9]*\.[0-9]+))",', output)
        if tp_matches:
            log.debug("tp_matches={}".format(tp_matches[0][0]))
            TP = float(tp_matches[0][0])
        else:
            log.debug("Could not parse TP in normalise json.")
            TP = float(0)

        thresh_matches = re.findall(r'"input_thresh" : "(-?([0-9]*\.[0-9]+))",', output)
        if thresh_matches:
            log.debug("thresh_matches={}".format(thresh_matches[0][0]))
            thresh = float(thresh_matches[0][0])
        else:
            log.debug("Could not parse thresh in normalise json.")
            thresh = float(0)

        offset_matches = re.findall(r'"target_offset" : "(-?([0-9]*\.[0-9]+))', output)
        if offset_matches:
            log.debug("offset_matches={}".format(offset_matches[0][0]))
            offset = float(offset_matches[0][0])
        else:
            log.debug("Could not parse offset in normalise json.")
            offset = float(0)

        return "-af loudnorm=I=-24.0:LRA=7.0:TP=-2.0:linear=true:measured_I={}:measured_LRA={}:measured_TP={}:measured_thresh={}:offset={}".format(
            IVAL, LRA, TP, thresh, offset
        )

    async def _really_download(self) -> None:
        log.info("Download started: {}".format(self.url))

        retry = 2
        info = None
        while True:
            try:
                info = await self.downloader.extract_info(self.url, download=True)
                break
            except ContentTooShortError as e:
                # this typically means connection was interupted, any download is probably partial.
                # we should definitely do something about it to prevent broken cached files.
                if retry > 0:
                    log.warning(f"Download may have failed, retrying.  Reason: {e}")
                    retry -= 1
                    await asyncio.sleep(1.5)  # TODO: backoff timer maybe?
                    continue
                else:
                    # Mark the file I guess, and maintain the default of raising ExtractionError.
                    log.error(f"Download failed, not retrying! Reason: {e}")
                    self.cache_busted = True
                    raise ExtractionError(e)
            except Exception as e:
                raise ExtractionError(str(e)) from e

        log.info("Download complete: {}".format(self.url))

        if info is None:
            log.critical("YTDL has failed, everyone panic")
            raise ExtractionError("ytdl broke and hell if I know why")
            # What the fuck do I do now?

        self._is_downloaded = True
        self.filename = info.expected_filename or ""

        # It should be safe to get our newly downloaded file size now...
        # This should also leave self.downloaded_bytes set to 0 if the file is in cache already.
        self.downloaded_bytes = os.path.getsize(self.filename)


class StreamPlaylistEntry(BasePlaylistEntry):
    SERIAL_VERSION = 2

    def __init__(
        self,
        playlist: "Playlist",
        info: YtdlpResponseDict,
        **meta: Dict[str, Any],
    ) -> None:
        super().__init__()

        self.playlist: "Playlist" = playlist
        self.info: YtdlpResponseDict = info
        self.meta: Dict[str, Any] = meta

        self.filename: str = self.url

    @property
    def url(self) -> str:
        """get extracted url if available or otherwise return the input subject"""
        if self.info.extractor and self.info.url:
            return self.info.url
        return self.info.get("__input_subject", "")

    @property
    def title(self) -> str:
        """Gets a title string from entry info or 'Unknown'"""
        # special case for twitch streams, from previous code.
        # TODO: test coverage here
        if self.info.extractor == "twitch:stream":
            dtitle = self.info.get("description", None)
            if dtitle and not self.info.title:
                return dtitle

        # TODO: i18n for this at some point.
        return self.info.title or "Unknown"

    @property
    def duration(self) -> Optional[float]:
        """Gets available duration data or None"""
        # duration can be 0, if so we make sure it returns None instead.
        return self.info.get("duration", None) or None

    @duration.setter
    def duration(self, value: float) -> None:
        self.info["duration"] = value

    @property
    def thumbnail_url(self) -> str:
        """Get available thumbnail from info or an empty string"""
        return self.info.thumbnail_url

    def __json__(self) -> Dict[str, Any]:
        return self._enclose_json(
            {
                "version": StreamPlaylistEntry.SERIAL_VERSION,
                "info": self.info.data,
                "filename": self.filename,
                "meta": {
                    name: {
                        "type": obj.__class__.__name__,
                        "id": obj.id,
                        "name": obj.name,
                    }
                    for name, obj in self.meta.items()
                    if obj
                },
            }
        )

    @classmethod
    def _deserialize(
        cls, raw_json: Dict[str, Any], playlist: Optional["Playlist"] = None, **kwargs
    ) -> Optional["StreamPlaylistEntry"]:
        assert playlist is not None, cls._bad("playlist")

        vernum = raw_json.get("version", None)
        if not vernum:
            raise InvalidDataError("Entry data is missing version number.")
        elif vernum != URLPlaylistEntry.SERIAL_VERSION:
            raise InvalidDataError("Entry data has the wrong version number.")

        try:
            info = YtdlpResponseDict(raw_json["info"])
            filename = raw_json["filename"]
            meta: Dict[str, Any] = {}

            # TODO: Better [name] fallbacks
            if "channel" in raw_json["meta"]:
                # int() it because persistent queue from pre-rewrite days saved ids as strings
                meta["channel"] = playlist.bot.get_channel(
                    int(raw_json["meta"]["channel"]["id"])
                )
                if not meta["channel"]:
                    log.warning(
                        "Cannot find channel in an entry loaded from persistent queue. Chennel id: {}".format(
                            raw_json["meta"]["channel"]["id"]
                        )
                    )
                    meta.pop("channel")
                elif "author" in raw_json["meta"] and isinstance(
                    meta["channel"], GuildChannel
                ):
                    # int() it because persistent queue from pre-rewrite days saved ids as strings
                    meta["author"] = meta["channel"].guild.get_member(
                        int(raw_json["meta"]["author"]["id"])
                    )
                    if not meta["author"]:
                        log.warning(
                            "Cannot find author in an entry loaded from persistent queue. Author id: {}".format(
                                raw_json["meta"]["author"]["id"]
                            )
                        )
                        meta.pop("author")

            entry = cls(playlist, info, **meta)
            entry.filename = filename
            return entry
        except Exception as e:
            log.error("Could not load {}".format(cls.__name__), exc_info=e)

        return None

    async def _download(self) -> None:
        self._is_downloading = True
        self._is_downloaded = True
        self.filename = self.url
        self._is_downloading = False
