import aiohttp
import asyncio
import asyncio.exceptions
import base64
import logging
import re
import time

from typing import List, Dict, Tuple

from .exceptions import SpotifyError

log = logging.getLogger(__name__)


class SpotifyObject:
    """Base class for spotify response objects."""
    def __init__(self, data: Dict):
        self.data = data

    @staticmethod
    def is_type(data: Dict, spotify_type: str) -> bool:
        """Verify if data has a 'type' key matching spotify_type value"""
        type_str = data.get("type", None)
        return True if type_str == spotify_type else False

    @staticmethod
    def is_track_data(data: Dict) -> bool:
        return SpotifyObject.is_type(data, "track")

    @staticmethod
    def is_playlist_data(data: Dict) -> bool:
        return SpotifyObject.is_type(data, "playlist")

    @staticmethod
    def is_album_data(data: Dict) -> bool:
        return SpotifyObject.is_type(data, "album")

    @property
    def spotify_id(self):
        return self.data.get("id", None)

    @property
    def spotify_url(self):
        exurls = self.data.get("external_urls", None)
        if exurls:
            return exurls.get("spotify", None)
        return None

    @property
    def name(self) -> str:
        return self.data.get("name", None)


class SpotifyTrack(SpotifyObject):
    def __init__(self, track_data: Dict):
        if not SpotifyObject.is_track_data(track_data):
            raise SpotifyError("Invalid track_data, must be of type 'track'")
        super().__init__(track_data)

    @property
    def artist_name(self) -> str:
        """Get the first artist name, if any, from track data. Can be empty string."""
        artists = self.data.get("artists", None)
        if artists:
            return artists[0].get("name", "")
        return ""

    @property
    def artist_names(self) -> List[str]:
        """Get all artist names for track in a list of strings. List may be empty"""
        artists = self.data.get("artists", [])
        names = []
        for artist in artists:
            n = artist.get("name", None)
            if n:
                names.append(n)
        return names

    def get_joined_artist_names(self, join_with: str = " & ") -> str:
        """Gets all non-empty artist names joined together as a string."""
        return join_with.join(self.artist_names)

    def get_track_search_string(self, format_str: str = "{0} {1}", join_artists_with: str = " & ") -> str:
        """Get track title with artist names for searching against"""
        return format_str.format(
            self.get_joined_artist_names(join_artists_with),
            self.name,
        )


class SpotifyPlaylist(SpotifyObject):
    def __init__(self, playlist_data: Dict):
        if not SpotifyObject.is_playlist_data(playlist_data):
            raise ValueError("Invalid playlist_data, must be of type 'playlist'")
        super().__init__(playlist_data)

    @property
    def total_tracks(self) -> int:
        """Get number of total tracks in playlist, as reported by API"""
        tracks = self.data.get("tracks", {})
        return tracks.get("total", 0)


