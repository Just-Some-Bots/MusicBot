import os
import asyncio
import datetime
import traceback

from hashlib import md5
from random import shuffle
from itertools import islice
from collections import deque

from .constants import AUDIO_CACHE_PATH
from .downloader import extract_info, ytdl
from .exceptions import ExtractionError
from .lib.event_emitter import EventEmitter


class Playlist(EventEmitter):
    """
        A playlist is manages the list of songs that will be played.
    """

    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.loop = bot.loop
        self.entries = deque()

    def __iter__(self):
        return iter(self.entries)

    def shuffle(self):
        shuffle(self.entries)

    def clear(self):
        self.entries.clear()

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
            info['title'],
            info.get('duration', 0) or 0,
            ytdl.prepare_filename(info),
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
        position = len(self.entries) + 1
        entry_list = []

        info = await extract_info(self.loop, playlist_url, download=False)

        if not info:
            raise ExtractionError('Could not extract information from %s' % playlist_url)

        baditems = 0
        for items in info['entries']:
            if items:
                try:
                    entry = PlaylistEntry(
                        self,
                        items['webpage_url'],
                        items['title'],
                        items.get('duration', 0) or 0,
                        ytdl.prepare_filename(info),
                        **meta
                    )

                    self._add_entry(entry)
                    entry_list.append(entry)
                except:
                    baditems += 1
                    # Once I know more about what's happening here I can add a proper message
                    traceback.print_exc()
                    print(items)
                    print("Could not add item")
            else:
                baditems += 1

        if baditems:
            print("Skipped %s bad entries" % baditems)

        return entry_list, position

    async def async_process_youtube_playlist(self, playlist_url, **meta):
        """
            Processes youtube playlists links from `playlist_url` in a questionable, async fashion.

            :param playlist_url: The playlist url to be cut into individual urls and added to the playlist
            :param meta: Any additional metadata to add to the playlist entry
        """

        info = await extract_info(self.loop, playlist_url, download=False, process=False)

        if not info:
            raise ExtractionError('Could not extract information from %s' % playlist_url)

        gooditems = []
        baditems = 0
        for entry_data in info['entries']:
            if entry_data:
                baseurl = info['webpage_url'].split('playlist?list=')[0]
                song_url = baseurl + 'watch?v=%s' % entry_data['id']

                try:
                    entry, elen = await self.add_entry(song_url, **meta)
                    gooditems.append(entry)
                except ExtractionError:
                    baditems += 1
                except Exception as e:
                    baditems += 1
                    print("There was an error adding the song %s: %s: %s" % (entry_data['id'], e.__class__, e))

            else:
                baditems += 1

        if baditems:
            print("Skipped %s bad entries" % baditems)

        return gooditems

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

    async def estimate_time_until(self, position, player):
        """
            (very) Roughly estimates the time till the queue will 'position'
        """
        estimated_time = sum([e.duration for e in islice(self.entries, position - 1)])

        # When the player plays a song, it eats the first playlist item, so we just have to add the time back
        if not player.is_stopped and player.current_entry:
            estimated_time += player.current_entry.duration - player.progress

        return datetime.timedelta(seconds=estimated_time)

    def count_for_user(self, user):
        return sum(1 for e in self.entries if e.meta.get('author', None) == user)


class PlaylistEntry:
    def __init__(self, playlist, url, title, duration=0, expected_filename=None, **meta):
        self.playlist = playlist
        self.url = url
        self.title = title
        self.duration = duration
        self.expected_filename = expected_filename
        self.meta = meta

        self.filename = None
        self._is_downloading = False
        self._waiting_futures = []

    @property
    def is_downloaded(self):
        if self._is_downloading:
            return False

        return bool(self.filename)

    @classmethod
    def from_json(cls, data):
        pass

    def to_json(self):
        data = {
            'url': self.url,
            'title': self.title,
            'duration': self.duration,
            # I think filename might have to be regenerated

            # I think these are only channels and members (author)
            'meta': {i: {'type': self.meta[i].__class__.__name__, 'id': self.meta[i].id} for i in self.meta}
            # Actually I think I can just getattr instead, getattr(discord, type)

            # I do need to test if these can be pickled properly
        }
        return data

    async def _download(self):
        if self._is_downloading:
            return

        self._is_downloading = True
        try:
            # figure out if the filename without the hash is already in the cache folder
            wouldbe_fname_noex = self.expected_filename.rsplit('.', 1)[0]
            flistdir = [f.rsplit('-', 1)[0] for f in os.listdir(AUDIO_CACHE_PATH)]

            # we don't check for files downloaded with the generic extractor (direct links) since they're
            # the entire reason we're adding a hash to the filename to begin with (filename uniqueness)
            if wouldbe_fname_noex in flistdir and not wouldbe_fname_noex.startswith('generic'):
                self.filename = os.path.join(
                    AUDIO_CACHE_PATH,
                    os.listdir(AUDIO_CACHE_PATH)[flistdir.index(wouldbe_fname_noex)])
                # print("Found:\n    {}\nFor:\n    {}".format(self.filename, self.expected_filename))

            else:
                print("[Download] Started:", self.url)
                result = await extract_info(self.playlist.loop, self.url, download=True)
                print("[Download] Complete:", self.url)

                # insert the 8 last characters of the file hash to the file name to ensure uniqueness
                unhashed_fname = ytdl.prepare_filename(result)
                unmoved_fname = md5sum(unhashed_fname, 8).join('-.').join(unhashed_fname.rsplit('.', 1))
                self.filename = os.path.join(AUDIO_CACHE_PATH, unmoved_fname)

                # Ensure the folder that we're going to move into exists.
                directory = os.path.dirname(self.filename)
                if not os.path.exists(directory):
                    os.makedirs(directory)

                # Move the temporary file to it's final location.
                os.replace(ytdl.prepare_filename(result), self.filename)

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


def md5sum(filename, limit=0):
    fhash = md5()
    with open(filename, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            fhash.update(chunk)
    return fhash.hexdigest()[-limit:]
