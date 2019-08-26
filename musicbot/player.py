import os
import sys
import json
import logging
import asyncio
import audioop
import subprocess
import re

from discord import FFmpegPCMAudio, PCMVolumeTransformer, AudioSource

from enum import Enum
from array import array
from threading import Thread
from collections import deque
from shutil import get_terminal_size
from websockets.exceptions import InvalidState

from .utils import avg, _func_
from .lib.event_emitter import EventEmitter
from .constructs import Serializable, Serializer
from .exceptions import FFmpegError, FFmpegWarning
from .entry import URLPlaylistEntry, StreamPlaylistEntry

log = logging.getLogger(__name__)


class PatchedBuff:
    """
        PatchedBuff monkey patches a readable object, allowing you to vary what the volume is as the song is playing.
    """

    def __init__(self, buff, *, draw=False):
        self.buff = buff
        self.frame_count = 0
        self.volume = 1.0

        self.draw = draw
        self.use_audioop = True
        self.frame_skip = 2
        self.rmss = deque([2048], maxlen=90)

    def __del__(self):
        if self.draw:
            print(' ' * (get_terminal_size().columns-1), end='\r')

    def read(self, frame_size):
        self.frame_count += 1

        frame = self.buff.read(frame_size)

        if self.volume != 1:
            frame = self._frame_vol(frame, self.volume, maxv=2)

        if self.draw and not self.frame_count % self.frame_skip:
            # these should be processed for every frame, but "overhead"
            rms = audioop.rms(frame, 2)
            self.rmss.append(rms)

            max_rms = sorted(self.rmss)[-1]
            meter_text = 'avg rms: {:.2f}, max rms: {:.2f} '.format(avg(self.rmss), max_rms)
            self._pprint_meter(rms / max(1, max_rms), text=meter_text, shift=True)

        return frame

    def _frame_vol(self, frame, mult, *, maxv=2, use_audioop=True):
        if use_audioop:
            return audioop.mul(frame, 2, min(mult, maxv))
        else:
            # ffmpeg returns s16le pcm frames.
            frame_array = array('h', frame)

            for i in range(len(frame_array)):
                frame_array[i] = int(frame_array[i] * min(mult, min(1, maxv)))

            return frame_array.tobytes()

    def _pprint_meter(self, perc, *, char='#', text='', shift=True):
        tx, ty = get_terminal_size()

        if shift:
            outstr = text + "{}".format(char * (int((tx - len(text)) * perc) - 1))
        else:
            outstr = text + "{}".format(char * (int(tx * perc) - 1))[len(text):]

        print(outstr.ljust(tx - 1), end='\r')


class MusicPlayerState(Enum):
    STOPPED = 0  # When the player isn't playing anything
    PLAYING = 1  # The player is actively playing music.
    PAUSED = 2   # The player is paused on a song.
    WAITING = 3  # The player has finished its song but is still downloading the next one
    DEAD = 4     # The player has been killed.

    def __str__(self):
        return self.name

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

    def cleanup(self):
        self._source.cleanup()


