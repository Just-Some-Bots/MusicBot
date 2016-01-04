import asyncio
import collections
import itertools
import datetime
import os
import os.path
import traceback
from random import shuffle

from .constants import AUDIO_CACHE_PATH
from .downloader import extract_info
from .exceptions import ExtractionError
from .utils import slugify
from .lib.event_emitter import EventEmitter


class Playlist(EventEmitter):
    """
        A playlist is manages the list of songs that will be played.
    """

    def __init__(self, loop):
        super().__init__()
        self.loop = loop
        self.entries = collections.deque()

    def shuffle(self):
        shuffle(self.entries)

    async def add_entry(self, song_url, **meta):
        """
            Validates and adds a song_url to be played. This does not start the download of the song.

            Returns the entry & the position it is in the queue.

            :param song_url: The song url to add to the playlist.
            :param meta: Any additional metadata to add to the playlist entry.
        """
        info = await extract_info(self.loop, song_url, download=False)
        if not info:
            raise ExtractionError('Could not extract information from %s' % song_url)

        entry = PlaylistEntry(
            self,
            song_url,
            info['id'],
            info['title'],
            info.get('duration', 0),
            **meta
        )
        self._add_entry(entry)
        return entry, len(self.entries)

    async def import_from(self, playlist_url, **meta):
        """
            Imports the songs from `playlist_url` and queues them to be played.

            Returns a list of `entries` that have been enqueued.

            :param playlist_url: The playlist url to be cut into individual urls and added to the playlist
            :param meta: Any additional metadata to add to the playlist entry
        """
        position = len(self.entries)+1
        entry_list = []
        
        info = await extract_info(self.loop, playlist_url, download=False)
        
        if not info:
            raise ExtractionError('Could not extract information from %s' % playlist_url)
        
        for items in info['entries']:
            entry = PlaylistEntry(
                self,
                items['webpage_url'],
                items['id'],
                items['title'],
                items.get('duration', 0),
                **meta
            )
            
            self._add_entry(entry)
            entry_list.append(entry)
        
        return entry_list, position

    def _add_entry(self, entry):
        self.entries.append(entry)
        self.emit('entry-added', playlist=self, entry=entry)

        if self.peek() is entry:
            entry.get_ready_future()

    async def get_next_entry(self, predownload_next=True):
        """
            A coroutine which will return the next song or None if no songs left to play.

            Additionally, if predownload_next is set to True, it will attempt to download the next
            song to be played - so that it's ready by the time we get to it.
        """
        if not self.entries:
            return None

        entry = self.entries.popleft()

        if predownload_next:
            next_entry = self.peek()
            if next_entry:
                next_entry.get_ready_future()

        return await entry.get_ready_future()

    def peek(self):
        """
            Returns the next entry that should be scheduled to be played.
        """
        if self.entries:
            return self.entries[0]

    async def estimate_time_until(self, position):
        """
            (very) Roughly estimates the time till the queue will 'position'
        """
        estimated_time = 0
        
        for i in range(0, position):
            estimated_time += self.entries[i].duration

        print('rhino time:', estimated_time)
        print('bork time list:', [e.duration for e in list(itertools.islice(self.entries, 0, position-1))])
        print('bork time:', sum([e.duration for e in list(itertools.islice(self.entries, 0, position-1))]))

        # I think this is correct, we just need to subtract now_playing_song_length + duration_song_has_been_playing
        
        # print('Entries:', self.entries)
        # print('positioned entries:', list(itertools.islice(self.entries, 0, position)))
        
        return datetime.timedelta(seconds=estimated_time)

    def __iter__(self):
        return iter(self.entries)


class PlaylistEntry(object):
    def __init__(self, playlist, url, id, title, duration=0, **meta):
        self.playlist = playlist
        self.url = url
        self.id = id
        self.title = title
        self.duration = duration
        self.meta = meta
        self._is_downloading = False
        self._waiting_futures = []

    @property
    def is_downloaded(self):
        if self._is_downloading:
            return False

        return os.path.isfile(self.filename)

    @property
    def filename(self):
        """
        The filename of where this playlist entry will exist.
        """
        return os.path.join(AUDIO_CACHE_PATH, '%s.mp3' % self.slug)

    @property
    def slug(self):
        """
        Returns a slug generated from the ID and title of this PlaylistEntry
        """
        return slugify('%s-%s' % (self.id, self.title))

    async def _download(self):
        if self._is_downloading:
            return

        self._is_downloading = True
        try:
            result = await extract_info(self.playlist.loop, self.url, download=True)
            filename = self.filename

            # If the file existed, we're going to remove it to overwrite.
            if os.path.isfile(filename):
                os.unlink(filename)

            # Ensure the folder that we're going to move into exists.
            directory = os.path.dirname(filename)
            if not os.path.exists(directory):
                os.makedirs(directory)

            # Move the temporary file to it's final location.
            os.rename(result['id'], self.filename)

            # Trigger ready callbacks.
            self._for_each_future(lambda future: future.set_result(self))

        except Exception as e:
            self._for_each_future(lambda future: future.set_exception(e))

        finally:
            self._is_downloading = False

    def get_ready_future(self):
        """
        Returns a future that will fire when the song is ready to be played. The future will either fire with the result (being the entry) or an exception
        as to why the song download failed.
        """
        future = asyncio.Future()
        if self.is_downloaded:
            # In the event that we're downloaded, we're already ready for playback.
            future.set_result(self)

        else:
            # If we request a ready future, let's ensure that it'll actually resolve at one point.
            asyncio.ensure_future(self._download())
            self._waiting_futures.append(future)

        return future

    def _for_each_future(self, cb):
        """
            Calls `cb` for each future that is not cancelled. Absorbs and logs any errors that may have occurred.
        """
        futures = self._waiting_futures
        self._waiting_futures = []

        for future in futures:
            if future.cancelled():
                continue

            try:
                cb(future)

            except:
                traceback.print_exc()

    def __eq__(self, other):
        return self is other

    def __hash__(self):
        return id(self)
