""" Load environment variables into a dict
"""

import warnings
from typing import Dict, List, Optional, Union


from pydantic import BaseSettings, SecretStr

class MusicBotSettings(BaseSettings):

    discord_token: Optional[SecretStr] = None
    spotify_client_id: Optional[str] = None
    spotify_client_secret: Optional[SecretStr] = None
    bind_to_channels: Optional[List[str]] = None

    # {user_group: "xxxxxxxxx yyyyyyyy"}
    authorized_user_dict: Optional[Dict[str,Union[None,str]]] = None
    class Config:
        env_prefix = "MUSICBOT_"
        case_sensitive = False
        secrets_dir = "musicbot/.secrets/"

def get_env_settings():
    """ Cleans up settings
    """

    # Catch warnings when working locally and ./secrets does not exist
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        settings = MusicBotSettings().dict()

    if settings["bind_to_channels"]:
        settings["bind_to_channels"] = set(settings["bind_to_channels"])
    else:
        settings["bind_to_channels"] = set()

    if not settings["authorized_user_dict"]:
        settings["authorized_user_dict"] = {}

    return settings