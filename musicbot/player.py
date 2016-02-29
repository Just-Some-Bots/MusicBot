import os
import time
import asyncio
import traceback

from array import array
from enum import Enum

from .lib.event_emitter import EventEmitter


class PatchedBuff:
    """
        PatchedBuff monkey patches a readable object, allowing you to vary what the volume is as the song is playing.
    """

    def __init__(self, player, buff):
        self.player = player
        self.buff = buff
        self.frame_count = 0

    def read(self, frame_size):
        self.frame_count += 1
        frame = self.buff.read(frame_size)

        volume = self.player.volume
        # Only make volume go down. Never up.
        if volume < 1.0:
            # Ffmpeg returns s16le pcm frames.
            frame_array = array('h', frame)

            for i in range(len(frame_array)):
                frame_array[i] = int(frame_array[i] * volume)

            frame = frame_array.tobytes()

        return frame


class MusicPlayerState(Enum):
    STOPPED = 0  # When the player isn't playing anything
    PLAYING = 1  # The player is actively playing music.
    PAUSED = 2  # The player is paused on a song.

    def __str__(self):
        return self.name


class MusicPlayer(EventEmitter):
    def __init__(self, bot, voice_client, playlist):
        super().__init__()
        self.bot = bot
        self.loop = bot.loop
        self.voice_client = voice_client
        self.playlist = playlist
        self.playlist.on('entry-added', self.on_entry_added)
        self.volume = bot.config.default_volume

        self._play_lock = asyncio.Lock()
        self._current_player = None
        self._current_entry = None
        self.state = MusicPlayerState.STOPPED


    def on_entry_added(self, playlist, entry):
        if self.is_stopped:
            self.loop.call_later(2, self.play)

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

    def _playback_finished(self):
        entry = self._current_entry
        self._current_entry = None
        self._current_player = None

        if not self.is_stopped:
            self.play(_continue=True)

        if not self.bot.config.save_videos and entry:
            if any([entry.filename == e.filename for e in self.playlist.entries]):
                print("[Config:SaveVideos] Skipping deletion, found song in queue")

            else:
                # print("[Config:SaveVideos] Deleting file: %s" % os.path.relpath(entry.filename))
                asyncio.ensure_future(self._delete_file(entry.filename))

        self.emit('finished-playing', player=self, entry=entry)

    def _kill_current_player(self):
        if self._current_player:
            if self.player.is_paused:
                self.resume()

            self._current_player.stop()
            self._current_player = None
            return True

        return False

    async def _delete_file(self, filename):
        for x in range(30):
            try:
                os.unlink(filename)
                break
            except PermissionError as e:
                if e.winerror == 32: # File is in use
                    await asyncio.sleep(0.25)
            except Exception as e:
                traceback.print_exc()
                print("Error trying to delete " + filename)
                break
        else:
            print("[Config:SaveVideos] Could not delete file {}, giving up and moving on".format(
                os.path.relpath(filename)))

    def play(self, _continue=False):
        self.loop.create_task(self._play(_continue=_continue))

    async def _play(self, _continue=False):
        """
            Plays the next entry from the playlist, or resumes playback of the current entry if paused.
        """
        if self.is_paused:
            return self.resume()

        with await self._play_lock:
            if self.is_stopped or _continue:
                try:
                    entry = await self.playlist.get_next_entry()

                except Exception as e:
                    print("Failed to get entry.")
                    traceback.print_exc()
                    # Retry playing the next entry in a sec.
                    self.loop.call_later(0.1, self.play)
                    return

                # If nothing left to play, transition to the stopped state.
                if not entry:
                    self.stop()
                    return

                # In-case there was a player, kill it. RIP.
                self._kill_current_player()

                self._current_player = self._monkeypatch_player(self.voice_client.create_ffmpeg_player(
                    entry.filename,
                    # Threadsafe call soon, b/c after will be called from the voice playback thread.
                    after=lambda: self.loop.call_soon_threadsafe(self._playback_finished)
                ))

                # I need to add ytdl hooks and set a DOWNLOADING state
                self.state = MusicPlayerState.PLAYING
                self._current_entry = entry

                self._current_player.start()
                self.emit('play', player=self, entry=entry)

    def _monkeypatch_player(self, player):
        original_buff = player.buff
        player.buff = PatchedBuff(self, original_buff)
        return player

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
    def progress(self):
        return round(self._current_player.buff.frame_count * 0.02)
        # TODO: Properly implement this
        #       Correct calculation should be bytes_read/192k
        #       192k AKA sampleRate * (bitDepth / 8) * channelCount
        #       Change frame_count to bytes_read in the PatchedBuff


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
