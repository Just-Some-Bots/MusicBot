import aiohttp
import asyncio
import asyncio.exceptions
import base64
import logging
import re
import time

from typing import List, Dict, Optional, NoReturn
from urllib.parse import urlparse

from .exceptions import SpotifyError

log = logging.getLogger(__name__)


class SpotifyObject:
    """Base class for parsed spotify response objects."""
    def __init__(self, data: Dict, origin_url: Optional[str] = None) -> NoReturn:
        self.data = data
        if origin_url:
            self.origin_url = origin_url
        else:
            self.origin_url = self.spotify_url

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
    def spotify_type(self) -> Optional[str]:
        """Returns the type string of the object as reported by the API data."""
        return self.data.get("type", None)

    @property
    def spotify_id(self) -> Optional[str]:
        """Returns the Spotify ID of the object, as reported by the API data."""
        return self.data.get("id", None)

    @property
    def spotify_url(self) -> Optional[str]:
        """Returns the spotify external url for this object, if it exists in the API data."""
        exurls = self.data.get("external_urls", None)
        if exurls:
            return exurls.get("spotify", None)
        return None

    @property
    def spotify_uri(self) -> Optional[str]:
        return self.data.get("uri", None)

    @property
    def name(self) -> Optional[str]:
        return self.data.get("name", None)

    @property
    def ytdl_type(self) -> str:
        return "url" if self.spotify_type == "track" else "playlist"

    def to_ytdl_dict(self) -> Dict:
        """Returns object data in a format similar to ytdl."""
        return {
            "_type": self.ytdl_type,
            "id": self.spotify_uri,
            "original_url": self.origin_url,
            "webpage_url": self.spotify_url,
            "extractor": "spotify:musicbot",
            "extractor_key": "SpotifyMusicBot",
        }


class SpotifyTrack(SpotifyObject):
    """Track data for an individual track, parsed from spotify API response data."""
    def __init__(self, track_data: Dict, origin_url: Optional[str] = None) -> NoReturn:
        if not SpotifyObject.is_track_data(track_data):
            raise SpotifyError("Invalid track_data, must be of type 'track'")
        super().__init__(track_data, origin_url)

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

    def get_joined_artist_names(self, join_with: str = " ") -> str:
        """Gets all non-empty artist names joined together as a string."""
        return join_with.join(self.artist_names)

    def get_track_search_string(self, format_str: str = "{0} {1}", join_artists_with: str = " ") -> str:
        """Get track title with artist names for searching against"""
        return format_str.format(
            self.get_joined_artist_names(join_artists_with),
            self.name,
        )

    def to_ytdl_dict(self) -> Dict:
        return {
            **super().to_ytdl_dict(),
            "title": self.name,
            "artists": self.artist_names,
            "url": self.get_track_search_string("ytsearch:{0} {1}"),
            "playlist_count": 1,
        }


class SpotifyAlbum(SpotifyObject):
    """Album object with all or partial tracks, as parsed from spotify API response data."""
    def __init__(self, album_data: Dict, origin_url: Optional[str] = None) -> NoReturn:
        if not SpotifyObject.is_album_data(album_data):
            raise ValueError("Invalid album_data, must be of type 'playlist'")
        super().__init__(album_data, origin_url)
        self._track_objects = []

        self._create_track_objects()

    def _create_track_objects(self) -> NoReturn:
        tracks_data = self.data.get("tracks", None)
        if not tracks_data:
            raise ValueError("Invalid album_data, missing tracks key")

        items = tracks_data.get("items", None)
        if not items:
            raise ValueError("Invalid album_data, missing items key in tracks")

        # albums use a slightly different "SimplifiedTrackObject" without the album key.
        # each item is a track, versus having a "track" key for TrackObject data, like Playlists do.
        for item in items:
            self._track_objects.append(SpotifyTrack(item))

    @property
    def track_objects(self) -> List[SpotifyTrack]:
        """List of SpotifyTrack objects loaded with the playlist API data."""
        return self._track_objects

    @property
    def track_urls(self) -> List[str]:
        """List of spotify URLs for all tracks in ths playlist data."""
        return [x.spotify_url for x in self.track_objects]

    @property
    def track_count(self) -> int:
        """Get number of total tracks in playlist, as reported by API"""
        tracks = self.data.get("tracks", {})
        return tracks.get("total", 0)

    def to_ytdl_dict(self) -> Dict:
        return {
            **super().to_ytdl_dict(),
            "title": self.name,
            "url": "",
            "playlist_count": self.track_count,
            "entries": [t.to_ytdl_dict() for t in self.track_objects],
        }


