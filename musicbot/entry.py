import asyncio
import datetime
import logging
import os
import re
import shutil
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from discord.abc import GuildChannel
from yt_dlp.utils import (  # type: ignore[import-untyped]
    ContentTooShortError,
    YoutubeDLError,
)

from .constructs import Serializable
from .downloader import YtdlpResponseDict
from .exceptions import ExtractionError, InvalidDataError, MusicbotException
from .spotify import Spotify

if TYPE_CHECKING:
    from .downloader import Downloader
    from .filecache import AudioFileCache
    from .playlist import Playlist

    # Explicit compat with python 3.8
    AsyncFuture = asyncio.Future[Any]
else:
    AsyncFuture = asyncio.Future


log = logging.getLogger(__name__)

# optionally using pymediainfo instead of ffprobe if presents
try:
    import pymediainfo  # type: ignore[import-untyped]
except ImportError:
    log.debug("module 'pymediainfo' not found, will fall back to ffprobe.")
    pymediainfo = None


class BasePlaylistEntry(Serializable):
    def __init__(self) -> None:
        """
        Manage a playable media reference and its meta data.
        Either a URL or a local file path that ffmpeg can use.
        """
        self.filename: str = ""
        self.downloaded_bytes: int = 0
        self.cache_busted: bool = False
        self.from_auto_playlist: bool = False
        self._is_downloading: bool = False
        self._is_downloaded: bool = False
        self._waiting_futures: List[AsyncFuture] = []

    @property
    def url(self) -> str:
        """
        Get a URL suitable for YoutubeDL to download, or likewise
        suitable for ffmpeg to stream or directly play back.
        """
        raise NotImplementedError

    @property
    def title(self) -> str:
        """
        Get a title suitable for display using any extracted info.
        """
        raise NotImplementedError

    @property
    def duration_td(self) -> datetime.timedelta:
        """
        Get this entry's duration as a timedelta object.
        The object may contain a 0 value.
        """
        raise NotImplementedError

    @property
    def is_downloaded(self) -> bool:
        """
        Get the entry's downloaded status.
        Typically set by _download function.
        """
        if self._is_downloading:
            return False

        return bool(self.filename) and self._is_downloaded

    @property
    def is_downloading(self) -> bool:
        """Get the entry's downloading status. Usually False."""
        return self._is_downloading

    async def _download(self) -> None:
        """
        Take any steps needed to download the media and make it ready for playback.
        If the media already exists, this function can return early.
        """
        raise NotImplementedError

    def get_ready_future(self) -> AsyncFuture:
        """
        Returns a future that will fire when the song is ready to be played.
        The future will either fire with the result (being the entry) or an exception
        as to why the song download failed.
        """
        future = asyncio.Future()  # type: AsyncFuture
        if self.is_downloaded:
            # In the event that we're downloaded, we're already ready for playback.
            future.set_result(self)

        else:
            # If we request a ready future, let's ensure that it'll actually resolve at one point.
            self._waiting_futures.append(future)
            asyncio.ensure_future(self._download())

        name = self.title or self.filename or self.url
        log.debug("Created future for %s", name)
        return future

    def _for_each_future(self, cb: Callable[..., Any]) -> None:
        """
        Calls `cb` for each future that is not canceled.
        Absorbs and logs any errors that may have occurred.
        """
        futures = self._waiting_futures
        self._waiting_futures = []

        for future in futures:
            if future.cancelled():
                continue

            try:
                cb(future)

            except Exception:  # pylint: disable=broad-exception-caught
                log.exception("Unhandled exception in _for_each_future callback.")

    def __eq__(self, other: object) -> bool:
        return self is other

    def __hash__(self) -> int:
        return id(self)


