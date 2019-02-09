from discord import Guild, Message, VoiceChannel, VoiceClient
from .messagemanager import safe_delete_message, safe_edit_message, safe_send_message
from .playlist import Playlist
from .player import MusicPlayer
from .bot import MusicBot
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

class ManagedGuild:
    """
    ManagedGuild is an object that abstract the discord's Guild object.

    Parameters
    -----------
    client: MusicBot
        Client that will be use to manage the guild
    guild: discord.Guild
        Guild that you want to be managed
    """

    def __init__(self, client: MusicBot, guild: Guild):
        self._aiolocks = defaultdict(asyncio.Lock)
        self._client = client
        self._guild = guild
        self._player_channel = None
        self._data = defaultdict(lambda: None, _guild_data_defaults)

    async def handle_command(self, msg: Message):
        pass

    async def change_player_channel(self, channel: VoiceChannel):
        pass

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

        guild = self._guild

        player = self._player_channel._player
        if not player:
            return

        if dir is None:
            dir = 'data/%s/queue.json' % guild.id

        async with self._aiolocks['queue_serialization']:
            log.debug("Serializing queue for %s", guild.id)

            with open(dir, 'w', encoding='utf8') as f:
                f.write(player.serialize(sort_keys=True))

    async def deserialize_queue(self, voice_client: VoiceClient, playlist=None, *, dir=None) -> MusicPlayer:
        """
        Deserialize a saved queue for a server into a MusicPlayer.  If no queue is saved, returns None.
        """

        guild = self._guild

        if playlist is None:
            playlist = Playlist(self)

        if dir is None:
            dir = 'data/%s/queue.json' % guild.id

        async with self._aiolocks['queue_serialization']:
            if not os.path.isfile(dir):
                return None

            log.debug("Deserializing queue for %s", guild.id)

            with open(dir, 'r', encoding='utf8') as f:
                data = f.read()

        return MusicPlayer.from_json(data, self, voice_client, playlist)

    async def write_current_song(self, entry, *, dir=None):
        """
        Writes the current song to file
        """

        guild = self._guild

        player = self._player_channel._player
        if not player:
            return

        if dir is None:
            dir = 'data/%s/current.txt' % guild.id

        async with self._aiolocks['current_song']:
            log.debug("Writing current song for %s", guild.id)

            with open(dir, 'w', encoding='utf8') as f:
                f.write(entry.title)

    # @TheerapakG TODO: rw
    async def on_guild_update(self, before:Guild, after:Guild):
        if before.region != after.region:
            log.warning("Guild \"%s\" changed regions: %s -> %s" % (after.name, before.region, after.region))

    async def on_guild_join(self):

        guild = self._guild

        log.info("Bot has been added to guild: {}".format(guild.name))
        owner = self._client.get_owner(voice=True) or self._client.get_owner()
        if self._client.config.leavenonowners:
            check = guild.get_member(owner.id)
            if check == None:
                await guild.leave()
                log.info('Left {} due to bot owner not found.'.format(guild.name))
                await owner.send(self._client.str.get('left-no-owner-guilds', 'Left `{}` due to bot owner not being found in it.'.format(guild.name)))

        log.debug("Creating data folder for guild %s", guild.id)
        pathlib.Path('data/%s/' % guild.id).mkdir(exist_ok=True)

    async def on_guild_remove(self):

        guild = self._guild

        log.info("Bot has been removed from guild: {}".format(guild.name))

        self._player_channel.kill_player()


    async def on_guild_available(self):

        guild = self._guild

        if not self._client.init_ok:
            return # Ignore pre-ready events

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