class SpotifyPlaylist(SpotifyObject):
    """Playlist object with all or partial tracks, as parsed from spotify API response data."""
    def __init__(self, playlist_data: Dict, origin_url: Optional[str] = None) -> NoReturn:
        if not SpotifyObject.is_playlist_data(playlist_data):
            raise ValueError("Invalid playlist_data, must be of type 'playlist'")
        super().__init__(playlist_data, origin_url)
        self._track_objects = []

        self._create_track_objects()

    def _create_track_objects(self) -> NoReturn:
        tracks_data = self.data.get("tracks", None)
        if not tracks_data:
            raise ValueError("Invalid playlist_data, missing tracks key")

        items = tracks_data.get("items", None)
        if not items:
            raise ValueError("Invalid playlist_data, missing items key in tracks")

        for item in items:
            track_data = item.get("track", None)
            if track_data:
                self._track_objects.append(SpotifyTrack(track_data))
            else:
                raise ValueError("Invalid playlist_data, missing track key in items")

    @property
    def track_objects(self) -> List[SpotifyTrack]:
        """List of SpotifyTrack objects loaded with the playlist API data."""
        return self._track_objects

    @property
    def track_urls(self) -> List[str]:
        """List of spotify URLs for all tracks in ths playlist data."""
        return [x.spotify_url for x in self.track_objects]

    @property
    def track_count(self) -> int:
        """Get number of total tracks in playlist, as reported by API"""
        tracks = self.data.get("tracks", {})
        return tracks.get("total", 0)

    def to_ytdl_dict(self) -> Dict:
        return {
            **super().to_ytdl_dict(),
            "title": self.name,
            "url": "",
            "playlist_count": self.track_count,
            "entries": [t.to_ytdl_dict() for t in self.track_objects],
        }


