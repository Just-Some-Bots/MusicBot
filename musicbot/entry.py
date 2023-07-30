import os
import asyncio
import logging
import traceback
import re
import sys

from enum import Enum
from .constructs import Serializable
from .exceptions import ExtractionError
from .utils import get_header, md5sum

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
        Returns a future that will fire when the song is ready to be played. The future will either fire with the result (being the entry) or an exception
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

        log.debug("Created future for {0}".format(self.filename))
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

            except:
                traceback.print_exc()

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
    def __init__(
        self, playlist, url, title, duration=None, expected_filename=None, **meta
    ):
        super().__init__()

        self.playlist = playlist
        self.url = url
        self.title = title
        self.duration = duration
        if duration is None:  # duration could be 0
            log.info(
                "Cannot extract duration of the entry. This does not affect the ability of the bot. "
                "However, estimated time for this entry will not be unavailable and estimated time "
                "of the queue will also not be available until this entry got downloaded.\n"
                "entry name: {}".format(self.title)
            )
        self.expected_filename = expected_filename
        self.meta = meta
        self.aoptions = "-vn"

        self.download_folder = self.playlist.downloader.download_folder

    def __json__(self):
        return self._enclose_json(
            {
                "version": 1,
                "url": self.url,
                "title": self.title,
                "duration": self.duration,
                "downloaded": self.is_downloaded,
                "expected_filename": self.expected_filename,
                "filename": self.filename,
                "full_filename": os.path.abspath(self.filename)
                if self.filename
                else self.filename,
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
    def _deserialize(cls, data, playlist=None):
        assert playlist is not None, cls._bad("playlist")

        try:
            # TODO: version check
            url = data["url"]
            title = data["title"]
            duration = data["duration"]
            downloaded = (
                data["downloaded"] if playlist.bot.config.save_videos else False
            )
            filename = data["filename"] if downloaded else None
            expected_filename = data["expected_filename"]
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

            entry = cls(playlist, url, title, duration, expected_filename, **meta)
            entry.filename = filename

            return entry
        except Exception as e:
            log.error("Could not load {}".format(cls.__name__), exc_info=e)

    # noinspection PyTypeChecker
    async def _download(self):
        if self._is_downloading:
            return

        self._is_downloading = True
        try:
            # Ensure the folder that we're going to move into exists.
            if not os.path.exists(self.download_folder):
                os.makedirs(self.download_folder)

            # self.expected_filename: audio_cache\youtube-9R8aSKwTEMg-NOMA_-_Brain_Power.m4a
            extractor = os.path.basename(self.expected_filename).split("-")[0]

            # the generic extractor requires special handling
            if extractor == "generic":
                flistdir = [
                    f.rsplit("-", 1)[0] for f in os.listdir(self.download_folder)
                ]
                expected_fname_noex, fname_ex = os.path.basename(
                    self.expected_filename
                ).rsplit(".", 1)

                if expected_fname_noex in flistdir:
                    try:
                        rsize = int(
                            await get_header(
                                self.playlist.bot.aiosession, self.url, "CONTENT-LENGTH"
                            )
                        )
                    except:
                        rsize = 0

                    lfile = os.path.join(
                        self.download_folder,
                        os.listdir(self.download_folder)[
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
                ldir = os.listdir(self.download_folder)
                flistdir = [f.rsplit(".", 1)[0] for f in ldir]
                expected_fname_base = os.path.basename(self.expected_filename)
                expected_fname_noex = expected_fname_base.rsplit(".", 1)[0]

                # idk wtf this is but its probably legacy code
                # or i have youtube to blame for changing shit again

                if expected_fname_base in ldir:
                    self.filename = os.path.join(
                        self.download_folder, expected_fname_base
                    )
                    log.info("Download cached: {}".format(self.url))

                elif expected_fname_noex in flistdir:
                    log.info(
                        "Download cached (different extension): {}".format(self.url)
                    )
                    self.filename = os.path.join(
                        self.download_folder, ldir[flistdir.index(expected_fname_noex)]
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
                    except:
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
                except Exception as e:
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

        except Exception as e:
            traceback.print_exc()
            self._for_each_future(lambda future: future.set_exception(e))

        finally:
            self._is_downloading = False

    async def get_mean_volume(self, input_file):
        log.debug("Calculating mean volume of {0}".format(input_file))
        cmd = (
            '"'
            + get("ffmpeg")
            + '" -i "'
            + input_file
            + '" -af loudnorm=I=-24.0:LRA=7.0:TP=-2.0:linear=true:print_format=json -f null /dev/null'
        )
        output = await run_command(cmd)
        output = output.decode("utf-8")
        log.debug(output)
        # print('----', output)

        i_matches = re.findall(r'"input_i" : "(-?([0-9]*\.[0-9]+))",', output)
        if i_matches:
            log.debug("i_matches={}".format(i_matches[0][0]))
            I = float(i_matches[0][0])
        else:
            log.debug("Could not parse I in normalise json.")
            I = float(0)

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

        thresh_matches = re.findall(
            r'"input_thresh" : "(-?([0-9]*\.[0-9]+))",', output
        )
        if thresh_matches:
            log.debug("thresh_matches={}".format(thresh_matches[0][0]))
            thresh = float(thresh_matches[0][0])
        else:
            log.debug("Could not parse thresh in normalise json.")
            thresh = float(0)

        offset_matches = re.findall(
            r'"target_offset" : "(-?([0-9]*\.[0-9]+))', output
        )
        if offset_matches:
            log.debug("offset_matches={}".format(offset_matches[0][0]))
            offset = float(offset_matches[0][0])
        else:
            log.debug("Could not parse offset in normalise json.")
            offset = float(0)

        return "-af loudnorm=I=-24.0:LRA=7.0:TP=-2.0:linear=true:measured_I={}:measured_LRA={}:measured_TP={}:measured_thresh={}:offset={}".format(
            I, LRA, TP, thresh, offset
        )

    # noinspection PyShadowingBuiltins
    async def _really_download(self, *, hash=False):
        log.info("Download started: {}".format(self.url))

        retry = True
        result = None
        while retry:
            try:
                result = await self.playlist.downloader.extract_info(
                    self.playlist.loop, self.url, download=True
                )
                break
            except Exception as e:
                raise ExtractionError(e)

        log.info("Download complete: {}".format(self.url))

        if result is None:
            log.critical("YTDL has failed, everyone panic")
            raise ExtractionError("ytdl broke and hell if I know why")
            # What the fuck do I do now?

        self.filename = unhashed_fname = self.playlist.downloader.ytdl.prepare_filename(
            result
        )

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


class StreamPlaylistEntry(BasePlaylistEntry):
    def __init__(self, playlist, url, title, *, destination=None, **meta):
        super().__init__()

        self.playlist = playlist
        self.url = url
        self.title = title
        self.destination = destination
        self.duration = None
        self.meta = meta

        if self.destination:
            self.filename = self.destination

    def __json__(self):
        return self._enclose_json(
            {
                "version": 1,
                "url": self.url,
                "filename": self.filename,
                "title": self.title,
                "destination": self.destination,
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

        try:
            # TODO: version check
            url = data["url"]
            title = data["title"]
            destination = data["destination"]
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

            entry = cls(playlist, url, title, destination=destination, **meta)
            if not destination and filename:
                entry.filename = destination

            return entry
        except Exception as e:
            log.error("Could not load {}".format(cls.__name__), exc_info=e)

    # noinspection PyMethodOverriding
    async def _download(self, *, fallback=False):
        self._is_downloading = True

        url = self.destination if fallback else self.url

        try:
            result = await self.playlist.downloader.extract_info(
                self.playlist.loop, url, download=False
            )
        except Exception as e:
            if not fallback and self.destination:
                return await self._download(fallback=True)

            raise ExtractionError(e)
        else:
            self.filename = result["url"]
            # I might need some sort of events or hooks or shit
            # for when ffmpeg inevitebly fucks up and i have to restart
            # although maybe that should be at a slightly lower level
        finally:
            self._is_downloading = False
