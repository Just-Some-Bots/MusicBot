import os
import asyncio
import logging
import functools
import yt_dlp as youtube_dl

from concurrent.futures import ThreadPoolExecutor
from types import MappingProxyType

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
                return await self.bot.spotify.get_spotify_ytdl_data(args[0])

            # modify args to have ytdl return search data, only for singular tracks.
            # for albums & playlists, we want to return full playlist data rather than partial as above.
            if process:
                data = await self.bot.spotify.get_spotify_ytdl_data(args[0], process)
                if data["_type"] == "url":
                    args = (data["url"],)
                elif data["_type"] == "playlist":
                    return data

        if callable(on_error):
            try:
                return await self.bot.loop.run_in_executor(
                    self.thread_pool,
                    functools.partial(self.unsafe_ytdl.extract_info, *args, **kwargs),
                )

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
                    return await self.safe_extract_info(*args, **kwargs)
        else:
            return await self.bot.loop.run_in_executor(
                self.thread_pool,
                functools.partial(self.unsafe_ytdl.extract_info, *args, **kwargs),
            )

    async def safe_extract_info(self, *args, **kwargs):
        log.noise(f"Called safe_extract_info with:  {args}, {kwargs}")
        return await self.bot.loop.run_in_executor(
            self.thread_pool,
            functools.partial(self.safe_ytdl.extract_info, *args, **kwargs),
        )
