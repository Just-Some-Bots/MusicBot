import asyncio
import discord
import collections
import configparser
import re
import functools
import datetime
import youtube_dl
import os
import traceback
import inspect
import unicodedata
import array
from random import shuffle
from concurrent.futures import ThreadPoolExecutor
from discord.object import Object
from discord.voice_client import VoiceClient
from discord.enums import ChannelType
from discord import utils

if not discord.opus.is_loaded():
    opus_libs = ['libopus-0.x86.dll', 'libopus-0.x64.dll', 'libopus.so.0', '/usr/lib/libopus.so.0', '/usr/local/lib/libopus.0.dylib']
    # maybe add mlocate support

    opus_loaded = False
    for opus_lib in opus_libs:
        try:
            discord.opus.load_opus(opus_lib)
            opus_loaded = True
            break
        except OSError:
            pass

    if not opus_loaded:
        raise RuntimeError('Could not load an opus lib. Tried %s' % (', '.join(opus_libs)))

VERSION = '2.0'

def load_file(filename):
    try:
        with open(filename) as f:
            results = []
            for line in f:
                line = line.strip()
                if line:
                    results.append(line)

            return results

    except IOError as e:
        print ("Error loading", filename, e)
        return []

def write_file(filename, contents):
    with open(filename, 'w') as f:
        for item in contents:
            f.write(item)
            f.write('\n')

_USER_ID_MATCH = re.compile(r'\<\@(\d+)\>')
def extract_user_id(argument):
    match = _USER_ID_MATCH.match(argument)
    if match:
        return long(match.group(1))

def slugify(value):
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub('[^\w\s-]', '', value).strip().lower()
    return re.sub('[-\s]+', '-', value)

class CommandError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__()


AUDIO_CACHE_PATH = os.path.join(os.getcwd(), 'audio_cache')
DEFAULT_VOLUME = 0.10

ytdl_format_options = {
    'format': 'bestaudio/best',
    'extractaudio': True,
    'audioformat': "mp3",
    'outtmpl': '%(id)s',
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': True,
    'quiet': True,
    'no_warnings': True
}

thread_pool = ThreadPoolExecutor(max_workers=2)
ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

def extract_info(loop, *args, **kwargs):
    """
        Runs ytdl.extract_info within the threadpool. Returns a future that will fire when it's done.
    """
    return loop.run_in_executor(thread_pool, functools.partial(ytdl.extract_info, *args, **kwargs))


class EventEmitter(object):
    def __init__(self):
        self._events = collections.defaultdict(list)

    def emit(self, event, *args, **kwargs):
        if event not in self._events:
            return

        for cb in self._events[event]:
            try:
                cb(*args, **kwargs)

            except:
                traceback.print_exc()


    def on(self, event, cb):
        self._events[event].append(cb)
        return self

    def off(self, event, cb):
        self._events[event].remove(cb)

        if not self._events[event]:
            del self._events[event]

        return self

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

    @asyncio.coroutine
    def add_entry(self, song_url, **meta):
        """
            Validates and adds a song_url to be played. This does not start the download of the song.

            Returns the entry & the position it is in the queue.
        """
        info = yield from extract_info(self.loop, song_url, download=False)
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

    @asyncio.coroutine
    def import_from(self, playlist_url, **meta):
        """
            Imports the songs from `playlist_url` and queues them to be played. Returns a list of `entries` that have been enqueued.
        """
        pass

    def _add_entry(self, entry):
        self.entries.append(entry)
        self.emit('entry-added', playlist=self, entry=entry)

        if self.peek() is entry:
            entry.get_ready_future()

    @asyncio.coroutine
    def get_next_entry(self, predownload_next=True):
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

        entry = yield from entry.get_ready_future()
        return entry

    def peek(self):
        """
            Returns the next entry that should be scheduled to be played.
        """
        if self.entries:
            return self.entries[0]

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

    @asyncio.coroutine
    def _download(self):
        if self._is_downloading:
            return

        self._is_downloading = True
        try:
            result = yield from extract_info(self.playlist.loop, self.url, download=True)
            filename = self.filename

            # If the file existed, we're going to remove it to overwrite.
            if os.path.isfile(filename):
                os.path.unlink(filename)

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


