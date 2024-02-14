import asyncio
import io
import json
import logging
import os
import sys
from enum import Enum
from threading import Thread
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from discord import AudioSource, FFmpegPCMAudio, PCMVolumeTransformer, VoiceClient

from .constructs import Serializable, Serializer, SkipState
from .entry import StreamPlaylistEntry, URLPlaylistEntry
from .exceptions import FFmpegError, FFmpegWarning
from .lib.event_emitter import EventEmitter

if TYPE_CHECKING:
    from .bot import MusicBot
    from .playlist import Playlist

    AsyncFuture = asyncio.Future[Any]
else:
    AsyncFuture = asyncio.Future

# Type alias
EntryTypes = Union[URLPlaylistEntry, StreamPlaylistEntry]

log = logging.getLogger(__name__)


class MusicPlayerState(Enum):
    STOPPED = 0  # When the player isn't playing anything
    PLAYING = 1  # The player is actively playing music.
    PAUSED = 2  # The player is paused on a song.
    WAITING = (
        3  # The player has finished its song but is still downloading the next one
    )
    DEAD = 4  # The player has been killed.

    def __str__(self) -> str:
        return self.name


class SourcePlaybackCounter(AudioSource):
    def __init__(
        self,
        source: PCMVolumeTransformer[FFmpegPCMAudio],
        progress: int = 0,
    ) -> None:
        """
        Manage playback source and attempt to count progress frames used
        to measure playback progress.
        """
        self._source = source
        self.progress = progress

    def read(self) -> bytes:
        res = self._source.read()
        if res:
            self.progress += 1
        return res

    def get_progress(self) -> float:
        """Get an approximate playback progress."""
        return self.progress * 0.02

    def cleanup(self) -> None:
        self._source.cleanup()


