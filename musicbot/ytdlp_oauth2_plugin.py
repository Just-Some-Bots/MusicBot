"""
 ytdlp_oauth2_plugin contains code provided under an Unlicense license,
 based on the plugin found here:
   https://github.com/coletdjnz/yt-dlp-youtube-oauth2

 It is modified by MusicBot contributors to better integrate features.
 It may not contain all features or updates, and may break at any time.
 It will be replaced with the original plugin if it is installed.
"""

import datetime
import importlib
import inspect
import json
import logging
import pathlib
import time
import urllib.parse
import uuid
from typing import TYPE_CHECKING, Any, Dict, Tuple

import yt_dlp.networking  # type: ignore[import-untyped]
from yt_dlp.extractor.common import InfoExtractor  # type: ignore[import-untyped]
from yt_dlp.extractor.youtube import (  # type: ignore[import-untyped]
    YoutubeBaseInfoExtractor,
)
from yt_dlp.utils.traversal import traverse_obj  # type: ignore[import-untyped]

from . import write_path
from .constants import (
    DATA_FILE_YTDLP_OAUTH2,
    DEFAULT_DATA_DIR,
    DEFAULT_YTDLP_OAUTH2_SCOPES,
    DEFAULT_YTDLP_OAUTH2_TTL,
    YTDLP_OAUTH2_CLIENTS,
    YTDLP_OAUTH2_EXCLUDED_IES,
    YTDLP_OAUTH2_UNSUPPORTED_CLIENTS,
)

if TYPE_CHECKING:
    from .config import Config

TokenDict = Dict[str, Any]

log = logging.getLogger(__name__)


class YtdlpOAuth2Exception(Exception):
    pass


