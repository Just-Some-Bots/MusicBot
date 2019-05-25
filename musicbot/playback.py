from asyncio import Lock, CancelledError, run_coroutine_threadsafe, sleep, Future, ensure_future
from enum import Enum
from collections import defaultdict, deque
from typing import Union, Optional
from discord import FFmpegPCMAudio, PCMVolumeTransformer, AudioSource
from functools import partial
from .utils import callback_dummy_future
from itertools import islice
from datetime import timedelta
import traceback
import subprocess
import json
import os
from random import shuffle

from .lib.event_emitter import EventEmitter
from .constructs import Serializable, Serializer
from .exceptions import VersionError
import logging

log = logging.getLogger()

class Entry(Serializable):
    def __init__(self, source_url, title, duration, queuer_id, metadata, *, stream = False):
        self.source_url = source_url
        self.title = title
        self.duration = duration
        self.queuer_id = queuer_id
        self._aiolocks = defaultdict(Lock)
        self._preparing_cache = False
        self._cached = False
        self._cache_task = None # playlists set this
        self._metadata = metadata
        self._local_url = None
        self.stream = stream

    def __json__(self):
        return self._enclose_json({
            'version': 2,
            'source_url': self.source_url,
            'title': self.title,
            'duration': self.duration,
            'queuer_id': self.queuer_id,
            '_full_local_url': os.path.abspath(self._local_url) if self._local_url else self._local_url,
            'stream': self.stream,
            'meta': {
                name: obj for name, obj in self._metadata.items() if obj
            }
        })

    @classmethod
    def _deserialize(cls, data):

        if 'version' not in data or data['version'] < 2:
            raise VersionError('data version needs to be higher than 2')

        try:
            # TODO: version check
            source_url = data['source_url']
            title = data['title']
            duration = data['duration']
            queuer_id = data['queuer_id']
            _local_url = data['_full_local_url']
            stream = data['stream']
            meta = {}

            # TODO: Better [name] fallbacks
            if 'channel_id' in data['meta']:
                meta['channel_id'] = int(data['meta']['channel_id'])
                if not meta['channel_id']:
                    log.warning('Cannot find channel in an entry loaded from persistent queue. Chennel id: {}'.format(data['meta']['channel_id']))
                    meta.pop('channel_id')
            entry = cls(source_url, title, duration, queuer_id, meta, stream = stream)

            return entry
        except Exception as e:
            log.error("Could not load {}".format(cls.__name__), exc_info=e)

    async def is_preparing_cache(self):
        async with self._aiolocks['preparing_cache_set']:
            return self._preparing_cache

    async def is_cached(self):
        async with self._aiolocks['cached_set']:
            return self._cached

    async def prepare_cache(self):
        async with self._aiolocks['preparing_cache_set']:
            if self._preparing_cache:
                return
            self._preparing_cache = True

        async with self._aiolocks['preparing_cache_set']:
            async with self._aiolocks['cached_set']:
                self._preparing_cache = False
                self._cached = True

    def get_metadata(self):
        return self._metadata

    def get_duration(self):
        return timedelta(seconds=self.duration)

    async def set_local_url(self, local_url):
        self._local_url = local_url

