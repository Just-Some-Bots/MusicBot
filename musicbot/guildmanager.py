from discord import Guild, Message, VoiceChannel, VoiceClient
from discord import utils as discordutils
from .messagemanager import safe_delete_message, safe_edit_message, safe_send_message
from .playlist import Playlist
from .player import MusicPlayer
from . import exceptions
from collections import defaultdict
import os
import asyncio
import logging
import pathlib

log = logging.getLogger(__name__)

# TODO: Do these properly (this todo is there before spliting the code)
_guild_data_defaults = {
    'last_np_msg': None,
    'auto_paused': False,
    'availability_paused': False
    }

_guild_dict = {}

class ManagedGuild:
    """
    ManagedGuild is an object that abstract the discord's Guild object.
    This class should not be instantiated manually.

    Parameters
    -----------
    client: MusicBot
        Client that will be use to manage the guild
    guild: discord.Guild
        Guild that you want to be managed
    """

    def __init__(self, client, guild: Guild):
        self._aiolocks = defaultdict(asyncio.Lock)
        self._client = client
        self._guildid = guild.id
        self._player_channel = None
        self._data = defaultdict(lambda: None, _guild_data_defaults)

    @property
    def _guild(self):
        return self._client.get_guild(self._guildid)

    def __str__(self):
        return self._guild.name

    def __repr__(self):
        return '<ManagedGuild guild={guild} client={client}>'.format(guild=repr(self._guild), client=repr(self._client))

    def get_owner(self, *, voice=False):
        return discordutils.find(
            lambda m: m.id == self._client.config.owner_id and (m.voice if voice else True),
            self._guild.members
        )

    async def handle_command(self, msg: Message):
        pass

    async def change_player_channel(self, channel: VoiceChannel):
        await self._player_channel.move_channel()

    async def get_voice_client(self, create=True):
        guild = self._guild
        if guild.voice_client:
            return guild.voice_client
        elif create:
            if self._player_channel:
                return await self._player_channel._vc.connect(timeout=60, reconnect=True)
            else:
                raise exceptions.MusicbotException("There is no voice channel associated with the bot in this guild")
        else:
            return

    async def disconnect_voice_client(self):
        if not self._player_channel:
            return

        await self._player_channel.disconnect_voice_client()

    async def update_now_playing_message(self, message, *, channel=None):
        lnp = self._data['last_np_msg']
        m = None

        if message is None and lnp:
            await safe_delete_message(lnp, quiet=True)

        elif lnp:  # If there was a previous lp message
            oldchannel = lnp.channel

            if lnp.channel == oldchannel:  # If we have a channel to update it in
                async for lmsg in lnp.channel.history(limit=1):
                    if lmsg != lnp and lnp:  # If we need to resend it
                        await safe_delete_message(lnp, quiet=True)
                        m = await safe_send_message(channel, message, quiet=True)
                    else:
                        m = await safe_edit_message(lnp, message, send_if_fail=True, quiet=False)

            elif channel: # If we have a new channel to send it to
                await safe_delete_message(lnp, quiet=True)
                m = await safe_send_message(channel, message, quiet=True)

            else:  # we just resend it in the old channel
                await safe_delete_message(lnp, quiet=True)
                m = await safe_send_message(oldchannel, message, quiet=True)

        elif channel: # No previous message
            m = await safe_send_message(channel, message, quiet=True)

        self._data['last_np_msg'] = m

    async def serialize_queue(self, *, dir=None):
        """
        Serialize the current queue for a server's player to json.
        """

        player = self._player_channel._player
        if not player:
            return

        if dir is None:
            dir = 'data/%s/queue.json' % self._guildid

        async with self._aiolocks['queue_serialization']:
            log.debug("Serializing queue for %s", self._guildid)

            with open(dir, 'w', encoding='utf8') as f:
                f.write(player.serialize(sort_keys=True))

    async def deserialize_queue(self, voice_client: VoiceClient, playlist=None, *, dir=None) -> MusicPlayer:
        """
        Deserialize a saved queue for a server into a MusicPlayer.  If no queue is saved, returns None.
        """

        if playlist is None:
            playlist = Playlist(self._client)

        if dir is None:
            dir = 'data/%s/queue.json' % self._guildid

        async with self._aiolocks['queue_serialization']:
            if not os.path.isfile(dir):
                return None

            log.debug("Deserializing queue for %s", self._guildid)

            with open(dir, 'r', encoding='utf8') as f:
                data = f.read()

        return MusicPlayer.from_json(data, self._client, voice_client, playlist)

    async def write_current_song(self, entry, *, dir=None):
        """
        Writes the current song to file
        """

        player = self._player_channel._player
        if not player:
            return

        if dir is None:
            dir = 'data/%s/current.txt' % self._guildid

        async with self._aiolocks['current_song']:
            log.debug("Writing current song for %s", self._guildid)

            with open(dir, 'w', encoding='utf8') as f:
                f.write(entry.title)

    def get_player_in(self):
        if self._player_channel:
            return self._player_channel._player

    async def on_guild_remove(self):

        log.info("Bot has been removed from guild: {}".format(self._guild.name))

        self._player_channel.kill_player()

        del _guild_dict[self._client][self._guildid]


    async def on_guild_available(self):

        guild = self._guild

        log.debug("Guild \"{}\" has become available.".format(guild.name))

        player = self._player_channel._player

        if player and player.is_paused:
            av_paused = self._data['availability_paused']

            if av_paused:
                log.debug("Resuming player in \"{}\" due to availability.".format(guild.name))
                self._data['availability_paused'] = False
                player.resume()


    async def on_guild_unavailable(self):
        
        guild = self._guild

        log.debug("Guild \"{}\" has become unavailable.".format(guild.name))

        player = self._player_channel._player

        if player and player.is_playing:
            log.debug("Pausing player in \"{}\" due to unavailability.".format(guild.name))
            self._data['availability_paused'] = True
            player.pause()

def registerguildmanage(client):
    _guild_dict[client.user.id] = {guild.id:ManagedGuild(client, guild) for guild in client.guilds}

def getguildlist(client) -> list:
    return list(_guild_dict[client.user.id].values())

def get_guild(client, guild: Guild) -> ManagedGuild:
    return _guild_dict[client.user.id][guild.id]

def prunenoowner(client) -> int:
    unavailable_servers = 0
    for server in getguildlist(client):
        if server._guild.unavailable:
            unavailable_servers += 1
        elif server.get_owner() == None:
            server._guild.leave()
            log.info('Left {} due to bot owner not found'.format(server._guild.name))
    return unavailable_servers

def add_guild(client, guild: Guild):
    _guild_dict[client.user.id][guild.id] = ManagedGuild(client, guild)
