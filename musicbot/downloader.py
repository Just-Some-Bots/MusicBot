import os
import asyncio
import logging
import functools
import inspect
import yt_dlp as youtube_dl

from concurrent.futures import ThreadPoolExecutor
from types import MappingProxyType
from typing import NoReturn, Optional, List, Dict
from urllib.parse import urlparse
from pprint import pformat

from .exceptions import ExtractionError
from .spotify import Spotify

log = logging.getLogger(__name__)

# Immutable dict is needed, because something is modifying the 'outtmpl' value. I suspect it being ytdl, but I'm not sure.
ytdl_format_options_immutable = MappingProxyType(
    {
        "format": "bestaudio/best",
        "outtmpl": "%(extractor)s-%(id)s-%(title)s.%(ext)s",
        "restrictfilenames": True,
        "noplaylist": True,
        "nocheckcertificate": True,
        "ignoreerrors": False,
        "logtostderr": False,
        "quiet": True,
        "no_warnings": True,
        # "geo_bypass": True,  #  this might be worth using.
        "extract_flat": 'in_playlist',  # do not process playlist results, only list them.
        "default_search": "auto",
        "source_address": "0.0.0.0",
        "usenetrc": True,
    }
)


# Fuck your useless bugreports message that gets two link embeds and confuses users
youtube_dl.utils.bug_reports_message = lambda: ""

"""
    Alright, here's the problem.  To catch youtube-dl errors for their useful information, I have to
    catch the exceptions with `ignoreerrors` off.  To not break when ytdl hits a dumb video
    (rental videos, etc), I have to have `ignoreerrors` on.  I can change these whenever, but with async
    that's bad.  So I need multiple ytdl objects.

"""


class Downloader:
    def __init__(self, bot, download_folder=None):
        self.bot = bot
        self.thread_pool = ThreadPoolExecutor(max_workers=2)
        self.download_folder = download_folder

        # Copy immutable dict and use the mutable copy for everything else.
        ytdl_format_options = ytdl_format_options_immutable.copy()

        if download_folder:
            # print("setting template to " + os.path.join(download_folder, otmpl))
            otmpl = ytdl_format_options["outtmpl"]
            ytdl_format_options["outtmpl"] = os.path.join(download_folder, otmpl)

        self.unsafe_ytdl = youtube_dl.YoutubeDL(ytdl_format_options)
        self.safe_ytdl = youtube_dl.YoutubeDL(
            {**ytdl_format_options, "ignoreerrors": True}
        )

    @property
    def ytdl(self):
        return self.safe_ytdl

    def get_url_or_none(self, url: str) -> str:
        """Uses ytdl.utils.url_or_none() to validate a playable URL"""
        # Discord might add < and > to the URL, this strips them out if they exist.
        if url.startswith("<") and url.endswith(">"):
            log.debug("stripped it of <>")
            url = url[1:-1]
        return youtube_dl.utils.url_or_none(url)

    async def extract_info(
        self, *args, on_error=None, retry_on_error=False, **kwargs
    ):
        """
        Runs ytdl.extract_info within the threadpool. Returns a future that will fire when it's done.
        If `on_error` is passed and an exception is raised, the exception will be caught and passed to
        on_error as an argument.
        
        Note: on_error seems to never be used in the code base.
        """

        log.noise(f"Called extract_info with:  {args}, oe={on_error}, roe={retry_on_error}, {kwargs}")

        # TODO:  clean up calls to this function, ensure on_error and retry are used at all.
        # TODO:  if cleanup fails, make on_error work for spotify too.
        # handle extracting spotify links before ytdl get ahold of them.
        if args and "open.spotify.com" in args[0].lower() and self.bot.config._spotify:
            log.noise("Handling spotify link...")
            if not Spotify.is_url_supported(args[0]):
                raise ExtractionError("Spotify URL is invalid or not supported.")

            process = kwargs.get("process", True)
            download = kwargs.get("download", True)

            # return only basic ytdl-flavored data from the Spotify API.
            # This call will not fetch all tracks in playlists or albums.
            if not process and not download:
                data = await self.bot.spotify.get_spotify_ytdl_data(args[0])
                log.noise(f"Spotify YTDL data:  {pformat(data)}")
                return data

            # modify args to have ytdl return search data, only for singular tracks.
            # for albums & playlists, we want to return full playlist data rather than partial as above.
            if process:
                data = await self.bot.spotify.get_spotify_ytdl_data(args[0], process)
                log.noise(f"Spotify Process YTDL data:  {pformat(data)}")
                if data["_type"] == "url":
                    args = (data["url"],)
                elif data["_type"] == "playlist":
                    return data

        if callable(on_error):
            try:
                data = await self.bot.loop.run_in_executor(
                    self.thread_pool,
                    functools.partial(self.unsafe_ytdl.extract_info, *args, **kwargs),
                )
                self._experiment_with_data(data, "Callable Unsafe ")
                return data

            except Exception as e:
                # (youtube_dl.utils.ExtractorError, youtube_dl.utils.DownloadError)
                # I hope I don't have to deal with ContentTooShortError's
                if asyncio.iscoroutinefunction(on_error):
                    asyncio.ensure_future(on_error(e), loop=self.bot.loop)

                elif asyncio.iscoroutine(on_error):
                    asyncio.ensure_future(on_error, loop=self.bot.loop)

                else:
                    self.bot.loop.call_soon_threadsafe(on_error, e)

                if retry_on_error:
                    data = await self.safe_extract_info(*args, **kwargs)
                    self._experiment_with_data(data, "Retry Safe ")
                    return data
        else:
            data = await self.bot.loop.run_in_executor(
                self.thread_pool,
                functools.partial(self.unsafe_ytdl.extract_info, *args, **kwargs),
            )
            self._experiment_with_data(data, "Unsafe ")
            return data

    def _experiment_with_data(self, data, place=""):
        d = YtdlpResponseObject(data)
        xd = "__REDACTED_FOR_CLARITY__"
        if "entries" in data:
            # cleaning up entry data to make it easier to parse in logs.
            for i, e in enumerate(data["entries"]):
                if "automatic_captions" in e:
                    data["entries"][i]["automatic_captions"] = xd
                if "formats" in e:
                    data["entries"][i]["formats"] = xd

        if "formats" in data:
            data["formats"] = xd

        if "automatic_captions" in data:
            data["automatic_captions"] = xd

        log.debug(f"{place}Extract needs process:  {d.needs_processing}")
        log.noise(f"Serial-Safe Data:  {pformat(self.ytdl.sanitize_info(data))}")

    async def safe_extract_info(self, *args, **kwargs):
        log.noise(f"Called safe_extract_info with:  {args}, {kwargs}")
        return await self.bot.loop.run_in_executor(
            self.thread_pool,
            functools.partial(self.safe_ytdl.extract_info, *args, **kwargs),
        )