class Playlist(EventEmitter, Serializable):
    def __init__(self, name, bot, *, persistent = False):
        super().__init__()
        self.karaoke_mode = False
        self._bot = bot
        self._name = name
        self._aiolocks = defaultdict(Lock)
        self._list = deque()
        self._precache = 1

    def __json__(self):
        return self._enclose_json({
            'version': 2,
            'name': self._name,
            'karaoke': self.karaoke_mode,
            'entries': list(self._list)
        })

    @classmethod
    def _deserialize(cls, data, bot=None):
        assert bot is not None, cls._bad('bot')

        if 'version' not in data or data['version'] < 2:
            raise VersionError('data version needs to be higher than 2')

        data_n = data.get('name')
        playlist = cls(data_n, bot)

        data_e = data.get('entries')
        if data_e:
            playlist._list.extend(data_e)
        data_k = data.get('karaoke')
        playlist.karaoke_mode = data_k

        return playlist

    async def __getitem__(self, item: Union[int, slice]):
        async with self._aiolocks['list']:
            if isinstance(item, slice):
                ret = list()
                for entry in self._list[item]:
                    ret = await entry.get_metadata()
                return ret
            else:
                return await self._list[item].get_metadata()

    async def stop(self):
        async with self._aiolocks['list']:
            for entry in self._list:
                if entry._cache_task:
                    entry._cache_task.cancel()
                    try:
                        await entry._cache_task
                    except:
                        pass
                    entry._cache_task = None
                    entry._preparing_cache = False
                    entry._cached = False

    async def shuffle(self):
        async with self._aiolocks['list']:
            shuffle(self._list)
            for entry in self._list[:self._precache]:
                if not entry._cache_task:
                    entry._cache_task = ensure_future(entry.prepare_cache())

    async def clear(self):
        async with self._aiolocks['list']:
            self._list.clear()

    def get_name(self):
        return self._name

    async def _get_entry(self):
        async with self._aiolocks['list']:
            if not self._list:
                return

            entry = self._list.popleft()
            if not entry._cache_task:
                entry._cache_task = ensure_future(entry.prepare_cache())

            if self._precache <= len(self._list):
                consider = self._list[self._precache - 1]
                if not consider:
                    consider._cache_task = ensure_future(consider.prepare_cache())

        return (entry, entry._cache_task)

    async def add_entry(self, entry, *, head = False):
        async with self._aiolocks['list']:
            if head:
                self._list.appendleft(entry)
                position = 0
            else:
                self._list.append(entry)
                position = len(self._list) - 1
            if self._precache > position:
                entry._cache_task = ensure_future(entry.prepare_cache())
            return position + 1

        self.emit('entry-added', playlist=self, entry=entry)

    async def get_length(self):
        async with self._aiolocks['list']:
            return len(self._list)

    async def remove_position(self, position):
        async with self._aiolocks['list']:
            if position < self._precache:
                self._list[position]._cache_task.cancel()
                self._list[position]._cache_task = None
                if self._precache <= len(self._list):
                    consider = self._list[self._precache - 1]
                    if not consider.cache_task:
                        consider.cache_task = ensure_future(consider.prepare_cache())
            val = self._list[position]
            del self._list[position]
            return val

    async def get_entry_position(self, entry):
        async with self._aiolocks['list']:
            return self._list.index(entry)

    async def estimate_time_until(self, position):
        async with self._aiolocks['list']:
            estimated_time = sum(e.duration for e in islice(self._list, position - 1))
        return timedelta(seconds=estimated_time)

    async def estimate_time_until_entry(self, entry):
        estimated_time = 0
        async with self._aiolocks['list']:
            for e in self._list:
                if e is not entry:  
                    estimated_time += e.duration
                else:
                    break
        return timedelta(seconds=estimated_time)            

    async def num_entry_of(self, user_id):
        async with self._aiolocks['list']:
            return sum(1 for e in self._list if e.queuer_id == user_id)

class PlayerState(Enum):
    PLAYING = 0
    PAUSE = 1
    DOWNLOADING = 2
    WAITING = 3


class SourcePlaybackCounter(AudioSource):
    def __init__(self, source, progress = 0):
        self._source = source
        self.progress = progress

    def read(self):
        res = self._source.read()
        if res:
            self.progress += 1
        return res

    def get_progress(self):
        return self.progress * 0.02

