import os
import asyncio
import logging
import functools
import yt_dlp as youtube_dl

from urllib.parse import quote_plus
from concurrent.futures import ThreadPoolExecutor
from types import MappingProxyType
from typing import List, Union

from .exceptions import ExtractionError
from .spotify import Spotify, SpotifyTrack

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
        if url.startswith("<") and  url.endswith(">"):
            log.debug("stripped it of <>")
            url = url[1:-1]
        return youtube_dl.utils.url_or_none(url)

    async def get_spotify_data(self, spotify_url: str) -> Union[str, None]:
        if self.bot.config._spotify:
            raise ExtractionError("Spotify is not enabled.")

        if "open.spotify.com" not in spotify_url:
            raise ExtractionError("Song URL is not a spotify URL.")

        parts = Spotify.url_to_parts(song_url)
        data = None

        if parts and (
            parts[0] != "spotify"
            or all([_ not in parts for _ in ["track", "album", "playlist"]])
        ):
            raise ExtractionError(
                self.bot.str.get(
                    "cmd-play-spotify-invalid",
                    "Detected a spotify link, but it appears to be invalid or not supported.",
                )
            )
        elif "track" in parts:
            track = await self.spotify.get_track_object(parts[-1])
            await self.safe_send_message(
                channel,
                self.bot.str.get(
                    "cmd-play-spotify-track",
                    "Found spotify track, will search youtube for:  {song_subject}",
                    expire_in=30,
                ).format(song_subject=track.get_track_search_string())
            )
            
        elif "album" in parts:
            res = await self.spotify.get_album(parts[-1])
            res["total"]  # should contain number of total tracks.

            await self._do_playlist_checks(
                permissions, player, author, res["tracks"]["items"], total=res["total"]
            )
            
            procmesg = await self.safe_send_message(
                channel,
                self.str.get(
                    "cmd-play-spotify-album-process",
                    "Processing album `{0}` (`{1}`)",
                ).format(res["name"], song_url),
            )
            for i in res["tracks"]["items"]:
                if self.server_specific_data[channel.guild.id][
                    "halt_playlist_unpack"
                ]:
                    log.debug(
                        "Halting spotify album queuing due to clear command."
                    )
                    break
                song_url = i["name"] + " " + i["artists"][0]["name"]
                log.debug(
                    "Processing spotify album track:  {0}".format(
                        song_url
                    )
                )
                await self.cmd_play(
                    message,
                    player,
                    channel,
                    author,
                    permissions,
                    leftover_args,
                    song_url,
                )

            await self.safe_delete_message(procmesg)
            return Response(
                self.bot.str.get(
                    "cmd-play-spotify-album-queued",
                    "Enqueued `{0}` with **{1}** songs.",
                ).format(res["name"], len(res["tracks"]["items"]))
            )
        elif "playlist" in parts:
            obj = await self.spotify.get_playlist(parts[-1])
            data = await self.spotify.get_all_tracks_in_playlist(obj.spotify_id)
            log.debug(f"Spotify Playlist Data:  {obj.name} / {obj.total_tracks} --  {data}")
        

    async def get_playable_data(self, song_subject: str, subject_args: List):
        """
        Gets a playable URL and associated info, as quickly as possible.
        Return a tuple: (song_url, track_count, ytdl_info)
        """
        log.debug(f"Getting Playable Data for subject: {song_subject} {subject_args}")

        # Test the first argument as a URL right away.
        song_url = self.get_url_or_none(song_subject)
        search_terms = None

        if song_url:  # this is a valid URL.
            if "open.spotify.com" in song_url:
                # process initial spotify, extract track(s) and turn them into search URLs.
                pass
            info = await self.extract_info(self.bot.loop, song_url, download=False, process=False)
            log.noise(f"Info from playable data:  {info}")
        elif subject_args:  # not a URL, treat it as search terms.
            #search_terms = quote_plus(" ".join([song_subject, *subject_args]))
            search_terms = " ".join([song_subject, *subject_args])
            info = await self.extract_info(self.bot.loop, search_terms, download=False, process=False)
            log.noise(f"Info from playable data:  {info}")
        log.debug(f"Get Playable Data:  {song_url} -- {search_terms}")
        return (song_url, 1, {"_search_terms": search_terms})

        """
        # Rewrite YouTube playlist URLs if the wrong URL type is given
        playlist_regex = r"watch\?v=.+&(list=[^&]+)"
        matches = re.search(playlist_regex, song_url)
        groups = matches.groups() if matches is not None else []
        song_url = (
            "https://www.youtube.com/playlist?" + groups[0]
            if len(groups) > 0
            else song_url
        )"""
    '''
        if self.config._spotify and "open.spotify.com" in song_url:
            parts = Spotify.url_to_parts(song_url)

            if parts and (
                parts[0] != "spotify"
                or all([_ not in parts for _ in ["track", "album", "playlist"]])
            ):
                raise exceptions.CommandError(
                    self.str.get(
                        "cmd-play-spotify-invalid",
                        "Detected a spotify link, but it appears to be invalid or not supported.",
                    )
                )
            elif "track" in parts:
                res = await self.spotify.get_track(parts[-1])
                song_url = res["artists"][0]["name"] + " " + res["name"]
                await self.safe_send_message(
                    channel,
                    self.str.get(
                        "cmd-play-spotify-track",
                        "Found spotify track, now searching youtube for:  {song_subject}",
                        expire_in=30,
                    )
                )
            elif "album" in parts:
                res = await self.spotify.get_album(parts[-1])
                res["total"]  # should contain number of total tracks.

                await self._do_playlist_checks(
                    permissions, player, author, res["tracks"]["items"], total=res["total"]
                )
                
                procmesg = await self.safe_send_message(
                    channel,
                    self.str.get(
                        "cmd-play-spotify-album-process",
                        "Processing album `{0}` (`{1}`)",
                    ).format(res["name"], song_url),
                )
                for i in res["tracks"]["items"]:
                    if self.server_specific_data[channel.guild.id][
                        "halt_playlist_unpack"
                    ]:
                        log.debug(
                            "Halting spotify album queuing due to clear command."
                        )
                        break
                    song_url = i["name"] + " " + i["artists"][0]["name"]
                    log.debug(
                        "Processing spotify album track:  {0}".format(
                            song_url
                        )
                    )
                    await self.cmd_play(
                        message,
                        player,
                        channel,
                        author,
                        permissions,
                        leftover_args,
                        song_url,
                    )

                await self.safe_delete_message(procmesg)
                return Response(
                    self.str.get(
                        "cmd-play-spotify-album-queued",
                        "Enqueued `{0}` with **{1}** songs.",
                    ).format(res["name"], len(res["tracks"]["items"]))
                )
            elif "playlist" in parts:
                obj = await self.spotify.get_playlist(parts[-1])
                data = await self.spotify.get_all_tracks_in_playlist(obj.spotify_id)
                log.debug(f"Spotify Playlist Data:  {obj.name} / {obj.total_tracks} --  {data}")
    '''
    """
            # TODO: make the rest of this move to beyond the lock...
            # TODO: maybe get as much info as we can first and report back on the track/album/playlist and entry counts.
            #  - Also use the counts for rough estimates.
                try:
                    if "track" in parts:
                        res = await self.spotify.get_track(parts[-1])
                        song_url = res["artists"][0]["name"] + " " + res["name"]

                    elif "album" in parts:
                        res = await self.spotify.get_album(parts[-1])

                        await self._do_playlist_checks(
                            permissions, player, author, res["tracks"]["items"]
                        )
                        procmesg = await self.safe_send_message(
                            channel,
                            self.str.get(
                                "cmd-play-spotify-album-process",
                                "Processing album `{0}` (`{1}`)",
                            ).format(res["name"], song_url),
                        )
                        for i in res["tracks"]["items"]:
                            if self.server_specific_data[channel.guild.id][
                                "halt_playlist_unpack"
                            ]:
                                log.debug(
                                    "Halting spotify album queuing due to clear command."
                                )
                                break
                            song_url = i["name"] + " " + i["artists"][0]["name"]
                            log.debug(
                                "Processing spotify album track:  {0}".format(
                                    song_url
                                )
                            )
                            await self.cmd_play(
                                message,
                                player,
                                channel,
                                author,
                                permissions,
                                leftover_args,
                                song_url,
                            )

                        await self.safe_delete_message(procmesg)
                        return Response(
                            self.str.get(
                                "cmd-play-spotify-album-queued",
                                "Enqueued `{0}` with **{1}** songs.",
                            ).format(res["name"], len(res["tracks"]["items"]))
                        )

                    elif "playlist" in parts:
                        res = []
                        r = await self.spotify.get_playlist_tracks(parts[-1])
                        while True:
                            res.extend(r["items"])
                            if r["next"] is not None:
                                r = await self.spotify.make_spotify_req(r["next"])
                                continue
                            else:
                                break
                        await self._do_playlist_checks(
                            permissions, player, author, res
                        )
                        procmesg = await self.safe_send_message(
                            channel,
                            self.str.get(
                                "cmd-play-spotify-playlist-process",
                                "Processing playlist `{0}` (`{1}`)",
                            ).format(parts[-1], song_url),
                        )
                        for i in res:
                            if self.server_specific_data[channel.guild.id][
                                "halt_playlist_unpack"
                            ]:
                                log.debug(
                                    "Halting spotify playlist queuing due to clear command."
                                )
                                break
                            song_url = (
                                i["track"]["name"]
                                + " "
                                + i["track"]["artists"][0]["name"]
                            )
                            log.debug(
                                "Processing spotify playlist track:  {0}".format(
                                    song_url
                                )
                            )
                            await self.cmd_play(
                                message,
                                player,
                                channel,
                                author,
                                permissions,
                                leftover_args,
                                song_url,
                            )

                        await self.safe_delete_message(procmesg)
                        return Response(
                            self.str.get(
                                "cmd-play-spotify-playlist-queued",
                                "Enqueued `{0}` with **{1}** songs.",
                            ).format(parts[-1], len(res))
                        )

                    else:
                        raise exceptions.CommandError(
                            self.str.get(
                                "cmd-play-spotify-unsupported",
                                "That is not a supported Spotify URI.",
                            ),
                            expire_in=30,
                        )
                except exceptions.SpotifyError:
                    raise exceptions.CommandError(
                        self.str.get(
                            "cmd-play-spotify-invalid",
                            "You either provided an invalid URI, or there was a problem.",
                        )
                    )
    ##"""
    '''
        async def get_info(song_url):
            info = await self.extract_info(
                self.loop, song_url, download=False, process=False
            )
            # If there is an exception arise when processing we go on and let extract_info down the line report it
            # because info might be a playlist and thing that's broke it might be individual entry
            try:
                info_process = await self.extract_info(
                    self.loop, song_url, download=False
                )
                info_process_err = None
            except Exception as e:
                info_process = None
                info_process_err = e

            return (info, info_process, info_process_err)
    #'''

    async def extract_info(
        self, loop, *args, on_error=None, retry_on_error=False, **kwargs
    ):
        """
        Runs ytdl.extract_info within the threadpool. Returns a future that will fire when it's done.
        If `on_error` is passed and an exception is raised, the exception will be caught and passed to
        on_error as an argument.
        """

        log.noise(f"Called extract_info with:  {args}, oe={on_error}, roe={retry_on_error}, {kwargs}")

        # handle extracting spotify links before ytdl get ahold of them.
        if args and "open.spotify.com" in args[0].lower() and self.bot.config._spotify:
            log.noise("Handling spofity link...")
            if not Spotify.is_url_supported(args[0]):
                raise ExtractionError("Spotify URL is invalid or not supported.")

            process = kwargs.get("process", False)
            download = kwargs.get("download", False)
            uri_parts = Spotify.url_to_parts(args[0])
            
            # return only basic ytdl-flavored data from the Spotify API.
            if not process and not download:
                return await self.bot.spotify.get_spotify_ytdl_data(arg[0])
            
            # modify args to have ytdl return search data, only for singular tracks.
            # for albums & playlists, we want to return full playlist data rather than partial as above.
            if process and not download:
                return await self.bot.spotify.get_spotify_ytdl_data(args[0], process=True)
                
            data = Spotify.get_spotify_ytdl_data(arg[0])
            if kwargs.get("process", False):
                # if process is set, return youtube search results instead of spotify data.
                pass

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