class YtdlpResponseObject:
    """Object with helpers to normalize YoutubeDL response data and make it easier to use."""
    def __init__(self, data: Dict) -> NoReturn:
        self.data = data

    def get(self, key, default=None):
        """Helper to access the data dict in this response object."""
        return self.data.get(key, default)

    def get_entries_dict(self) -> List[Dict]:
        """will return entries as-is from data or an empty list if no entries are set."""
        entries = self.data.get("entries", [])
        if type(entries) is List:
            return entries
        return []

    def get_entries_object(self) -> List["YtdlpResponseObject"]:
        """will iterate over entries and return list of YtdlResponseObjects"""
        return [YtdlpResponseObject(e) for e in self.get_entries_dict]

    @property
    def needs_processing(self) -> bool:
        """Return true if this response needs extra processing to extract completely."""
        # direct youtube watch links usually have this key set to None.
        if "__post_extractor" in self.data:
            if not self.data["__post_extractor"]:
                return False

        # youtube search always need processing.
        if self.url.startswith("ytsearch:"):
            return True

        # searches are returned as playlist with 1 entry.
        # playlists often need processing for complete extraction.
        if self.ytdl_type == "playlist":
            # if we don't have entries or a playlist_count, its likely we need processing.
            if "playlist_count" not in self.data or "entries" not in self.data:
                return True

            # youtube playlists always contain a playlist_count and entries keys
            # but entries can be an empty generator before processing.
            # if we use ytdl.sanitize_info() we need to check for a string rather than a generator.
            entries = self.data.get("entries", None)
            if (
                inspect.isgeneratorfunction(entries)
                or inspect.isgenerator(entries)
                or (type(entries) is str and entries.startswith("<generator"))
            ):
                return True

            # if we have a playlist_count and size of entries does not match it.
            entry_count = sum(1 for _ in entries)
            if entry_count != self.playlist_count:
                return True

        return False

    @property
    def thumbnail_url(self) -> str:
        """return a sanitized thumbnail url if available, or create one if possible."""
        turl = self.data.get("thumbnail", None)
        # if we have a thumbnail url, clean it up if needed and return it.
        if turl:
            if "i.ytimg.com" in turl:  # reduce youtube tracking
                return urlparse(turl)._replace(params="", query="", fragment="").geturl()
            return turl

        # TODO: maybe check in "thumbnails" key?  picking the right one could be interesting.
        # if all else fails, try to make a URL on our own.
        if self.extractor == "youtube":
            if self.video_id:
                return f"https://i.ytimg.com/vi/{self.video_id}/maxresdefault.jpg"

    @property
    def ytdl_type(self) -> str:
        """returns value for data key '_type' or empty string"""
        return self.data.get("_type", "")

    @property
    def extractor(self) -> str:
        """returns value for data key 'extractor' or empty string"""
        return self.data.get("extractor", "")

    @property
    def extractor_key(self) -> str:
        """returns value for data key 'extractor_key' or empty string"""
        return self.data.get("extractor_key", "")

    @property
    def url(self) -> str:
        """returns value for data key 'url' or empty string"""
        return self.data.get("url", "")

    @property
    def webpage_url(self) -> Optional[str]:
        """returns value for data key 'webpage_url' or None"""
        return self.data.get("webpage_url", None)

    @property
    def webpage_basename(self) -> Optional[str]:
        """returns value for data key 'webpage_url_basename' or None"""
        return self.data.get("webpage_url_basename", None)

    @property
    def webpage_domain(self) -> Optional[str]:
        """returns value for data key 'webpage_url_domain' or None"""
        return self.data.get("webpage_url_domain", None)

    @property
    def original_url(self) -> Optional[str]:
        """returns value for data key 'original_url' or None"""
        return self.data.get("original_url", None)

    @property
    def video_id(self) -> Optional[str]:
        """returns the 'id' value if it is set or None"""
        return self.data.get("id", None)

    @property
    def playlist_count(self) -> int:
        """returns the playlist_count value if it exists, or 0"""
        return self.data.get("playlist_count", 0)

    @property
    def duration(self) -> float:
        """returns duration data if available, or 0"""
        try:
            return float(self.data.get("duration", 0))
        except ValueError:
            return 0.0
