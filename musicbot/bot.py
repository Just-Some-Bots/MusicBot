import time
import inspect
import traceback
import asyncio
import discord
import sys

from discord import utils
from discord.enums import ChannelType
from discord.object import Object
from discord.voice_client import VoiceClient

from musicbot.config import Config
from musicbot.player import MusicPlayer
from musicbot.playlist import Playlist
from musicbot.utils import load_file, extract_user_id, write_file

from .downloader import extract_info
from .exceptions import CommandError
from .exceptions import CommandInfo #X4: Custom exception for non-warning end of function
from .constants import DISCORD_MSG_CHAR_LIMIT
from .opus_loader import load_opus_lib

from random import choice
from datetime import timedelta

import configparser #X4: Import ConfigParser for work with language file
import codecs #X4: Import codecs for work with UTF-8 language file

# if sys.platform.startswith('win'):
#     import win_unicode_console
#     win_unicode_console.enable()

VERSION = '2.0'

load_opus_lib()

undoentry = None #X4: Used for undo tracks
langconf = configparser.ConfigParser() #X4: Define new ConfigParser element
langconf.readfp(codecs.open('config/userlang.txt', "r", "utf8")) #X4: Read our config as UTF-8-file

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


class Response(object):
    def __init__(self, content, reply=False, delete_after=0):
        self.content = content
        self.reply = reply
        self.delete_after = delete_after


