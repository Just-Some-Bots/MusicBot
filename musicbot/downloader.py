import os
import asyncio
import logging
import functools
import yt_dlp as youtube_dl

from concurrent.futures import ThreadPoolExecutor

log = logging.getLogger(__name__)

ytdl_format_options = {
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

    async def extract_info(
        self, loop, *args, on_error=None, retry_on_error=False, **kwargs
    ):
        """
        Runs ytdl.extract_info within the threadpool. Returns a future that will fire when it's done.
        If `on_error` is passed and an exception is raised, the exception will be caught and passed to
        on_error as an argument.
        """

        #converting Spotify URL to URI for the bot to use
        def convert_url_to_uri(spotify_url):
            parts = spotify_url.split('/')
            spotify_type = parts[-2]  # 'track' or 'playlist'
            spotify_id = parts[-1]  # the ID of the track or playlist
            spotify_uri = f'spotify:{spotify_type}:{spotify_id}'
            return spotify_uri
        
        if args and args[0].startswith('https://open.spotify.com/'):
            # Convert the Spotify URL to a URI
            spotify_url = args[0]
            spotify_uri = convert_url_to_uri(spotify_url)
            
            # Replace the Spotify URL with the URI in the arguments
            args = (spotify_uri,) + args[1:]

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
