import os
import sys
import time
import shlex
import shutil
import random
import inspect
import logging
import asyncio
import pathlib
import traceback

import aiohttp
import discord
import colorlog

from io import BytesIO, StringIO
from functools import wraps
from textwrap import dedent
from datetime import timedelta
from collections import defaultdict

from discord.enums import ChannelType
from discord.ext.commands.bot import _get_variable

from . import exceptions
from . import downloader

from .playlist import Playlist
from .player import MusicPlayer
from .entry import StreamPlaylistEntry
from .opus_loader import load_opus_lib
from .config import Config, ConfigDefaults
from .permissions import Permissions, PermissionsDefaults
from .constructs import SkipState, Response, VoiceStateUpdate
from .utils import load_file, write_file, sane_round_int, fixg, ftimedelta, _func_

from .constants import VERSION as BOTVERSION
from .constants import DISCORD_MSG_CHAR_LIMIT, AUDIO_CACHE_PATH

# List of custom command
# Should be in a form of method with a start of 'cmd_' + {Command Name}
# This list of method will be bound to bot object, thats why they need self param
  
async def cmd_apakah(self, user_mentions, leftover_args):
    """
    Usage:
        {command_prefix}apakah [your query]

    Let kak seto tell his opinion about your question, better prophet than kerang ajaib
    This command will only answer with 'ya' or 'tidak'.
    """
    standardize_user = [user.name for user in user_mentions]

    randomize = random.seed(hash(' '.join(leftover_args + standardize_user)))
    seed = random.random()
    if  seed > 0.5:
        result = 'ya'
    else:
        result = 'tidak'
    return Response(result, reply=True, tts=True)

async def cmd_sleding(self, author, user_mentions):
    """
    Usage:
        {command_prefix}sleding [target...]

    Let kak seto do the sleding, because f*ck your friend
    You should use mention also when executing this command so you won't get sleding-ed
    """
    if user_mentions:
        anak2bgst = [user.mention for user in user_mentions]
        return Response('SAYA SLEDING KEPALA KAMU %s' % ', '.join(anak2bgst), tts=True)
    else:
        return Response('SAYA SLEDING KEPALA KAMU %s' % author.mention, tts=True)

async def cmd_yoi(self, author, leftover_args):
    """
    Usage:
        {command_prefix}yoi [times...]

    Let kak seto tell yoi.
    Set number of times to amplify the memes metre, but please not too many or kak seto will mad at you
    """
    try:
        times = int(leftover_args)
    except:
        return Response('Bgst kamu %s, kasi angka yang bener' % author.mention, tts=True)

    if times < 1:
        return Response('Bgst kamu %s, input harus positif' % author.mention, tts=True)
    elif times > 10:
        return Response('Bgst kamu %s, kebanyakan gblk' % author.mention, tts=True)
    else:
        yoi_str = "yo" * times + "i"
        Response(yoi_str, tts=True)
   