class MusicPlayer(EventEmitter, Serializable):
    def __init__(self, bot, voice_client, playlist):
        super().__init__()
        self.bot = bot
        self.loop = bot.loop
        self.voice_client = voice_client
        self.playlist = playlist
        self.autoplaylist = None
        self.state = MusicPlayerState.STOPPED
        self.skip_state = None
        self.karaoke_mode = False

        self._volume = bot.config.default_volume
        self._play_lock = asyncio.Lock()
        self._current_player = None
        self._current_entry = None
        self._stderr_future = None

        self._source = None

        self.playlist.on('entry-added', self.on_entry_added)

    @property
    def volume(self):
        return self._volume

    @volume.setter
    def volume(self, value):
        self._volume = value
        if self._source:
            self._source._source.volume = value

    def on_entry_added(self, playlist, entry):
        if self.is_stopped:
            self.loop.call_later(2, self.play)

        self.emit('entry-added', player=self, playlist=playlist, entry=entry)

    def skip(self):
        self._kill_current_player()

    def stop(self):
        self.state = MusicPlayerState.STOPPED
        self._kill_current_player()

        self.emit('stop', player=self)

    def resume(self):
        if self.is_paused and self._current_player:
            self._current_player.resume()
            self.state = MusicPlayerState.PLAYING
            self.emit('resume', player=self, entry=self.current_entry)
            return

        if self.is_paused and not self._current_player:
            self.state = MusicPlayerState.PLAYING
            self._kill_current_player()
            return

        raise ValueError('Cannot resume playback from state %s' % self.state)

    def pause(self):
        if self.is_playing:
            self.state = MusicPlayerState.PAUSED

            if self._current_player:
                self._current_player.pause()

            self.emit('pause', player=self, entry=self.current_entry)
            return

        elif self.is_paused:
            return

        raise ValueError('Cannot pause a MusicPlayer in state %s' % self.state)

    def kill(self):
        self.state = MusicPlayerState.DEAD
        self.playlist.clear()
        self._events.clear()
        self._kill_current_player()

    def _playback_finished(self, error=None):
        entry = self._current_entry

        if self._current_player:
            self._current_player.after = None
            self._kill_current_player()

        self._current_entry = None
        self._source = None

        if self._stderr_future.done() and self._stderr_future.exception():
            # I'm not sure that this would ever not be done if it gets to this point
            # unless ffmpeg is doing something highly questionable
            self.emit('error', player=self, entry=entry, ex=self._stderr_future.exception())

        if not self.bot.config.save_videos and entry:
            if not isinstance(entry, StreamPlaylistEntry):
                if any([entry.filename == e.filename for e in self.playlist.entries]):
                    log.debug("Skipping deletion of \"{}\", found song in queue".format(entry.filename))

                else:
                    log.debug("Deleting file: {}".format(os.path.relpath(entry.filename)))
                    filename = entry.filename
                    for x in range(30):
                        try:
                            os.unlink(filename)
                            log.debug('File deleted: {0}'.format(filename))
                            break
                        except PermissionError as e:
                            if e.winerror == 32:  # File is in use
                                log.error('Can\'t delete file, it is currently in use: {0}'.format(filename))
                        except FileNotFoundError:
                            log.debug('Could not find delete {} as it was not found. Skipping.'.format(filename), exc_info=True)
                            break
                        except Exception:
                            log.error("Error trying to delete {}".format(filename), exc_info=True)
                            break
                    else:
                        print("[Config:SaveVideos] Could not delete file {}, giving up and moving on".format(
                            os.path.relpath(filename)))

        self.emit('finished-playing', player=self, entry=entry)

    def _kill_current_player(self):
        if self._current_player:
            if self.voice_client.is_paused():
                self.voice_client.resume()

            try:
                self.voice_client.stop()
            except OSError:
                pass
            self._current_player = None
            return True

        return False

    def play(self, _continue=False):
        self.loop.create_task(self._play(_continue=_continue))

    async def _play(self, _continue=False):
        """
            Plays the next entry from the playlist, or resumes playback of the current entry if paused.
        """
        if self.is_paused and self._current_player:
            return self.resume()

        if self.is_dead:
            return

        with await self._play_lock:
            if self.is_stopped or _continue:
                try:
                    entry = await self.playlist.get_next_entry()
                except:
                    log.warning("Failed to get entry, retrying", exc_info=True)
                    self.loop.call_later(0.1, self.play)
                    return

                # If nothing left to play, transition to the stopped state.
                if not entry:
                    self.stop()
                    return

                # In-case there was a player, kill it. RIP.
                self._kill_current_player()

                boptions = "-nostdin"
                # aoptions = "-vn -b:a 192k"
                if isinstance(entry, URLPlaylistEntry):
                    aoptions = entry.aoptions
                else:
                    aoptions = "-vn"

                log.ffmpeg("Creating player with options: {} {} {}".format(boptions, aoptions, entry.filename))

                self._source = SourcePlaybackCounter(
                    PCMVolumeTransformer(
                        FFmpegPCMAudio(
                            entry.filename,
                            before_options=boptions,
                            options=aoptions,
                            stderr=subprocess.PIPE
                        ),
                        self.volume
                    )
                )
                log.debug('Playing {0} using {1}'.format(self._source, self.voice_client))
                self.voice_client.play(self._source, after=self._playback_finished)

                self._current_player = self.voice_client

                # I need to add ytdl hooks
                self.state = MusicPlayerState.PLAYING
                self._current_entry = entry

                self._stderr_future = asyncio.Future()

                stderr_thread = Thread(
                    target=filter_stderr,
                    args=(self._source._source.original._process, self._stderr_future),
                    name="stderr reader"
                )

                stderr_thread.start()

                self.emit('play', player=self, entry=entry)

    def __json__(self):
        return self._enclose_json({
            'current_entry': {
                'entry': self.current_entry,
                'progress': self.progress,
                'progress_frames': self._current_player._player.loops if self.progress is not None else None
            },
            'entries': self.playlist
        })

    @classmethod
    def _deserialize(cls, data, bot=None, voice_client=None, playlist=None):
        assert bot is not None, cls._bad('bot')
        assert voice_client is not None, cls._bad('voice_client')
        assert playlist is not None, cls._bad('playlist')

        player = cls(bot, voice_client, playlist)

        data_pl = data.get('entries')
        if data_pl and data_pl.entries:
            player.playlist.entries = data_pl.entries

        current_entry_data = data['current_entry']
        if current_entry_data['entry']:
            player.playlist.entries.appendleft(current_entry_data['entry'])
            # TODO: progress stuff
            # how do I even do this
            # this would have to be in the entry class right?
            # some sort of progress indicator to skip ahead with ffmpeg (however that works, reading and ignoring frames?)

        return player

    @classmethod
    def from_json(cls, raw_json, bot, voice_client, playlist):
        try:
            return json.loads(raw_json, object_hook=Serializer.deserialize)
        except Exception as e:
            log.exception("Failed to deserialize player", e)


    @property
    def current_entry(self):
        return self._current_entry

    @property
    def is_playing(self):
        return self.state == MusicPlayerState.PLAYING

    @property
    def is_paused(self):
        return self.state == MusicPlayerState.PAUSED

    @property
    def is_stopped(self):
        return self.state == MusicPlayerState.STOPPED

    @property
    def is_dead(self):
        return self.state == MusicPlayerState.DEAD

    @property
    def progress(self):
        if self._source:
            return self._source.get_progress()
            # TODO: Properly implement this
            #       Correct calculation should be bytes_read/192k
            #       192k AKA sampleRate * (bitDepth / 8) * channelCount
            #       Change frame_count to bytes_read in the PatchedBuff

