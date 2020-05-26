"""
MusicBot: The original Discord music bot written for Python 3.5+, using the discord.py library.
ModuBot: A modular discord bot with dependency management
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The MIT License (MIT)

Copyright (c) 2019 TheerapakG
Copyright (c) 2019-2020 Just-Some-Bots (https://github.com/Just-Some-Bots)

This file incorporates work covered by the following copyright and  
permission notice:

    Copyright (c) 2015-2019 Just-Some-Bots (https://github.com/Just-Some-Bots)

    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in
    all copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
    THE SOFTWARE.

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""

import os
import asyncio
import functools
import youtube_dl
from .exceptions import VersionError, ExtractionError
from .playback import Entry
from .utils import get_header, md5sum, run_command

from urllib.error import URLError
from youtube_dl.utils import DownloadError, UnsupportedError

from concurrent.futures import ThreadPoolExecutor

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
    'usenetrc': True,
    'writesubtitles': True,
    'allsubtitles': True,
    'subtitlesformat': 'srt',
    'postprocessors': [
        {
            'key': 'FFmpegSubtitlesConvertor',
            'format': 'srt'
        }
    ]
}

youtube_dl.utils.bug_reports_message = lambda: ''

'''
    Alright, here's the problem.  To catch youtube-dl errors for their useful information, I have to
    catch the exceptions with `ignoreerrors` off.  To not break when ytdl hits a dumb video
    (rental videos, etc), I have to have `ignoreerrors` on.  I can change these whenever, but with async
    that's bad.  So I need multiple ytdl objects.
'''

class YtdlDownloader:
    def __init__(self, bot, download_folder=None):
        self._bot = bot
        self.thread_pool = ThreadPoolExecutor(max_workers=2)
        self.unsafe_ytdl = youtube_dl.YoutubeDL(ytdl_format_options)
        self.safe_ytdl = youtube_dl.YoutubeDL(ytdl_format_options)
        self.safe_ytdl.params['ignoreerrors'] = True
        os.makedirs(download_folder, exist_ok=True)
        self.download_folder = download_folder

        if self.download_folder:
            otmpl = self.unsafe_ytdl.params['outtmpl']
            self.unsafe_ytdl.params['outtmpl'] = os.path.join(self.download_folder, otmpl)
            # print("setting template to " + os.path.join(self.download_folder, otmpl))

            otmpl = self.safe_ytdl.params['outtmpl']
            self.safe_ytdl.params['outtmpl'] = os.path.join(self.download_folder, otmpl)

    def shutdown(self):
        self.thread_pool.shutdown()

    @property
    def ytdl(self):
        return self.safe_ytdl

    async def extract_info(self, *args, on_error=None, retry_on_error=False, **kwargs):
        """
            Runs ytdl.extract_info within the threadpool. Returns a future that will fire when it's done.
            If `on_error` is passed and an exception is raised, the exception will be caught and passed to
            on_error as an argument.
        """
        if callable(on_error):
            try:
                return await self._bot.loop.run_in_executor(self.thread_pool, functools.partial(self.unsafe_ytdl.extract_info, *args, **kwargs))

            except Exception as e:

                # (youtube_dl.utils.ExtractorError, youtube_dl.utils.DownloadError)
                # I hope I don't have to deal with ContentTooShortError's
                if asyncio.iscoroutinefunction(on_error):
                    asyncio.ensure_future(on_error(e), loop=self._bot.loop)

                elif asyncio.iscoroutine(on_error):
                    asyncio.ensure_future(on_error, loop=self._bot.loop)

                else:
                    self._bot.loop.call_soon_threadsafe(on_error, e)

                if retry_on_error:
                    return await self.safe_extract_info(self._bot.loop, *args, **kwargs)
        else:
            return await self._bot.loop.run_in_executor(self.thread_pool, functools.partial(self.unsafe_ytdl.extract_info, *args, **kwargs))

    async def safe_extract_info(self, *args, **kwargs):
        return await self._bot.loop.run_in_executor(self.thread_pool, functools.partial(self.safe_ytdl.extract_info, *args, **kwargs))

    async def process_url_to_info(self, song_url, on_search_error = None):
        while True:
            try:
                info = await self.extract_info(song_url, download=False, process=False)
                # If there is an exception arise when processing we go on and let extract_info down the line report it
                # because info might be a playlist and thing that's broke it might be individual entry
                try:
                    info_process = await self.extract_info(song_url, download=False)
                except:
                    info_process = None
                    
                self._bot.log.debug(info)
                if info_process and info and info_process.get('_type', None) == 'playlist' and 'entries' not in info and not info.get('url', '').startswith('ytsearch'):
                    use_url = info_process.get('webpage_url', None) or info_process.get('url', None)
                    if use_url == song_url:
                        self._bot.log.warning("Determined incorrect entry type, but suggested url is the same.  Help.")
                        break # If we break here it will break things down the line and give "This is a playlist" exception as a result

                    self._bot.log.debug("Assumed url \"%s\" was a single entry, was actually a playlist" % song_url)
                    self._bot.log.debug("Using \"%s\" instead" % use_url)
                    song_url = use_url
                else:
                    break

            except Exception as e:
                if 'unknown url type' in str(e):
                    song_url = song_url.replace(':', '')  # it's probably not actually an extractor
                    info = await self.extract_info(song_url, download=False, process=False)
                else:
                    raise e

        if not info:
            raise ExtractionError("That video cannot be played. Try using the stream command.")

        # abstract the search handling away from the user
        # our ytdl options allow us to use search strings as input urls
        if info.get('url', '').startswith('ytsearch'):
            info = await self.extract_info(
                song_url,
                download=False,
                process=True,    # ASYNC LAMBDAS WHEN
                on_error=on_search_error,
                retry_on_error=True
            )

            if not info:
                raise ExtractionError(
                    "Error extracting info from search string, youtubedl returned no data. "
                    "You may need to restart the bot if this continues to happen."
                )

            if not all(info.get('entries', [])):
                # empty list, no data
                self._bot.log.debug("Got empty list, no data")
                return

            # TODO: handle 'webpage_url' being 'ytsearch:...' or extractor type
            song_url = info['entries'][0]['webpage_url']
            info = await self.extract_info(song_url, download=False, process=False)

        return (info, song_url)

class YtdlUrlEntry(Entry):
    def __init__(self, url, title, duration, queuer_id, metadata, extractor, expected_filename=None):
        self._extractor = extractor
        super().__init__(url, title, duration, queuer_id, metadata)
        self._download_folder = self._extractor.download_folder
        self._expected_filename = expected_filename

    def __json__(self):
        return self._enclose_json({
            'version': 2,
            'source_url': self.source_url,
            'title': self.title,
            'duration': self.duration,
            'queuer_id': self.queuer_id,
            'expected_file': self._expected_filename,
            '_full_local_url': os.path.abspath(self._local_url) if self._local_url else self._local_url,
            'meta': {
                name: obj for name, obj in self._metadata.items() if obj
            }
        })

    @classmethod
    def _deserialize(cls, data, extractor=None):
        assert extractor is not None, cls._bad('extractor')

        if 'version' not in data or data['version'] < 2:
            raise VersionError('data version needs to be higher than 2')

        try:
            # TODO: version check
            source_url = data['source_url']
            title = data['title']
            duration = data['duration']
            queuer_id = data['queuer_id']
            _expected_filename = data['expected_file']
            _local_url = data['_full_local_url']
            meta = {}

            # TODO: Better [name] fallbacks
            if 'channel_id' in data['meta']:
                meta['channel_id'] = int(data['meta']['channel_id'])
                if not meta['channel_id']:
                    extractor._bot.log.warning('Cannot find channel in an entry loaded from persistent queue. Chennel id: {}'.format(data['meta']['channel_id']))
                    meta.pop('channel_id')
            entry = cls(source_url, title, duration, queuer_id, meta, extractor, _expected_filename)

            return entry
        except Exception as e:
            extractor._bot.log.error("Could not load {}".format(cls.__name__), exc_info=e)

    async def _prepare(self):
        extractor = os.path.basename(self._expected_filename).split('-')[0]

        # the generic extractor requires special handling
        if extractor == 'generic':
            flistdir = [f.rsplit('-', 1)[0] for f in os.listdir(self._download_folder)]
            expected_fname_noex, fname_ex = os.path.basename(self._expected_filename).rsplit('.', 1)

            if expected_fname_noex in flistdir:
                try:
                    rsize = int(await get_header(self._extractor._bot.aiosession, self.source_url, 'CONTENT-LENGTH'))
                except:
                    rsize = 0

                lfile = os.path.join(
                    self._download_folder,
                    os.listdir(self._download_folder)[flistdir.index(expected_fname_noex)]
                )

                # print("Resolved %s to %s" % (self.expected_filename, lfile))
                lsize = os.path.getsize(lfile)
                # print("Remote size: %s Local size: %s" % (rsize, lsize))

                if lsize != rsize:
                    await self._really_download(hashing=True)
                else:
                    # print("[Download] Cached:", self.url)
                    await self.set_local_url(lfile)

            else:
                # print("File not found in cache (%s)" % expected_fname_noex)
                await self._really_download(hashing=True)

        else:
            ldir = os.listdir(self._download_folder)
            flistdir = [f.rsplit('.', 1)[0] for f in ldir]
            expected_fname_base = os.path.basename(self._expected_filename)
            expected_fname_noex = expected_fname_base.rsplit('.', 1)[0]

            # idk wtf this is but its probably legacy code
            # or i have youtube to blame for changing shit again

            self._extractor._bot.log.info("Expecting file: {} in {}".format(expected_fname_base, self._download_folder))

            if expected_fname_base in ldir:
                await self.set_local_url(os.path.join(self._download_folder, expected_fname_base))
                self._extractor._bot.log.info("Download cached: {}".format(self.source_url))

            elif expected_fname_noex in flistdir:
                self._extractor._bot.log.info("Download cached (different extension): {}".format(self.source_url))
                await self.set_local_url(os.path.join(self._download_folder, ldir[flistdir.index(expected_fname_noex)]))
                self._extractor._bot.log.debug("Expected {}, got {}".format(
                    self._expected_filename.rsplit('.', 1)[-1],
                    self._local_url.rsplit('.', 1)[-1]
                ))
            else:
                await self._really_download()

        if self.duration == None:
            if pymediainfo:
                try:
                    mediainfo = pymediainfo.MediaInfo.parse(self.filename)
                    self.duration = (mediainfo.tracks[0].duration)/1000
                except:
                    self.duration = None

            else:
                args = [
                    'ffprobe', 
                    '-i', self.filename, 
                    '-show_entries', 'format=duration', 
                    '-v', 'quiet', 
                    '-of', 'csv="p=0"'
                ]

                output = await run_command(' '.join(args))
                output = output.decode("utf-8")

                try:
                    self.duration = float(output)
                except ValueError:
                    # @TheerapakG: If somehow it is not string of float
                    self.duration = None

            if not self.duration:
                self._extractor._bot.log.error('Cannot extract duration of downloaded entry, invalid output from ffprobe or pymediainfo. '
                                                'This does not affect the ability of the bot. However, estimated time for this entry '
                                                'will not be unavailable and estimated time of the queue will also not be available '
                                                'until this entry got removed.\n'
                                                'entry file: {}'.format(self.filename))
            else:
                self._extractor._bot.log.debug('Get duration of {} as {} seconds by inspecting it directly'.format(self.filename, self.duration))

    async def prepare_cache(self):
        with self._threadlocks['preparing_cache_set']:
            if self._preparing_cache:
                return
            self._preparing_cache = True

        try:
            await self._prepare()
        finally:
            with self._threadlocks['preparing_cache_set']:
                with self._threadlocks['cached_set']:
                    self._preparing_cache = False
                    self._cached = True

    async def _really_download(self, *, hashing=False):
        self._extractor._bot.log.info("Download started: {}".format(self.source_url))

        retry = True
        while retry:
            try:
                result = await self._extractor.extract_info(self.source_url, download=True)
                break
            except Exception as e:
                raise e

        self._extractor._bot.log.info("Download complete: {}".format(self.source_url))

        if result is None:
            self._extractor._bot.log.critical("YTDL has failed, everyone panic")
            raise ExtractionError("ytdl broke and hell if I know why")
            # What the fuck do I do now?

        unhashed_fname = self._extractor.ytdl.prepare_filename(result)


        # TODO: check storage limit


        if hashing:
            # insert the 8 last characters of the file hash to the file name to ensure uniqueness
            await self.set_local_url(md5sum(unhashed_fname, 8).join('-.').join(unhashed_fname.rsplit('.', 1)))

            if os.path.isfile(self._local_url):
                # Oh bother it was actually there.
                os.unlink(unhashed_fname)
            else:
                # Move the temporary file to it's final location.
                os.rename(unhashed_fname, self._local_url)

        else:
            await self.set_local_url(unhashed_fname)

class YtdlUrlUnprocessedEntry(YtdlUrlEntry):
    def __init__(self, url, queuer_id, metadata, extractor):
        super().__init__(url, 'Information have not been fetched yet ({})'.format(url), None, queuer_id, metadata, extractor, None)

    def __json__(self):
        return self._enclose_json({
            'version': 1,
            'source_url': self.source_url,
            'title': self.title,
            'duration': self.duration,
            'queuer_id': self.queuer_id,
            'expected_file': self._expected_filename,
            '_full_local_url': os.path.abspath(self._local_url) if self._local_url else self._local_url,
            'meta': {
                name: obj for name, obj in self._metadata.items() if obj
            }
        })

    @classmethod
    def _deserialize(cls, data, extractor=None):
        assert extractor is not None, cls._bad('extractor')

        if 'version' not in data or data['version'] < 1:
            raise VersionError('data version needs to be higher than 2')

        try:
            # TODO: version check
            source_url = data['source_url']
            title = data['title']
            duration = data['duration']
            queuer_id = data['queuer_id']
            meta = {}

            # TODO: Better [name] fallbacks
            if 'channel_id' in data['meta']:
                meta['channel_id'] = int(data['meta']['channel_id'])
                if not meta['channel_id']:
                    extractor._bot.log.warning('Cannot find channel in an entry loaded from persistent queue. Chennel id: {}'.format(data['meta']['channel_id']))
                    meta.pop('channel_id')
            entry = cls(source_url, queuer_id, meta, extractor)
            entry.title = title
            entry.duration = duration

            return entry
        except Exception as e:
            extractor._bot.log.error("Could not load {}".format(cls.__name__), exc_info=e)

    async def prepare_cache(self):
        with self._threadlocks['preparing_cache_set']:
            if self._preparing_cache:
                return
            self._preparing_cache = True
            
        try:
            try:
                info = await self._extractor.extract_info(self.source_url, download=False)
            except Exception as e:
                raise ExtractionError('Could not extract information from {}\n\n{}'.format(self.source_url, e))

            if not info:
                raise ExtractionError('Could not extract information from %s' % self.source_url)

            # TODO: Sort out what happens next when this happens
            if info.get('_type', None) == 'playlist':
                raise WrongEntryTypeError("This is a playlist.", True, info.get('webpage_url', None) or info.get('url', None))

            if info.get('is_live', False):
                # TODO: return stream entry
                pass

            # TODO: Extract this to its own function
            if info['extractor'] in ['generic', 'Dropbox']:
                self._extractor._bot.log.debug('Detected a generic extractor, or Dropbox')
                try:
                    headers = await get_header(self._extractor._bot.aiosession, info['url'])
                    content_type = headers.get('CONTENT-TYPE')
                    self._extractor._bot.log.debug("Got content type {}".format(content_type))
                except Exception as e:
                    self._extractor._bot.log.warning("Failed to get content type for url {} ({})".format(self.source_url, e))
                    content_type = None

                if content_type:
                    if content_type.startswith(('application/', 'image/')):
                        if not any(x in content_type for x in ('/ogg', '/octet-stream')):
                            # How does a server say `application/ogg` what the actual fuck
                            raise ExtractionError("Invalid content type \"%s\" for url %s" % (content_type, self.source_url))

                    elif content_type.startswith('text/html') and info['extractor'] == 'generic':
                        self._extractor._bot.log.warning("Got text/html for content-type, this might be a stream.")
                        # TODO: return stream entry
                        pass

                    elif not content_type.startswith(('audio/', 'video/')):
                        self._extractor._bot.log.warning("Questionable content-type \"{}\" for url {}".format(content_type, self.source_url))
            
            self.title = info.get('title', 'Untitled')
            self.duration = info.get('duration', None) or None
            self._expected_filename = self._extractor.ytdl.prepare_filename(info)
            
            await self._prepare()
        finally:
            with self._threadlocks['preparing_cache_set']:
                with self._threadlocks['cached_set']:
                    self._preparing_cache = False
                    self._cached = True

class YtdlStreamEntry(Entry):
    def __init__(self, source_url, title, queuer_id, metadata, extractor, destination = None):
        self._extractor = extractor
        super().__init__(source_url, title, None, queuer_id, metadata, stream = True)
        self._destination = destination

    def __json__(self):
        return self._enclose_json({
            'version': 2,
            'source_url': self.source_url,
            'title': self.title,
            'queuer_id': self.queuer_id,
            'destination': self._destination,
            '_full_local_url': os.path.abspath(self._local_url) if self._local_url else self._local_url,
            'meta': {
                name: obj for name, obj in self._metadata.items() if obj
            }
        })

    @classmethod
    def _deserialize(cls, data, extractor=None):
        assert extractor is not None, cls._bad('extractor')

        if 'version' not in data or data['version'] < 2:
            raise VersionError('data version needs to be higher than 2')

        try:
            # TODO: version check
            source_url = data['source_url']
            title = data['title']
            queuer_id = data['queuer_id']
            _destination = data['destination']
            _local_url = data['_full_local_url']
            meta = {}

            # TODO: Better [name] fallbacks
            if 'channel_id' in data['meta']:
                meta['channel_id'] = int(data['meta']['channel_id'])
                if not meta['channel_id']:
                    extractor._bot.log.warning('Cannot find channel in an entry loaded from persistent queue. Chennel id: {}'.format(data['meta']['channel_id']))
                    meta.pop('channel_id')
            entry = cls(source_url, title, queuer_id, meta, extractor, _destination)

            return entry
        except Exception as e:
            extractor._bot.log.error("Could not load {}".format(cls.__name__), exc_info=e)

    async def prepare_cache(self):
        with self._threadlocks['preparing_cache_set']:
            if self._preparing_cache:
                return
            self._preparing_cache = True

        try:
            await self._really_download()

        finally:
            with self._threadlocks['preparing_cache_set']:
                with self._threadlocks['cached_set']:
                    self._preparing_cache = False
                    self._cached = True

    async def _really_download(self, *, fallback=False):
        url = self._destination if fallback else self.source_url

        try:
            result = await self._extractor.extract_info(url, download=False)
        except Exception as e:
            if not fallback and self._destination:
                return await self._really_download(fallback=True)

            raise e
        else:
            await self.set_local_url(result['url'])
            # I might need some sort of events or hooks or shit
            # for when ffmpeg inevitebly fucks up and i have to restart
            # although maybe that should be at a slightly lower level

class LocalEntry(Entry):
    def __init__(self, source_url, queuer_id, metadata):
        super().__init__(source_url, source_url, None, queuer_id, metadata, local = True)

    def __json__(self):
        return self._enclose_json({
            'version': 1,
            'source_url': self.source_url,
            'queuer_id': self.queuer_id,
            '_full_local_url': os.path.abspath(self._local_url) if self._local_url else self._local_url,
            'meta': {
                name: obj for name, obj in self._metadata.items() if obj
            }
        })

    @classmethod
    def _deserialize(cls, data, extractor=None):
        assert extractor is not None, cls._bad('extractor')

        if 'version' not in data or data['version'] < 2:
            raise VersionError('data version needs to be higher than 2')

        try:
            # TODO: version check
            source_url = data['source_url']
            queuer_id = data['queuer_id']
            _local_url = data['_full_local_url']
            meta = {}

            # TODO: Better [name] fallbacks
            if 'channel_id' in data['meta']:
                meta['channel_id'] = int(data['meta']['channel_id'])
                if not meta['channel_id']:
                    extractor._bot.log.warning('Cannot find channel in an entry loaded from persistent queue. Chennel id: {}'.format(data['meta']['channel_id']))
                    meta.pop('channel_id')
            entry = cls(source_url, queuer_id, meta)

            return entry
        except Exception as e:
            extractor._bot.log.error("Could not load {}".format(cls.__name__), exc_info=e)

    async def prepare_cache(self):
        async with self._aiolocks['preparing_cache_set']:
            if self._preparing_cache:
                return
            self._preparing_cache = True

        self._local_url = self.source_url

        async with self._aiolocks['preparing_cache_set']:
            async with self._aiolocks['cached_set']:
                self._preparing_cache = False
                self._cached = True

class WrongEntryTypeError(Exception):
    def __init__(self, message, is_playlist, use_url):
        super().__init__(message)
        self.is_playlist = is_playlist
        self.use_url = use_url


async def get_stream_entry(song_url, queuer_id, extractor, metadata):
    info = {'title': song_url, 'extractor': None}

    try:
        info = await extractor.extract_info(song_url, download=False)

    except DownloadError as e:
        if e.exc_info[0] == UnsupportedError:  # ytdl doesn't like it but its probably a stream
            extractor._bot.log.debug("Assuming content is a direct stream")

        elif e.exc_info[0] == URLError:
            if os.path.exists(os.path.abspath(song_url)):
                raise ExtractionError("This is not a stream, this is a file path.")

            else:  # it might be a file path that just doesn't exist
                raise ExtractionError("Invalid input: {0.exc_info[0]}: {0.exc_info[1].reason}".format(e))

        else:
            # traceback.print_exc()
            raise ExtractionError("Unknown error: {}".format(e))

    except Exception as e:
        extractor._bot.log.error('Could not extract information from {} ({}), falling back to direct'.format(song_url, e), exc_info=True)

    if info.get('is_live') is None and info.get('extractor', None) != 'generic':  # wew hacky
        raise ExtractionError("This is not a stream.")

    dest_url = song_url
    if info.get('extractor'):
        dest_url = info.get('url')

    if info.get('extractor', None) == 'twitch:stream':  # may need to add other twitch types
        title = info.get('description')
    else:
        title = info.get('title', 'Untitled')

    # TODO: A bit more validation, "~stream some_url" should not just say :ok_hand:
    entry = YtdlStreamEntry(
        song_url,
        title,
        queuer_id,
        metadata,
        extractor,
        destination = dest_url
    )

    return entry

async def get_entry(song_url, queuer_id, extractor, metadata):
    try:
        info = await extractor.extract_info(song_url, download=False)
    except Exception as e:
        raise ExtractionError('Could not extract information from {}\n\n{}'.format(song_url, e))

    if not info:
        raise ExtractionError('Could not extract information from %s' % song_url)

    # TODO: Sort out what happens next when this happens
    if info.get('_type', None) == 'playlist':
        raise WrongEntryTypeError("This is a playlist.", True, info.get('webpage_url', None) or info.get('url', None))

    if info.get('is_live', False):
        return await get_stream_entry(song_url, queuer_id, extractor, metadata)

    # TODO: Extract this to its own function
    if info['extractor'] in ['generic', 'Dropbox']:
        extractor._bot.log.debug('Detected a generic extractor, or Dropbox')
        try:
            headers = await get_header(extractor._bot.aiosession, info['url'])
            content_type = headers.get('CONTENT-TYPE')
            extractor._bot.log.debug("Got content type {}".format(content_type))
        except Exception as e:
            extractor._bot.log.warning("Failed to get content type for url {} ({})".format(song_url, e))
            content_type = None

        if content_type:
            if content_type.startswith(('application/', 'image/')):
                if not any(x in content_type for x in ('/ogg', '/octet-stream')):
                    # How does a server say `application/ogg` what the actual fuck
                    raise ExtractionError("Invalid content type \"%s\" for url %s" % (content_type, song_url))

            elif content_type.startswith('text/html') and info['extractor'] == 'generic':
                extractor._bot.log.warning("Got text/html for content-type, this might be a stream.")
                # TODO: return stream entry
                pass

            elif not content_type.startswith(('audio/', 'video/')):
                extractor._bot.log.warning("Questionable content-type \"{}\" for url {}".format(content_type, song_url))

    entry = YtdlUrlEntry(
        song_url,
        info.get('title', 'Untitled'),
        info.get('duration', None) or None,
        queuer_id,
        metadata,
        extractor,
        extractor.ytdl.prepare_filename(info)
    )

    return entry

async def get_unprocessed_entry(song_url, queuer_id, extractor, metadata):
    entry = YtdlUrlUnprocessedEntry(
        song_url,
        queuer_id,
        metadata,
        extractor
    )

    return entry

async def get_entry_list_from_playlist_url(playlist_url, queuer_id, extractor, metadata):
    entry_list = []

    try:
        info = await extractor.safe_extract_info(playlist_url, download=False)
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
                entry = YtdlUrlEntry(
                    item[url_field],
                    item.get('title', 'Untitled'),
                    item.get('duration', None) or None,
                    queuer_id,
                    metadata,
                    extractor,
                    extractor.ytdl.prepare_filename(info)
                )
                entry_list.append(entry)
            except Exception as e:
                baditems += 1
                extractor._bot.log.warning("Could not add item", exc_info=e)
                extractor._bot.log.debug("Item: {}".format(item), exc_info=True)
        else:
            baditems += 1

    if baditems:
        extractor._bot.log.info("Skipped {} bad entries".format(baditems))

    return entry_list

async def get_local_entry(song_url, queuer_id, metadata):

    entry = LocalEntry(
        song_url,
        queuer_id,
        metadata
    )

    return entry