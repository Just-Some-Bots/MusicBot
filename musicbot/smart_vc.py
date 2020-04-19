from discord import VoiceChannel, VoiceClient, AudioSource
from threading import RLock
from collections import defaultdict
from typing import Optional, DefaultDict, Callable, Any

from . import exceptions

def _check_perm_connect(self, voice_channel: VoiceChannel):
    perms = voice_channel.permissions_for(voice_channel.guild.me)
    if not perms.connect:
        raise exceptions.VoiceConnectionError('Cannot join channel, no permission to connect.')
    elif not perms.speak:
        raise exceptions.VoiceConnectionError('Cannot join channel, no permission to speak.')

class SmartVC:
    _lock: DefaultDict[str, RLock] = defaultdict(RLock)
    _connected_voice: Optional[VoiceChannel] = None
    _connected_client: Optional[VoiceClient] = None

    def __bool__(self):
        with self._lock['change_voice']:
            return bool(self._connected_voice)

    def voice_channel(self):
        with self._lock['change_voice']:
            return self._connected_voice

    def voice_client(self):
        with self._lock['change_voice']:
            return self._connected_client

    async def _move_channel(self, new_channel: VoiceChannel):
        if self._connected_voice == new_channel:
            raise exceptions.VoiceConnectionError('Already connected to the voice channel.')
        self._check_perm_connect(new_channel)
        await self._connected_client.move_to(new_channel)
        self._connected_voice = new_channel

    async def _disconnect_channel(self):
        if not self._connected_voice:
            raise exceptions.VoiceConnectionError('Already disconnected from the voice channel.')
        await self._connected_client.disconnect()
        self._connected_voice = None
        self._connected_client = None

    async def _connect_channel(self, new_channel: VoiceChannel):
        self._check_perm_connect(new_channel)
        self._connected_client = await new_channel.connect()
        self._connected_voice = new_channel

    async def set_voice_channel(self, voice_channel: VoiceChannel):
        with self._lock['change_voice']:
            if voice_channel:
                if self._connected_voice:
                    await self._move_channel(voice_channel)
                else:
                    await self._connect_channel(voice_channel)
            else:
                await self._disconnect_channel()

    def pause(self):
        with self._lock['change_voice']:
            if not self:
                raise exceptions.VoiceConnectionError('Disconnected from the voice channel.')
            self._connected_client.pause()

    def resume(self):
        with self._lock['change_voice']:
            if not self:
                raise exceptions.VoiceConnectionError('Disconnected from the voice channel.')
            self._connected_client.resume()

    def stop(self):
        with self._lock['change_voice']:
            if not self:
                raise exceptions.VoiceConnectionError('Disconnected from the voice channel.')
            self._connected_client.stop()

    def play(self, source: AudioSource, *, after: Optional[Callable[[Exception], Any]] = None):
        with self._lock['change_voice']:
            if not self:
                raise exceptions.VoiceConnectionError('Disconnected from the voice channel.')
            self._connected_client.play(source, after = after)