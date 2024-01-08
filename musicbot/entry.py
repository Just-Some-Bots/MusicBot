import os
import asyncio
import logging
import typing
import re
import sys

from enum import Enum
from typing import Dict, Optional
from yt_dlp.utils import ContentTooShortError
from .constructs import Serializable
from .exceptions import ExtractionError, InvalidDataError
from .utils import md5sum
from .spotify import Spotify
from .downloader import YtdlpResponseDict

if typing.TYPE_CHECKING:
    from .playlist import Playlist

# optionally using pymediainfo instead of ffprobe if presents
try:
    import pymediainfo
except ImportError:
    pymediainfo = None

log = logging.getLogger(__name__)


class EntryTypes(Enum):
    URL = 1
    STEAM = 2
    FILE = 3

    def __str__(self):
        return self.name


class BasePlaylistEntry(Serializable):
    def __init__(self):
        self.filename = None
        self.downloaded_bytes = 0
        self.cache_busted = False
        self._is_downloading = False
        self._waiting_futures = []

    @property
    def is_downloaded(self):
        if self._is_downloading:
            return False

        return bool(self.filename)

    async def _download(self):
        raise NotImplementedError

    def get_ready_future(self):
        """
        Returns a future that will fire when the song is ready to be played.
        The future will either fire with the result (being the entry) or an exception
        as to why the song download failed.
        """
        future = asyncio.Future()
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

    def _for_each_future(self, cb):
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

    def __eq__(self, other):
        return self is other

    def __hash__(self):
        return id(self)


async def run_command(cmd):
    p = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    log.debug("Starting asyncio subprocess ({0}) with command: {1}".format(p, cmd))
    stdout, stderr = await p.communicate()
    return stdout + stderr


def get(program):
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
    SERIAL_VERSION = 2  # version for serial data checks.

    def __init__(
        self,
        playlist: "Playlist",
        info: "YtdlpResponseDict",
        **meta,
    ) -> None:
        super().__init__()

        # TODO: perhaps remove arguments here that are inside info dict, and just pass info dict.
        self.playlist = playlist
        self.downloader = playlist.bot.downloader

        self.info = info

        if self.duration is None:
            log.info(
                "Cannot extract duration of the entry. This does not affect the ability of the bot. "
                "However, estimated time for this entry will not be unavailable and estimated time "
                "of the queue will also not be available until this entry got downloaded.\n"
                "entry name: {}".format(self.title)
            )

        self.meta = meta
        self.aoptions = "-vn"

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
    def duration(self) -> typing.Optional[float]:
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
    def expected_filename(self) -> typing.Optional[str]:
        """Get the expected filename from info if available or None"""
        return self.info.get("__expected_filename", None)

    def __json__(self) -> str:
        """
        Handles representing this object as JSON.
        """
        # WARNING:  if you change this function, you must increase SERIAL_VERSION.
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
    def _deserialize(cls, data: Dict, playlist: "Playlist" = None):
        """
        Handles converting from JSON to URLPlaylistEntry.
        """
        # WARNING:  if you change this function, you must increase SERIAL_VERSION.

        assert playlist is not None, cls._bad("playlist")

        vernum = data.get("version", None)
        if not vernum:
            raise InvalidDataError("Entry data is missing version number.")
        elif vernum != URLPlaylistEntry.SERIAL_VERSION:
            raise InvalidDataError("Entry data has the wrong version number.")

        try:
            info = YtdlpResponseDict(data["info"])
            downloaded = (
                data["downloaded"] if playlist.bot.config.save_videos else False
            )
            filename = data["filename"] if downloaded else None
            meta = {}

            # TODO: Better [name] fallbacks
            if "channel" in data["meta"]:
                # int() it because persistent queue from pre-rewrite days saved ids as strings
                meta["channel"] = playlist.bot.get_channel(
                    int(data["meta"]["channel"]["id"])
                )
                if not meta["channel"]:
                    log.warning(
                        "Cannot find channel in an entry loaded from persistent queue. Chennel id: {}".format(
                            data["meta"]["channel"]["id"]
                        )
                    )
                    meta.pop("channel")
                elif "author" in data["meta"]:
                    # int() it because persistent queue from pre-rewrite days saved ids as strings
                    meta["author"] = meta["channel"].guild.get_member(
                        int(data["meta"]["author"]["id"])
                    )
                    if not meta["author"]:
                        log.warning(
                            "Cannot find author in an entry loaded from persistent queue. Author id: {}".format(
                                data["meta"]["author"]["id"]
                            )
                        )
                        meta.pop("author")

            entry = cls(playlist, info, **meta)
            entry.filename = filename

            return entry
        except Exception as e:
            log.error("Could not load {}".format(cls.__name__), exc_info=e)

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

        # if this isn't set we are probably a playlist entry and need more info.
        if not self.expected_filename:
            new_info = await self.downloader.extract_info(self.url, download=False)
            self.info.data = {**self.info.data, **new_info.data}

    # noinspection PyTypeChecker
    async def _download(self):
        if self._is_downloading:
            return
        log.debug("URLPlaylistEntry is now checking download status.")

        self._is_downloading = True
        try:
            await self._ensure_entry_info()

            # Ensure the folder that we're going to move into exists.
            if not os.path.exists(self.downloader.download_folder):
                os.makedirs(self.downloader.download_folder)

            # self.expected_filename: audio_cache\youtube-9R8aSKwTEMg-NOMA_-_Brain_Power.m4a
            extractor = os.path.basename(self.expected_filename).split("-")[0]

            # the generic extractor requires special handling
            if extractor == "generic":
                flistdir = [
                    f.rsplit("-", 1)[0]
                    for f in os.listdir(self.downloader.download_folder)
                ]
                expected_fname_noex, fname_ex = os.path.basename(
                    self.expected_filename
                ).rsplit(".", 1)

                if expected_fname_noex in flistdir:
                    rsize = int(self.info.http_header("CONTENT-LENGTH", 0))

                    lfile = os.path.join(
                        self.downloader.download_folder,
                        os.listdir(self.downloader.download_folder)[
                            flistdir.index(expected_fname_noex)
                        ],
                    )

                    # print("Resolved %s to %s" % (self.expected_filename, lfile))
                    lsize = os.path.getsize(lfile)
                    # print("Remote size: %s Local size: %s" % (rsize, lsize))

                    if lsize != rsize:
                        await self._really_download(hash=True)
                    else:
                        # print("[Download] Cached:", self.url)
                        self.filename = lfile

                else:
                    # print("File not found in cache (%s)" % expected_fname_noex)
                    await self._really_download(hash=True)

            else:
                ldir = os.listdir(self.downloader.download_folder)
                flistdir = [f.rsplit(".", 1)[0] for f in ldir]
                expected_fname_base = os.path.basename(self.expected_filename)
                expected_fname_noex = expected_fname_base.rsplit(".", 1)[0]

                # idk wtf this is but its probably legacy code
                # or i have youtube to blame for changing shit again

                if expected_fname_base in ldir:
                    self.filename = os.path.join(
                        self.downloader.download_folder, expected_fname_base
                    )
                    log.info("Download cached: {}".format(self.url))

                elif expected_fname_noex in flistdir:
                    log.info(
                        "Download cached (different extension): {}".format(self.url)
                    )
                    self.filename = os.path.join(
                        self.downloader.download_folder,
                        ldir[flistdir.index(expected_fname_noex)],
                    )
                    log.debug(
                        "Expected {}, got {}".format(
                            self.expected_filename.rsplit(".", 1)[-1],
                            self.filename.rsplit(".", 1)[-1],
                        )
                    )
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

                    output = await run_command(" ".join(args))
                    output = output.decode("utf-8")

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

    async def get_mean_volume(self, input_file):
        log.debug("Calculating mean volume of {0}".format(input_file))
        exe = get("ffmpeg")
        args = "-af loudnorm=I=-24.0:LRA=7.0:TP=-2.0:linear=true:print_format=json -f null /dev/null"

        output = await run_command(f'"{exe}" -i "{input_file}" {args}')
        output = output.decode("utf-8")
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

    # noinspection PyShadowingBuiltins
    async def _really_download(self, *, hash=False):
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
                raise ExtractionError(e)

        log.info("Download complete: {}".format(self.url))

        if info is None:
            log.critical("YTDL has failed, everyone panic")
            raise ExtractionError("ytdl broke and hell if I know why")
            # What the fuck do I do now?

        # TODO: remove this since we previously prepared the name.
        # self.filename = unhashed_fname = self.downloader.ytdl.prepare_filename(result)
        self.filename = unhashed_fname = info.expected_filename

        if hash:
            # insert the 8 last characters of the file hash to the file name to ensure uniqueness
            self.filename = (
                md5sum(unhashed_fname, 8).join("-.").join(unhashed_fname.rsplit(".", 1))
            )

            if os.path.isfile(self.filename):
                # Oh bother it was actually there.
                os.unlink(unhashed_fname)
            else:
                # Move the temporary file to it's final location.
                os.rename(unhashed_fname, self.filename)

        # It should be safe to get our newly downloaded file size now...
        # This should also leave self.downloaded_bytes set to 0 if the file is in cache already.
        self.downloaded_bytes = os.path.getsize(self.filename)


