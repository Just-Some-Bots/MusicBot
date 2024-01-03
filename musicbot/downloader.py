import os
import asyncio
import copy
import logging
import functools
import inspect
import yt_dlp as youtube_dl

from yt_dlp.networking.exceptions import NoSupportingHandlers

from collections import UserDict
from concurrent.futures import ThreadPoolExecutor
from types import MappingProxyType
from typing import NoReturn, Optional, List, Dict, Any
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
        # extract_flat speeds up extract_info by only listing playlist entries rather than extracting them as well.
        "extract_flat": 'in_playlist',
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

    async def extract_info(self, song_subject: str, *args, **kwargs):
        """temporary function to handle logs for returned data"""
        data = await self._extract_info(song_subject, *args, **kwargs)
        self._experiment_with_data(data)
        return YtdlpResponseDict(data)

    async def _extract_info(self, song_subject: str, *args, **kwargs):
        """
        Runs ytdlp.extract_info with all arguments passed to this function.
        Resulting data is passed through ytdlp's sanitize_info and returned
        inside of a YtdlpResponseDict.
        
        :param: song_subject: a song_url or search subject.
        :returns: YtdlpResponseDict containing sanitized extraction data.
        :raises: YoutubeDLError as base exception.
        """

        log.noise(f"Called extract_info with:  '{song_subject}', {args}, {kwargs}")

        # handle extracting spotify links before ytdl get ahold of them.
        if "open.spotify.com" in song_subject.lower() and self.bot.config._spotify:
            log.noise("Handling spotify link...")
            if not Spotify.is_url_supported(song_subject):
                raise ExtractionError("Spotify URL is invalid or not supported.")

            process = kwargs.get("process", True)
            download = kwargs.get("download", True)

            # return only basic ytdl-flavored data from the Spotify API.
            # This call will not fetch all tracks in playlists or albums.
            if not process and not download:
                data = await self.bot.spotify.get_spotify_ytdl_data(song_subject)
                log.noise(f"Spotify YTDL data:  {pformat(data)}")
                return data

            # modify args to have ytdl return search data, only for singular tracks.
            # for albums & playlists, we want to return full playlist data rather than partial as above.
            if process:
                data = await self.bot.spotify.get_spotify_ytdl_data(song_subject, process)
                log.noise(f"Spotify Process YTDL data:  {pformat(data)}")
                if data["_type"] == "url":
                    song_subject = data["url"]
                elif data["_type"] == "playlist":
                    return data

        # Actually call YoutubeDL extract_info, and deal with no-handler errors quietly.
        try:
            data = await self.bot.loop.run_in_executor(
                self.thread_pool,
                functools.partial(self.unsafe_ytdl.extract_info, song_subject, *args, **kwargs),
            )
        except NoSupportingHandlers:
            # due to how we allow search service strings we can't just encode this by default.
            song_subject = song_subject.replace(":", " ")
            data = await self.bot.loop.run_in_executor(
                self.thread_pool,
                functools.partial(self.unsafe_ytdl.extract_info, song_subject, *args, **kwargs),
            )

        # make sure the ytdlp data is serializable to make it more predictable.
        data = self.ytdl.sanitize_info(data)

        # Extractor youtube:search returns a playlist-like result, usually with one entry.
        # Combine the entry dict with the info dict as if it was a top-level extraction.
        # This prevents single-entry searches being processed like a playlist later.
        if (
            data.get("extractor", "") == "youtube:search"
            and len(data.get("entries", [])) == 1
            and type(data.get("entries", None)) is list
            and data.get("playlist_count", 0) == 1
        ):
            log.noise("Extractor youtube:search returned single-entry result, replacing base info with entry info.")
            entry_info = copy.deepcopy(data["entries"][0])
            for key in entry_info:
                if key in data:
                    data[key] = entry_info[key]
                else:
                    data[key] = entry_info[key]
            del data["entries"]

        return data

    def _experiment_with_data(self, data, place=""):
        d = YtdlpResponseDict(data)
        xd = "__REDACTED_FOR_CLARITY__"
        if "entries" in data:
            # cleaning up entry data to make it easier to parse in logs.
            for i, e in enumerate(data["entries"]):
                if "automatic_captions" in e:
                    data["entries"][i]["automatic_captions"] = xd
                if "formats" in e:
                    data["entries"][i]["formats"] = xd
                if "heatmap" in e and e["heatmap"]:
                    data["entries"][i]["heatmap"] = xd
                if "description" in e:
                    data["entries"][i]["description"] = xd

        if "formats" in data:
            data["formats"] = xd

        if "automatic_captions" in data:
            data["automatic_captions"] = xd

        if "heatmap" in data and data["heatmap"]:
            data["heatmap"] = xd

        if "description" in data:
            data["description"] = xd

        log.debug(f"{place}Extract needs process:  {d.needs_processing}")
        log.noise(f"Serial-Safe Data:  {pformat(data)}")

    async def safe_extract_info(self, *args, **kwargs):
        log.noise(f"Called safe_extract_info with:  {args}, {kwargs}")
        return await self.bot.loop.run_in_executor(
            self.thread_pool,
            functools.partial(self.safe_ytdl.extract_info, *args, **kwargs),
        )