class MusicPlayer(EventEmitter, Serializable):
    def __init__(
        self,
        bot: "MusicBot",
        voice_client: VoiceClient,
        playlist: "Playlist",
    ):
        """
        Manage a MusicPlayer with all its bits and bolts.

        :param: bot:  A MusicBot discord client instance.
        :param: voice_client:  a discord.VoiceClient object used for playback.
        :param: playlist:  a collection of playable entries to be played.
        """
        super().__init__()
        self.bot: "MusicBot" = bot
        self.loop: asyncio.AbstractEventLoop = bot.loop
        self.loopqueue: bool = False
        self.repeatsong: bool = False
        self.voice_client: VoiceClient = voice_client
        self.playlist: "Playlist" = playlist
        self.autoplaylist: List[str] = []
        self.state: MusicPlayerState = MusicPlayerState.STOPPED
        self.skip_state: SkipState = SkipState()
        self.karaoke_mode: bool = False

        self._volume = bot.config.default_volume
        self._play_lock = asyncio.Lock()
        self._current_player: Optional[VoiceClient] = None
        self._current_entry: Optional[EntryTypes] = None
        self._stderr_future: Optional[AsyncFuture] = None

        self._source: Optional[SourcePlaybackCounter] = None

        self.playlist.on("entry-added", self.on_entry_added)
        self.playlist.on("entry-failed", self.on_entry_failed)

    @property
    def volume(self) -> float:
        """Get the volume level as last set by config or command."""
        return self._volume

    @volume.setter
    def volume(self, value: float) -> None:
        """
        Set volume to the given `value` and immediately apply it to any
        active playback source.
        """
        self._volume = value
        if self._source:
            self._source._source.volume = value

    def on_entry_added(
        self, playlist: "Playlist", entry: EntryTypes, defer_serialize: bool = False
    ) -> None:
        """
        Event dispatched by Playlist when an entry is added to the queue.
        """
        if self.is_stopped:
            log.noise("calling-later, self.play from player.")  # type: ignore[attr-defined]
            self.loop.call_later(2, self.play)

        self.emit(
            "entry-added",
            player=self,
            playlist=playlist,
            entry=entry,
            defer_serialize=defer_serialize,
        )

    def on_entry_failed(self, entry: EntryTypes, error: Exception) -> None:
        """
        Event dispatched by Playlist when an entry failed to ready or play.
        """
        self.emit("error", player=self, entry=entry, ex=error)

    def skip(self) -> None:
        """Skip the current playing entry but just killing playback."""
        self._kill_current_player()

    def stop(self) -> None:
        """
        Immediately halt playback, killing current player source, setting
        state to stopped and emitting an event.
        """
        self.state = MusicPlayerState.STOPPED
        self._kill_current_player()

        self.emit("stop", player=self)

    def resume(self) -> None:
        """
        Resume the player audio playback if it was paused and we have a
        VoiceClient playback source.
        If MusicPlayer was paused but the VoiceClient player is missing,
        do something odd and set state to playing but kill the player...
        """
        if self.is_paused and self._current_player:
            self._current_player.resume()
            self.state = MusicPlayerState.PLAYING
            self.emit("resume", player=self, entry=self.current_entry)
            return

        if self.is_paused and not self._current_player:
            self.state = MusicPlayerState.PLAYING
            self._kill_current_player()
            return

        raise ValueError(f"Cannot resume playback from state {self.state}")

    def pause(self) -> None:
        """
        Suspend player audio playback and emit an event, if the player was playing.
        """
        if self.is_playing:
            self.state = MusicPlayerState.PAUSED

            if self._current_player:
                self._current_player.pause()

            self.emit("pause", player=self, entry=self.current_entry)
            return

        if self.is_paused:
            return

        raise ValueError(f"Cannot pause a MusicPlayer in state {self.state}")

    def kill(self) -> None:
        """
        Set the state of the bot to Dead, clear all events and playlists,
        then kill the current VoiceClient source player.
        """
        self.state = MusicPlayerState.DEAD
        self.playlist.clear()
        self._events.clear()
        self._kill_current_player()

    def _playback_finished(self, error: Optional[Exception] = None) -> None:
        """
        Event fired by discord.VoiceClient after playback has finished
        or when playback stops due to an error.
        This function is responsible tidying the queue post-playback,
        propagating player error or finished-playing events, and
        triggering the media file cleanup task.

        :param: error:  An exception, if any, raised by playback.
        """
        entry = self._current_entry
        if entry is None:
            log.debug("Playback finished, but _current_entry is None.")
            return

        if self.repeatsong:
            self.playlist.entries.appendleft(entry)
        elif self.loopqueue:
            self.playlist.entries.append(entry)

        if self._current_player:
            if hasattr(self._current_player, "after"):
                self._current_player.after = None
            self._kill_current_player()

        self._current_entry = None
        self._source = None

        if error:
            self.stop()
            self.emit("error", player=self, entry=entry, ex=error)
            return

        if (
            isinstance(self._stderr_future, asyncio.Future)
            and self._stderr_future.done()
            and self._stderr_future.exception()
        ):
            # I'm not sure that this would ever not be done if it gets to this point
            # unless ffmpeg is doing something highly questionable
            self.stop()
            self.emit(
                "error", player=self, entry=entry, ex=self._stderr_future.exception()
            )
            return

        if not self.bot.config.save_videos and entry:
            self.loop.create_task(self._handle_file_cleanup(entry))

        self.emit("finished-playing", player=self, entry=entry)

    def _kill_current_player(self) -> bool:
        """
        If there is a current player source, attempt to stop it, then
        say "Garbage day!" and set it to None anyway.
        """
        if self._current_player:
            try:
                self._current_player.stop()
            except OSError:
                log.noise(  # type: ignore[attr-defined]
                    "Possible Warning from kill_current_player()", exc_info=True
                )

            self._current_player = None
            return True

        return False

    def play(self, _continue: bool = False) -> None:
        """
        Immediately try to gracefully play the next entry in the queue.
        If there is already an entry, but player is paused, playback will
        resume instead of playing a new entry.
        If the player is dead, this will silently return.

        :param: _continue:  Force a player that is not dead or stopped to
            start a new playback source anyway.
        """
        self.loop.create_task(self._play(_continue=_continue))

    async def _play(self, _continue: bool = False) -> None:
        """
        Plays the next entry from the playlist, or resumes playback of the current entry if paused.
        """
        if self.is_paused and self._current_player:
            return self.resume()

        if self.is_dead:
            return

        async with self._play_lock:
            if self.is_stopped or _continue:
                try:
                    entry = await self.playlist.get_next_entry()
                except IndexError:
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

                log.ffmpeg(  # type: ignore[attr-defined]
                    "Creating player with options: %s %s %s",
                    boptions,
                    aoptions,
                    entry.filename,
                )

                stderr_io = io.BytesIO()

                self._source = SourcePlaybackCounter(
                    PCMVolumeTransformer(
                        FFmpegPCMAudio(
                            entry.filename,
                            before_options=boptions,
                            options=aoptions,
                            stderr=stderr_io,
                        ),
                        self.volume,
                    )
                )
                log.debug(
                    "Playing %s using %s", repr(self._source), repr(self.voice_client)
                )
                self.voice_client.play(self._source, after=self._playback_finished)

                self._current_player = self.voice_client

                # I need to add ytdl hooks
                self.state = MusicPlayerState.PLAYING
                self._current_entry = entry

                self._stderr_future = asyncio.Future()

                stderr_thread = Thread(
                    target=filter_stderr,
                    args=(stderr_io, self._stderr_future),
                    name="stderr reader",
                )

                stderr_thread.start()

                self.emit("play", player=self, entry=entry)

    async def _handle_file_cleanup(self, entry: EntryTypes) -> None:
        """
        A helper used to clean up media files via call-later, when file
        cache is not enabled.
        """
        if not isinstance(entry, StreamPlaylistEntry):
            if any(entry.filename == e.filename for e in self.playlist.entries):
                log.debug(
                    "Skipping deletion of '%s', found song in queue",
                    entry.filename,
                )
            else:
                log.debug("Deleting file:  %s", os.path.relpath(entry.filename))
                filename = entry.filename
                for _ in range(3):
                    try:
                        os.unlink(filename)
                        log.debug("File deleted:  %s", filename)
                        break
                    except PermissionError as e:
                        if e.errno == 32:  # File is in use
                            log.warning("Cannot delete file, it is currently in use.")
                        else:
                            log.warning(
                                "Cannot delete file due to a permissions error.",
                                exc_info=True,
                            )
                    except FileNotFoundError:
                        log.warning(
                            "Cannot delete file, it was not found.",
                            exc_info=True,
                        )
                        break
                    except (OSError, IsADirectoryError):
                        log.warning(
                            "Error while trying to delete file.",
                            exc_info=True,
                        )
                        break
                else:
                    log.debug(
                        "[Config:SaveVideos] Could not delete file, giving up and moving on"
                    )

    def __json__(self) -> Dict[str, Any]:
        progress_frames = None
        if (
            self._current_player
            and self._current_player._player  # pylint: disable=protected-access
        ):
            if self.progress is not None:
                progress_frames = (
                    self._current_player._player.loops  # pylint: disable=protected-access
                )

        return self._enclose_json(
            {
                "current_entry": {
                    "entry": self.current_entry,
                    "progress": self.progress,
                    "progress_frames": progress_frames,
                },
                "entries": self.playlist,
            }
        )

    @classmethod
    def _deserialize(
        cls,
        raw_json: Dict[str, Any],
        bot: Optional["MusicBot"] = None,
        voice_client: Optional[VoiceClient] = None,
        playlist: Optional["Playlist"] = None,
        **kwargs: Any,
    ) -> "MusicPlayer":
        assert bot is not None, cls._bad("bot")
        assert voice_client is not None, cls._bad("voice_client")
        assert playlist is not None, cls._bad("playlist")

        player = cls(bot, voice_client, playlist)

        data_pl = raw_json.get("entries")
        if data_pl and data_pl.entries:
            player.playlist.entries = data_pl.entries

        current_entry_data = raw_json["current_entry"]
        if current_entry_data["entry"]:
            player.playlist.entries.appendleft(current_entry_data["entry"])
            # TODO: progress stuff
            # how do I even do this
            # this would have to be in the entry class right?
            # some sort of progress indicator to skip ahead with ffmpeg (however that works, reading and ignoring frames?)

        return player

    @classmethod
    def from_json(
        cls,
        raw_json: str,
        bot: "MusicBot",  # pylint: disable=unused-argument
        voice_client: VoiceClient,  # pylint: disable=unused-argument
        playlist: "Playlist",  # pylint: disable=unused-argument
    ) -> Optional["MusicPlayer"]:
        """
        Create a MusicPlayer instance from serialized `raw_json` string data.
        The remaining arguments are made available to the MusicPlayer
        and other serialized instances via call frame inspection.
        """
        try:
            obj = json.loads(raw_json, object_hook=Serializer.deserialize)
            if isinstance(obj, MusicPlayer):
                return obj
            log.error(
                "Deserialize returned a non-MusicPlayer:  %s",
                type(obj),
            )
            return None
        except json.JSONDecodeError:
            log.exception("Failed to deserialize player")
            return None

    @property
    def current_entry(self) -> Optional[EntryTypes]:
        """Get the currently playing entry if there is one."""
        return self._current_entry

    @property
    def is_playing(self) -> bool:
        """Test if MusicPlayer is in a playing state"""
        return self.state == MusicPlayerState.PLAYING

    @property
    def is_paused(self) -> bool:
        """Test if MusicPlayer is in a paused state"""
        return self.state == MusicPlayerState.PAUSED

    @property
    def is_stopped(self) -> bool:
        """Test if MusicPlayer is in a stopped state"""
        return self.state == MusicPlayerState.STOPPED

    @property
    def is_dead(self) -> bool:
        """Test if MusicPlayer is in a dead state"""
        return self.state == MusicPlayerState.DEAD

    @property
    def progress(self) -> float:
        """
        Return a progress value for the media playback.
        """
        if self._source:
            return self._source.get_progress()
            # TODO: Properly implement this
            #       Correct calculation should be bytes_read/192k
            #       192k AKA sampleRate * (bitDepth / 8) * channelCount
            #       Change frame_count to bytes_read in the PatchedBuff
        return 0