class Player(EventEmitter, Serializable):
    def __init__(self, guild, volume = 0.15):
        super().__init__()
        self._aiolocks = defaultdict(Lock)
        self._current = None
        self._playlist = None
        self._guild = guild
        self._player = None
        self._play_task = None
        self._play_safe_task = None
        self._source = None
        self._volume = volume
        self.state = PlayerState.PAUSE
        self.effects = list()

        ensure_future(self.play())

    def __json__(self):
        return self._enclose_json({
            'version': 2,
            'current_entry': {
                'entry': self._current,
                'progress': self._source.progress if self._source else None
            },
            'entries': self._playlist,
            'effects': self.effects
        })

    @classmethod
    def _deserialize(cls, data, guild=None):
        assert guild is not None, cls._bad('guild')

        if 'version' not in data or data['version'] < 2:
            raise VersionError('data version needs to be higher than 2')

        player = cls(guild)

        data_pl = data.get('entries')
        if data_pl:
            player._playlist = data_pl

        current_entry_data = data['current_entry']
        if current_entry_data['entry']:
            player._playlist._list.appendleft(current_entry_data['entry'])
            # TODO: progress stuff
            # how do I even do this
            # this would have to be in the entry class right?
            # some sort of progress indicator to skip ahead with ffmpeg (however that works, reading and ignoring frames?)
        if player._playlist:
            player._playlist.on('entry-added', player.on_playlist_entry_added)

        player.effects = data['effects']

        return player

    @classmethod
    def from_json(cls, raw_json, guild, bot, extractor):
        try:
            obj = json.loads(raw_json, object_hook=Serializer.deserialize)
            if isinstance(obj, dict):
                guild._bot.log.warning('Cannot parse incompatible player data. Instantiating new player instead.')
                guild._bot.log.debug(raw_json)
                obj = cls(guild)
            return obj
        except Exception as e:
            guild._bot.log.exception("Failed to deserialize player", e)

    async def on_playlist_entry_added(self, playlist, entry):
        self.emit('entry-added', player = self, playlist = playlist, entry = entry)

    @property
    def volume(self):
        return self._volume

    @volume.setter
    def volume(self, val):
        self._volume = val
        async def set_if_source():
            async with self._aiolocks['player']:
                if self._source:
                    self._source._source.volume = val
        ensure_future(set_if_source())

    async def status(self):
        async with self._aiolocks['player']:
            return self.state

    async def set_playlist(self, playlist: Optional[Playlist]):
        async with self._aiolocks['playlist']:
            if self._playlist:
                self._playlist.off('entry-added', self.on_playlist_entry_added)
            self._playlist = playlist.on('entry-added', self.on_playlist_entry_added)

    async def get_playlist(self):
        async with self._aiolocks['playlist']:
            return self._playlist

    async def _play(self, *, play_wait_cb = None, play_success_cb = None):
        async with self._aiolocks['player']:
            self.state = PlayerState.WAITING
            self._current = None
        entry = None
        while not entry:
            try:
                async with self._aiolocks['playlist']:
                    entry, cache = await self._playlist._get_entry()
                    async with self._aiolocks['player']:
                        self.state = PlayerState.DOWNLOADING
                        self._guild._bot.log.debug('got entry...')
                        self._guild._bot.log.debug(str(entry))
                        self._guild._bot.log.debug(str(cache))
                        self._current = entry
            except (TypeError, AttributeError):
                if play_wait_cb:
                    play_wait_cb()
                    play_wait_cb = None
                    play_success_cb = None
                await sleep(1)                 

        if play_success_cb:
            play_success_cb()

        def _playback_finished(error = None):
            async def _async_playback_finished():
                entry = self._current
                async with self._aiolocks['player']:
                    self._current = None
                    self._player = None
                    self._source = None

                if error:
                    self.emit('error', player=self, entry=entry, ex=error)

                if not self._guild._bot.config.save_videos and entry:
                    if not entry.stream:
                        if any([entry._local_url == e._local_url for e in self._playlist._list]):
                            self._guild._bot.log.debug("Skipping deletion of \"{}\", found song in queue".format(entry._local_url))

                        else:
                            self._guild._bot.log.debug("Deleting file: {}".format(os.path.relpath(entry._local_url)))
                            filename = entry._local_url
                            for x in range(30):
                                try:
                                    os.unlink(filename)
                                    self._guild._bot.log.debug('File deleted: {0}'.format(filename))
                                    break
                                except PermissionError as e:
                                    if e.winerror == 32:  # File is in use
                                        self._guild._bot.log.error('Can\'t delete file, it is currently in use: {0}').format(filename)
                                        break
                                except FileNotFoundError:
                                    self._guild._bot.log.debug('Could not find delete {} as it was not found. Skipping.'.format(filename), exc_info=True)
                                    break
                                except Exception:
                                    self._guild._bot.log.error("Error trying to delete {}".format(filename), exc_info=True)
                                    break
                            else:
                                print("[Config:SaveVideos] Could not delete file {}, giving up and moving on".format(
                                    os.path.relpath(filename)))

                self.emit('finished-playing', player=self, entry=entry)
                ensure_future(self._play())

            future = run_coroutine_threadsafe(_async_playback_finished(), self._guild._bot.loop)
            future.result()

        async def _download_and_play():
            try:
                self._guild._bot.log.debug('waiting for cache...')
                await cache
                self._guild._bot.log.debug('finish cache...')
            except:
                self._guild._bot.log.error('cannot cache...')
                self._guild._bot.log.error(traceback.format_exc())
                async with self._aiolocks['player']:
                    if self.state != PlayerState.PAUSE:
                        await self._play()                    

            boptions = "-nostdin"
            aoptions = "-vn"

            if self.effects:
                aoptions += " -af \"{}\"".format(', '.join(["{}{}".format(key, arg) for key, arg in self.effects]))

            self._guild._bot.log.debug("Creating player with options: {} {} {}".format(boptions, aoptions, entry._local_url))

            source = SourcePlaybackCounter(
                PCMVolumeTransformer(
                    FFmpegPCMAudio(
                        entry._local_url,
                        before_options=boptions,
                        options=aoptions,
                        stderr=subprocess.PIPE
                    ),
                    self._volume
                )
            )

            async with self._aiolocks['player']:
                self._player = self._guild._voice_client
                self._guild._voice_client.play(source, after=_playback_finished)
                self._source = source
                self.state = PlayerState.PLAYING

            self.emit('play', player=self, entry=self._current)
        
        async with self._aiolocks['playtask']:
            self._play_task = ensure_future(_download_and_play())            

        try:
            self._guild._bot.log.debug('waiting for task to play...')
            await self._play_task
        except CancelledError:
            async with self._aiolocks['player']:
                if self.state != PlayerState.PAUSE:
                    await self._play()

    async def _play_safe(self, *callback, play_wait_cb = None, play_success_cb = None):
        async with self._aiolocks['playsafe']:
            if not self._play_safe_task:
                self._play_safe_task = ensure_future(self._play(play_wait_cb = play_wait_cb, play_success_cb = play_success_cb))
                def clear_play_safe_task(future):
                    self._play_safe_task = None
                self._play_safe_task.add_done_callback(clear_play_safe_task)

                for cb in callback:
                    self._play_safe_task.add_done_callback(callback_dummy_future(cb))
            else:
                return

    async def play(self, *, play_fail_cb = None, play_success_cb = None, play_wait_cb = None):
        async with self._aiolocks['play']:
            async with self._aiolocks['player']:
                if self.state != PlayerState.PAUSE:
                    exc = Exception('player is not paused')
                    if play_fail_cb:
                        play_fail_cb(exc)
                    else:
                        raise exc
                    return

                if self._player:
                    self.state = PlayerState.PLAYING
                    self._player.resume()
                    if play_success_cb:
                        play_success_cb()
                    self.emit('resume', player=self, entry=self._current)
                    return

                await self._play_safe(play_wait_cb = play_wait_cb, play_success_cb = play_success_cb)

    async def _pause(self):
        async with self._aiolocks['player']:
            if self.state != PlayerState.PAUSE:
                if self._player:
                    self._player.pause()
                    self.state = PlayerState.PAUSE
                    self.emit('pause', player=self, entry=self._current)

    async def pause(self):
        async with self._aiolocks['pause']:
            async with self._aiolocks['player']:
                if self.state == PlayerState.PAUSE:
                    return

                elif self.state == PlayerState.PLAYING:
                    self._player.pause()
                    self.state = PlayerState.PAUSE
                    self.emit('pause', player=self, entry=self._current)
                    return

                elif self.state == PlayerState.DOWNLOADING:
                    async with self._aiolocks['playtask']:
                        self._play_task.add_done_callback(
                            callback_dummy_future(
                                partial(ensure_future, self._pause())
                            )
                        )
                    return

                elif self.state == PlayerState.WAITING:
                    self._play_safe_task.cancel()
                    self.state = PlayerState.PAUSE
                    self.emit('pause', player=self, entry=self._current)
                    return
        

    async def skip(self):
        async with self._aiolocks['skip']:
            async with self._aiolocks['player']:
                if self.state == PlayerState.PAUSE:
                    await self._play_safe(partial(ensure_future, self._pause()))
                    return

                elif self.state == PlayerState.PLAYING:
                    self._player.stop()
                    return

                elif self.state == PlayerState.DOWNLOADING:
                    async with self._aiolocks['playtask']:
                        self._play_task.cancel()
                    return

                elif self.state == PlayerState.WAITING:
                    raise Exception('nothing to skip!')
    
    async def kill(self):
        async with self._aiolocks['kill']:
            # TODO: destruct
            pass
        self.emit('stop', player=self)

    async def progress(self):
        async with self._aiolocks['player']:
            if self._source:
                return self._source.get_progress()
            else:
                raise Exception('not playing!')

    async def estimate_time_until(self, position):
        async with self._aiolocks['playlist']:
            future = None
            async with self._aiolocks['player']:
                if self.state == PlayerState.DOWNLOADING:
                    self._guild._bot.log.debug('scheduling estimate time after current entry is playing')
                    future = Future()
                    async def call_after_downloaded():
                        future.set_result(await self.estimate_time_until(position))
                    self._play_task.add_done_callback(
                        callback_dummy_future(
                            partial(ensure_future, call_after_downloaded())
                        )
                    )
                if self._current:
                    estimated_time = self._current.duration
                if self._source:
                    estimated_time -= self._source.get_progress()

            if future:
                estimated_time = await future

            estimated_time = timedelta(seconds=estimated_time)

            estimated_time += await self._playlist.estimate_time_until(position)
            return estimated_time

    async def estimate_time_until_entry(self, entry):
        async with self._aiolocks['playlist']:
            future = None
            async with self._aiolocks['player']:
                if self.state == PlayerState.DOWNLOADING:
                    self._guild._bot.log.debug('scheduling estimate time after current entry is playing')
                    future = Future()
                    async def call_after_downloaded():
                        future.set_result(await self.estimate_time_until_entry(entry))
                    self._play_task.add_done_callback(
                        callback_dummy_future(
                            partial(ensure_future, call_after_downloaded())
                        )
                    )
                if self._current is entry:
                    return 0
                if self._current:
                    estimated_time = self._current.duration
                    if self._source:
                        estimated_time -= self._source.get_progress()
                else:
                    estimated_time = 0

            if future:
                estimated_time = await future

            estimated_time = timedelta(seconds=estimated_time)
                
            estimated_time += await self._playlist.estimate_time_until_entry(entry)
            return estimated_time

    async def get_current_entry(self):
        async with self._aiolocks['player']:
            return self._current