class YtdlpResponseDict(UserDict):
    """Object with helpers to normalize YoutubeDL response data and make it easier to use."""
    def __init__(self, data: Dict) -> NoReturn:
       super().__init__(data)

    def get_entries_dicts(self) -> List[Dict]:
        """will return entries as-is from data or an empty list if no entries are set."""
        entries = self.data.get("entries", [])
        if type(entries) is List:
            return entries
        return []

    def get_entries_objects(self) -> List["YtdlpResponseDict"]:
        """will iterate over entries and return list of YtdlpResponseDicts"""
        return [YtdlpResponseDict(e) for e in self.get_entries_dict]

    def get_entry_dict_at(self, idx: int) -> Optional[Dict]:
        """Get a dict from "entries" at the given index or None."""
        entries = self.get_entries_dicts()
        if entries:
            try:
                return entries[idx]
            except IndexError:
                pass
        return None

    def get_entry_object_at(self, idx: int) -> Optional["YtdlpResponseDict"]:
        """Get a YtdlpResponseDict for given entry or None."""
        e = self.get_entry_dict_at(idx)
        if e:
            return YtdlpResponseDict(e)
        return None

    def get_playable_url(self) -> str:
        """
        Get a playable URL for any given response type.
        will try 'url', then 'webpage_url'
        """
        if self.ytdl_type == "video":
            if not self.webpage_url:
                return self.url
            else:
                return self.webpage_url
        
        if not self.url:
            return self.webpage_url
        else:
            return self.url

    @property
    def entry_count(self) -> int:
        """count of existing entries if available or 0"""
        if self.has_entries:
            return len(self.data["entries"])
        return 0

    @property
    def has_entries(self) -> bool:
        """bool status if iterable entries are present."""
        if "entries" not in self.data:
            return False
        if type(self.data["entries"]) is not list:
            return False
        return bool(len(self.data["entries"]))

    @property
    def needs_processing(self) -> bool:
        """Return true if this response data needs extra processing to extract completely."""
        return True

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
            #if "playlist_count" not in self.data and "entries" not in self.data:
            #    return True

            # Bandcamp:album extractor only populates "playlist_count" after processing.
            # seems nothing else useful is returned by processing, so we can probably skip it.
            if self.extractor == "Bandcamp:album" and "entries" in self.data:
                return False

            # youtube playlists always contain a playlist_count and entries keys
            # but entries can be an empty generator before processing.
            # if we use ytdl.sanitize_info() we need to check for a string rather than a generator.
            entries = self.data.get("entries", None)
            if (
                not entries
                or inspect.isgeneratorfunction(entries)
                or inspect.isgenerator(entries)
                or (type(entries) is str and entries.startswith("<generator"))
            ):
                return True

            if "entries" in self.data and "playlist_count" in self.data:
                # if we have a playlist_count and size of entries does not match it.
                entry_count = sum(1 for _ in entries)
                if entry_count != self.playlist_count:
                    return True

        return False

    @property
    def thumbnail_url(self) -> str:
        """
        Get a thumbnail url if available, or create one if possible, otherwise returns an empty string.
        Note, the URLs returned from this function may be time-sensitive. 
        In the case of spotify, URLs may not last longer than a day.
        """
        # TODO: IF time-sensitive URLs are a problem; might get away with downloading and sending as an attachment? 
        turl = self.data.get("thumbnail", None)
        # if we have a thumbnail url, clean it up if needed and return it.
        if turl:
            return turl

        # Check if we have a thumbnails key and pick a thumb from it.
        # TODO: maybe loop over these finding the largest / highest priority entry instead?.
        thumbs = self.data.get("thumbnails", [])
        if thumbs:
            if self.extractor == "youtube":
                # youtube seems to set the last list entry to the largest.
                turl = thumbs[-1].get("url")

            # spotify images are in size desending order. though we don't use them at the moment.
            # elif self.extractor == "spotify:musicbot":
                # turl = thumbs[0].get("url")
            elif len(thumbs):
                turl = thumbs[0].get("url")

            if turl:
                return turl

        # if all else fails, try to make a URL on our own.
        if self.extractor == "youtube":
            if self.video_id:
                return f"https://i.ytimg.com/vi/{self.video_id}/maxresdefault.jpg"

        # Extractor Bandcamp:album unfortunately does not give us thumbail(s)
        # tracks do have thumbs, but process does not return them while "extract_flat" is enabled.
        # we don't get enough data with albums to make a thumbnail URL either.
        # really this is an upstream issue with ytdlp, and should be patched there.
        # See: BandcampAlbumIE and add missing thumbnail: self._og_search_thumbnail(webpage)

        return ""

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
    def title(self) -> str:
        """returns title value if it exists, empty string otherwise."""
        # Note: seemingly all processed data should have "title" key
        # entries in data may also have "fulltitle" and "playlist_title" keys.
        return self.data.get("title", "")

    @property
    def playlist_count(self) -> int:
        """returns the playlist_count value if it exists, or 0"""
        return self.data.get("playlist_count", 0)

    @property
    def duration(self) -> float:
        """returns duration in seconds if available, or 0"""
        try:
            return float(self.data.get("duration", 0))
        except ValueError:
            return 0.0

    @property
    def is_live(self) -> bool:
        """return is_live key status or False if not found."""
        return self.data.get("is_live", False)