# TODO: I need to add a check if the event loop is closed?


def filter_stderr(stderr: io.BytesIO, future: AsyncFuture) -> None:
    """
    Consume a `stderr` bytes stream and check it for errors or warnings.
    Set the given `future` with either an error found in the stream or
    set the future with a successful result.
    """
    last_ex = None

    while True:
        data = stderr.readline()
        if data:
            log.ffmpeg(  # type: ignore[attr-defined]
                "Data from ffmpeg: %s",
                repr(data),
            )
            try:
                if check_stderr(data):
                    sys.stderr.buffer.write(data)
                    sys.stderr.buffer.flush()

            except FFmpegError as e:
                log.ffmpeg(  # type: ignore[attr-defined]
                    "Error from ffmpeg: %s", str(e).strip()
                )
                last_ex = e

            except FFmpegWarning as e:
                log.ffmpeg(  # type: ignore[attr-defined]
                    "Warning from ffmpeg:  %s", str(e).strip()
                )
        else:
            break

    if last_ex:
        future.set_exception(last_ex)
    else:
        future.set_result(True)


def check_stderr(data: bytes) -> bool:
    """
    Inspect `data` from a subprocess call's stderr output for specific
    messages and raise them as a suitable exception.

    :returns:  True if nothing was detected or nothing could be detected.

    :raises: musicbot.exceptions.FFmpegWarning
        If a warning level message was detected in the `data`
    :raises: musicbot.exceptions.FFmpegError
        If an error message was detected in the `data`
    """
    ddata = ""
    try:
        ddata = data.decode("utf8")
    except UnicodeDecodeError:
        log.ffmpeg(  # type: ignore[attr-defined]
            "Unknown error decoding message from ffmpeg", exc_info=True
        )
        return True  # fuck it

    log.ffmpeg("Decoded data from ffmpeg: %s", ddata)  # type: ignore[attr-defined]

    # TODO: Regex
    warnings = [
        "Header missing",
        "Estimating duration from birate, this may be inaccurate",
        "Using AVStream.codec to pass codec parameters to muxers is deprecated, use AVStream.codecpar instead.",
        "Application provided invalid, non monotonically increasing dts to muxer in stream",
        "Last message repeated",
        "Failed to send close message",
        "decode_band_types: Input buffer exhausted before END element found",
    ]
    errors = [
        "Invalid data found when processing input",  # need to regex this properly, its both a warning and an error
    ]

    if any(msg in ddata for msg in warnings):
        raise FFmpegWarning(ddata)

    if any(msg in ddata for msg in errors):
        raise FFmpegError(ddata)

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