class Spotify:
    OAUTH_TOKEN_URL = "https://accounts.spotify.com/api/token"
    API_BASE = "https://api.spotify.com/v1/"
    URL_REGEX = re.compile(r"(?:https?://)?open\.spotify\.com/")

    def __init__(self, client_id: str, client_secret: str, aiosession: aiohttp.ClientSession, loop: asyncio.AbstractEventLoop = None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.guest_mode = client_id is None or client_secret is None

        self.aiosession = aiosession
        self.loop = loop if loop else asyncio.get_event_loop()

        self._token = None

        self.max_token_tries = 2

    @staticmethod
    def url_to_uri(url: str) -> str:
        """
        Convert a spotify url to a spotify URI string.
        If the URL is valid it will start with "spotify:"
        """
        # strip away any query string data.
        url = url.split("?")[0]
        # replace protocol and FQDN with our local "scheme" and clean it up.
        return Spotify.URL_REGEX.sub("spotify:", url).replace("/", ":")

    @staticmethod
    def url_to_parts(url: str) -> List[str]:
        """
        Convert a spotify url to a string list of URI parts.
        If the URL is valid, index 0 will equal "spotify".
        Empty list is returned if URL is not a valid spotify URL.
        """
        uri = Spotify.url_to_uri(url)
        if uri.startswith("spotify:"):
            return uri.split(":")
        else:
            return []

    def api_safe_url(self, url: str) -> str:
        return url.replace(self.API_BASE, "")

    async def get_all_tracks_in_playlist(self, playlist_id: str) -> List[str]:
        """Fetch a playlist and return its tracks as a list of spotify URLs"""
        track_urls = []
        bad_entries = 0  # counter for items in playlist which aren't tracks.
        start_time = time.time()
        pldata = await self.get_playlist_tracks(playlist_id)
        # pldata["tracks"]["items"] <- array of track/episode objects
        # pldata["tracks"]["total"] <- total tracks in playlist.
        # pldata["tracks"]["next"] <- next URL.
        log.debug(f"Spotify Playlist total tacks: {pldata['total']}")
        while True:
            
            for item in pldata["items"]:
                track = item["track"]
                if track["type"] == "track":
                    track_urls.append(track["external_urls"]["spotify"])
                else:
                    bad_entries += 1

            # TODO: if we have a next url to fetch, we should convert it to a playlist_tracks request to reduce overhead.
            next_url = pldata["next"]
            if next_url is not None:
                log.debug(f"Playlist Next URL:  {next_url}")
                pldata = await self.make_api_req(
                    self.api_safe_url(next_url))
                continue
            else:
                break

        time_taken = time.time() - start_time
        url_set = set(track_urls)
        if len(track_urls) > len(url_set):
            dupe_count = len(track_urls) - len(url_set)
            track_urls = list(url_set)
            log.debug(f"Spotify playlist tracks processing found {dupe_count} dupe(s)")
        log.debug(f"Spofify playist tracks took {time_taken:.3f} seconds for {len(track_urls)} tracks and {bad_entries} bad tracks.")
        return (track_urls, bad_entries, time_taken)


    async def get_all_tracks_in_album(self, album_id: str) -> List[str]:
        pass
        """
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
        """

    async def get_search_string_from_track_id(self, track_id: str) -> str:
        """jus liek cuzin okri"""
        pass


    async def get_track(self, track_id: str):
        """Get a track's info from its Spotify ID"""
        return await self.make_api_req(f"tracks/{track_id}")

    async def get_album(self, album_id: str):
        """Get an album's info from its Spotify ID"""
        return await self.make_api_req(f"albums/{album_id}")

    async def get_album_tracks(self, album_id: str):
        """Get an album's tracks info from its Spotify ID"""
        return await self.make_api_req(f"albums/{album_id}")

    async def get_user_playlist(self, user_id: str, list_id: str):
        """Get a user playlist info from its Spotify ID"""
        return await self.make_api_req(f"users/{user_id}/playlists/{list_id}")

    async def get_playlist(self, list_id: str) -> SpotifyPlaylist:
        """Get a playlist's info from its Spotify ID"""
        pldata = await self.make_api_req(f"playlists/{list_id}")
        return SpotifyPlaylist(pldata)

    async def get_playlist_tracks(self, list_id: str):
        """Get a list of a playlist's tracks from its Spotify ID"""
        return await self.make_api_req(f"playlists/{list_id}/tracks")

    async def make_api_req(self, endpoint: str):
        """Proxy method for making a Spotify req using the correct Auth headers"""
        url = self.API_BASE + endpoint
        token = await self._get_token()
        return await self._make_get(
            url, headers={"Authorization": f"Bearer {token}"}
        )

    async def _make_get(self, url: str, headers=None):
        """Makes a GET request and returns the results"""
        async with self.aiosession.get(url, headers=headers) as r:
            if r.status != 200:
                raise SpotifyError(
                    "Issue making GET request to {0}: [{1.status}] {2}".format(
                        url, r, await r.json()
                    )
                )
            return await r.json()

    async def _make_post(self, url: str, payload, headers=None):
        """Makes a POST request and returns the results"""
        async with self.aiosession.post(url, data=payload, headers=headers) as r:
            if r.status != 200:
                raise SpotifyError(
                    "Issue making POST request to {0}: [{1.status}] {2}".format(
                        url, r, await r.json()
                    )
                )
            return await r.json()

    def _make_token_auth(self, client_id, client_secret):
        auth_header = base64.b64encode((client_id + ":" + client_secret).encode("ascii"))
        return {"Authorization": "Basic %s" % auth_header.decode("ascii")}

    def _is_token_valid(self):
        """Checks if the token is valid"""
        if not self._token:
            return False
        return self._token["expires_at"] - int(time.time()) > 60

    async def has_token(self):
        """Attempt to get token and return True if successful."""
        if await self._get_token():
            return True
        return False

    async def _get_token(self):
        """Gets the token or creates a new one if expired"""
        if self._is_token_valid():
            return self._token["access_token"]

        if self.guest_mode:
            token = await self._request_guest_token()
            if token is None:
                raise SpotifyError(
                    "Failed to get a guest token from Spotify, please try specifying client id and client secret"
                )
            self._token = {
                "access_token": token["accessToken"],
                "expires_at": int(token["accessTokenExpirationTimestampMs"]) / 1000,
            }
        else:
            token = await self._request_token()
            if token is None:
                raise SpotifyError(
                    "Requested a token from Spotify, did not end up getting one"
                )
            token["expires_at"] = int(time.time()) + token["expires_in"]
            self._token = token
        log.debug(
            "Created a new {0}access token: {1}".format(
                "guest " if self.guest_mode else "", self._token
            )
        )
        return self._token["access_token"]

    async def _request_token(self):
        """Obtains a token from Spotify and returns it"""
        try:
            payload = {"grant_type": "client_credentials"}
            headers = self._make_token_auth(self.client_id, self.client_secret)
            r = await self._make_post(
                self.OAUTH_TOKEN_URL, payload=payload, headers=headers
            )
            return r
        except asyncio.exceptions.CancelledError as e:  # see request_guest_token()
            if self.max_token_tries == 0:
                raise e

            self.max_token_tries -= 1
            return await self._request_token()

    async def _request_guest_token(self):
        """Obtains a web player token from Spotify and returns it"""
        try:
            async with self.aiosession.get(
                "https://open.spotify.com/get_access_token?reason=transport&productType=web_player",
            ) as r:
                if r.status != 200:
                    try:
                        raise SpotifyError(
                            "Issue generating guest token: [{0.status}] {1}".format(
                                r, await r.json()
                            )
                        )
                    except aiohttp.ContentTypeError as e:
                        raise SpotifyError(
                            "Issue generating guest token: [{0.status}] {1}".format(
                                r, e
                            )
                        )
                return await r.json()
        except (
            asyncio.exceptions.CancelledError
        ) as e:  # fails to generate after a restart, but succeeds if you just try again
            if (
                self.max_token_tries == 0
            ):  # Unfortunately this logic has to be here, because if just tried
                raise e  # to get a token in get_token() again it fails for some reason

            self.max_token_tries -= 1
            return await self._request_guest_token()