class YouTubeOAuth2Handler(InfoExtractor):  # type: ignore[misc]
    # pylint: disable=W0223
    _oauth2_token_path: pathlib.Path = write_path(DEFAULT_DATA_DIR).joinpath(
        DATA_FILE_YTDLP_OAUTH2
    )
    _client_token_data: TokenDict = {}
    _client_id: str = ""
    # I hate this, I am stupid and lazy. Future me/you, sorry and thanks ahead of time. :)
    _client_secret: str = ""
    _client_scopes: str = DEFAULT_YTDLP_OAUTH2_SCOPES

    @staticmethod
    def set_client_id(client_id: str) -> None:
        """
        Sets the shared, static client ID for use by OAuth2.
        """
        YouTubeOAuth2Handler._client_id = client_id

    @staticmethod
    def set_client_secret(client_secret: str) -> None:
        """
        Sets the shared, static client secret for use by OAuth2.
        """
        YouTubeOAuth2Handler._client_secret = client_secret

    def _save_token_data(self, token_data: TokenDict) -> None:
        """
        Handles saving token data as JSON to file system.
        """
        try:
            with open(self._oauth2_token_path, "w", encoding="utf8") as fh:
                json.dump(token_data, fh)
        except (OSError, TypeError) as e:
            log.error("Failed to save ytdlp oauth2 token data due to:  %s", e)

    def _load_token_data(self) -> TokenDict:
        """
        Handles loading token data as JSON from file system.
        """
        log.everything(  # type: ignore[attr-defined]
            "Loading YouTube TV OAuth2 token data."
        )
        d: TokenDict = {}
        if not self._oauth2_token_path.is_file():
            return d

        try:
            with open(self._oauth2_token_path, "r", encoding="utf8") as fh:
                d = json.load(fh)
        except (OSError, json.JSONDecodeError) as e:
            log.error("Failed to load ytdlp oauth2 token data due to:  %s", e)
        return d

    def store_token(self, token_data: TokenDict) -> None:
        """
        Saves token data to cache.
        """
        log.everything(  # type: ignore[attr-defined]
            "Storing YouTube TV OAuth2 token data"
        )
        self._save_token_data(token_data)
        self._client_token_data = token_data

    def get_token(self) -> TokenDict:
        """
        Returns token data from cache.
        """
        if not getattr(self, "_client_token_data", None):
            self._client_token_data = self._load_token_data()

        return self._client_token_data

    def validate_token_data(self, token_data: TokenDict) -> bool:
        """
        Validate required token data exists.
        """
        return all(
            key in token_data
            for key in ("access_token", "expires", "refresh_token", "token_type")
        )

    def initialize_oauth(self) -> TokenDict:
        """
        Validates existing OAuth2 data or triggers authorization flow.
        """
        token_data = self.get_token()

        if token_data and not self.validate_token_data(token_data):
            log.warning("Invalid cached OAuth2 token data.")
            token_data = {}

        if not token_data:
            token_data = self.authorize()
            self.store_token(token_data)

            if not token_data:
                raise YtdlpOAuth2Exception("Ytdlp OAuth2 failed to fetch token data.")

        if (
            token_data.get("expires", 0)
            < datetime.datetime.now(datetime.timezone.utc).timestamp() + 60
        ):
            log.everything(  # type: ignore[attr-defined]
                "Access token expired, refreshing"
            )
            token_data = self.refresh_token(token_data["refresh_token"])
            self.store_token(token_data)

        return token_data

    def handle_oauth(self, request: yt_dlp.networking.Request) -> None:
        """
        Fix up request to include proper OAuth2 data.
        """
        if not urllib.parse.urlparse(request.url).netloc.endswith("youtube.com"):
            return

        token_data = self.initialize_oauth()
        # These are only require for cookies and interfere with OAuth2
        request.headers.pop("X-Goog-PageId", None)
        request.headers.pop("X-Goog-AuthUser", None)
        # In case user tries to use cookies at the same time
        if "Authorization" in request.headers:
            log.warning(
                "YouTube cookies have been provided, but OAuth2 is being used. "
                "If you encounter problems, stop providing YouTube cookies to yt-dlp."
            )
            request.headers.pop("Authorization", None)
            request.headers.pop("X-Origin", None)

        # Not even used anymore, should be removed from core...
        request.headers.pop("X-Youtube-Identity-Token", None)

        authorization_header = {
            "Authorization": f'{token_data["token_type"]} {token_data["access_token"]}'
        }
        request.headers.update(authorization_header)

    def refresh_token(self, refresh_token: TokenDict) -> TokenDict:
        """
        Refresh authorization using refresh data or restarting auth flow.
        """
        log.info("Refreshing YouTube TV oauth2 token...")
        token_response = self._download_json(
            "https://www.youtube.com/o/oauth2/token",
            video_id="oauth2",
            note="Refreshing OAuth2 Token",
            data=json.dumps(
                {
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                }
            ).encode(),
            headers={"Content-Type": "application/json", "__youtube_oauth__": True},
        )
        error = traverse_obj(token_response, "error")
        if error:
            log.warning(
                "Failed to refresh OAuth2 access token due to:  %s\n"
                "Restarting authorization flow...",
                error,
            )
            return self.authorize()

        return {
            "access_token": token_response["access_token"],
            "expires": datetime.datetime.now(datetime.timezone.utc).timestamp()
            + token_response["expires_in"],
            "token_type": token_response["token_type"],
            "refresh_token": token_response.get("refresh_token", refresh_token),
        }

    def authorize(self) -> TokenDict:
        """
        Start authorization flow and loop until authorized or time-out.
        """
        log.everything("Starting oauth2 flow...")  # type: ignore[attr-defined]
        code_response = self._download_json(
            "https://www.youtube.com/o/oauth2/device/code",
            video_id="oauth2",
            note="Initializing OAuth2 Authorization Flow",
            data=json.dumps(
                {
                    "client_id": YouTubeOAuth2Handler._client_id,
                    "scope": YouTubeOAuth2Handler._client_scopes,
                    "device_id": uuid.uuid4().hex,
                    "device_model": "ytlr::",
                }
            ).encode(),
            headers={"Content-Type": "application/json", "__youtube_oauth__": True},
        )

        verification_url = code_response["verification_url"]
        user_code = code_response["user_code"]
        log.info(
            "\nNOTICE:\n"
            "To give yt-dlp access to your account, visit:\n  %s\n"
            "Then enter this authorization code:  %s\n"
            "You have %s seconds to complete authorization.\n",
            verification_url,
            user_code,
            DEFAULT_YTDLP_OAUTH2_TTL,
        )
        log.warning(
            "The application may hang until authorization time out if closed at this point. This is normal."
        )

        ttl = time.time() + DEFAULT_YTDLP_OAUTH2_TTL
        while True:
            if time.time() > ttl:
                log.error("Timed out while waiting for OAuth2 token.")
                raise YtdlpOAuth2Exception(
                    "OAuth2 is enabled but authorization was not given in time.\n"
                    "The owner must authorize YouTube before you can play from it."
                )

            token_response = self._download_json(
                "https://www.youtube.com/o/oauth2/token",
                video_id="oauth2",
                note=False,
                data=json.dumps(
                    {
                        "client_id": YouTubeOAuth2Handler._client_id,
                        "client_secret": YouTubeOAuth2Handler._client_secret,
                        "code": code_response["device_code"],
                        "grant_type": "http://oauth.net/grant_type/device/1.0",
                    }
                ).encode(),
                headers={"Content-Type": "application/json", "__youtube_oauth__": True},
            )

            error = traverse_obj(token_response, "error")
            if error:
                if error == "authorization_pending":
                    time.sleep(code_response["interval"])
                    continue
                if error == "expired_token":
                    log.warning(
                        "The device code has expired, restarting authorization flow for yt-dlp."
                    )
                    return self.authorize()
                raise YtdlpOAuth2Exception(f"Unhandled OAuth2 Error: {error}")

            log.everything(  # type: ignore[attr-defined]
                "Yt-dlp OAuth2 authorization successful."
            )
            return {
                "access_token": token_response["access_token"],
                "expires": datetime.datetime.now(datetime.timezone.utc).timestamp()
                + token_response["expires_in"],
                "refresh_token": token_response["refresh_token"],
                "token_type": token_response["token_type"],
            }