class MusicBot(discord.Client):
    def __init__(self, config_file='config/options.txt'):
        super().__init__()

        self.players = {}
        self.voice_clients = {}
        self.voice_client_connect_lock = asyncio.Lock()
        self.config = Config(config_file)

        self.blacklist = set(map(int, load_file(self.config.blacklist_file)))
        self.whitelist = set(map(int, load_file(self.config.whitelist_file)))
        self.backuplist = load_file(self.config.backup_playlist_file)
        self.userlang = load_file(self.config.user_language_file) #X4: Load language file (id=language)

        self.last_np_msg = None
        
        self.dialogue = configparser.ConfigParser() #X4: Define new ConfigParser element
        self.dialogue.readfp(codecs.open('config/lang.txt', "r", "utf8")) #X4: Read dialogue file as UTF-8-file because translated on many languages

    async def get_voice_client(self, channel):
        if isinstance(channel, Object):
            channel = self.get_channel(channel.id)

        if getattr(channel, 'type', ChannelType.text) != ChannelType.voice:
            raise AttributeError('%s' % self.dialogue.get(self.config.server_language_mode, 'Dialog_ChannelIsText', fallback='Channel passed must be a voice channel')) #X4: Translated

        with await self.voice_client_connect_lock:
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

            await self.ws.send(utils.to_json(payload))
            await asyncio.wait_for(self._session_id_found.wait(), timeout=5.0, loop=self.loop)
            await asyncio.wait_for(self._voice_data_found.wait(), timeout=5.0, loop=self.loop)

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

            await voice_client.connect()
            return voice_client

    async def get_player(self, channel, author, create=False): #X4: Added author for use his id
        global landconf #X4: Use language mode
        if author is not None: #X4: For first run on_ready does not have author, because it called as server
            lang = langconf.get('User', author.id, fallback=self.config.server_language_mode) #X4: Use personal language or default
        else: #X4: Else for author == None
            lang = self.config.server_language_mode #X4: So use server settings for run

        server = channel.server

        if server.id not in self.players:
            if not create:
                raise CommandError('%s %s%s' % (self.dialogue.get(lang, 'Dialog_NoSummonedA', fallback='Player does not exist. It has not been summoned yet into a voice channel.\nUse').replace(u'\x5cn', '\n'), self.config.command_prefix, self.dialogue.get(lang, 'Dialog_NoSummonedB', fallback='summon to summon it to your voice channel.').replace(u'\x5cn', '\n'))) #X4: Translated

            voice_client = await self.get_voice_client(channel)

            playlist = Playlist(self.loop)
            player = MusicPlayer(self, voice_client, playlist) \
                .on('play', self.on_play) \
                .on('resume', self.on_resume) \
                .on('pause', self.on_pause) \
                .on('stop', self.on_stop) \
                .on('finished-playing', self.on_finished_playing)

            player.skip_state = SkipState()
            self.players[server.id] = player

        return self.players[server.id]

    async def on_play(self, player, entry): #X4: on_play can't use author.id, so used default server language
        
        self.update_now_playing(entry)
        player.skip_state.reset()
        if entry.url not in self.backuplist: #X4: Check that URL not exist in our playlist
            self.backuplist.append(entry.url.replace("http://", "https://")) #X4: Add URL in our playlist
            write_file(self.config.backup_playlist_file, self.backuplist) #X4: Save and close file backuplist.txt (with new track)

        channel = entry.meta.get('channel', None)
        author = entry.meta.get('author', None)

        if channel and author:
            if self.last_np_msg and self.last_np_msg.channel == channel:

                async for lmsg in self.logs_from(channel, limit=1):
                    if lmsg.author != self.user:
                        await self.delete_message(self.last_np_msg)
                        self.last_np_msg = None
                    break

            if self.config.now_playing_mentions:
                newmsg = '%s - %s **%s** %s %s!' % (
                    entry.meta['author'].mention, self.dialogue.get(self.config.server_language_mode, 'Dialog_NowPlayingMentionsA', fallback='your song'), entry.title, self.dialogue.get(self.config.server_language_mode, 'Dialog_NowPlayingMentionsB', fallback='is now playing in'), player.voice_client.channel.name) #X4: Translated
            else:
                newmsg = '%s %s: **%s**' % (
                    self.dialogue.get(self.config.server_language_mode, 'Dialog_NowPlayingIn', fallback='Now playing in'), player.voice_client.channel.name, entry.title) #X4: Translated

            if self.last_np_msg:
                self.last_np_msg = await self.edit_message(self.last_np_msg, newmsg)
            else:
                self.last_np_msg = await self.send_message(channel, newmsg)

    def on_resume(self, entry, **_):
        self.update_now_playing(entry)

    def on_pause(self, entry, **_):
        self.update_now_playing(entry, True)

    def on_stop(self, **_):
        self.update_now_playing()

    async def on_finished_playing(self, player, **_):
        if not player.playlist.entries and self.config.auto_playlist:
            song_url = choice(self.backuplist)
            await player.playlist.add_entry(song_url, channel=None, author=None)

    def update_now_playing(self, entry=None, is_paused=False):
        game = None
        if entry:
            prefix = u'\u275A\u275A ' if is_paused else ''

            name = u'{}{}'.format(prefix, entry.title)[:128]
            game = discord.Game(name=name)

        self.loop.create_task(self.change_status(game))

    # noinspection PyMethodOverriding
    def run(self):
        return super().run(self.config.username, self.config.password)

    async def on_ready(self):
        print('%s\n' % self.dialogue.get(self.config.server_language_mode, 'Dialog_Connected', fallback='Connected! But you have bad parameter \"ServerLanguageMode\" in options.txt. You must restart server and setup correctly!'))
        print('%s: %s' % (self.dialogue.get(self.config.server_language_mode, 'Dialog_Username', fallback='Username'), self.user.name))
        print('%s: %s' % (self.dialogue.get(self.config.server_language_mode, 'Dialog_BotID', fallback='Bot ID'), self.user.id))
        print('%s: %s' % (self.dialogue.get(self.config.server_language_mode, 'Dialog_OwnerID', fallback='Owner ID'), self.config.owner_id))

        if self.config.owner_id == self.user.id:
            print("\n%s" % self.dialogue.get(self.config.server_language_mode, 'Dialog_OwnerBadID', fallback=None).replace(u'\x5cn', '\n'))
        print()

        # TODO: Make this prettier and easier to read (in the console)
        print("%s %s" % (self.dialogue.get(self.config.server_language_mode, 'Dialog_ComPrefix', fallback='Command prefix is'), self.config.command_prefix))
        # print("Days active required to use commands is %s" % self.config.days_active) # NYI
        print("%s %s" % (self.dialogue.get(self.config.server_language_mode, 'Dialog_WhlistCheck', fallback='Whitelist check is'), [self.dialogue.get(self.config.server_language_mode, 'Dialog_disabled', fallback='disabled'), self.dialogue.get(self.config.server_language_mode, 'Dialog_enabled', fallback='enabled')][self.config.white_list_check]))
        print("%s %s %s %s%%" % (self.dialogue.get(self.config.server_language_mode, 'Dialog_SkipThrA', fallback='Skip threshold at'), self.config.skips_required, self.dialogue.get(self.config.server_language_mode, 'Dialog_SkipThrB', fallback='votes or'), self._fixg(self.config.skip_ratio_required*100)))
        print("%s %s" % (self.dialogue.get(self.config.server_language_mode, 'Dialog_MentionsCheck', fallback='Now Playing message @mentions are'), [self.dialogue.get(self.config.server_language_mode, 'Dialog_disabled', fallback='disabled'), self.dialogue.get(self.config.server_language_mode, 'Dialog_enabled', fallback='enabled')][self.config.now_playing_mentions]))
        print("%s %s" % (self.dialogue.get(self.config.server_language_mode, 'Dialog_AutosummonCheck', fallback='Autosummon is'), [self.dialogue.get(self.config.server_language_mode, 'Dialog_disabled', fallback='disabled'), self.dialogue.get(self.config.server_language_mode, 'Dialog_enabled', fallback='enabled')][self.config.auto_summon]))
        print("%s %s" % (self.dialogue.get(self.config.server_language_mode, 'Dialog_AutoPlListCheck', fallback='Auto-playlist is'), [self.dialogue.get(self.config.server_language_mode, 'Dialog_disabled', fallback='disabled'), self.dialogue.get(self.config.server_language_mode, 'Dialog_enabled', fallback='enabled')][self.config.auto_playlist]))
        print("%s %s %s" % (self.dialogue.get(self.config.server_language_mode, 'Dialog_SongSaveCheckA', fallback='Downloaded songs will be'), [self.dialogue.get(self.config.server_language_mode, 'Dialog_deleted', fallback='deleted'), self.dialogue.get(self.config.server_language_mode, 'Dialog_saved', fallback='saved')][self.config.save_videos], self.dialogue.get(self.config.server_language_mode, 'Dialog_SongSaveCheckB', fallback='after playback')))
        print("Default language mode is \"%s\" (this message on English for DEBUG)" % self.config.server_language_mode) #X4: Add notification in console about default language.
        print()

        if self.servers:
            print('%s' % self.dialogue.get(self.config.server_language_mode, 'Dialog_ServerList', fallback='--Server List--'))
            [print(s) for s in self.servers]
        else:
            print("%s" % self.dialogue.get(self.config.server_language_mode, 'Dialog_NoSrv', fallback='No servers have been joined yet.').replace(u'\x5cn', '\n'))

        print()
        """print('Connected!\n')
        print('Username: %s' % self.user.name)
        print('Bot ID: %s' % self.user.id)
        print('Owner ID: %s' % self.config.owner_id)

        if self.config.owner_id == self.user.id:
            print("\n"
                "[NOTICE] You have either set the OwnerID config option to the bot's id instead "
                "of yours, or you've used your own credentials to log the bot in instead of the "
                "bot's account (the bot needs its own account to work properly).")
        print()

        # TODO: Make this prettier and easier to read (in the console)
        print("Command prefix is %s" % self.config.command_prefix)
        # print("Days active required to use commands is %s" % self.config.days_active) # NYI
        print("Whitelist check is %s" % ['disabled', 'enabled'][self.config.white_list_check])
        print("Skip threshold at %s votes or %s%%" % (self.config.skips_required, self._fixg(self.config.skip_ratio_required*100)))
        print("Now Playing message @mentions are %s" % ['disabled', 'enabled'][self.config.now_playing_mentions])
        print("Autosummon is %s" % ['disabled', 'enabled'][self.config.auto_summon])
        print("Auto-playlist is %s" % ['disabled', 'enabled'][self.config.auto_playlist])
        print("Downloaded songs will be %s after playback" % ['deleted', 'saved'][self.config.save_videos])
        print("Default language mode is \"%s\"" % self.config.server_language_mode) #X4: Add notification in console about default language.
        print()

        if self.servers:
            print('--Server List--')
            [print(s) for s in self.servers]
        else:
            print("No servers have been joined yet.")

        print()"""

        # maybe option to leave the ownerid blank and generate a random command for the owner to use

        if self.config.auto_summon:
            as_ok = await self._auto_summon()

            if self.config.auto_playlist and as_ok:
                #a = Author() #a = Author(id='000000000000000000')
                #a.id = '000000000000000000'
                await self.on_finished_playing(await self.get_player(self._get_owner_voice_channel(), author=None)) #X4: Added author, because it needed to use in multilanguage system ERROR if chanel not avaiable


    # TODO: autosummon option to a specific channel
    async def _auto_summon(self):
        channel = self._get_owner_voice_channel()
        if channel:
            await self.handle_summon(channel, discord.Object(id=str(self.config.owner_id)))
            return True
        else:
            print("%s" % self.dialogue.get(self.config.server_language_mode, 'Dialog_Owner404', fallback='Owner not found in a voice channel, could not autosummon.')) #X4: Translated
            #print("Owner not found in a voice channel, could not autosummon.")
            return False

    def _get_owner_voice_channel(self):
        for server in self.servers:
            for channel in server.channels:
                if discord.utils.get(channel.voice_members, id=self.config.owner_id):
                    return channel

    def _fixg(self, x, dp=2):
        return ('{:.%sf}' % dp).format(x).rstrip('0').rstrip('.')


    async def handle_help(self, author): #X4: Added author for use his id
        """
        Usage: {command_prefix}help
        Prints a help message
        """
        global landconf #X4: Use language mode
        lang = langconf.get('User', author.id, fallback=self.config.server_language_mode) #X4: Use personal language or default

        helpmsg = "**%s**\n```" % self.dialogue.get(lang, 'Dialog_Commands', fallback='Commands') #X4: Translated
        commands = []

        # TODO: Get this to format nicely
        for att in dir(self):
            if att.startswith('handle_') and att != 'handle_help':
                command_name = att.replace('handle_', '').lower()
                commands.append("{}{}".format(self.config.command_prefix, command_name))

        helpmsg += ", ".join(commands)
        helpmsg += "```"
        helpmsg += "https://github.com/SexualRhinoceros/MusicBot/wiki/Commands-list + https://github.com/JumpJets/MusicBot" #X4: Added link to our repository if someone needed this fork

        return Response(helpmsg, reply=True, delete_after=60)

    async def handle_whitelist(self, author, message, option, username): #X4: Added author for use his id
        """
        Usage: {command_prefix}whitelist [ + | - | add | remove ] @UserName
        Adds or removes the user to the whitelist. When the whitelist is enabled,
        whitelisted users are permitted to use bot commands.
        """
        global landconf #X4: Use language mode
        lang = langconf.get('User', author.id, fallback=self.config.server_language_mode) #X4: Use personal language or default

        if message.author.id != self.config.owner_id:
            return

        user_id = extract_user_id(username)
        if not user_id:
            raise CommandError('%s' % self.dialogue.get(lang, 'Dialog_InvalidUser', fallback='Invalid user specified')) #X4: Translated

        if option not in ['+', '-', 'add', 'remove']:
            raise CommandError('%s "%s" %s' % (self.dialogue.get(lang, 'Dialog_InvalidOptionA', fallback='Invalid option'), option, self.dialogue.get(lang, 'Dialog_InvalidOptionB', fallback='specified, use +, -, add, or remove'))) #X4: Translated

        if option in ['+', 'add']:
            self.whitelist.add(user_id)
            write_file('./config/whitelist.txt', self.whitelist)

            return Response('%s' % self.dialogue.get(lang, 'Dialog_AddedWhitelist', fallback='user has been added to the whitelist'), reply=True, delete_after=10) #X4: Translated

        else:
            if user_id not in self.whitelist:
                return Response('%s' % self.dialogue.get(lang, 'Dialog_NotInWhitelist', fallback='user is not in the whitelist'), reply=True, delete_after=10) #X4: Translated

            else:
                self.whitelist.remove(user_id)
                write_file('./config/whitelist.txt', self.whitelist)

                return Response('%s' % self.dialogue.get(lang, 'Dialog_RemovedFromWhitelist', fallback='user has been removed from the whitelist'), reply=True, delete_after=10) #X4: Translated


    async def handle_blacklist(self, author, message, option, username): #X4: Added author for use his id
        """
        Usage: {command_prefix}blacklist [ + | - | add | remove ] @UserName
        Adds or removes the user to the blacklist. Blacklisted users are forbidden from
        using bot commands. Blacklisting a user also removes them from the whitelist.
        """
        global landconf #X4: Use language mode
        lang = langconf.get('User', author.id, fallback=self.config.server_language_mode) #X4: Use personal language or default

        if message.author.id != self.config.owner_id:
            return

        user_id = extract_user_id(username)
        if not user_id:
            raise CommandError('%s' % self.dialogue.get(lang, 'Dialog_InvalidUser', fallback='Invalid user specified')) #X4: Translated

        if str(user_id) == self.config.owner_id:
            return Response("%s" % self.dialogue.get(lang, 'Dialog_OwnerToBL', fallback='The owner cannot be blacklisted.'), delete_after=10) #X4: Translated

        if option not in ['+', '-', 'add', 'remove']:
            raise CommandError('%s "%s" %s' % (self.dialogue.get(lang, 'Dialog_InvalidOptionA', fallback='Invalid option'), option, self.dialogue.get(lang, 'Dialog_InvalidOptionB', fallback='specified, use +, -, add, or remove'))) #X4: Translated

        if option in ['+', 'add']:
            self.blacklist.add(user_id)
            write_file('./config/blacklist.txt', self.blacklist)

            if user_id in self.whitelist:
                self.whitelist.remove(user_id)
                write_file('./config/whitelist.txt', self.whitelist)
                return Response('%s' % self.dialogue.get(lang, 'Dialog_RemovedFromBLToWL', fallback='user has been added to the blacklist and removed from the whitelist'), reply=True, delete_after=10) #X4: Translated

            else:
                return Response('%s' % self.dialogue.get(lang, 'Dialog_AddedBlacklist', fallback='user has been added to the blacklist'), reply=True, delete_after=10) #X4: Translated

        else:
            if user_id not in self.blacklist:
                return Response('%s' % self.dialogue.get(lang, 'Dialog_NotInBL', fallback='user is not in the blacklist'), reply=True, delete_after=10) #X4: Translated

            else:
                self.blacklist.remove(user_id)
                write_file('./config/blacklist.txt', self.blacklist)

                return Response('%s' % self.dialogue.get(lang, 'Dialog_RemovedFromBlacklist', fallback='user has been removed from the blacklist'), reply=True, delete_after=10) #X4: Translated


    async def handle_id(self, author):
        """
        Usage: {command_prefix}id
        Tells the user their id.
        """
        global landconf #X4: Use language mode
        lang = langconf.get('User', author.id, fallback=self.config.server_language_mode) #X4: Use personal language or default

        return Response('%s `%s`' % (self.dialogue.get(lang, 'Dialog_YourID', fallback='your id is'), author.id), reply=True) #X4: Translated

    async def handle_joinserver(self, author, message, server_link): #X4: Added author for use his id
        """
        Usage {command_prefix}joinserver [Server Link]
        Asks the bot to join a server. [todo: add info about if it breaks or whatever]
        """
        global landconf #X4: Use language mode
        lang = langconf.get('User', author.id, fallback=self.config.server_language_mode) #X4: Use personal language or default

        try:
            if message.author.id == self.config.owner_id:
                await self.accept_invite(server_link)

        except:
            raise CommandError('%s:\n{}\n'.format(server_link) % self.dialogue.get(lang, 'Dialog_InvalidJoin', fallback='Invalid URL provided')) #X4: Translated

    async def handle_play(self, player, channel, author, song_url):
        """
        Usage {command_prefix}play [song link]
        Adds the song to the playlist.
        """
        global landconf #X4: Use language mode
        lang = langconf.get('User', author.id, fallback=self.config.server_language_mode) #X4: Use personal language or default

        try:
            await self.send_typing(channel)

            reply_text = "%s **%s** %s %s" #X4: Move text to translation

            info = await extract_info(player.playlist.loop, song_url, download=False, process=False)

            if not info:
                raise CommandError("%s" % self.dialogue.get(lang, 'Dialog_VCannotPlayed', fallback='That video cannot be played.').replace(u'\x5cn', '\n'))

            if 'entries' in info:
                t0 = time.time()

                # My test was 1.2 seconds per song, but we maybe should fudge it a bit, unless we can
                # monitor it and edit the message with the estimated time, but that's some ADVANCED SHIT
                # I don't think we can hook into it anyways, so this will have to do.
                # It would probably be a thread to check a few playlists and get the speed from that
                # Different playlists might download at different speeds though
                wait_per_song = 1.2

                num_songs = sum(1 for _ in info['entries'])

                procmesg = await self.send_message(channel,
                    '{} {} {}{}'.format(
                        self.dialogue.get(lang, 'Dialog_PlaylistInfoA', fallback='Gathering playlist information for').replace(u'\x5cn', '\n'),
                        num_songs,
                        self.dialogue.get(lang, 'Dialog_PlaylistInfoB', fallback='songs').replace(u'\x5cn', '\n'),
                        ', {} {} {}'.format(self.dialogue.get(lang, 'Dialog_PlaylistInfoC', fallback='ETA:').replace(u'\x5cn', '\n'), self._fixg(num_songs*wait_per_song), self.dialogue.get(lang, 'Dialog_PlaylistInfoD', fallback='seconds').replace(u'\x5cn', '\n')) if num_songs >= 10 else '.')) #X4: Translated

                # We don't have a pretty way of doing this yet.  We need either a loop
                # that sends these every 10 seconds or a nice context manager.
                await self.send_typing(channel)

                entry_list, position = await player.playlist.import_from(song_url, channel=channel, author=author)
                entry = entry_list[0]

                tnow = time.time()
                ttime = tnow - t0
                listlen = len(entry_list)

                print("{} {} {} {} {} {:.2f}{}, {:+.2g}{} ({}{})".format(
                    self.dialogue.get(lang, 'Dialog_PlaylistNotifyA', fallback='Processed').replace(u'\x5cn', '\n'),
                    listlen,
                    self.dialogue.get(lang, 'Dialog_PlaylistNotifyB', fallback='songs in').replace(u'\x5cn', '\n'),
                    self._fixg(ttime),
                    self.dialogue.get(lang, 'Dialog_PlaylistNotifyC', fallback='seconds at').replace(u'\x5cn', '\n'),
                    ttime/listlen,
                    self.dialogue.get(lang, 'Dialog_PlaylistNotifyD', fallback='s/song').replace(u'\x5cn', '\n'),
                    ttime/listlen - wait_per_song,
                    self.dialogue.get(lang, 'Dialog_PlaylistNotifyE', fallback='/song from expected').replace(u'\x5cn', '\n'),
                    self._fixg(wait_per_song*num_songs),
                    self.dialogue.get(lang, 'Dialog_PlaylistNotifyF', fallback='s').replace(u'\x5cn', '\n')) #X4: Translated
                )

                await self.delete_message(procmesg)

            else:
                entry, position = await player.playlist.add_entry(song_url, channel=channel, author=author)

            time_until = await player.playlist.estimate_time_until(position, player)

            if position == 1 and player.is_stopped:
                position = 'Up next!'
                reply_text = reply_text % (entry.title, position)
            else:
                reply_text += ' %s %s'
                reply_text = reply_text % (self.dialogue.get(lang, 'Dialog_EnqueuedA', fallback='Enqueued').replace(u'\x5cn', '\n'), entry.title, self.dialogue.get(lang, 'Dialog_EnqueuedB', fallback='to be played. Position in queue:').replace(u'\x5cn', '\n'), position, self.dialogue.get(lang, 'Dialog_EnqueuedC', fallback='- estimated time until playing:').replace(u'\x5cn', '\n'), time_until) #X4: Translated
                # TODO: Subtract time the current song has been playing for

            return Response(reply_text, reply=True, delete_after=15)

        except Exception as e:
            traceback.print_exc()
            raise CommandError('%s %s %s' % (self.dialogue.get(lang, 'Dialog_UnablePlayingA', fallback='Unable to queue up song at').replace(u'\x5cn', '\n'), song_url, self.dialogue.get(lang, 'Dialog_UnablePlayingB', fallback='to be played.').replace(u'\x5cn', '\n'))) #X4: Translated

    # X4: Additional functions as link
    async def handle_p(self, player, channel, author, song_url):
        """
        Usage {command_prefix}p [song link]
        Adds the song to the playlist.
        """
        global landconf #X4: Use language mode
        lang = langconf.get('User', author.id, fallback=self.config.server_language_mode) #X4: Use personal language or default

        try:
            await self.send_typing(channel)

            reply_text = "%s **%s** %s %s" #X4: Move text to translation

            info = await extract_info(player.playlist.loop, song_url, download=False, process=False)

            if not info:
                raise CommandError("%s" % self.dialogue.get(lang, 'Dialog_VCannotPlayed', fallback='That video cannot be played.').replace(u'\x5cn', '\n'))

            if 'entries' in info:
                t0 = time.time()

                # My test was 1.2 seconds per song, but we maybe should fudge it a bit, unless we can
                # monitor it and edit the message with the estimated time, but that's some ADVANCED SHIT
                # I don't think we can hook into it anyways, so this will have to do.
                # It would probably be a thread to check a few playlists and get the speed from that
                # Different playlists might download at different speeds though
                wait_per_song = 1.2

                num_songs = sum(1 for _ in info['entries'])

                procmesg = await self.send_message(channel,
                    '{} {} {}{}'.format(
                        self.dialogue.get(lang, 'Dialog_PlaylistInfoA', fallback='Gathering playlist information for').replace(u'\x5cn', '\n'),
                        num_songs,
                        self.dialogue.get(lang, 'Dialog_PlaylistInfoB', fallback='songs').replace(u'\x5cn', '\n'),
                        ', {} {} {}'.format(self.dialogue.get(lang, 'Dialog_PlaylistInfoC', fallback='ETA:').replace(u'\x5cn', '\n'), self._fixg(num_songs*wait_per_song), self.dialogue.get(lang, 'Dialog_PlaylistInfoD', fallback='seconds').replace(u'\x5cn', '\n')) if num_songs >= 10 else '.')) #X4: Translated

                # We don't have a pretty way of doing this yet.  We need either a loop
                # that sends these every 10 seconds or a nice context manager.
                await self.send_typing(channel)

                entry_list, position = await player.playlist.import_from(song_url, channel=channel, author=author)
                entry = entry_list[0]

                tnow = time.time()
                ttime = tnow - t0
                listlen = len(entry_list)

                print("{} {} {} {} {} {:.2f}{}, {:+.2g}{} ({}{})".format(
                    self.dialogue.get(lang, 'Dialog_PlaylistNotifyA', fallback='Processed').replace(u'\x5cn', '\n'),
                    listlen,
                    self.dialogue.get(lang, 'Dialog_PlaylistNotifyB', fallback='songs in').replace(u'\x5cn', '\n'),
                    self._fixg(ttime),
                    self.dialogue.get(lang, 'Dialog_PlaylistNotifyC', fallback='seconds at').replace(u'\x5cn', '\n'),
                    ttime/listlen,
                    self.dialogue.get(lang, 'Dialog_PlaylistNotifyD', fallback='s/song').replace(u'\x5cn', '\n'),
                    ttime/listlen - wait_per_song,
                    self.dialogue.get(lang, 'Dialog_PlaylistNotifyE', fallback='/song from expected').replace(u'\x5cn', '\n'),
                    self._fixg(wait_per_song*num_songs),
                    self.dialogue.get(lang, 'Dialog_PlaylistNotifyF', fallback='s').replace(u'\x5cn', '\n')) #X4: Translated
                )

                await self.delete_message(procmesg)

            else:
                entry, position = await player.playlist.add_entry(song_url, channel=channel, author=author)

            time_until = await player.playlist.estimate_time_until(position, player)

            if position == 1 and player.is_stopped:
                position = 'Up next!'
                reply_text = reply_text % (entry.title, position)
            else:
                reply_text += ' %s %s'
                reply_text = reply_text % (self.dialogue.get(lang, 'Dialog_EnqueuedA', fallback='Enqueued').replace(u'\x5cn', '\n'), entry.title, self.dialogue.get(lang, 'Dialog_EnqueuedB', fallback='to be played. Position in queue:').replace(u'\x5cn', '\n'), position, self.dialogue.get(lang, 'Dialog_EnqueuedC', fallback='- estimated time until playing:').replace(u'\x5cn', '\n'), time_until) #X4: Translated
                # TODO: Subtract time the current song has been playing for

            return Response(reply_text, reply=True, delete_after=15)

        except Exception as e:
            traceback.print_exc()
            raise CommandError('%s %s %s' % (self.dialogue.get(lang, 'Dialog_UnablePlayingA', fallback='Unable to queue up song at').replace(u'\x5cn', '\n'), song_url, self.dialogue.get(lang, 'Dialog_UnablePlayingB', fallback='to be played.').replace(u'\x5cn', '\n'))) #X4: Translated

    async def handle_add(self, player, channel, author, song_url):
        """
        Usage {command_prefix}add [song link]
        Adds the song to the playlist.
        """
        global landconf #X4: Use language mode
        lang = langconf.get('User', author.id, fallback=self.config.server_language_mode) #X4: Use personal language or default

        try:
            await self.send_typing(channel)

            reply_text = "%s **%s** %s %s" #X4: Move text to translation

            info = await extract_info(player.playlist.loop, song_url, download=False, process=False)

            if not info:
                raise CommandError("%s" % self.dialogue.get(lang, 'Dialog_VCannotPlayed', fallback='That video cannot be played.').replace(u'\x5cn', '\n'))

            if 'entries' in info:
                t0 = time.time()

                # My test was 1.2 seconds per song, but we maybe should fudge it a bit, unless we can
                # monitor it and edit the message with the estimated time, but that's some ADVANCED SHIT
                # I don't think we can hook into it anyways, so this will have to do.
                # It would probably be a thread to check a few playlists and get the speed from that
                # Different playlists might download at different speeds though
                wait_per_song = 1.2

                num_songs = sum(1 for _ in info['entries'])

                procmesg = await self.send_message(channel,
                    '{} {} {}{}'.format(
                        self.dialogue.get(lang, 'Dialog_PlaylistInfoA', fallback='Gathering playlist information for').replace(u'\x5cn', '\n'),
                        num_songs,
                        self.dialogue.get(lang, 'Dialog_PlaylistInfoB', fallback='songs').replace(u'\x5cn', '\n'),
                        ', {} {} {}'.format(self.dialogue.get(lang, 'Dialog_PlaylistInfoC', fallback='ETA:').replace(u'\x5cn', '\n'), self._fixg(num_songs*wait_per_song), self.dialogue.get(lang, 'Dialog_PlaylistInfoD', fallback='seconds').replace(u'\x5cn', '\n')) if num_songs >= 10 else '.')) #X4: Translated

                # We don't have a pretty way of doing this yet.  We need either a loop
                # that sends these every 10 seconds or a nice context manager.
                await self.send_typing(channel)

                entry_list, position = await player.playlist.import_from(song_url, channel=channel, author=author)
                entry = entry_list[0]

                tnow = time.time()
                ttime = tnow - t0
                listlen = len(entry_list)

                print("{} {} {} {} {} {:.2f}{}, {:+.2g}{} ({}{})".format(
                    self.dialogue.get(lang, 'Dialog_PlaylistNotifyA', fallback='Processed').replace(u'\x5cn', '\n'),
                    listlen,
                    self.dialogue.get(lang, 'Dialog_PlaylistNotifyB', fallback='songs in').replace(u'\x5cn', '\n'),
                    self._fixg(ttime),
                    self.dialogue.get(lang, 'Dialog_PlaylistNotifyC', fallback='seconds at').replace(u'\x5cn', '\n'),
                    ttime/listlen,
                    self.dialogue.get(lang, 'Dialog_PlaylistNotifyD', fallback='s/song').replace(u'\x5cn', '\n'),
                    ttime/listlen - wait_per_song,
                    self.dialogue.get(lang, 'Dialog_PlaylistNotifyE', fallback='/song from expected').replace(u'\x5cn', '\n'),
                    self._fixg(wait_per_song*num_songs),
                    self.dialogue.get(lang, 'Dialog_PlaylistNotifyF', fallback='s').replace(u'\x5cn', '\n')) #X4: Translated
                )

                await self.delete_message(procmesg)

            else:
                entry, position = await player.playlist.add_entry(song_url, channel=channel, author=author)

            time_until = await player.playlist.estimate_time_until(position, player)

            if position == 1 and player.is_stopped:
                position = 'Up next!'
                reply_text = reply_text % (entry.title, position)
            else:
                reply_text += ' %s %s'
                reply_text = reply_text % (self.dialogue.get(lang, 'Dialog_EnqueuedA', fallback='Enqueued').replace(u'\x5cn', '\n'), entry.title, self.dialogue.get(lang, 'Dialog_EnqueuedB', fallback='to be played. Position in queue:').replace(u'\x5cn', '\n'), position, self.dialogue.get(lang, 'Dialog_EnqueuedC', fallback='- estimated time until playing:').replace(u'\x5cn', '\n'), time_until) #X4: Translated
                # TODO: Subtract time the current song has been playing for

            return Response(reply_text, reply=True, delete_after=15)

        except Exception as e:
            traceback.print_exc()
            raise CommandError('%s %s %s' % (self.dialogue.get(lang, 'Dialog_UnablePlayingA', fallback='Unable to queue up song at').replace(u'\x5cn', '\n'), song_url, self.dialogue.get(lang, 'Dialog_UnablePlayingB', fallback='to be played.').replace(u'\x5cn', '\n'))) #X4: Translated

    async def handle_music(self, player, channel, author, song_url):
        """
        Usage {command_prefix}music [song link]
        Adds the song to the playlist.
        """
        global landconf #X4: Use language mode
        lang = langconf.get('User', author.id, fallback=self.config.server_language_mode) #X4: Use personal language or default

        try:
            await self.send_typing(channel)

            reply_text = "%s **%s** %s %s" #X4: Move text to translation

            info = await extract_info(player.playlist.loop, song_url, download=False, process=False)

            if not info:
                raise CommandError("%s" % self.dialogue.get(lang, 'Dialog_VCannotPlayed', fallback='That video cannot be played.').replace(u'\x5cn', '\n'))

            if 'entries' in info:
                t0 = time.time()

                # My test was 1.2 seconds per song, but we maybe should fudge it a bit, unless we can
                # monitor it and edit the message with the estimated time, but that's some ADVANCED SHIT
                # I don't think we can hook into it anyways, so this will have to do.
                # It would probably be a thread to check a few playlists and get the speed from that
                # Different playlists might download at different speeds though
                wait_per_song = 1.2

                num_songs = sum(1 for _ in info['entries'])

                procmesg = await self.send_message(channel,
                    '{} {} {}{}'.format(
                        self.dialogue.get(lang, 'Dialog_PlaylistInfoA', fallback='Gathering playlist information for').replace(u'\x5cn', '\n'),
                        num_songs,
                        self.dialogue.get(lang, 'Dialog_PlaylistInfoB', fallback='songs').replace(u'\x5cn', '\n'),
                        ', {} {} {}'.format(self.dialogue.get(lang, 'Dialog_PlaylistInfoC', fallback='ETA:').replace(u'\x5cn', '\n'), self._fixg(num_songs*wait_per_song), self.dialogue.get(lang, 'Dialog_PlaylistInfoD', fallback='seconds').replace(u'\x5cn', '\n')) if num_songs >= 10 else '.')) #X4: Translated

                # We don't have a pretty way of doing this yet.  We need either a loop
                # that sends these every 10 seconds or a nice context manager.
                await self.send_typing(channel)

                entry_list, position = await player.playlist.import_from(song_url, channel=channel, author=author)
                entry = entry_list[0]

                tnow = time.time()
                ttime = tnow - t0
                listlen = len(entry_list)

                print("{} {} {} {} {} {:.2f}{}, {:+.2g}{} ({}{})".format(
                    self.dialogue.get(lang, 'Dialog_PlaylistNotifyA', fallback='Processed').replace(u'\x5cn', '\n'),
                    listlen,
                    self.dialogue.get(lang, 'Dialog_PlaylistNotifyB', fallback='songs in').replace(u'\x5cn', '\n'),
                    self._fixg(ttime),
                    self.dialogue.get(lang, 'Dialog_PlaylistNotifyC', fallback='seconds at').replace(u'\x5cn', '\n'),
                    ttime/listlen,
                    self.dialogue.get(lang, 'Dialog_PlaylistNotifyD', fallback='s/song').replace(u'\x5cn', '\n'),
                    ttime/listlen - wait_per_song,
                    self.dialogue.get(lang, 'Dialog_PlaylistNotifyE', fallback='/song from expected').replace(u'\x5cn', '\n'),
                    self._fixg(wait_per_song*num_songs),
                    self.dialogue.get(lang, 'Dialog_PlaylistNotifyF', fallback='s').replace(u'\x5cn', '\n')) #X4: Translated
                )

                await self.delete_message(procmesg)

            else:
                entry, position = await player.playlist.add_entry(song_url, channel=channel, author=author)

            time_until = await player.playlist.estimate_time_until(position, player)

            if position == 1 and player.is_stopped:
                position = 'Up next!'
                reply_text = reply_text % (entry.title, position)
            else:
                reply_text += ' %s %s'
                reply_text = reply_text % (self.dialogue.get(lang, 'Dialog_EnqueuedA', fallback='Enqueued').replace(u'\x5cn', '\n'), entry.title, self.dialogue.get(lang, 'Dialog_EnqueuedB', fallback='to be played. Position in queue:').replace(u'\x5cn', '\n'), position, self.dialogue.get(lang, 'Dialog_EnqueuedC', fallback='- estimated time until playing:').replace(u'\x5cn', '\n'), time_until) #X4: Translated
                # TODO: Subtract time the current song has been playing for

            return Response(reply_text, reply=True, delete_after=15)

        except Exception as e:
            traceback.print_exc()
            raise CommandError('%s %s %s' % (self.dialogue.get(lang, 'Dialog_UnablePlayingA', fallback='Unable to queue up song at').replace(u'\x5cn', '\n'), song_url, self.dialogue.get(lang, 'Dialog_UnablePlayingB', fallback='to be played.').replace(u'\x5cn', '\n'))) #X4: Translated

    async def handle_m(self, player, channel, author, song_url):
        """
        Usage {command_prefix}m [song link]
        Adds the song to the playlist.
        """
        global landconf #X4: Use language mode
        lang = langconf.get('User', author.id, fallback=self.config.server_language_mode) #X4: Use personal language or default

        try:
            await self.send_typing(channel)

            reply_text = "%s **%s** %s %s" #X4: Move text to translation

            info = await extract_info(player.playlist.loop, song_url, download=False, process=False)

            if not info:
                raise CommandError("%s" % self.dialogue.get(lang, 'Dialog_VCannotPlayed', fallback='That video cannot be played.').replace(u'\x5cn', '\n'))

            if 'entries' in info:
                t0 = time.time()

                # My test was 1.2 seconds per song, but we maybe should fudge it a bit, unless we can
                # monitor it and edit the message with the estimated time, but that's some ADVANCED SHIT
                # I don't think we can hook into it anyways, so this will have to do.
                # It would probably be a thread to check a few playlists and get the speed from that
                # Different playlists might download at different speeds though
                wait_per_song = 1.2

                num_songs = sum(1 for _ in info['entries'])

                procmesg = await self.send_message(channel,
                    '{} {} {}{}'.format(
                        self.dialogue.get(lang, 'Dialog_PlaylistInfoA', fallback='Gathering playlist information for').replace(u'\x5cn', '\n'),
                        num_songs,
                        self.dialogue.get(lang, 'Dialog_PlaylistInfoB', fallback='songs').replace(u'\x5cn', '\n'),
                        ', {} {} {}'.format(self.dialogue.get(lang, 'Dialog_PlaylistInfoC', fallback='ETA:').replace(u'\x5cn', '\n'), self._fixg(num_songs*wait_per_song), self.dialogue.get(lang, 'Dialog_PlaylistInfoD', fallback='seconds').replace(u'\x5cn', '\n')) if num_songs >= 10 else '.')) #X4: Translated

                # We don't have a pretty way of doing this yet.  We need either a loop
                # that sends these every 10 seconds or a nice context manager.
                await self.send_typing(channel)

                entry_list, position = await player.playlist.import_from(song_url, channel=channel, author=author)
                entry = entry_list[0]

                tnow = time.time()
                ttime = tnow - t0
                listlen = len(entry_list)

                print("{} {} {} {} {} {:.2f}{}, {:+.2g}{} ({}{})".format(
                    self.dialogue.get(lang, 'Dialog_PlaylistNotifyA', fallback='Processed').replace(u'\x5cn', '\n'),
                    listlen,
                    self.dialogue.get(lang, 'Dialog_PlaylistNotifyB', fallback='songs in').replace(u'\x5cn', '\n'),
                    self._fixg(ttime),
                    self.dialogue.get(lang, 'Dialog_PlaylistNotifyC', fallback='seconds at').replace(u'\x5cn', '\n'),
                    ttime/listlen,
                    self.dialogue.get(lang, 'Dialog_PlaylistNotifyD', fallback='s/song').replace(u'\x5cn', '\n'),
                    ttime/listlen - wait_per_song,
                    self.dialogue.get(lang, 'Dialog_PlaylistNotifyE', fallback='/song from expected').replace(u'\x5cn', '\n'),
                    self._fixg(wait_per_song*num_songs),
                    self.dialogue.get(lang, 'Dialog_PlaylistNotifyF', fallback='s').replace(u'\x5cn', '\n')) #X4: Translated
                )

                await self.delete_message(procmesg)

            else:
                entry, position = await player.playlist.add_entry(song_url, channel=channel, author=author)

            time_until = await player.playlist.estimate_time_until(position, player)

            if position == 1 and player.is_stopped:
                position = 'Up next!'
                reply_text = reply_text % (entry.title, position)
            else:
                reply_text += ' %s %s'
                reply_text = reply_text % (self.dialogue.get(lang, 'Dialog_EnqueuedA', fallback='Enqueued').replace(u'\x5cn', '\n'), entry.title, self.dialogue.get(lang, 'Dialog_EnqueuedB', fallback='to be played. Position in queue:').replace(u'\x5cn', '\n'), position, self.dialogue.get(lang, 'Dialog_EnqueuedC', fallback='- estimated time until playing:').replace(u'\x5cn', '\n'), time_until) #X4: Translated
                # TODO: Subtract time the current song has been playing for

            return Response(reply_text, reply=True, delete_after=15)

        except Exception as e:
            traceback.print_exc()
            raise CommandError('%s %s %s' % (self.dialogue.get(lang, 'Dialog_UnablePlayingA', fallback='Unable to queue up song at').replace(u'\x5cn', '\n'), song_url, self.dialogue.get(lang, 'Dialog_UnablePlayingB', fallback='to be played.').replace(u'\x5cn', '\n'))) #X4: Translated

    """async def handle_p(self, player, channel, author, song_url): #X4: Add shortcut command
        "" "
        Usage {command_prefix}p [song link]
        Adds the song to the playlist.
        "" "

        try:
            await self.handle_play(player, channel, author, song_url) #X4: Use shortcut to main function

            return Response("Enqueued **%s** to be played. Position in queue: %s", reply=True, delete_after=15)

        except Exception as e:
            traceback.print_exc()
            raise CommandError('Unable to queue up song at %s to be played.' % song_url)

    async def handle_add(self, player, channel, author, song_url): #X4: Add shortcut command
        "" "
        Usage {command_prefix}add [song link]
        Adds the song to the playlist.
        "" "

        await self.handle_play(player, channel, author, song_url) #X4: Use shortcut to main function

    async def handle_music(self, player, channel, author, song_url): #X4: Add shortcut command
        "" "
        Usage {command_prefix}music [song link]
        Adds the song to the playlist.
        "" "

        await self.handle_play(player, channel, author, song_url) #X4: Use shortcut to main function

    async def handle_m(self, player, channel, author, song_url): #X4: Add shortcut command
        "" "
        Usage {command_prefix}m [song link]
        Adds the song to the playlist.
        "" "

        await self.handle_play(player, channel, author, song_url) #X4: Use shortcut to main function"""

    """async def handle_replay(self, player, channel, author): #X4: Define command that add track in queue, but in second position.
        "" "
        Usage {command_prefix}replay
        This command make bot playing current track again, after it finished.
        "" "
        player = await self.get_player(channel) #X4: Initialize player

        self.backuplist.append(player.current_entry.url) #X4: Add URL in our playlist

        return Response("**Undo successful.** Song **%s** is back from rotation." % player.current_entry.title, delete_after=15) #X4: End UNDO"""

    async def handle_summon(self, channel, author):
        """
        Usage {command_prefix}summon
        This command is for summoning the bot into your voice channel [but it should do it automatically the first time]
        """
        global landconf #X4: Use language mode
        lang = langconf.get('User', author.id, fallback=self.config.server_language_mode) #X4: Use personal language or default

        if self.voice_clients:
            raise CommandError("Multiple servers not supported at this time. / X4: In queue to update")
            """
            server = channel.server #X4: Define server
            channel = None #X4: Set null, because undefined
            for channel in server.channels: #X4: List of channels on the server
                if discord.utils.get(channel.voice_members, id=author.id): #X4: Searching user in channels
                    break #X4: Stop at current seleced channel and go next
            player = await self.get_player(channel, create=True) #X4: Check player
            if channel.server.id in self.players: #X4: Check same server (true) or other (else)
                await self.get_voice_client(channel) #X4: This does not work on same server, need to fix!
            else: #X4: Else
                await self.get_voice_client(channel) #X4: Move bot to other new server and in new channel
            if player.is_stopped: #X4: Check if player stopped (practically almost stopped)
                player.play() #X4: Send "play" state
            if not player.playlist.entries and self.config.auto_playlist: #X4: Check player for tracks. New summoned player is empty.
                song_url = choice(self.backuplist) #X4: Choose random track from auto playlist
                await player.playlist.add_entry(song_url, channel=None, author=None) #X4: Send chosen track to player and start playing music
            """

        # moving = False
        # if channel.server.id in self.players:
        #     moving = True
        #     print("Already in channel, moving")


        server = channel.server

        channel = None
        for channel in server.channels:
            if discord.utils.get(channel.voice_members, id=author.id):
                break

        if not channel:
            raise CommandError('%s' % self.dialogue.get(lang, 'Dialog_UserNoVoChSummon', fallback='You are not in a voice channel!')) #X4: Translated

        chperms = channel.permissions_for(channel.server.me)

        if not chperms.connect:
            print("%s \"%s\", %s." % (self.dialogue.get(lang, 'Dialog_SummonPermissionA', fallback='Cannot join channel').replace(u'\x5cn', '\n'), channel.name, self.dialogue.get(lang, 'Dialog_SummonPermissionB', fallback='no permission').replace(u'\x5cn', '\n'))) #X4: Translated
            return Response("```%s \"%s\", %s.```" % (self.dialogue.get(lang, 'Dialog_SummonPermissionA', fallback='Cannot join channel').replace(u'\x5cn', '\n'), channel.name, self.dialogue.get(lang, 'Dialog_SummonPermissionB', fallback='no permission').replace(u'\x5cn', '\n')), delete_after=15) #X4: Translated

        elif not chperms.speak:
            print("%s \"%s\", %s." % (self.dialogue.get(lang, 'Dialog_SummonPermissionSpeakA', fallback='Will not join channel').replace(u'\x5cn', '\n'), channel.name, self.dialogue.get(lang, 'Dialog_SummonPermissionSpeakB', fallback='no permission to speak').replace(u'\x5cn', '\n'))) #X4: Translated
            return Response("```%s \"%s\", %s.```" % (self.dialogue.get(lang, 'Dialog_SummonPermissionSpeakA', fallback='Will not join channel').replace(u'\x5cn', '\n'), channel.name, self.dialogue.get(lang, 'Dialog_SummonPermissionSpeakB', fallback='no permission to speak').replace(u'\x5cn', '\n')), delete_after=15) #X4: Translated

        # if moving:
        #     await self.move_member(channel.server.me, channel)
        #     return Response('ok?')

        player = await self.get_player(channel, author, create=True)

        if player.is_stopped:
            player.play()

    async def handle_pause(self, player, author):
        """
        Usage {command_prefix}pause
        Pauses playback of the current song. [todo: should make sure it works fine when used inbetween songs]
        """
        global landconf #X4: Use language mode
        lang = langconf.get('User', author.id, fallback=self.config.server_language_mode) #X4: Use personal language or default

        if player.is_playing:
            player.pause()

        else:
            raise CommandError('%s' % self.dialogue.get(lang, 'Dialog_PauseError', fallback='Player is not playing.').replace(u'\x5cn', '\n')) #X4: Translated

    async def handle_resume(self, player, author):
        """
        Usage {command_prefix}resume
        Resumes playback of a paused song.
        """
        global landconf #X4: Use language mode
        lang = langconf.get('User', author.id, fallback=self.config.server_language_mode) #X4: Use personal language or default

        if player.is_paused:
            player.resume()

        else:
            raise CommandError('%s' % self.dialogue.get(lang, 'Dialog_ResumeError', fallback='Player is not paused.').replace(u'\x5cn', '\n')) #X4: Translated

    async def handle_shuffle(self, player, author): #X4: Added author for use his id
        """
        Usage {command_prefix}shuffle
        Shuffles the playlist.
        """
        global landconf #X4: Use language mode
        lang = langconf.get('User', author.id, fallback=self.config.server_language_mode) #X4: Use personal language or default

        player.playlist.shuffle()
        return Response('%s' % self.dialogue.get(lang, 'Dialog_Shuffle', fallback='*shuffleshuffleshuffle*').replace(u'\x5cn', '\n'), delete_after=10) #X4: Translated

    async def handle_clear(self, player, author): #X4: Added author for use his id
        """
        Usage {command_prefix}clear
        Clears the playlist.
        """
        global landconf #X4: Use language mode
        lang = langconf.get('User', author.id, fallback=self.config.server_language_mode) #X4: Use personal language or default

        if author.id == self.config.owner_id:
            player.playlist.clear()
            return Response('%s' % self.dialogue.get(lang, 'Dialog_Clear', fallback='*Playlist cleared*').replace(u'\x5cn', '\n'), delete_after=10) #X4: Added response and also translated
        else: #X4: Notify user, that he can't use this command
            raise CommandError('%s' % self.dialogue.get(lang, 'Dialog_ClearError', fallback='Only Owner can use this command.').replace(u'\x5cn', '\n')) #X4: Notify, translated

    async def handle_skip(self, player, channel, author):
        """
        Usage {command_prefix}skip
        Skips the current song when enough votes are cast, or by the bot owner.
        """
        global landconf #X4: Use language mode
        lang = langconf.get('User', author.id, fallback=self.config.server_language_mode) #X4: Use personal language or default

        if player.is_stopped or player.is_paused: # TODO: pausing and skipping a song breaks /something/, i'm not sure what
            raise CommandError("%s" % self.dialogue.get(lang, 'Dialog_SkipWhileNoSummon', fallback='Can\'t skip! The player is not playing!').replace(u'\x5cn', '\n')) #X4: Translated

        if author.id == self.config.owner_id:
            player.skip()
            return

        voice_channel = player.voice_client.channel

        num_voice = sum(1 for m in voice_channel.voice_members if not (
            m.deaf or m.self_deaf or m.id == str(self.config.owner_id)))

        num_skips = player.skip_state.add_skipper(author.id)

        skips_remaining = min(self.config.skips_required, round(num_voice * self.config.skip_ratio_required)) - num_skips

        if skips_remaining <= 0:
            player.skip()
            return Response(
                '{} **{}** {}{}'.format(
                    self.dialogue.get(lang, 'Dialog_SkipRemainA', fallback='your skip for').replace(u'\x5cn', '\n'),
                    player.current_entry.title,
                    self.dialogue.get(lang, 'Dialog_SkipRemainB', fallback='was acknowledged.\nThe vote to skip has been passed.').replace(u'\x5cn', '\n'),
                    ' %s' % self.dialogue.get(lang, 'Dialog_SkipRemainC', fallback='Next song coming up!').replace(u'\x5cn', '\n') if player.playlist.peek() else ''
                ), #X4: Translated
                reply=True,
                delete_after=10
            )

        else:
            # TODO: When a song gets skipped, delete the old x needed to skip messages
            return Response(
                '{} **{}** {} **{}** {} {} {}'.format(
                    self.dialogue.get(lang, 'Dialog_SkipRemainA', fallback='your skip for').replace(u'\x5cn', '\n'),
                    player.current_entry.title,
                    self.dialogue.get(lang, 'Dialog_SkipRemainB2', fallback='was acknowledged.\n').replace(u'\x5cn', '\n'),
                    skips_remaining,
                    self.dialogue.get(lang, 'Dialog_SkipRemainC2', fallback='more').replace(u'\x5cn', '\n'),
                    '%s' % self.dialogue.get(lang, 'Dialog_SkipRemain21', fallback='person is').replace(u'\x5cn', '\n') if skips_remaining == 1 else '%s' % self.dialogue.get(lang, 'Dialog_SkipRemain2m', fallback='people are').replace(u'\x5cn', '\n'),
                    self.dialogue.get(lang, 'Dialog_SkipRemainD2', fallback='required to vote to skip this song.').replace(u'\x5cn', '\n')
                ),
                reply=True
            ) #X4: This response translated

    async def handle_s(self, player, channel, author): #X4: Add shortcut command
        """
        Usage {command_prefix}s
        Skips the current song when enough votes are cast, or by the bot owner.
        """

        await self.handle_skip(player, channel, author) #X4: Use shortcut to main function

    async def handle_volume(self, author, message, new_volume=None): #X4: Added author for use his id
        """
        Usage {command_prefix}volume (+/-)[volume]
        Sets the playback volume. Accepted values are from 1 to 100.
        Putting + or - before the volume will make the volume change relative to the current volume.
        """
        global landconf #X4: Use language mode
        lang = langconf.get('User', author.id, fallback=self.config.server_language_mode) #X4: Use personal language or default

        player = await self.get_player(message.channel, author)

        if not new_volume:
            return Response('%s `%s%%`' % (self.dialogue.get(lang, 'Dialog_NewVolumeA', fallback='Current volume:').replace(u'\x5cn', '\n'), int(player.volume * 100)), reply=True, delete_after=10) #X4: Translated

        relative = False
        if new_volume[0] in '+-':
            relative = True

        try:
            new_volume = int(new_volume)

        except ValueError:
            raise CommandError('{} {}'.format(new_volume, self.dialogue.get(lang, 'Dialog_NewVolumeError', fallback='is not a valid number').replace(u'\x5cn', '\n'))) #X4: Translated

        if relative:
            vol_change = new_volume
            new_volume += (player.volume * 100)

        old_volume = int(player.volume * 100)

        if 0 < new_volume <= 100:
            player.volume = new_volume / 100.0

            return Response('%s %d %s %d' % (self.dialogue.get(lang, 'Dialog_NewVolumeB', fallback='updated volume from').replace(u'\x5cn', '\n'), old_volume, self.dialogue.get(lang, 'Dialog_NewVolumeC', fallback='to').replace(u'\x5cn', '\n'), new_volume), reply=True, delete_after=10) #X4: Translated

        else:
            if relative:
                raise CommandError('{} {}{:+} -> {}%. {} {} {} {:+}.'.format(self.dialogue.get(lang, 'Dialog_VolChangeErrorA', fallback='Unreasonable volume change provided:').replace(u'\x5cn', '\n'), old_volume, vol_change, old_volume + vol_change, self.dialogue.get(lang, 'Dialog_VolChangeErrorB', fallback='Provide a change between').replace(u'\x5cn', '\n'), 1 - old_volume, self.dialogue.get(lang, 'Dialog_VolChangeErrorC', fallback='and').replace(u'\x5cn', '\n'), 100 - old_volume)) #X4: Translated
            else:
                raise CommandError('{} {}%. {}'.format(self.dialogue.get(lang, 'Dialog_VolChangeErrorA2', fallback='Unreasonable volume provided:').replace(u'\x5cn', '\n'), new_volume, self.dialogue.get(lang, 'Dialog_VolChangeErrorB2', fallback='Provide a value between 1 and 100.').replace(u'\x5cn', '\n'))) #X4: Translated

    async def handle_queue(self, channel, author): #X4: Added author for use his id
        """
        Usage {command_prefix}queue
        Prints the current song queue.
        """
        global landconf #X4: Use language mode
        lang = langconf.get('User', author.id, fallback=self.config.server_language_mode) #X4: Use personal language or default

        player = await self.get_player(channel, author) #X4: Added author for use his id

        lines = []
        unlisted = 0
        andmoretext = '* ... %s %s %s*' % (self.dialogue.get(lang, 'Dialog_AndMoreA', fallback='and'), 'x'*len(player.playlist.entries), self.dialogue.get(lang, 'Dialog_AndMoreB', fallback='more')) #X4: Translated

        if player.current_entry:
            song_progress = str(timedelta(seconds=player.progress)).lstrip('0').lstrip(':')
            song_total = str(timedelta(seconds=player.current_entry.duration)).lstrip('0').lstrip(':')
            prog_str = '`[%s/%s]`' % (song_progress, song_total)

            if player.current_entry.meta.get('channel', False) and player.current_entry.meta.get('author', False):
                lines.append("%s **%s** %s **%s** %s\n" % (
                    self.dialogue.get(lang, 'Dialog_NowPlaying', fallback='Now Playing:').replace(u'\x5cn', '\n'), player.current_entry.title, self.dialogue.get(lang, 'Dialog_AddedBy', fallback='added by').replace(u'\x5cn', '\n'), player.current_entry.meta['author'].name, prog_str)) #X4: Translated
            else:
                lines.append("%s **%s** %s\n" % (self.dialogue.get(lang, 'Dialog_NowPlaying', fallback='Now Playing:').replace(u'\x5cn', '\n'), player.current_entry.title, prog_str)) #X4: Translated


        for i, item in enumerate(player.playlist, 1):
            if item.meta.get('channel', False) and item.meta.get('author', False):
                nextline = '`{}.` **{}** {} **{}**'.format(i, item.title, self.dialogue.get(lang, 'Dialog_AddedBy', fallback='added by'), item.meta['author'].name).strip() #X4: Translated
            else:
                nextline = '`{}.` **{}**'.format(i, item.title).strip()

            currentlinesum = sum([len(x)+1 for x in lines]) # +1 is for newline char

            if currentlinesum + len(nextline) + len(andmoretext) > DISCORD_MSG_CHAR_LIMIT:
                if currentlinesum + len(andmoretext):
                    unlisted += 1
                    continue

            lines.append(nextline)

        if unlisted:
            lines.append('\n*... %s %s %s*' % (self.dialogue.get(lang, 'Dialog_AndMoreA', fallback='and'), unlisted, self.dialogue.get(lang, 'Dialog_AndMoreB', fallback='more'))) #X4: Translated

        if not lines: 
            lines.append('{} {}play.'.format(self.dialogue.get(lang, 'Dialog_NoQueue', fallback='There are no songs queued! Queue something with').replace(u'\x5cn', '\n'), self.config.command_prefix)) #X4: Translated

        message = '\n'.join(lines)
        return Response(message, delete_after=30)

    async def handle_q(self, channel, author): #X4: Add shortcut command, use author.id for language
        """
        Usage {command_prefix}q
        Prints the current song queue.
        """
        global landconf #X4: Use language mode
        lang = langconf.get('User', author.id, fallback=self.config.server_language_mode) #X4: Use personal language or default

        player = await self.get_player(channel, author) #X4: Added author for use his id

        lines = []
        unlisted = 0
        andmoretext = '* ... %s %s %s*' % (self.dialogue.get(lang, 'Dialog_AndMoreA', fallback='and'), 'x'*len(player.playlist.entries), self.dialogue.get(lang, 'Dialog_AndMoreB', fallback='more')) #X4: Translated

        if player.current_entry:
            song_progress = str(timedelta(seconds=player.progress)).lstrip('0').lstrip(':')
            song_total = str(timedelta(seconds=player.current_entry.duration)).lstrip('0').lstrip(':')
            prog_str = '`[%s/%s]`' % (song_progress, song_total)

            if player.current_entry.meta.get('channel', False) and player.current_entry.meta.get('author', False):
                lines.append("%s **%s** %s **%s** %s\n" % (
                    self.dialogue.get(lang, 'Dialog_NowPlaying', fallback='Now Playing:').replace(u'\x5cn', '\n'), player.current_entry.title, self.dialogue.get(lang, 'Dialog_AddedBy', fallback='added by').replace(u'\x5cn', '\n'), player.current_entry.meta['author'].name, prog_str)) #X4: Translated
            else:
                lines.append("%s **%s** %s\n" % (self.dialogue.get(lang, 'Dialog_NowPlaying', fallback='Now Playing:').replace(u'\x5cn', '\n'), player.current_entry.title, prog_str)) #X4: Translated


        for i, item in enumerate(player.playlist, 1):
            if item.meta.get('channel', False) and item.meta.get('author', False):
                nextline = '`{}.` **{}** {} **{}**'.format(i, item.title, self.dialogue.get(lang, 'Dialog_AddedBy', fallback='added by'), item.meta['author'].name).strip() #X4: Translated
            else:
                nextline = '`{}.` **{}**'.format(i, item.title).strip()

            currentlinesum = sum([len(x)+1 for x in lines]) # +1 is for newline char

            if currentlinesum + len(nextline) + len(andmoretext) > DISCORD_MSG_CHAR_LIMIT:
                if currentlinesum + len(andmoretext):
                    unlisted += 1
                    continue

            lines.append(nextline)

        if unlisted:
            lines.append('\n*... %s %s %s*' % (self.dialogue.get(lang, 'Dialog_AndMoreA', fallback='and'), unlisted, self.dialogue.get(lang, 'Dialog_AndMoreB', fallback='more'))) #X4: Translated

        if not lines:
            lines.append('{} {}play.'.format(self.dialogue.get(lang, 'Dialog_NoQueue', fallback='There are no songs queued! Queue something with').replace(u'\x5cn', '\n'), self.config.command_prefix)) #X4: Translated

        message = '\n'.join(lines)
        return Response(message, delete_after=30)

    """async def handle_q(self, channel): #X4: Add shortcut command
        "" "
        Usage {command_prefix}q
        Prints the current song queue.
        "" "

        await self.handle_queue(channel) #X4: Use shortcut to main function"""

    async def handle_remove(self, author, player, channel): #X4: New command REMOVE to remove trash in auto playlist
        """
        Usage {command_prefix}remove
        Remove this URL into auto playlist.
        """
        global landconf #X4: Use language mode
        lang = langconf.get('User', author.id, fallback=self.config.server_language_mode) #X4: Use personal language or default

        player = await self.get_player(channel, author) #X4: Initialize player

        if player.current_entry.url in self.backuplist: #X4: Check that URL not exist in our playlist
            self.backuplist.remove(player.current_entry.url) #X4: Remove URL from autoplaylist (because it don't interesting or trash or too long or else...)
            write_file(self.config.backup_playlist_file, self.backuplist) #X4: Save and close our autoplaylist without current playing song
        else:
            raise CommandInfo('%s %s' % (player.current_entry.title, self.dialogue.get(lang, 'Dialog_RemoveError', fallback='not in playlist. Can\'t remove it.').replace(u'\x5cn', '\n'))) #X4: Translated

        return Response("%s **%s** %s" % (self.dialogue.get(lang, 'Dialog_RemovedA', fallback='Song').replace(u'\x5cn', '\n'), player.current_entry.title, self.dialogue.get(lang, 'Dialog_RemovedB', fallback='**__removed__** from rotation. Use command `undo` to back this track.').replace(u'\x5cn', '\n')), delete_after=25) #X4: End REMOVE, translated

    async def handle_rem(self, author, player, channel): #X4: New command REM (copy of REMOVE) to remove trash in auto playlist
        """
        Usage {command_prefix}rem
        Remove this URL into auto playlist.
        """
        global landconf #X4: Use language mode
        lang = langconf.get('User', author.id, fallback=self.config.server_language_mode) #X4: Use personal language or default

        player = await self.get_player(channel, author) #X4: Initialize player

        if player.current_entry.url in self.backuplist: #X4: Check that URL not exist in our playlist
            self.backuplist.remove(player.current_entry.url) #X4: Remove URL from autoplaylist (because it don't interesting or trash or too long or else...)
            write_file(self.config.backup_playlist_file, self.backuplist) #X4: Save and close our autoplaylist without current playing song
        else:
            raise CommandInfo('**%s** %s' % (player.current_entry.title, self.dialogue.get(lang, 'Dialog_RemoveError', fallback='not in playlist. Can\'t remove it.').replace(u'\x5cn', '\n'))) #X4: Translated

        return Response("%s **%s** %s" % (self.dialogue.get(lang, 'Dialog_RemovedA', fallback='Song').replace(u'\x5cn', '\n'), player.current_entry.title, self.dialogue.get(lang, 'Dialog_RemovedB', fallback='**__removed__** from rotation. Use command `undo` to back this track.').replace(u'\x5cn', '\n')), delete_after=25) #X4: End REM, translated

    """async def handle_rem(self, player, channel): #X4: Add shortcut command
        "" "
        Usage {command_prefix}rem
        Remove this URL into auto playlist.
        "" "

        await self.handle_remove(player, channel) #X4: Use shortcut to main function"""

    async def handle_undo(self, author, player, channel): #X4: New command UNDO to undo remove command
        """
        Usage {command_prefix}undo
        Undo removed URL.
        """
        global landconf #X4: Use language mode
        lang = langconf.get('User', author.id, fallback=self.config.server_language_mode) #X4: Use personal language or default

        player = await self.get_player(channel, author) #X4: Initialize player

        if player.current_entry.url not in self.backuplist: #X4: Check that URL not exist in our playlist
            self.backuplist.append(player.current_entry.url) #X4: Add URL in our playlist
            write_file(self.config.backup_playlist_file, self.backuplist) #X4: Save and close file backuplist.txt (with new track)
        else:
            raise CommandInfo('%s **%s** %s' % (self.dialogue.get(lang, 'Dialog_UndoWarningA', fallback='No need to undo.').replace(u'\x5cn', '\n'), player.current_entry.title, self.dialogue.get(lang, 'Dialog_UndoWarningB', fallback='Already have in playlist.').replace(u'\x5cn', '\n'))) #X4: Translated

        return Response("%s **%s** %s" % (self.dialogue.get(lang, 'Dialog_UndoA', fallback='**Undo successful.** Song').replace(u'\x5cn', '\n'), player.current_entry.title, self.dialogue.get(lang, 'Dialog_UndoB', fallback='is back from rotation.').replace(u'\x5cn', '\n')), delete_after=15) #X4: End UNDO, translated

    async def handle_u(self, author, player, channel): #X4: New command U (copy of UNDO) to undo remove command
        """
        Usage {command_prefix}u
        Undo removed URL.
        """
        global landconf #X4: Use language mode
        lang = langconf.get('User', author.id, fallback=self.config.server_language_mode) #X4: Use personal language or default

        player = await self.get_player(channel, author) #X4: Initialize player

        if player.current_entry.url not in self.backuplist: #X4: Check that URL not exist in our playlist
            self.backuplist.append(player.current_entry.url) #X4: Add URL in our playlist
            write_file(self.config.backup_playlist_file, self.backuplist) #X4: Save and close file backuplist.txt (with new track)
        else:
            raise CommandInfo('%s **%s** %s' % (self.dialogue.get(lang, 'Dialog_UndoWarningA', fallback='No need to undo.').replace(u'\x5cn', '\n'), player.current_entry.title, self.dialogue.get(lang, 'Dialog_UndoWarningB', fallback='Already have in playlist.').replace(u'\x5cn', '\n'))) #X4: Translated

        return Response("%s **%s** %s" % (self.dialogue.get(lang, 'Dialog_UndoA', fallback='**Undo successful.** Song').replace(u'\x5cn', '\n'), player.current_entry.title, self.dialogue.get(lang, 'Dialog_UndoB', fallback='is back from rotation.').replace(u'\x5cn', '\n')), delete_after=15) #X4: End U, translated

    """async def handle_u(self, player, channel): #X4: Add shortcut command
        "" "
        Usage {command_prefix}u
        Undo removed URL.
        "" "

        await self.handle_undo(player, channel) #X4: Use shortcut to main function"""

    async def handle_clean(self, message, author, amount):
        """
        Usage {command_prefix}clean [amount]
        Removes [amount] messages the bot has posted in chat.
        """
        pass

    async def handle_setlanguage(self, message, author, language): #X4: This function setup custom language per user. And save in userlang.txt.
        """
        Usage {command_prefix}setlanguage [language]
        Setup bot language for your reply. Language is 2 letters abbreviation (see http://www.abbreviations.com/acronyms/LANGUAGES2L).
        """
        global landconf #X4: Use language mode
        lang = langconf.get('User', author.id, fallback=None) #X4: Get current language
        if lang == language: #X4: If user try to apply same language, no need to reapply it
            raise CommandInfo('%s' % self.dialogue.get(language, 'Dialog_SameLanguage', fallback=None)) #X4: Send notification to user
        if lang == None: #X4: For empty setting
            lang = self.config.server_language_mode #X4: Set default server language
            langconf.set('User', author.id, language) #X4: Set new language for user
            with open('config/userlang.txt', 'w') as lwritefile: #X4: Open our config with write access
                langconf.write(lwritefile) #X4: Apply changes in file and auto-close it
            raise CommandInfo('Changed your custom language to **%s**. %s' % (language, self.dialogue.get(language, 'Dialog_NewLanguage', fallback=None))) #X4: Send notification to user (also use new language)
        langconf.set('User', author.id, language) #X4: Set new language for user
        with open('config/userlang.txt', 'w') as lwritefile: #X4: Open our config with write access
            langconf.write(lwritefile) #X4: Apply changes in file and auto-close it
        raise CommandInfo('Changed your custom language **%s** to new **%s**. %s' % (lang, language, self.dialogue.get(language, 'Dialog_NewLanguage', fallback=None))) #X4: Send notification to user (also use new language)

    """ X4: First version of code
    async def handle_setlanguage(self, message, author, language): #X4: This function setup custom language per user. And save in userlang.txt.
        "" "
        Usage {command_prefix}setlanguage [language]
        Setup bot language for your reply. Language is 2 letters abbreviation (see http://www.abbreviations.com/acronyms/LANGUAGES2L).
        "" "
        for lconfstring in self.userlang: #X4: Separate multiline file into strings
            if author.id in lconfstring: #X4: Check per string author.id and if found use replace algorithm
                aid, sep, lang = lconfstring.partition('=') #X4: Separate id=language into 'id', '=' and 'language'
                if lang == language: #X4: If user try to apply same language, no need to reapply it
                    raise CommandInfo('You already setup bot to reply on **%s** language.' % language) #X4: Send notification to user
                else: #X4: Else
                    self.userlang.remove(lconfstring) #X4: Remove old setting about user language
                    lconfstring = aid + sep + language #X4: Create new string with new parameter
                    self.userlang.append(lconfstring) #X4: Add new parameter in database
                    write_file(self.config.user_language_file, self.userlang) #X4: Save and close language database file
                    raise CommandInfo('Changed your custom language **%s** to new **%s**. Now bot will speak to you on this language.' % (lang, language)) #X4: Send notification to user
                
        #X4: algorithm if settings don't setup (first time)
        lconfstring = author.id + '=' + language #X4: Use string to make one argument for append
        self.userlang.append(lconfstring) #X4: Add new parameter in database
        write_file(self.config.user_language_file, self.userlang) #X4: Save and close language database file
        raise CommandInfo('Default language is now **%s**. Now bot will speak to you on this language.' % language) #X4: Send notification to user"""

    async def handle_sl(self, message, author, language): #X4: This function setup custom language per user. And save in userlang.txt.
        """
        Usage {command_prefix}sl [language]
        Setup bot language for your reply. Language is 2 letters abbreviation (see http://www.abbreviations.com/acronyms/LANGUAGES2L).
        """
        global landconf #X4: Use language mode
        lang = langconf.get('User', author.id, fallback=None) #X4: Get current language
        if lang == language: #X4: If user try to apply same language, no need to reapply it
            raise CommandInfo('%s' % self.dialogue.get(language, 'Dialog_SameLanguage', fallback=None)) #X4: Send notification to user
        if lang == None: #X4: For empty setting
            lang = self.config.server_language_mode #X4: Set default server language
            langconf.set('User', author.id, language) #X4: Set new language for user
            with open('config/userlang.txt', 'w') as lwritefile: #X4: Open our config with write access
                langconf.write(lwritefile) #X4: Apply changes in file and auto-close it
            raise CommandInfo('Changed your custom language to **%s**. %s' % (language, self.dialogue.get(language, 'Dialog_NewLanguage', fallback=None))) #X4: Send notification to user (also use new language)
        langconf.set('User', author.id, language) #X4: Set new language for user
        with open('config/userlang.txt', 'w') as lwritefile: #X4: Open our config with write access
            langconf.write(lwritefile) #X4: Apply changes in file and auto-close it
        raise CommandInfo('Changed your custom language **%s** to new **%s**. %s' % (lang, language, self.dialogue.get(language, 'Dialog_NewLanguage', fallback=None))) #X4: Send notification to user (also use new language)

    async def handle_unsetlanguage(self, message, author): #X4: This function delete custom language per user. It will use default bot language.
        """
        Usage {command_prefix}unsetlanguage
        Setup bot language for your reply. 
        """
        global landconf
        if langconf.get('User', author.id, fallback=None) != None:
            langconf.remove_option('User', author.id) #X4: Remove string with language settings for user who call function
            with open('config/userlang.txt', 'w') as lwritefile: #X4: Open our config with write access
                langconf.write(lwritefile) #X4: Apply changes in file and auto-close it
            raise CommandInfo('%s' % self.dialogue.get(langconf.get('User', author.id, fallback=self.config.server_language_mode), 'Dialog_ResetLanguage', fallback=None)) #X4: Send notification to user
            """ X4: First version of code
            for lconfstring in self.userlang: #X4: Sepagate multiline file into strings
                if author.id in lconfstring: #X4: Check per string author.id and if found use replace algorithm
                    self.userlang.remove(lconfstring) #X4: Remove user custom language
                    write_file(self.config.user_language_file, self.userlang) #X4: Save and close language database file"""
        raise CommandInfo('%s' % self.dialogue.get(langconf.get('User', author.id, fallback=self.config.server_language_mode), 'Dialog_NoLanguage', fallback=None)) #X4: Send notification to user

    async def on_message(self, message):

        if message.author == self.user:
            if message.content.startswith(self.config.command_prefix):
                print("Ignoring command from myself (%s)" % message.content)
            return

        if message.channel.is_private:
            await self.send_message(message.channel, 'You cannot use this bot in private messages.')
            return

        message_content = message.content.strip()
        if not message_content.startswith(self.config.command_prefix):
            return
      
        if self.config.exclusive_text_channel:
            if not message.channel.name == self.config.exclusive_text_channel:
                print("Ignoring command from channel #{0}, because I am using exclusive channel #{1}"
                        .format(message.channel.name, self.config.exclusive_text_channel))
                return

        command, *args = message_content.split()
        command = command[len(self.config.command_prefix):].lower().strip()

        handler = getattr(self, 'handle_%s' % command, None)
        if not handler:
            return


        if int(message.author.id) in self.blacklist and message.author.id != self.config.owner_id:
            print("[Blacklisted] {0.id}/{0.name} ({1})".format(message.author, message_content))
            return

        elif self.config.white_list_check and int(message.author.id) not in self.whitelist and message.author.id != self.config.owner_id:
            print("[Not whitelisted] {0.id}/{0.name} ({1})".format(message.author, message_content))
            return

        else:
            print("[Command] {0.id}/{0.name} ({1})".format(message.author, message_content))


        argspec = inspect.signature(handler)
        params = argspec.parameters.copy()

        # noinspection PyBroadException
        try:
            handler_kwargs = {}
            if params.pop('message', None):
                handler_kwargs['message'] = message

            if params.pop('channel', None):
                handler_kwargs['channel'] = message.channel

            if params.pop('author', None):
                handler_kwargs['author'] = message.author

            if params.pop('player', None):
                handler_kwargs['player'] = await self.get_player(message.channel, message.author) #X4: Added author argument for use his id

            args_expected = []
            for key, param in list(params.items()):
                doc_key = '[%s=%s]' % (key, param.default) if param.default is not inspect.Parameter.empty else key
                args_expected.append(doc_key)

                if not args and param.default is not inspect.Parameter.empty:
                    params.pop(key)
                    continue

                if args:
                    arg_value = args.pop(0)
                    handler_kwargs[key] = arg_value
                    params.pop(key)

            if params:
                docs = getattr(handler, '__doc__', None)
                if not docs:
                    docs = 'Usage: {}{} {}'.format(
                        self.config.command_prefix,
                        command,
                        ' '.join(args_expected)
                    )

                docs = '\n'.join(l.strip() for l in docs.split('\n'))
                await self.send_message(
                    message.channel,
                    '```\n%s\n```' % docs.format(command_prefix=self.config.command_prefix)
                )
                return

            response = await handler(**handler_kwargs)
            if response and isinstance(response, Response):
                content = response.content
                if response.reply:
                    content = '%s, %s' % (message.author.mention, content)

                sentmsg = await self.send_message(message.channel, content)

                if response.delete_after > 0:
                    await asyncio.sleep(response.delete_after)
                    await self.delete_message(sentmsg)
                    # TODO: Add options for deletion toggling

        except CommandError as e:
            await self.send_message(message.channel, '```\n%s\n```' % e.message)

        except CommandInfo as e: #X4: Custom exception for non-warning end of function
            await self.send_message(message.channel, '%s' % e.message) #X4: Style of output message

        except:
            await self.send_message(message.channel, '```\n%s\n```' % traceback.format_exc())
            traceback.print_exc()

"""class Author: #X4: on_ready call summon without author argument
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)"""

if __name__ == '__main__':
    bot = MusicBot()
    bot.run()


'''
TODOs:
  Deleting messages
    Maybe Response objects can have a parameter that deletes the message
    Probably should have an section for it in the options file
    If not, we should have a cleanup command, or maybe have one anyways

  Command to clear the queue, either a `!skip all` argument or a `!clear` or `!queue clear` or whatever

'''
