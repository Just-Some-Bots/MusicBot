import os.path
import logging
import datetime

from random import shuffle
from itertools import islice
from collections import deque

from urllib.error import URLError
from youtube_dl.utils import ExtractorError, DownloadError, UnsupportedError

from .utils import get_header
from .constructs import Serializable
from .lib.event_emitter import EventEmitter
from .entry import URLPlaylistEntry, StreamPlaylistEntry
from .exceptions import ExtractionError, WrongEntryTypeError

log = logging.getLogger(__name__)


class Playlist(EventEmitter, Serializable):
    """
        A playlist is manages the list of songs that will be played.
    """

    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.loop = bot.loop
        self.downloader = bot.downloader
        self.entries = deque()

    def __iter__(self):
        return iter(self.entries)

    def __len__(self):
        return len(self.entries)

    def shuffle(self):
        shuffle(self.entries)

    def clear(self):
        self.entries.clear()

    async def remove_entry(self, index):
        """
            Removes a song from the playlist.

            :param index: The index of the song to remove from the queue.
        """

        removed_entries = deque()

        if index == 1:
            return self.entries.popleft()

        for i in range(1, index):
            removed_entries.appendleft(self.entries.popleft())
        removed_entry = self.entries.popleft()

        for entry in removed_entries:
            self.entries.appendleft(entry)

        return removed_entry

    async def add_entry(self, song_url, **meta):
        """
            Validates and adds a song_url to be played. This does not start the download of the song.

            Returns the entry & the position it is in the queue.

            :param song_url: The song url to add to the playlist.
            :param meta: Any additional metadata to add to the playlist entry.
        """

        try:
            info = await self.downloader.extract_info(self.loop, song_url, download=False)
        except Exception as e:
            raise ExtractionError('Could not extract information from {}\n\n{}'.format(song_url, e))

        if not info:
            raise ExtractionError('Could not extract information from %s' % song_url)

        # TODO: Sort out what happens next when this happens
        if info.get('_type', None) == 'playlist':
            raise WrongEntryTypeError("This is a playlist.", True, info.get('webpage_url', None) or info.get('url', None))

        if info.get('is_live', False):
            return await self.add_stream_entry(song_url, info=info, **meta)

        # TODO: Extract this to its own function
        if info['extractor'] in ['generic', 'Dropbox']:
            try:
                headers = await get_header(self.bot.aiosession, info['url'])
                content_type = headers.get('CONTENT-TYPE')
                log.debug("Got content type {}".format(content_type))

            except Exception as e:
                log.warning("Failed to get content type for url {} ({})".format(song_url, e))
                content_type = None

            if content_type:
                if content_type.startswith(('application/', 'image/')):
                    if not any(x in content_type for x in ('/ogg', '/octet-stream')):
                        # How does a server say `application/ogg` what the actual fuck
                        raise ExtractionError("Invalid content type \"%s\" for url %s" % (content_type, song_url))

                elif content_type.startswith('text/html'):
                    log.warning("Got text/html for content-type, this might be a stream")
                    pass # TODO: Check for shoutcast/icecast

                elif not content_type.startswith(('audio/', 'video/')):
                    log.warning("Questionable content-type \"{}\" for url {}".format(content_type, song_url))

        entry = URLPlaylistEntry(
            self,
            song_url,
            info.get('title', 'Untitled'),
            info.get('duration', 0) or 0,
            self.downloader.ytdl.prepare_filename(info),
            **meta
        )
        self._add_entry(entry)
        return entry, len(self.entries)

    async def add_stream_entry(self, song_url, info=None, **meta):
        if info is None:
            info = {'title': song_url, 'extractor': None}

            try:
                info = await self.downloader.extract_info(self.loop, song_url, download=False)

            except DownloadError as e:
                if e.exc_info[0] == UnsupportedError: # ytdl doesn't like it but its probably a stream
                    log.debug("Assuming content is a direct stream")

                elif e.exc_info[0] == URLError:
                    if os.path.exists(os.path.abspath(song_url)):
                        raise ExtractionError("This is not a stream, this is a file path.")

                    else: # it might be a file path that just doesn't exist
                        raise ExtractionError("Invalid input: {0.exc_info[0]}: {0.exc_info[1].reason}".format(e))

                else:
                    # traceback.print_exc()
                    raise ExtractionError("Unknown error: {}".format(e))

            except Exception as e:
                log.error('Could not extract information from {} ({}), falling back to direct'.format(song_url, e), exc_info=True)

        dest_url = song_url
        if info.get('extractor'):
            dest_url = info.get('url')

        if info.get('extractor', None) == 'twitch:stream': # may need to add other twitch types
            title = info.get('description')
        else:
            title = info.get('title', 'Untitled')

        # TODO: A bit more validation, "~stream some_url" should not just say :ok_hand:

        entry = StreamPlaylistEntry(
            self,
            song_url,
            title,
            destination = dest_url,
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

        try:
            info = await self.downloader.safe_extract_info(self.loop, playlist_url, download=False)
        except Exception as e:
            raise ExtractionError('Could not extract information from {}\n\n{}'.format(playlist_url, e))

        if not info:
            raise ExtractionError('Could not extract information from %s' % playlist_url)

        # Once again, the generic extractor fucks things up.
        if info.get('extractor', None) == 'generic':
            url_field = 'url'
        else:
            url_field = 'webpage_url'

        baditems = 0
        for item in info['entries']:
            if item:
                try:
                    entry = URLPlaylistEntry(
                        self,
                        item[url_field],
                        item.get('title', 'Untitled'),
                        item.get('duration', 0) or 0,
                        self.downloader.ytdl.prepare_filename(item),
                        **meta
                    )

                    self._add_entry(entry)
                    entry_list.append(entry)
                except Exception as e:
                    baditems += 1
                    log.warning("Could not add item", exc_info=e)
                    log.debug("Item: {}".format(item), exc_info=True)
            else:
                baditems += 1

        if baditems:
            log.info("Skipped {} bad entries".format(baditems))

        return entry_list, position

    async def async_process_youtube_playlist(self, playlist_url, **meta):
        """
            Processes youtube playlists links from `playlist_url` in a questionable, async fashion.

            :param playlist_url: The playlist url to be cut into individual urls and added to the playlist
            :param meta: Any additional metadata to add to the playlist entry
        """

        try:
            info = await self.downloader.safe_extract_info(self.loop, playlist_url, download=False, process=False)
        except Exception as e:
            raise ExtractionError('Could not extract information from {}\n\n{}'.format(playlist_url, e))

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
                    log.error("Error adding entry {}".format(entry_data['id']), exc_info=e)
            else:
                baditems += 1

        if baditems:
            log.info("Skipped {} bad entries".format(baditems))

        return gooditems

    async def async_process_sc_bc_playlist(self, playlist_url, **meta):
        """
            Processes soundcloud set and bancdamp album links from `playlist_url` in a questionable, async fashion.

            :param playlist_url: The playlist url to be cut into individual urls and added to the playlist
            :param meta: Any additional metadata to add to the playlist entry
        """

        try:
            info = await self.downloader.safe_extract_info(self.loop, playlist_url, download=False, process=False)
        except Exception as e:
            raise ExtractionError('Could not extract information from {}\n\n{}'.format(playlist_url, e))

        if not info:
            raise ExtractionError('Could not extract information from %s' % playlist_url)

        gooditems = []
        baditems = 0

        for entry_data in info['entries']:
            if entry_data:
                song_url = entry_data['url']

                try:
                    entry, elen = await self.add_entry(song_url, **meta)
                    gooditems.append(entry)

                except ExtractionError:
                    baditems += 1

                except Exception as e:
                    baditems += 1
                    log.error("Error adding entry {}".format(entry_data['id']), exc_info=e)
            else:
                baditems += 1

        if baditems:
            log.info("Skipped {} bad entries".format(baditems))

        return gooditems

    def _add_entry(self, entry, *, head=False):
        if head:
            self.entries.appendleft(entry)
        else:
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
        estimated_time = sum(e.duration for e in islice(self.entries, position - 1))

        # When the player plays a song, it eats the first playlist item, so we just have to add the time back
        if not player.is_stopped and player.current_entry:
            estimated_time += player.current_entry.duration - player.progress

        return datetime.timedelta(seconds=estimated_time)

    def count_for_user(self, user):
        return sum(1 for e in self.entries if e.meta.get('author', None) == user)


    def __json__(self):
        return self._enclose_json({
            'entries': list(self.entries)
        })

    @classmethod
    def _deserialize(cls, raw_json, bot=None):
        assert bot is not None, cls._bad('bot')
        # log.debug("Deserializing playlist")
        pl = cls(bot)

        for entry in raw_json['entries']:
            pl.entries.append(entry)

        # TODO: create a function to init downloading (since we don't do it here)?
        return pl

