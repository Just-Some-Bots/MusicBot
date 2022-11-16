"""
Discord API Wrapper
~~~~~~~~~~~~~~~~~~~

A basic wrapper for the Discord API.

:copyright: (c) 2015-2021 Rapptz & (c) 2021-present Pycord Development
:license: MIT, see LICENSE for more details.
"""

__title__ = "pycord"
__author__ = "Pycord Development"
__license__ = "MIT"
__copyright__ = "Copyright 2015-2021 Rapptz & Copyright 2021-present Pycord Development"
__version__ = "2.2.2"

__path__ = __import__("pkgutil").extend_path(__path__, __name__)

import logging
from typing import Literal, NamedTuple

from . import abc, opus, sinks, ui, utils
from .activity import *
from .appinfo import *
from .asset import *
from .audit_logs import *
from .automod import *
from .bot import *
from .channel import *
from .client import *
from .cog import *
from .colour import *
from .commands import *
from .components import *
from .embeds import *
from .emoji import *
from .enums import *
from .errors import *
from .file import *
from .flags import *
from .guild import *
from .http import *
from .integrations import *
from .interactions import *
from .invite import *
from .member import *
from .mentions import *
from .message import *
from .object import *
from .partial_emoji import *
from .permissions import *
from .player import *
from .raw_models import *
from .reaction import *
from .role import *
from .scheduled_events import *
from .shard import *
from .stage_instance import *
from .sticker import *
from .team import *
from .template import *
from .threads import *
from .user import *
from .voice_client import *
from .webhook import *
from .welcome_screen import *
from .widget import *


class VersionInfo(NamedTuple):
    major: int
    minor: int
    micro: int
    releaselevel: Literal["alpha", "beta", "candidate", "final"]
    serial: int


version_info: VersionInfo = VersionInfo(
    major=2, minor=2, micro=2, releaselevel="final", serial=0
)

logging.getLogger(__name__).addHandler(logging.NullHandler())
