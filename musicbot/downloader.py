import os
import asyncio
import logging
import functools

# For the time being, youtube_dl is slow.
# With this in mind, lets stick to the fork until it gets a dev.
import yt_dlp as youtube_dl
import copy

from concurrent.futures import ThreadPoolExecutor

log = logging.getLogger(__name__)

ytdl_format_options = {
    "format": "bestaudio/best",
    "outtmpl": "%(extractor)s-%(id)s-%(title)s.%(ext)s",
    "restrictfilenames": True,
    "noplaylist": True,
    "nocheckcertificate": True,
    "ignoreerrors": True,
    "logtostderr": False,
    "quiet": True,
    "no_warnings": True,
    "default_search": "auto",
    "source_address": "0.0.0.0",
    "usenetrc": True,
}

"""
    https://github.com/yt-dlp/yt-dlp/commit/819e05319baff2d896df026f1ef905e1f21be942#diff-d3ba8be45cae8dd7889a71c3360c9e4ac1160de8a5f3443b6e4a656395267f9bL491
    With the aforementioned usage of yt-dlp, a commit *one week prior* to my work with this broke
    changing yt-dl object params after creation. I don't fully understand how this was broken in
    such a manner that two separate objects manage to share their params, nor do I understand how
    these lines relate to progress reporting, but they did it.
"""
unsafe_ytdl_format_options = copy.deepcopy(ytdl_format_options)
unsafe_ytdl_format_options["ignoreerrors"] = False

# Fuck your useless bugreports message that gets two link embeds and confuses users
youtube_dl.utils.bug_reports_message = lambda: ""

"""
    Alright, here's the problem.  To catch youtube-dl errors for their useful information, I have to
    catch the exceptions with `ignoreerrors` off.  To not break when ytdl hits a dumb video
    (rental videos, etc), I have to have `ignoreerrors` on.  I can change these whenever, but with async
    that's bad.  So I need multiple ytdl objects.

"""


class Downloader:
    def __init__(self, download_folder=None):
        self.thread_pool = ThreadPoolExecutor(max_workers=2)
        self.download_folder = download_folder

        if download_folder:
            otmpl = unsafe_ytdl_format_options["outtmpl"]
            unsafe_ytdl_format_options["outtmpl"] = os.path.join(download_folder, otmpl)
            # print("setting template to " + os.path.join(download_folder, otmpl))

            otmpl = ytdl_format_options["outtmpl"]
            ytdl_format_options["outtmpl"] = os.path.join(download_folder, otmpl)

        self.unsafe_ytdl = youtube_dl.YoutubeDL(unsafe_ytdl_format_options)
        self.safe_ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

    @property
    def ytdl(self):
        return self.safe_ytdl

    async def extract_info(
        self, loop, *args, on_error=None, retry_on_error=False, **kwargs
    ):
        """
        Runs ytdl.extract_info within the threadpool. Returns a future that will fire when it's done.
        If `on_error` is passed and an exception is raised, the exception will be caught and passed to
        on_error as an argument.
        """
        if callable(on_error):
            try:
                return await loop.run_in_executor(
                    self.thread_pool,
                    functools.partial(self.unsafe_ytdl.extract_info, *args, **kwargs),
                )

            except Exception as e:

                # (youtube_dl.utils.ExtractorError, youtube_dl.utils.DownloadError)
                # I hope I don't have to deal with ContentTooShortError's
                if asyncio.iscoroutinefunction(on_error):
                    asyncio.ensure_future(on_error(e), loop=loop)

                elif asyncio.iscoroutine(on_error):
                    asyncio.ensure_future(on_error, loop=loop)

                else:
                    loop.call_soon_threadsafe(on_error, e)

                if retry_on_error:
                    return await self.safe_extract_info(loop, *args, **kwargs)
        else:
            return await loop.run_in_executor(
                self.thread_pool,
                functools.partial(self.unsafe_ytdl.extract_info, *args, **kwargs),
            )

    async def safe_extract_info(self, loop, *args, **kwargs):
        return await loop.run_in_executor(
            self.thread_pool,
            functools.partial(self.safe_ytdl.extract_info, *args, **kwargs),
        )