async def run_command(command: List[str]) -> bytes:
    """
    Use an async subprocess exec to execute the given `command`
    This method will wait for then return the output.

    :param: command:
        Must be a list of arguments, where element 0 is an executable path.

    :returns:  stdout concatenated with stderr as bytes.
    """
    p = await asyncio.create_subprocess_exec(
        # The inconsistency between the various implements of subprocess, asyncio.subprocess, and
        # all the other process calling functions tucked into python is alone enough to be dangerous.
        # There is a time and place for everything, and this is not the time or place for shells.
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    log.noise(  # type: ignore[attr-defined]
        "Starting asyncio subprocess (%s) with command: %s", p, command
    )
    stdout, stderr = await p.communicate()
    return stdout + stderr


class URLPlaylistEntry(BasePlaylistEntry):
    SERIAL_VERSION: int = 2  # version for serial data checks.

    def __init__(
        self,
        playlist: "Playlist",
        info: YtdlpResponseDict,
        from_apl: bool = False,
        **meta: Dict[str, Any],
    ) -> None:
        """
        Create URL Playlist entry that will be downloaded for playback.

        :param: playlist:  The playlist object this entry should belong to.
        :param: info:  A YtdlResponseDict with from downloader.extract_info()
        :param: from_apl:  Flag this entry as automatic playback, not queued by a user.
        :param: meta:  a collection extra of key-values stored with the entry.
        """
        super().__init__()

        self.playlist: "Playlist" = playlist
        self.downloader: "Downloader" = playlist.bot.downloader
        self.filecache: "AudioFileCache" = playlist.bot.filecache

        self.info: YtdlpResponseDict = info
        self.from_auto_playlist = from_apl

        if self.duration is None:
            log.info(
                "Extraction did not provide a duration for this entry.\n"
                "MusicBot cannot estimate queue times until it is downloaded.\n"
                "Entry name:  %s",
                self.title,
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
    def duration_td(self) -> datetime.timedelta:
        """
        Returns duration as a datetime.timedelta object.
        May contain 0 seconds duration.
        """
        t = self.duration or 0
        return datetime.timedelta(seconds=t)

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
        cls,
        raw_json: Dict[str, Any],
        playlist: Optional["Playlist"] = None,
        **kwargs: Dict[str, Any],
    ) -> Optional["URLPlaylistEntry"]:
        """
        Handles converting from JSON to URLPlaylistEntry.
        """
        # WARNING:  if you change data or keys here, you must increase SERIAL_VERSION.

        # yes this is an Optional that is, in fact, not Optional. :)
        assert playlist is not None, cls._bad("playlist")

        vernum: Optional[int] = raw_json.get("version", None)
        if not vernum:
            log.error("Entry data is missing version number, cannot deserialize.")
            return None
        if vernum != URLPlaylistEntry.SERIAL_VERSION:
            log.error("Entry data has the wrong version number, cannot deserialize.")
            return None

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
                        "Deserialized URLPlaylistEntry Cannot find channel with id: %s",
                        raw_json["meta"]["channel"]["id"],
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
                            "Deserialized URLPlaylistEntry Cannot find author with id: %s",
                            raw_json["meta"]["author"]["id"],
                        )
                        meta.pop("author")

            entry = cls(playlist, info, **meta)
            entry.filename = filename

            return entry
        except (ValueError, TypeError, KeyError) as e:
            log.error("Could not load %s", cls.__name__, exc_info=e)

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
                raise InvalidDataError(
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
                        log.debug("Download already cached at:  %s", file_cache_path)
                        self.filename = file_cache_path
                        self._is_downloaded = True

                # nothing cached, time to download for real.
                else:
                    await self._really_download()

            # check for duration and attempt to extract it if missing.
            if self.duration is None:
                # optional pymediainfo over ffprobe?
                if pymediainfo:
                    self.duration = self._get_duration_pymedia(self.filename)

                # no matter what, ffprobe should be available.
                if self.duration is None:
                    self.duration = await self._get_duration_ffprobe(self.filename)

                if not self.duration:
                    log.error(
                        "MusicBot could not get duration data for this entry.\n"
                        "Queue time estimation may be unavailable until this track is cleared.\n"
                        "Entry file: %s",
                        self.filename,
                    )
                else:
                    log.debug(
                        "Got duration of %s seconds for file:  %s",
                        self.duration,
                        self.filename,
                    )

            if self.playlist.bot.config.use_experimental_equalization:
                try:
                    aoptions = await self.get_mean_volume(self.filename)

                # Unfortunate evil that we abide for now...
                except Exception:  # pylint: disable=broad-exception-caught
                    log.error(
                        "There as a problem with working out EQ, likely caused by a strange installation of FFmpeg. "
                        "This has not impacted the ability for the bot to work, but will mean your tracks will not be equalised.",
                        exc_info=True,
                    )
                    aoptions = "-vn"
            else:
                aoptions = "-vn"

            self.aoptions = aoptions

            # Trigger ready callbacks.
            self._for_each_future(lambda future: future.set_result(self))

        # Flake8 thinks 'e' is never used, and later undefined. Maybe the lambda is too much.
        except Exception as e:  # pylint: disable=broad-exception-caught
            ex = e
            log.exception("Exception while checking entry data.")
            self._for_each_future(lambda future: future.set_exception(ex))

        finally:
            self._is_downloading = False

    def _get_duration_pymedia(self, input_file: str) -> Optional[float]:
        """
        Tries to use pymediainfo module to extract duration, if the module is available.
        """
        if pymediainfo:
            log.debug("Trying to get duration via pymediainfo for:  %s", input_file)
            try:
                mediainfo = pymediainfo.MediaInfo.parse(input_file)
                if mediainfo.tracks:
                    return int(mediainfo.tracks[0].duration) / 1000
            except (FileNotFoundError, OSError, RuntimeError, ValueError, TypeError):
                log.exception("Failed to get duration via pymediainfo.")
        return None

    async def _get_duration_ffprobe(self, input_file: str) -> Optional[float]:
        """
        Tries to use ffprobe to extract duration from media if possible.
        """
        log.debug("Trying to get duration via ffprobe for:  %s", input_file)
        ffprobe_bin = shutil.which("ffprobe")
        if not ffprobe_bin:
            log.error("Could not locate ffprobe in your path!")
            return None

        ffprobe_cmd = [
            ffprobe_bin,
            "-i",
            self.filename,
            "-show_entries",
            "format=duration",
            "-v",
            "quiet",
            "-of",
            "csv=p=0",
        ]

        try:
            raw_output = await run_command(ffprobe_cmd)
            output = raw_output.decode("utf8")
            return float(output)
        except (ValueError, UnicodeError):
            log.error(
                "ffprobe returned something that could not be used.", exc_info=True
            )
        except Exception:  # pylint: disable=broad-exception-caught
            log.exception("ffprobe could not be executed for some reason.")

        return None

    async def get_mean_volume(self, input_file: str) -> str:
        """
        Attempt to calculate the mean volume of the `input_file` by using
        output from ffmpeg to provide values which can be used by command
        arguments sent to ffmpeg during playback.
        """
        log.debug("Calculating mean volume of:  %s", input_file)
        ffmpeg_bin = shutil.which("ffmpeg")
        if not ffmpeg_bin:
            log.error("Could not locate ffmpeg on your path!")
            return ""

        # NOTE: this command should contain JSON, but I have no idea how to make
        # ffmpeg spit out only the JSON.
        ffmpeg_cmd = [
            ffmpeg_bin,
            "-i",
            input_file,
            "-af",
            "loudnorm=I=-24.0:LRA=7.0:TP=-2.0:linear=true:print_format=json",
            "-f",
            "null",
            "/dev/null",
            "-hide_banner",
            "-nostats",
        ]

        raw_output = await run_command(ffmpeg_cmd)
        output = raw_output.decode("utf-8")

        i_matches = re.findall(r'"input_i" : "(-?([0-9]*\.[0-9]+))",', output)
        if i_matches:
            # log.debug("i_matches=%s", i_matches[0][0])
            i_value = float(i_matches[0][0])
        else:
            log.debug("Could not parse I in normalise json.")
            i_value = float(0)

        lra_matches = re.findall(r'"input_lra" : "(-?([0-9]*\.[0-9]+))",', output)
        if lra_matches:
            # log.debug("lra_matches=%s", lra_matches[0][0])
            lra_value = float(lra_matches[0][0])
        else:
            log.debug("Could not parse LRA in normalise json.")
            lra_value = float(0)

        tp_matches = re.findall(r'"input_tp" : "(-?([0-9]*\.[0-9]+))",', output)
        if tp_matches:
            # log.debug("tp_matches=%s", tp_matches[0][0])
            tp_value = float(tp_matches[0][0])
        else:
            log.debug("Could not parse TP in normalise json.")
            tp_value = float(0)

        thresh_matches = re.findall(r'"input_thresh" : "(-?([0-9]*\.[0-9]+))",', output)
        if thresh_matches:
            # log.debug("thresh_matches=%s", thresh_matches[0][0])
            thresh = float(thresh_matches[0][0])
        else:
            log.debug("Could not parse thresh in normalise json.")
            thresh = float(0)

        offset_matches = re.findall(r'"target_offset" : "(-?([0-9]*\.[0-9]+))', output)
        if offset_matches:
            # log.debug("offset_matches=%s", offset_matches[0][0])
            offset = float(offset_matches[0][0])
        else:
            log.debug("Could not parse offset in normalise json.")
            offset = float(0)

        loudnorm_opts = (
            "-af loudnorm=I=-24.0:LRA=7.0:TP=-2.0:linear=true:"
            f"measured_I={i_value}:"
            f"measured_LRA={lra_value}:"
            f"measured_TP={tp_value}:"
            f"measured_thresh={thresh}:"
            f"offset={offset}"
        )
        return loudnorm_opts

    async def _really_download(self) -> None:
        """
        Actually download the media in this entry into cache.
        """
        log.info("Download started:  %s", self.url)

        retry = 2
        info = None
        while True:
            try:
                info = await self.downloader.extract_info(self.url, download=True)
                break
            except ContentTooShortError as e:
                # this typically means connection was interrupted, any
                # download is probably partial. we should definitely do
                # something about it to prevent broken cached files.
                if retry > 0:
                    log.warning(
                        "Download may have failed, retrying.  Reason: %s", str(e)
                    )
                    retry -= 1
                    await asyncio.sleep(1.5)  # TODO: backoff timer maybe?
                    continue

                # Mark the file I guess, and maintain the default of raising ExtractionError.
                log.error("Download failed, not retrying! Reason:  %s", str(e))
                self.cache_busted = True
                raise ExtractionError(str(e)) from e
            except YoutubeDLError as e:
                # as a base exception for any exceptions raised by yt_dlp.
                raise ExtractionError(str(e)) from e

            except Exception as e:
                log.exception("Extraction encountered an unhandled exception.")
                raise MusicbotException(str(e)) from e

        log.info("Download complete:  %s", self.url)

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
        from_apl: bool = False,
        **meta: Dict[str, Any],
    ) -> None:
        """
        Create Stream Playlist entry that will be sent directly to ffmpeg for playback.

        :param: playlist:  The playlist object this entry should belong to.
        :param: info:  A YtdlResponseDict with from downloader.extract_info()
        :param: from_apl:  Flag this entry as automatic playback, not queued by a user.
        :param: meta:  a collection extra of key-values stored with the entry.
        """
        super().__init__()

        self.playlist: "Playlist" = playlist
        self.info: YtdlpResponseDict = info
        self.from_auto_playlist = from_apl
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
                return str(dtitle)

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
    def duration_td(self) -> datetime.timedelta:
        """
        Get timedelta object from any known duration data.
        May contain a 0 second duration.
        """
        t = self.duration or 0
        return datetime.timedelta(seconds=t)

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
        cls,
        raw_json: Dict[str, Any],
        playlist: Optional["Playlist"] = None,
        **kwargs: Any,
    ) -> Optional["StreamPlaylistEntry"]:
        assert playlist is not None, cls._bad("playlist")

        vernum = raw_json.get("version", None)
        if not vernum:
            log.error("Entry data is missing version number, cannot deserialize.")
            return None
        if vernum != URLPlaylistEntry.SERIAL_VERSION:
            log.error("Entry data has the wrong version number, cannot deserialize.")
            return None

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
                        "Deserialized StreamPlaylistEntry Cannot find channel with id: %s",
                        raw_json["meta"]["channel"]["id"],
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
                            "Deserialized StreamPlaylistEntry Cannot find author with id: %s",
                            raw_json["meta"]["author"]["id"],
                        )
                        meta.pop("author")

            entry = cls(playlist, info, **meta)
            entry.filename = filename
            return entry
        except (ValueError, KeyError, TypeError) as e:
            log.error("Could not load %s", cls.__name__, exc_info=e)

        return None

    async def _download(self) -> None:
        self._is_downloading = True
        self._is_downloaded = True
        self.filename = self.url
        self._is_downloading = False