class PatchedBuff(object):
    """
        PatchedBuff monkey patches a readable object, allowing you to vary what the volume is as the song is playing.
    """
        
    def __init__(self, player, buff):
        self.player = player
        self.buff = buff

    def read(self, frame_size):
        frame = self.buff.read(frame_size)

        volume = self.player.volume
        # Only make volume go down. Never up. 
        if volume < 1.0:
            # Ffmpeg returns s16le pcm frames.
            frame_array = array.array('h', frame)

            for i in range(len(frame_array)):
                frame_array[i] = int(frame_array[i] * volume)

            frame = frame_array.tobytes()

        return frame


class MusicPlayer(EventEmitter):
    class States(object):
        # TODO: Maybe use enum3?

        STOPPED = 0  # When the player isn't playing anything
        PLAYING = 1  # The player is actively playing music.
        PAUSED = 2   # The player is paused on a song.

        @classmethod
        def to_human(cls, state):
            if state == cls.STOPPED:
                return 'STOPPED'

            if state == cls.PLAYING:
                return 'PLAYING'

            if state == cls.PAUSED:
                return 'PAUSED'

            raise ValueError('Unknown state %s' % state)

    def __init__(self, bot, voice_client, playlist, volume=DEFAULT_VOLUME):
        super().__init__()
        self.bot = bot
        self.loop = bot.loop
        self.voice_client = voice_client
        self.playlist = playlist
        self.playlist.on('entry-added', self.on_entry_added)
        self._current_player = None
        self._current_entry = None
        self._state = MusicPlayer.States.STOPPED
        self.volume = volume

    def on_entry_added(self, playlist, entry):
        if self.is_stopped:
            self.loop.create_task(self.play())

    def skip(self):
        self._kill_current_player()

    def stop(self):
        self._state = MusicPlayer.States.STOPPED
        self._kill_current_player()

        self.emit('stop', player=self)

    def resume(self):
        if self.is_paused and self._current_player:
            self._current_player.resume()
            self._state = MusicPlayer.States.PLAYING
            self.emit('resume', player=self, entry=self.current_entry)
            return

        raise ValueError('Cannot resume playback from state %s' % self.state)

    def _playback_finished(self):
        self._current_player = None
        entry = self._current_entry
        self._current_entry = None
        if not self.is_stopped:
            self.loop.create_task(self.play(_continue=True))

        self.emit('finished-playing', player=self, entry=entry)

    @asyncio.coroutine
    def play(self, _continue=False):
        """
            Plays the next entry from the playlist, or resumes playback of the current entry if paused.
        """
        if self.is_paused:
            return self.resume()

        if self.is_stopped or _continue:
            try:
                entry = yield from self.playlist.get_next_entry()

            except Exception as e:
                print("Failed to get entry.")
                traceback.print_exc()
                # Retry playing the next entry in a sec.
                self.loop.call_later(1, lambda: self.loop.create_task(self.play()))
                return

            # If nothing left to play, transition to the stopped state.
            if not entry:
                self.stop()
                return

            self._state = MusicPlayer.States.PLAYING
            self._current_entry = entry

            # Incase there was a player, kill it. RIP.
            self._kill_current_player()

            self._current_player = self._monkeypatch_player(self.voice_client.create_ffmpeg_player(
                entry.filename,
                #  Threadsafe call soon, b/c after will be called from the voice playback thread.
                after=lambda: self.bot.loop.call_soon_threadsafe(self._playback_finished)
            ))
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
        return self._state == MusicPlayer.States.PLAYING

    @property
    def is_paused(self):
        return self._state == MusicPlayer.States.PAUSED

    @property
    def is_stopped(self):
        return self._state == MusicPlayer.States.STOPPED

    def pause(self):
        if self.is_playing:
            self._state = MusicPlayer.States.PAUSED

            if self._current_player:
                self._current_player.pause()

            self.emit('pause', player=self, entry=self.current_entry)
            return

        elif self.is_paused:
            return

        raise ValueError('Cannot pause a MusicPlayer in state %s' % self.state)

    @property
    def state(self):
        return MusicPlayer.States.to_human(self._state)

    def current_song(self):
        if self.is_playing or self.is_paused:
            return self._current_song

        return None

    def _kill_current_player(self):
        if self._current_player:
            self._current_player.stop()
            self._current_player = None
            return True

        return False


