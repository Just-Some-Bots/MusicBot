import aiohttp
import asyncio
import base64
import logging
import time

from .exceptions import SpotifyError

log = logging.getLogger(__name__)


def _make_token_auth(client_id, client_secret):
    auth_header = base64.b64encode(
        (client_id + ":" + client_secret).encode("ascii")
    )
    return {"Authorization": "Basic %s" % auth_header.decode("ascii")}


async def check_token(token):
    """Checks a token is valid"""
    now = int(time.time())
    return token["expires_at"] - now < 60


class Spotify:
    OAUTH_TOKEN_URL = "https://accounts.spotify.com/api/token"
    API_BASE = "https://api.spotify.com/v1/"

    def __init__(self, client_id, client_secret, aiosession=None, loop=None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.guest_mode = client_id is None or client_secret is None

        self.aiosession = aiosession if aiosession else aiohttp.ClientSession()
        self.loop = loop if loop else asyncio.get_event_loop()

        self.token = None

    async def get_track(self, uri):
        """Get a track's info from its URI"""
        return await self.make_spotify_req(self.API_BASE + "tracks/{0}".format(uri))

    async def get_album(self, uri):
        """Get an album's info from its URI"""
        return await self.make_spotify_req(self.API_BASE + "albums/{0}".format(uri))

    async def get_playlist(self, user, uri):
        """Get a playlist's info from its URI"""
        return await self.make_spotify_req(
            self.API_BASE + "users/{0}/playlists/{1}".format(user, uri)
        )

    async def get_playlist_tracks(self, uri):
        """Get a list of a playlist's tracks"""
        return await self.make_spotify_req(
            self.API_BASE + "playlists/{0}/tracks".format(uri)
        )

    async def make_spotify_req(self, url):
        """Proxy method for making a Spotify req using the correct Auth headers"""
        token = await self.get_token()
        return await self.make_get(
            url, headers={"Authorization": "Bearer {0}".format(token)}
        )

    async def make_get(self, url, headers=None):
        """Makes a GET request and returns the results"""
        async with self.aiosession.get(url, headers=headers) as r:
            if r.status != 200:
                raise SpotifyError(
                    "Issue making GET request to {0}: [{1.status}] {2}".format(
                        url, r, await r.json()
                    )
                )
            return await r.json()

    async def make_post(self, url, payload, headers=None):
        """Makes a POST request and returns the results"""
        async with self.aiosession.post(url, data=payload, headers=headers) as r:
            if r.status != 200:
                raise SpotifyError(
                    "Issue making POST request to {0}: [{1.status}] {2}".format(
                        url, r, await r.json()
                    )
                )
            return await r.json()

    async def get_token(self):
        """Gets the token or creates a new one if expired"""
        if self.token and not await check_token(self.token):
            return self.token["access_token"]

        if self.guest_mode:
            token = await self.request_guest_token()
            if token is None:
                raise SpotifyError(
                    "Failed to get a guest token from Spotify, please try specifying client id and client secret"
                )
            self.token = {
                "access_token": token["accessToken"],
                "expires_at": int(token["accessTokenExpirationTimestampMs"]) / 1000,
            }
        else:
            token = await self.request_token()
            if token is None:
                raise SpotifyError(
                    "Requested a token from Spotify, did not end up getting one"
                )
            token["expires_at"] = int(time.time()) + token["expires_in"]
            self.token = token
        log.debug(
            "Created a new {0}access token: {1}".format(
                "guest " if self.guest_mode else "", self.token
            )
        )
        return self.token["access_token"]

    async def request_token(self):
        """Obtains a token from Spotify and returns it"""
        payload = {"grant_type": "client_credentials"}
        headers = _make_token_auth(self.client_id, self.client_secret)
        r = await self.make_post(self.OAUTH_TOKEN_URL, payload=payload, headers=headers)
        return r

    async def request_guest_token(self):
        """Obtains a web player token from Spotify and returns it"""
        async with self.aiosession.get(
            "https://open.spotify.com/get_access_token?reason=transport&productType=web_player"
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
                        "Issue generating guest token: [{0.status}] {1}".format(r, e)
                    )
            return await r.json()