# TODO: I need to add a check for if the eventloop is closed

def filter_stderr(popen:subprocess.Popen, future:asyncio.Future):
    last_ex = None

    while True:
        data = popen.stderr.readline()
        if data:
            log.ffmpeg("Data from ffmpeg: {}".format(data))
            try:
                if check_stderr(data):
                    sys.stderr.buffer.write(data)
                    sys.stderr.buffer.flush()

            except FFmpegError as e:
                log.ffmpeg("Error from ffmpeg: %s", str(e).strip())
                last_ex = e

            except FFmpegWarning:
                pass # useless message
        else:
            break

    if last_ex:
        future.set_exception(last_ex)
    else:
        future.set_result(True)

def check_stderr(data:bytes):
    try:
        data = data.decode('utf8')
    except:
        log.ffmpeg("Unknown error decoding message from ffmpeg", exc_info=True)
        return True # fuck it

    # log.ffmpeg("Decoded data from ffmpeg: {}".format(data))

    # TODO: Regex
    warnings = [
        "Header missing",
        "Estimating duration from birate, this may be inaccurate",
        "Using AVStream.codec to pass codec parameters to muxers is deprecated, use AVStream.codecpar instead.",
        "Application provided invalid, non monotonically increasing dts to muxer in stream",
        "Last message repeated",
        "Failed to send close message",
        "decode_band_types: Input buffer exhausted before END element found"
    ]
    errors = [
        "Invalid data found when processing input", # need to regex this properly, its both a warning and an error
    ]

    if any(msg in data for msg in warnings):
        raise FFmpegWarning(data)

    if any(msg in data for msg in errors):
        raise FFmpegError(data)

    return True


# if redistributing ffmpeg is an issue, it can be downloaded from here:
#  - http://ffmpeg.zeranoe.com/builds/win32/static/ffmpeg-latest-win32-static.7z
#  - http://ffmpeg.zeranoe.com/builds/win64/static/ffmpeg-latest-win64-static.7z
#
# Extracting bin/ffmpeg.exe, bin/ffplay.exe, and bin/ffprobe.exe should be fine
# However, the files are in 7z format so meh
# I don't know if we can even do this for the user, at most we open it in the browser
# I can't imagine the user is so incompetent that they can't pull 3 files out of it...
# ...
# ...right?

# Get duration with ffprobe
#   ffprobe.exe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 -sexagesimal filename.mp3
# This is also how I fix the format checking issue for now
# ffprobe -v quiet -print_format json -show_format stream

# Normalization filter
# -af dynaudnorm