class SkipState(object):
    def __init__(self):
        self.skippers = set()

    @property
    def skip_count(self):
        return len(self.skippers)

    def reset(self):
        self.skippers.clear()

    def add_skipper(self, skipper):
        self.skippers.add(skipper)
        return self.skip_count


class MusicBot(discord.Client):

    helpmessage = (
        '`!play [youtube link]` will allow me to play a new song or add it to the queue.\n'
        '`!playlist` will print out all links to youtube videos currently in the queue!\n'
        '`!play skip` will make it skip to the next song after {} people vote to skip the current one!')

    def __init__(self):
        super().__init__()
        
        self.players = {}
        self.voice_clients = {}
        self.voice_client_connect_lock = asyncio.Lock()

        self.volume = 0.10
        self.skipCount = 0
        self.firstTime = None
        self.skipperlist = []

        self.load_settings()

        if not os.path.exists(self.video_folder):
            os.makedirs(self.video_folder)

    @asyncio.coroutine
    def get_voice_client(self, channel):
        if isinstance(channel, Object):
            channel = self.get_channel(channel.id)

        if getattr(channel, 'type', ChannelType.text) != ChannelType.voice:
            raise AttributeError('Channel passed must be a voice channel')
        
        with (yield from self.voice_client_connect_lock):
            server = channel.server
            if server.id in self.voice_clients:
                return self.voice_clients[server.id]
        
            payload = {
                'op': 4,
                'd': {
                    'guild_id': channel.server.id,
                    'channel_id': channel.id,
                    'self_mute': False,
                    'self_deaf': False
                }
            }
    
            yield from self.ws.send(utils.to_json(payload))
            yield from asyncio.wait_for(self._session_id_found.wait(), timeout=5.0, loop=self.loop)
            yield from asyncio.wait_for(self._voice_data_found.wait(), timeout=5.0, loop=self.loop)
            
            session_id = self.session_id
            voice_data = self._voice_data_found.data
    
            self._session_id_found.clear()
            self._voice_data_found.clear()
    
            kwargs = {
                'user': self.user,
                'channel': channel,
                'data': voice_data,
                'loop': self.loop,
                'session_id': session_id,
                'main_ws': self.ws
            }
    
            voice_client = VoiceClient(**kwargs)
            self.voice_clients[server.id] = voice_client
            yield from voice_client.connect()
            return voice_client

    @asyncio.coroutine
    def get_player(self, channel, create=False):
        server = channel.server
        
        if server.id not in self.players:
            if not create:
                raise KeyError('Player does not exist. It has not been summoned yet into a voice channel.')
            
            voice_client = yield from self.get_voice_client(channel)
            
            playlist = Playlist(self.loop)
            player = MusicPlayer(self, voice_client, playlist) \
                .on('play', self.on_play) \
                .on('resume', self.on_resume) \
                .on('pause', self.on_pause) \
                .on('stop', self.on_stop)
                
            player.skip_state = SkipState()
            self.players[server.id] = player
        
        return self.players[server.id]

    def on_play(self, player, entry):
        self.update_now_playing(entry)
        player.skip_state.reset()
        
        self.loop.create_task(self.send_message(entry.meta['channel'], '%s - your song %s is now playing!' % (
            entry.meta['author'].mention, entry.title
        )))
        

    def on_resume(self, player, entry):
        self.update_now_playing(entry)

    def on_pause(self, player, entry):
        self.update_now_playing(entry, True)

    def on_stop(self, player):
        self.update_now_playing()

    def update_now_playing(self, entry=None, is_paused=False):
        game = None
        if entry:
            prefix = u'\u275A\u275A ' if is_paused else ''

            name = u'{}{}'.format(prefix, entry.title)[:128]
            game = discord.Game(name=name)

        self.loop.create_task(self.change_status(game))

    def load_settings(self):
        # TODO: Dump default file if no options file exists

        self.blacklist = set(map(int, load_file('blacklist.txt')))
        self.whitelist = set(map(int, load_file('whitelist.txt')))
        self.backuplist = set(load_file('backuplist.txt'))

        # Loads configuration from a the options.txt
        # Example:
        # =========================================
        # [DEFAULT]
        # Username = test123
        # Password = mdypassw
        # DaysActive = 4
        # OwnerID = 112341234134
        # WhiteListCheck = yes
        # SkipsRequired = 7
        # SkipRatio = 0.5
        # CommandPrefix = !
        # SaveVideos = yes
        # VideoFolder = playlist

        # TODO: Resume on restart

        config = configparser.ConfigParser()
        config.read('options.txt')

        self.username = config.get('DEFAULT', 'Username', fallback=None)
        self.password = config.get('DEFAULT', 'Password', fallback=None)

        self.days_active = config.getint('DEFAULT', 'DaysActive', fallback=0)
        self.owner_id = config.get('DEFAULT', 'OwnerID')
        self.whitelistcheck = config.getboolean('DEFAULT', 'WhiteListCheck', fallback=False)
        self.skips_required = config.getint('DEFAULT', 'SkipsRequired', fallback=7)
        self.skip_ratio_required = config.getfloat('DEFAULT', 'SkipRatio', fallback=0.5)
        self.command_prefix = config.get('DEFAULT', 'CommandPrefix', fallback='!')
        self.save_videos = config.getboolean('DEFAULT', 'SaveVideos', fallback=True)
        self.video_folder = config.get('DEFAULT', 'VideoFolder', fallback='playlist')

        self.helpmessage = self.__class__.helpmessage.format(self.skips_required)

        # Validation logic for bot settings.
        if not self.username or not self.password:
            raise ValueError('A username or password was not specified in ihe configuration file.')

        if not self.owner_id:
            raise ValueError("An owner is not specified in the configuration file")

    def run(self):
        return super().run(self.username, self.password)

    @asyncio.coroutine
    def on_ready(self):
        print('Connected!')
        print('Username: ' + self.user.name)
        print('ID: ' + self.user.id)
        print('--Server List--')
        for server in self.servers:
            print(server.name)

    @asyncio.coroutine
    def handle_message(self, message):
        command, *args = message.content.split()
        if not command.startswith(self.command_prefix):
            return

        command = command[len(self.command_prefix):].lower().strip()

        handler = getattr(self, 'handle_%s' % command, None)
        if not handler:
            return

        argspec = inspect.getargspec(handler)
        expected_args = len(argspec.args) - 2
        if not argspec.varargs and len(args) != expected_args:
            docs = getattr(handler, '__doc__', None)
            if not docs:
                docs = '!%s requires %s argument%s' % (command, expected_args, '' if expected_args == '1' else 's')

            yield from self.send_message(message.channel, '```\n%s\n```' % docs.strip().format(command_prefix=self.command_prefix))
            return

        try:
            handler = asyncio.coroutine(handler)
            yield from handler(message, *args)

        except CommandError as e:
            yield from self.send_message(message.channel, '```\n%s\n```' % e.message)

        except Exception as e:
            yield from self.send_message(message.channel, '```\n%s\n```' % traceback.format_exc())
            traceback.print_exc()
            pass


    # Stub
    def handle_(self, message, args):
        pass


    def handle_whitelist(self, message, username):
        """
        Usage: {command_prefix}whitelist @UserName
        Adds the user to the whitelist, permitting them to add songs.
        """
        user_id = extract_user_id(username)
        if not user_id:
            raise CommandError('Invalid user specified')

        self.whitelist.add(user_id)
        write_file('whitelist.txt', self.whitelist)

    def handle_blacklist(self, message, username):
        """
        Usage: {command_prefix}blacklist @UserName
        Adds the user to the blacklist, forbidding them from using bot commands.
        """
        user_id = extract_user_id(username)
        if not user_id:
            raise CommandError('Invalid user specified')

        self.whitelist.add(user_id)
        write_file('blacklist.txt', self.whitelist)

    def handle_joinserver(self, message, server_link):
        """
        Usage {command_prefix}joinserver [Server Link]
        Asks the bot to join a server. [todo: add info about if it breaks or whatever]
        """
        try:
            yield from self.accept_invite(server_link)

        except:
            raise CommandError('Invalid URL provided:\n{}\n'.format(server_link))


    ##Mutliple servers supported, command depreciated
    #def handle_servers(self, message, args):
    #    """
    #    Usage: !servers#
    #    """
    #    if len(self.servers) > 1 and self.user.id != '127715185115791363':
    #      yield from self.send_message(message.channel, "I DIDN'T LISTEN TO DIRECTIONS AND HAVE MY BOT ON MORE THAN ONE SERVER")
    #    pass


    def handle_play(self, message, song_url):
        """
        Usage {command_prefix}play [song link]
        Adds the song to the playlist. [todo: list accepted data formats, full url, id, watch?v=id, etc]
        """
        player = yield from self.get_player(message.channel)
        
        try:
            yield from self.send_typing(message.channel)
            
            entry, position = yield from player.playlist.add_entry(song_url, channel=message.channel, author=message.author)
            if position == 1 and player.is_stopped:
                position = 'Up next!'
                
            #time_until = self.playlist.estimate_time_until(position)
            
            yield from self.send_message(message.channel, 'Enqueued **%s** to be played. Position in queue: %s - estimated time until playing %s' % (
                entry.title, position, '0:00' # todo: implement me.
            ))

        except Exception:
            raise CommandError('Unable to queue up song at %s to be played.' % song_url)

    #TODO: Update once Playlist objects are completed
    def handle_playlist(self, message, args):
        """
        Usage: {command_prefix}playlist
        Prints the playlist into chat.
        """

        # TODO: JAKE FIX THIS.
        msglist = []
        playlistmsgstorage = []
        endmsg = self.currentlyPlaying
        count = 1

        for titles in self.playlistnames:
            print(len(endmsg))
            if len(endmsg) > 1500:
                msglist.append(endmsg)
                endmsg = ''
            else:
                endmsg = endmsg + str(count) + ":  " + titles + " \n"
                count += 1

        msglist.append(endmsg)

        for items in msglist:
            temp = yield from self.send_message(message.channel, items)
            playlistmsgstorage.append(temp)

        try:
            yield from self.delete_message(message)
        except:
            print('Error: Cannot delete messages!')

        yield from asyncio.sleep(15)

        for msgs in playlistmsgstorage:
            yield from self.delete_message(msgs)
        pass

    def handle_summon(self, message):
        """
        Usage {command_prefix}summon
        This command is for summoning the bot into your voice channel [but it should do it automatically the first time]
        """
        if self.voice_clients:
            raise CommandError("Multiple servers not supported at this time.")
        
        server = message.channel.server
        
        channel = None
        for channel in server.channels:
            if discord.utils.get(channel.voice_members, id=message.author.id):
                break
            
        if not channel:
            raise CommandError('You are not in a voice channel!')
        
        player = yield from self.get_player(channel, create=True)
        
        if player.is_stopped:
            yield from player.play()
            
    def handle_pause(self, message):
        """
        Usage {command_prefix}pause
        Pauses playback of the current song. [todo: should make sure it works fine when used inbetween songs]
        """
        player = yield from self.get_player(message.channel)
        
        if player.is_playing:
            player.pause()
            
        else:
            raise CommandError('Player is not playing.')

    def handle_resume(self, message):
        """
        Usage {command_prefix}resume
        Resumes playback of a paused song.
        """
        player = yield from self.get_player(message.channel)
        
        if player.is_paused:
            player.resume()
        else:
            raise CommandError('Player is not paused.')

    def handle_shuffle(self, message):
        """
        Usage {command_prefix}shuffle
        Shuffles the playlist.
        """
        player = yield from self.get_player(message.channel)
        player.playlist.shuffle()

    def handle_skip(self, message):
        """
        Usage {command_prefix}skip
        Skips the current song when enough votes are cast, or by the bot owner.
        """
        player = yield from self.get_player(message.channel)
        
        if player.is_stopped:
            raise CommandError("Can't skip! The player is not playing!")
        
        if message.author.id == self.owner_id:
            player.skip()
            return
        
        voice_channel = player.voice_client.channel
        
        num_voice = sum(1 for m in voice_channel.voice_members if not (m.deaf or m.self_deaf))
        num_skips = player.skip_state.add_skipper(message.author.id)
        
        skips_required = min(self.skip_ratio_required, int(num_voice * self.skip_ratio_required))
        
        if num_skips >= skips_required:
            player.skip()
            
        else:
            self.send_message(message.channel, 'Skip acknowledged - %s more skips required to vote to skip this song.' % skips_required)

    def handle_volume(self, message, new_volume=None):
        """
        Usage {command_prefix}volume (+/-)[volume]
        Sets the playback volume. Accepted values are from 1 to 100. 
        Putting + or - before the volume will make the volume change relative to the current volume.
        """

        # TODO: Add relative volume change, +5, -10, etc
        
        player = yield from self.get_player(message.channel)
        
        relative = False
        if new_volume[0] in '+-':
            relative = True
        
        if new_volume is None:
            yield from self.send_message(message.channel, 'Current volume: %s' % player.volume)
            return
        
        try:
            new_volume = int(new_volume)
            
        except ValueError:
            raise CommandError('{} is not a valid number'.format(new_volume))
                
        if relative:
            new_volume = (player.volume * 100) + new_volume
        
        if 0 < new_volume <= 100:
            old_volume = int(player.volume * 100)
            player.volume = new_volume / 100.0
            
            yield from self.send_message(message.channel, 'Updated volume from %s to %s' % (old_volume, new_volume))
            
        else:
            raise CommandError('Unreasonable volume provided {}%. Provide a value between 1 and 100.'.format(new_volume))

    @asyncio.coroutine
    def on_ready(self):
        pass

    @asyncio.coroutine
    def on_message(self, message):
        if message.author == self.user:
            return

        if message.channel.is_private:
            yield from self.send_message(message.channel, 'You cannot use this bot in private messages.')
            
        yield from self.handle_message(message)

        # if message.content.lower().startswith('!whatismyuserid'):
        #     print('HELLO, ' + message.author.name + ' THE ID YOU NEED TO USE IS ' + message.author.id)

        # elif message.content.lower().startswith('!creator'):
        #     yield from self.send_message(message.channel,
        #         'I was coded by SexualRhinoceros and am currently on rev{}! Go here for more info: https://github.com/SexualRhinoceros/MusicBot'.format(VERSION))

        # ownerLocation = None
        # channelLocation = None

        # # TODO:  Fix this shitty algorithm.
        # for server in self.servers:
        #     for channel in server.channels:
        #         pre = discord.utils.get(channel.voice_members, id=self.owner_id)
        #         ownerLocation = pre.server if pre else None
        #         if ownerLocation and channel.type == discord.ChannelType.voice:
        #             channelLocation = channel
        #             break
        #     if ownerLocation: break

        # margs = message.content.split(' ')[1:]

        # if message.server == ownerLocation:
        #     if message.content.lower().startswith('!joinserver') and message.author.id == self.owner_id:
        #         msg = ''.join(margs).strip()
        #         try:
        #             print(msg)
        #             yield from self.accept_invite(msg)
        #         except:
        #             print('Ya dun fucked up with the URL:\n{}\n'.format(msg))

        #     elif message.content.lower().startswith('!servers') and message.author.id == '77511942717046784':
        #         if len(self.servers) > 1 and self.user.id != '127715185115791363':
        #             yield from self.send_message(message.channel, "I DIDN'T LISTEN TO DIRECTIONS AND HAVE MY BOT ON MORE THAN ONE SERVER")
        #         else:
        #             print("You good don't worry fam")

        #     elif message.content.lower().startswith('!playlist'):
        #         print('GETTING PLAYLIST: If this is large the bot WILL hang')

        #         msglist = []
        #         playlistmsgstorage = []
        #         endmsg = self.currentlyPlaying
        #         count = 1

        #         for titles in self.playlistnames:
        #             print(len(endmsg))
        #             if len(endmsg) > 1500:
        #                 print('doot')
        #                 msglist.append(endmsg)
        #                 endmsg = ''
        #             else:
        #                 endmsg = endmsg + str(count) + ":  " + titles + " \n"
        #                 count += 1

        #         msglist.append(endmsg)

        #         for items in msglist:
        #             temp = yield from self.send_message(message.channel, items)
        #             playlistmsgstorage.append(temp)

        #         try:
        #             yield from self.delete_message(message)
        #         except:
        #             print('Error: Cannot delete messages!')

        #         yield from asyncio.sleep(15)

        #         for msgs in playlistmsgstorage:
        #             yield from self.delete_message(msgs)

        #     elif message.content.lower().startswith('!play'):
        #         msg = ''.join(margs).strip()

        #         if message.author.id in self.blacklist:
        #             print('No, blacklisted.')
        #             return

        #         if self.whitelistcheck and message.author.id != self.owner_id:
        #             if not self._is_long_member(message.author.joined_at) and message.author.id not in self.whitelist:
        #                 print('no, not whitelisted and new')
        #                 return

        #         if len(margs) and margs[0].lower() == 'help':
        #             hotsmessage = yield from self.send_message(message.channel, self.helpmessage)
        #             yield from asyncio.sleep(10)
        #             yield from self.delete_message(hotsmessage)

        #         elif message.author.id == self.owner_id and self.firstTime:
        #             yield from self.join_voice_channel(channelLocation)

        #             self.firstTime = False

        #             if len(margs) and margs[0].lower() == 'playlist':
        #                 print('Playlist detected, attempting to parse all URLs. ERRORS MAY OCCUR!')
        #                 info = self.ytdl.extract_info(msg, download=False)

        #                 try:
        #                     boolfirst = True
        #                     for items in info['entries']:
        #                         if boolfirst:
        #                             boolfirst=False
        #                             self.playlist.append(items['webpage_url'])
        #                         else:
        #                             self.playlist.append(items['webpage_url'])
        #                             self.playlistnames.append(items['title'])
        #                 except:
        #                     print('Error with one URL, continuing processing!')

        #                 print('Playlist Processing finished!')

        #             else:
        #                 self.update_names(msg)

        #         elif len(margs) and margs[0].lower() == 'move' and message.author.id == self.owner_id:
        #             #self.option = 'pause'
        #             #self.playlist_update() 
        #             if self.voice:
        #                 yield from self.voice.disconnect()

        #             yield from self.join_voice_channel(channelLocation)

        #             #self.option = 'resume'
        #             #self.playlist_update()

        #         else:
        #             if len(margs) and margs[0].lower() == 'playlist':
        #                 print('Playlist detected, attempting to parse all URLs. ERRORS MAY OCCUR!')
        #                 try:
        #                     info = self.ytdl.extract_info(msg, download=False)
        #                     boolfirst = True

        #                     for items in info['entries']:
        #                         if boolfirst:
        #                             boolfirst=False
        #                             self.playlist.append(items['webpage_url'])
        #                         else:
        #                             self.playlist.append(items['webpage_url'])
        #                             self.playlistnames.append(items['title'])
        #                 except:
        #                     print('Error with one URL, continuing processing!')

        #                 print('Playlist Processing finished!')

        #             else:
        #                 # print(self.playlist.add_entry(margs[0]))
        #                 yield from self.playlist.add_entry(margs[0])

        #         yield from asyncio.sleep(5)

        #         try:
        #             yield from self.delete_message(message)
        #         except:
        #             print("Couldn't delete message for some reason")


    def _is_long_member(self, dateJoined):
        convDT = dateJoined.date()
        today = datetime.date.today()
        margin = datetime.timedelta(days=int(self.options[3]))
        return today - margin > convDT

if __name__ == '__main__':
    bot = MusicBot()
    bot.run() # TODO: Make that less hideous

# TODO: add audio stingers between songs