class Spotify:
    OAUTH_TOKEN_URL = "https://accounts.spotify.com/api/token"
    API_BASE = "https://api.spotify.com/v1/"
    # URL_REGEX allows missing protocol scheme intentionally.
    URL_REGEX = re.compile(r"(?:https?://)?open\.spotify\.com/")

    def __init__(self, client_id: str, client_secret: str, aiosession: aiohttp.ClientSession, loop: asyncio.AbstractEventLoop = None) -> NoReturn:
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

        Note: this function assumes `url` is already a valid URL.
        See `downloader.get_url_or_none()` for validating input URLs.
        """
        # strip away query strings and fragments.
        url = urlparse(url)._replace(query="", fragment="").geturl()
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

    @staticmethod
    def is_url_supported(url: str) -> bool:
        parts = Spotify.url_to_parts(url)
        if not parts:
            return False
        if parts and "spotify" != parts[0]:
            return False
        if parts[1] not in ["track", "album", "playlist"]:
            return False
        if len(parts) < 3:
            return False
        return True

    def api_safe_url(self, url: str) -> str:
        return url.replace(self.API_BASE, "")

    async def get_spotify_ytdl_data(self, spotify_url: str, process: bool = False) -> Dict:
        parts = Spotify.url_to_parts(spotify_url)
        obj_type = parts[1]
        spotify_id = parts[-1]
        if obj_type == "track":
            data = await self.get_track_object(spotify_id)
            data.origin_url = spotify_url
            return data.to_ytdl_dict()

        if obj_type == "album":
            if process:
                data = await self.get_album_object_complete(spotify_id)
                data.origin_url = spotify_url
                return data.to_ytdl_dict()
            data = await self.get_album_object(spotify_id)
            data.origin_url = spotify_url
            return data.to_ytdl_dict()

        if obj_type == "playlist":
            if process:
                data = await self.get_playlist_object_complete(spotify_id)
                data.origin_url = spotify_url
                return data.to_ytdl_dict()
            data = await self.get_playlist_object(spotify_id)
            data.origin_url = spotify_url
            return data.to_ytdl_dict()

        return {}

    async def get_track_object(self, track_id: str) -> SpotifyTrack:
        """Lookup a spotify track by its ID and return a SpotifyTrack object"""
        data = await self.get_track(track_id)
        return SpotifyTrack(data)

    async def get_track(self, track_id: str) -> Dict:
        """Get a track's info from its Spotify ID"""
        return await self.make_api_req(f"tracks/{track_id}")

    async def get_album_object_complete(self, album_id: str) -> SpotifyAlbum:
        """Fetch a playlist and all its tracks from Spotify API, returned as a SpotifyAlbum object."""
        aldata = await self.get_album(album_id)
        tracks = aldata.get("tracks", {}).get("items", [])
        next_url = aldata.get("tracks", {}).get("next", None)

        total_tracks = aldata["tracks"]["total"]  # total tracks in playlist.
        log.debug(f"Spotify Album total tacks: {total_tracks}  --  {next_url}")
        while True:
            if next_url:
                log.debug(f"Getting Spofity Album Next URL:  {next_url}")
                next_data = await self.make_api_req(
                    self.api_safe_url(next_url)
                )
                next_tracks = next_data.get("items", None)
                if next_tracks:
                    tracks.extend(next_tracks)
                next_url = next_data.get("next", None)
                continue
            else:
                break

        if total_tracks > len(tracks):
            log.debug(f"Spotify Album Object may not be complete, expected {total_tracks} tracks but got {len(tracks)}")

        aldata["tracks"]["items"] = tracks

        return SpotifyAlbum(aldata)

    async def get_album_object(self, album_id: str) -> SpotifyAlbum:
        """Lookup a spotify playlist by its ID and return a SpotifyAlbum object"""
        data = await self.get_album(album_id)
        return SpotifyAlbum(data)

    async def get_album(self, album_id: str) -> Dict:
        """Get an album's info from its Spotify ID"""
        return await self.make_api_req(f"albums/{album_id}")

    async def get_album_tracks(self, album_id: str) -> Dict:
        """Get an album's tracks info from its Spotify ID"""
        return await self.make_api_req(f"albums/{album_id}")

    async def get_playlist_object_complete(self, list_id: str) -> SpotifyPlaylist:
        """Fetch a playlist and all its tracks from Spotify API, returned as a SpotifyPlaylist object."""
        pldata = await self.get_playlist(list_id)
        tracks = pldata.get("tracks", {}).get("items", [])
        next_url = pldata.get("tracks", {}).get("next", None)

        total_tracks = pldata["tracks"]["total"]  # total tracks in playlist.
        log.debug(f"Spotify Playlist total tacks: {total_tracks}  --  {next_url}")
        while True:
            if next_url:
                log.debug(f"Getting Spofity Playlist Next URL:  {next_url}")
                next_data = await self.make_api_req(
                    self.api_safe_url(next_url)
                )
                next_tracks = next_data.get("items", None)
                if next_tracks:
                    tracks.extend(next_tracks)
                next_url = next_data.get("next", None)
                continue
            else:
                break

        if total_tracks > len(tracks):
            log.debug(f"Spotify Playlist Object may not be complete, expected {total_tracks} tracks but got {len(tracks)}")

        pldata["tracks"]["items"] = tracks

        return SpotifyPlaylist(pldata)

    async def get_playlist_object(self, list_id: str) -> SpotifyPlaylist:
        """Lookup a spotify playlist by its ID and return a SpotifyPlaylist object"""
        data = await self.get_playlist(list_id)
        return SpotifyPlaylist(data)

    async def get_playlist(self, list_id: str) -> Dict:
        """Get a playlist's info from its Spotify ID"""
        return await self.make_api_req(f"playlists/{list_id}")

    async def get_playlist_tracks(self, list_id: str) -> Dict:
        """Get a list of a playlist's tracks from its Spotify ID"""
        return await self.make_api_req(f"playlists/{list_id}/tracks")

    async def make_api_req(self, endpoint: str) -> Dict:
        """Proxy method for making a Spotify req using the correct Auth headers"""
        url = self.API_BASE + endpoint
        token = await self._get_token()
        return await self._make_get(
            url, headers={"Authorization": f"Bearer {token}"}
        )

    async def _make_get(self, url: str, headers: Dict = None) -> Dict:
        """Makes a GET request and returns the results"""
        async with self.aiosession.get(url, headers=headers) as r:
            if r.status != 200:
                raise SpotifyError(
                    "Issue making GET request to {0}: [{1.status}] {2}".format(
                        url, r, await r.json()
                    )
                )
            return await r.json()

    async def _make_post(self, url: str, payload, headers: Dict = None) -> Dict:
        """Makes a POST request and returns the results"""
        async with self.aiosession.post(url, data=payload, headers=headers) as r:
            if r.status != 200:
                raise SpotifyError(
                    "Issue making POST request to {0}: [{1.status}] {2}".format(
                        url, r, await r.json()
                    )
                )
            return await r.json()

    def _make_token_auth(self, client_id: str, client_secret: str) -> Dict:
        auth_header = base64.b64encode((client_id + ":" + client_secret).encode("ascii"))
        return {"Authorization": "Basic %s" % auth_header.decode("ascii")}

    def _is_token_valid(self) -> bool:
        """Checks if the token is valid"""
        if not self._token:
            return False
        return self._token["expires_at"] - int(time.time()) > 60

    async def has_token(self) -> bool:
        """Attempt to get token and return True if successful."""
        if await self._get_token():
            return True
        return False

    async def _get_token(self) -> str:
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

    async def _request_token(self) -> Dict:
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

    async def _request_guest_token(self) -> Dict:
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