# TODO: make this use info dict instead.
class StreamPlaylistEntry(BasePlaylistEntry):
    SERIAL_VERSION = 2

    def __init__(
        self,
        playlist: "Playlist",
        info: "YtdlpResponseDict",
        **meta,
    ):
        super().__init__()

        self.playlist = playlist
        self.info = info
        self.meta = meta

        self.filename = self.url

    @property
    def url(self) -> Optional[str]:
        """get extracted url if available or otherwise return the input subject"""
        if self.info.extractor and self.info.url:
            return self.info.url
        return self.info.get("__input_subject", None)

    @property
    def fallback_url(self) -> Optional[str]:
        """returns the extracted URL from the entry data."""
        return self.info.get("url", None)

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
    def duration(self) -> typing.Optional[float]:
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

    def __json__(self):
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
    def _deserialize(cls, data, playlist=None):
        assert playlist is not None, cls._bad("playlist")

        vernum = data.get("version", None)
        if not vernum:
            raise InvalidDataError("Entry data is missing version number.")
        elif vernum != URLPlaylistEntry.SERIAL_VERSION:
            raise InvalidDataError("Entry data has the wrong version number.")

        try:
            info = YtdlpResponseDict(data["info"])
            filename = data["filename"]
            meta = {}

            # TODO: Better [name] fallbacks
            if "channel" in data["meta"]:
                ch = playlist.bot.get_channel(data["meta"]["channel"]["id"])
                meta["channel"] = ch or data["meta"]["channel"]["name"]

            if "author" in data["meta"]:
                meta["author"] = meta["channel"].guild.get_member(
                    data["meta"]["author"]["id"]
                )

            entry = cls(playlist, info, **meta)
            entry.filename = filename
            return entry
        except Exception as e:
            log.error("Could not load {}".format(cls.__name__), exc_info=e)

    # noinspection PyMethodOverriding
    async def _download(self):
        self._is_downloading = True
        self.filename = self.url
        self._is_downloading = False
