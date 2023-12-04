import os
import asyncio
import logging
import functools
import yt_dlp as youtube_dl

from concurrent.futures import ThreadPoolExecutor

from types import MappingProxyType

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
    def __init__(self, download_folder=None):
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

    async def extract_info(
        self, loop, *args, on_error=None, retry_on_error=False, **kwargs
    ):
        """
        Runs ytdl.extract_info within the threadpool. Returns a future that will fire when it's done.
        If `on_error` is passed and an exception is raised, the exception will be caught and passed to
        on_error as an argument.
        """

        # converting Spotify URL to URI for the bot to use
        def convert_url_to_uri(url):
            parts = url.split("/")
            spotify_type = parts[-2]  # 'track' or 'playlist'
            spotify_id = parts[-1]  # the ID of the track or playlist
            uri = f"spotify:{spotify_type}:{spotify_id}"
            return uri

        if args and args[0].startswith("https://open.spotify.com/"):
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

    async def url_to_filename(self, bot, song_url: str) -> str:
        """
        Validates a song_url to be played and returns only the filename.

        :param song_url: The song url to add to the playlist.
        """

        try:
            info = await self.extract_info(bot.loop, song_url, download=False)
        except Exception as e:
            raise ExtractionError(
                "Could not extract information from {}\n\n{}".format(song_url, e)
            )

        if not info:
            raise ExtractionError("Could not extract information from %s" % song_url)

        # TODO: if/when playlists work in autoplaylist.txt we will need to handle this.
        if info.get("_type", None) == "playlist":
            raise WrongEntryTypeError(
                "This is a playlist.",
                True,
                info.get("webpage_url", None) or info.get("url", None),
            )

        if info.get("is_live", False):
            raise WrongEntryTypeError(
                "This is a live stream.",
                True,
                info.get("webpage_url", None) or info.get("url", None),
            )

        if info["extractor"] in ["generic", "Dropbox"]:
            log.debug("Detected a generic extractor, or Dropbox")
            try:
                headers = await get_header(bot.session, info["url"])
                content_type = headers.get("CONTENT-TYPE")
                log.debug("Got content type {}".format(content_type))
            except Exception as e:
                log.warning(
                    "Failed to get content type for url {} ({})".format(song_url, e)
                )
                content_type = None

            if content_type:
                if content_type.startswith(("application/", "image/")):
                    if not any(x in content_type for x in ("/ogg", "/octet-stream")):
                        # How does a server say `application/ogg` what the actual fuck
                        raise ExtractionError(
                            'Invalid content type "%s" for url %s'
                            % (content_type, song_url)
                        )

                elif (
                    content_type.startswith("text/html")
                    and info["extractor"] == "generic"
                ):
                    log.warning(
                        "Got text/html for content-type, this might be a stream."
                    )
                    raise WrongEntryTypeError(
                        "This is a playlist.",
                        True,
                        info.get("webpage_url", None) or info.get("url", None),
                    )

                elif not content_type.startswith(("audio/", "video/")):
                    log.warning(
                        'Questionable content-type "{}" for url {}'.format(
                            content_type, song_url
                        )
                    )

        return self.downloader.ytdl.prepare_filename(info)
