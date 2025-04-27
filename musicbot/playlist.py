import asyncio
import datetime
import logging
from collections import deque
from itertools import islice
from random import shuffle
from typing import (
    TYPE_CHECKING,
    Any,
    Deque,
    Dict,
    Iterator,
    List,
    Optional,
    Tuple,
    Union,
)

import discord

from .constants import DEFAULT_PRE_DOWNLOAD_DELAY
from .constructs import Serializable
from .entry import LocalFilePlaylistEntry, StreamPlaylistEntry, URLPlaylistEntry
from .exceptions import ExtractionError, InvalidDataError, WrongEntryTypeError
from .lib.event_emitter import EventEmitter

if TYPE_CHECKING:
    from .bot import MusicBot
    from .downloader import YtdlpResponseDict
    from .player import MusicPlayer

# type aliases
EntryTypes = Union[URLPlaylistEntry, StreamPlaylistEntry, LocalFilePlaylistEntry]

GuildMessageableChannels = Union[
    discord.VoiceChannel,
    discord.StageChannel,
    discord.Thread,
    discord.TextChannel,
]

log = logging.getLogger(__name__)


class Playlist(EventEmitter, Serializable):
    """
    A playlist that manages the queue of songs that will be played.
    """

    def __init__(self, bot: "MusicBot") -> None:
        """
        Manage a serializable, event-capable playlist of entries made up
        of validated extraction information.
        """
        super().__init__()
        self.bot: MusicBot = bot
        self.loop: asyncio.AbstractEventLoop = bot.loop
        self.entries: Deque[EntryTypes] = deque()

    def __iter__(self) -> Iterator[EntryTypes]:
        return iter(self.entries)

    def __len__(self) -> int:
        return len(self.entries)

    def shuffle(self) -> None:
        """Shuffle the deque of entries, in place."""
        shuffle(self.entries)

    def clear(self) -> None:
        """Clears the deque of entries."""
        self.entries.clear()

    def removerange(self, start: int, end: int) -> None:
        """Clears a range of the deque of entries."""
        if start == 0:
            for i in range(end - start + 1):
                self.entries.popleft()
        elif end == len(self.entries) - 1:
            for i in range(end - start + 1):
                self.entries.pop()
        else:
            # Reconstruct the deque excluding the range [a, b]
            self.entries = deque(list(self.entries)[:start] + list(self.entries)[end+1:])

    def get_entry_at_index(self, index: int) -> EntryTypes:
        """
        Uses deque rotate to seek to the given `index` and reference the
        entry at that position.
        """
        self.entries.rotate(-index)
        entry = self.entries[0]
        self.entries.rotate(index)
        return entry

    def delete_entry_at_index(self, index: int) -> EntryTypes:
        """Remove and return the entry at the given index."""
        self.entries.rotate(-index)
        entry = self.entries.popleft()
        self.entries.rotate(index)
        return entry

    def insert_entry_at_index(self, index: int, entry: EntryTypes) -> None:
        """Add entry to the queue at the given index."""
        self.entries.rotate(-index)
        self.entries.appendleft(entry)
        self.entries.rotate(index)

    async def add_stream_from_info(
        self,
        info: "YtdlpResponseDict",
        *,
        author: Optional["discord.Member"] = None,
        channel: Optional[GuildMessageableChannels] = None,
        head: bool = False,
        defer_serialize: bool = False,
    ) -> Tuple[StreamPlaylistEntry, int]:
        """
        Use the given `info` to create a StreamPlaylistEntry and add it
        to the queue.
        If the entry is the first in the queue, it will be called to ready
        for playback.

        :param: info:  Extracted info for this entry, even fudged.
        :param: head:  Toggle adding to the front of the queue.
        :param: defer_serialize:  Signal to defer serialization steps.
            Useful if many entries are added at once

        :returns:  A tuple with the entry object, and its position in the queue.
        """

        log.noise(  # type: ignore[attr-defined]
            "Adding stream entry for URL:  %(url)s",
            {"url": info.url},
        )
        entry = StreamPlaylistEntry(
            self,
            info,
            author=author,
            channel=channel,
        )
        self._add_entry(entry, head=head, defer_serialize=defer_serialize)
        return entry, len(self.entries)

    async def add_entry_from_info(
        self,
        info: "YtdlpResponseDict",
        *,
        author: Optional["discord.Member"] = None,
        channel: Optional[GuildMessageableChannels] = None,
        head: bool = False,
        defer_serialize: bool = False,
    ) -> Tuple[EntryTypes, int]:
        """
        Checks given `info` to determine if media is streaming or has a
        stream-able content type, then adds the resulting entry to the queue.
        If the entry is the first entry in the queue, it will be called
        to ready for playback.

        :param info: The extraction data of the song to add to the playlist.
        :param head: Add to front of queue instead of the end.
        :param defer_serialize:  Signal that serialization steps should be deferred.

        :returns: the entry & it's position in the queue.

        :raises: ExtractionError  If data is missing or the content type is invalid.
        :raises: WrongEntryTypeError  If the info is identified as a playlist.
        """

        if not info:
            raise ExtractionError("Could not extract information")

        # this should, in theory, never happen.
        if info.ytdl_type == "playlist":
            raise WrongEntryTypeError("This is a playlist.")

        # check if this is a local file entry.
        if info.ytdl_type == "local":
            return await self.add_local_file_entry(
                info,
                author=author,
                channel=channel,
                head=head,
                defer_serialize=defer_serialize,
            )

        # check if this is a stream, just in case.
        if info.is_stream:
            log.debug("Entry info appears to be a stream, adding stream entry...")
            return await self.add_stream_from_info(
                info,
                author=author,
                channel=channel,
                head=head,
                defer_serialize=defer_serialize,
            )

        # TODO: Extract this to its own function
        if any(info.extractor.startswith(x) for x in ["generic", "Dropbox"]):
            content_type = info.http_header("content-type", None)

            if content_type:
                if content_type.startswith(("application/", "image/")):
                    if not any(x in content_type for x in ("/ogg", "/octet-stream")):
                        # How does a server say `application/ogg` what the actual fuck
                        raise ExtractionError(
                            "Invalid content type `%(type)s` for URL: %(url)s",
                            fmt_args={"type": content_type, "url": info.url},
                        )

                elif (
                    content_type.startswith("text/html") and info.extractor == "generic"
                ):
                    log.warning(
                        "Got text/html for content-type, this might be a stream."
                    )
                    return await self.add_stream_from_info(info, head=head)
                    # TODO: Check for shoutcast/icecast

                elif not content_type.startswith(("audio/", "video/")):
                    log.warning(
                        'Questionable content-type "%(type)s" for url:  %(url)s',
                        {"type": content_type, "url": info.url},
                    )

        log.noise(  # type: ignore[attr-defined]
            "Adding URLPlaylistEntry for: %(subject)s",
            {"subject": info.input_subject},
        )
        entry = URLPlaylistEntry(self, info, author=author, channel=channel)
        self._add_entry(entry, head=head, defer_serialize=defer_serialize)
        return entry, (1 if head else len(self.entries))

    async def add_local_file_entry(
        self,
        info: "YtdlpResponseDict",
        *,
        author: Optional["discord.Member"] = None,
        channel: Optional[GuildMessageableChannels] = None,
        head: bool = False,
        defer_serialize: bool = False,
    ) -> Tuple[LocalFilePlaylistEntry, int]:
        """
        Adds a local media file entry to the playlist.
        """
        log.noise(  # type: ignore[attr-defined]
            "Adding LocalFilePlaylistEntry for: %(subject)s",
            {"subject": info.input_subject},
        )
        entry = LocalFilePlaylistEntry(self, info, author=author, channel=channel)
        self._add_entry(entry, head=head, defer_serialize=defer_serialize)
        return entry, (1 if head else len(self.entries))

    async def import_from_info(
        self,
        info: "YtdlpResponseDict",
        head: bool,
        ignore_video_id: str = "",
        author: Optional["discord.Member"] = None,
        channel: Optional[GuildMessageableChannels] = None,
    ) -> Tuple[List[EntryTypes], int]:
        """
        Validates the songs from `info` and queues them to be played.

        Returns a list of entries that have been queued, and the queue
        position where the first entry was added.

        :param: info:  YoutubeDL extraction data containing multiple entries.
        :param: head:  Toggle adding the entries to the front of the queue.
        """
        position = 1 if head else len(self.entries) + 1
        entry_list = []
        baditems = 0
        entries = info.get_entries_objects()
        author_perms = None
        defer_serialize = True

        if author:
            author_perms = self.bot.permissions.for_user(author)

        if head:
            entries.reverse()

        track_number = 0
        for item in entries:
            # count tracks regardless of conditions, used for missing track names
            # and also defers serialization of the queue for playlists.
            track_number += 1
            # Ignore playlist entry when it comes from compound links.
            if ignore_video_id and ignore_video_id == item.video_id:
                log.debug(
                    "Ignored video from compound playlist link with ID:  %s",
                    item.video_id,
                )
                baditems += 1
                continue

            # Check if the item is in the song block list.
            if self.bot.config.song_blocklist_enabled and (
                self.bot.config.song_blocklist.is_blocked(item.url)
                or self.bot.config.song_blocklist.is_blocked(item.title)
            ):
                log.info(
                    "Not allowing entry that is in song block list:  %(title)s  URL: %(url)s",
                    {"title": item.title, "url": item.url},
                )
                baditems += 1
                continue

            # Exclude entries over max permitted duration.
            if (
                author_perms
                and author_perms.max_song_length
                and item.duration > author_perms.max_song_length
            ):
                log.debug(
                    "Ignoring song in entries by '%s', duration longer than permitted maximum.",
                    author,
                )
                baditems += 1
                continue

            # Check youtube data to preemptively avoid adding Private or Deleted videos to the queue.
            if info.extractor.startswith("youtube") and (
                "[private video]" == item.get("title", "").lower()
                or "[deleted video]" == item.get("title", "").lower()
            ):
                log.warning(
                    "Not adding YouTube video because it is marked private or deleted:  %s",
                    item.get_playable_url(),
                )
                baditems += 1
                continue

            # Soundcloud playlists don't get titles in flat extraction. A bug maybe?
            # Anyway we make a temp title here, the real one is fetched at play.
            if "title" in info and "title" not in item:
                item["title"] = f"{info.title} - #{track_number}"

            if track_number >= info.entry_count:
                defer_serialize = False

            try:
                entry, _pos = await self.add_entry_from_info(
                    item,
                    head=head,
                    defer_serialize=defer_serialize,
                    author=author,
                    channel=channel,
                )
                entry_list.append(entry)
            except (WrongEntryTypeError, ExtractionError):
                baditems += 1
                log.warning("Could not add item")
                log.debug("Item: %s", item, exc_info=True)

        if baditems:
            log.info("Skipped %s bad entries", baditems)

        if head:
            entry_list.reverse()
        return entry_list, position

    def get_next_song_from_author(
        self, author: "discord.abc.User"
    ) -> Optional[EntryTypes]:
        """
        Get the next song in the queue that was added by the given `author`
        """
        for entry in self.entries:
            if entry.author == author:
                return entry

        return None

    def reorder_for_round_robin(self) -> None:
        """
        Reorders the current queue for round-robin, one song per author.
        Entries added by the auto playlist will be removed.
        """
        new_queue: Deque[EntryTypes] = deque()
        all_authors: List[discord.abc.User] = []

        # Make a list of unique authors from the current queue.
        for entry in self.entries:
            if entry.author and entry.author not in all_authors:
                all_authors.append(entry.author)

        # If all queue entries have no author, do nothing.
        if len(all_authors) == 0:
            return

        # Loop over the queue and organize it by requesting author.
        # This will remove entries which are added by the auto-playlist.
        request_counter = 0
        song: Optional[EntryTypes] = None
        while self.entries:
            log.everything(  # type: ignore[attr-defined]
                "Reorder looping over entries."
            )

            # Do not continue if we have no more authors.
            if len(all_authors) == 0:
                break

            # Reset the requesting author if needed.
            if request_counter >= len(all_authors):
                request_counter = 0

            song = self.get_next_song_from_author(all_authors[request_counter])

            # Remove the authors with no further songs.
            if song is None:
                all_authors.pop(request_counter)
                continue

            new_queue.append(song)
            self.entries.remove(song)
            request_counter += 1

        self.entries = new_queue

    def _add_entry(
        self, entry: EntryTypes, *, head: bool = False, defer_serialize: bool = False
    ) -> None:
        """
        Handle appending the `entry` to the queue. If the entry is he first,
        the entry will create a future to download itself.

        :param: head:  Toggle adding to the front of the queue.
        :param: defer_serialize:  Signal to events that serialization should be deferred.
        """
        if head:
            self.entries.appendleft(entry)
        else:
            self.entries.append(entry)

        if self.bot.config.round_robin_queue and not entry.from_auto_playlist:
            self.reorder_for_round_robin()

        self.emit(
            "entry-added", playlist=self, entry=entry, defer_serialize=defer_serialize
        )

    async def get_next_entry(self) -> Any:
        """
        A coroutine which will return the next song or None if no songs left to play.

        Additionally, if predownload_next is set to True, it will attempt to download the next
        song to be played - so that it's ready by the time we get to it.
        """
        if not self.entries:
            return None

        entry = self.entries.popleft()
        self.bot.create_task(
            self._pre_download_entry_after_next(entry),
            name="MB_PreDownloadNextUp",
        )

        return await entry.get_ready_future()

    async def _pre_download_entry_after_next(self, last_entry: EntryTypes) -> None:
        """
        Enforces a delay before doing pre-download of the "next" song.
        Should only be called from get_next_entry() after pop.
        """
        if not self.bot.config.pre_download_next_song:
            return

        if not self.entries:
            return

        # get the next entry to pre-download before we wait.
        next_entry = self.peek()

        await asyncio.sleep(DEFAULT_PRE_DOWNLOAD_DELAY)

        if next_entry and next_entry != last_entry:
            log.everything(  # type: ignore[attr-defined]
                "Pre-downloading next track:  %r", next_entry
            )
            next_entry.get_ready_future()

    def peek(self) -> Optional[EntryTypes]:
        """
        Returns the next entry that should be scheduled to be played.
        """
        if self.entries:
            return self.entries[0]
        return None

    async def estimate_time_until(
        self, position: int, player: "MusicPlayer"
    ) -> datetime.timedelta:
        """
        (very) Roughly estimates the time till the queue will reach given `position`.

        :param: position:  The index in the queue to reach.
        :param: player:  MusicPlayer instance this playlist should belong to.

        :returns: A datetime.timedelta object with the estimated time.

        :raises: musicbot.exceptions.InvalidDataError  if duration data cannot be calculated.
        """
        if any(e.duration is None for e in islice(self.entries, position - 1)):
            raise InvalidDataError("no duration data")

        estimated_time = sum(
            e.duration_td.total_seconds() for e in islice(self.entries, position - 1)
        )

        # When the player plays a song, it eats the first playlist item, so we just have to add the time back
        if not player.is_stopped and player.current_entry:
            if player.current_entry.duration is None:
                raise InvalidDataError("no duration data in current entry")

            estimated_time += (
                player.current_entry.duration_td.total_seconds() - player.progress
            )

        return datetime.timedelta(seconds=estimated_time)

    def count_for_user(self, user: "discord.abc.User") -> int:
        """Get a sum of entries added to the playlist by the given `user`"""
        return sum(1 for e in self.entries if e.author == user)

    def __json__(self) -> Dict[str, Any]:
        return self._enclose_json({"entries": list(self.entries)})

    @classmethod
    def _deserialize(
        cls, raw_json: Dict[str, Any], bot: Optional["MusicBot"] = None, **kwargs: Any
    ) -> "Playlist":
        assert bot is not None, cls._bad("bot")
        # log.debug("Deserializing playlist")
        pl = cls(bot)

        for entry in raw_json["entries"]:
            pl.entries.append(entry)

        # TODO: create a function to init downloading (since we don't do it here)?
        return pl