def enable_ytdlp_oauth2_plugin(config: "Config") -> None:
    """
    Controls addition of OAuth2 plugin to ytdlp.
    """
    YouTubeOAuth2Handler.set_client_id(config.ytdlp_oauth2_client_id)
    YouTubeOAuth2Handler.set_client_secret(config.ytdlp_oauth2_client_secret)

    # build a list of info extractors to be patched.
    youtube_extractors = filter(
        lambda m: issubclass(m[1], YoutubeBaseInfoExtractor)
        and m[0] not in YTDLP_OAUTH2_EXCLUDED_IES,
        inspect.getmembers(
            importlib.import_module("yt_dlp.extractor.youtube"), inspect.isclass
        ),
    )

    # patch each of the info extractors.
    for _, ie in youtube_extractors:
        log.everything(  # type: ignore[attr-defined]
            "Adding OAuth2 Plugin to Yt-dlp IE:  %s", ie
        )

        class _YouTubeOAuth(
            ie,  # type: ignore[valid-type, misc]
            YouTubeOAuth2Handler,
            plugin_name="oauth2",  # type: ignore[call-arg]
        ):
            # pylint: disable=W0223,C0103
            _DEFAULT_CLIENTS: Tuple[str]
            _NETRC_MACHINE = "youtube"
            _use_oauth2 = False

            def _perform_login(self, username: str, password: str) -> Any:
                if username == "mb_oauth2":
                    # Ensure clients are supported.
                    self._DEFAULT_CLIENTS = tuple(
                        c
                        for c in getattr(self, "_DEFAULT_CLIENTS", [])
                        if c not in YTDLP_OAUTH2_UNSUPPORTED_CLIENTS
                    ) + tuple(YTDLP_OAUTH2_CLIENTS)
                    log.everything(  # type: ignore[attr-defined]
                        "Default Yt-dlp Clients:  %s", self._DEFAULT_CLIENTS
                    )

                    self._use_oauth2 = True
                    self.initialize_oauth()
                    return None
                return super()._perform_login(username, password)

            def _create_request(self, *args, **kwargs):  # type: ignore[no-untyped-def]
                request = super()._create_request(*args, **kwargs)
                if "__youtube_oauth__" in request.headers:
                    request.headers.pop("__youtube_oauth__")
                elif self._use_oauth2:
                    self.handle_oauth(request)
                return request

            @property
            def is_authenticated(self) -> bool:
                """Validate oauth2 auth data or return super value."""
                if self._use_oauth2:
                    token_data = self.get_token()
                    if token_data and self.validate_token_data(token_data):
                        return True
                if super().is_authenticated:
                    return True
                return False
