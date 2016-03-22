import os
import sys
import time
import shlex
import shutil
import inspect
import discord
import asyncio
import traceback

from discord import utils
from discord.object import Object
from discord.enums import ChannelType
from discord.voice_client import VoiceClient

from random import choice
from functools import wraps
from textwrap import dedent
from datetime import timedelta

from musicbot.playlist import Playlist
from musicbot.player import MusicPlayer
from musicbot.config import Config, ConfigDefaults
from musicbot.permissions import Permissions, PermissionsDefaults
from musicbot.utils import load_file, extract_user_id, write_file, sane_round_int

from .downloader import extract_info
from .opus_loader import load_opus_lib
from .version import VERSION as BOTVERSION
from .constants import DISCORD_MSG_CHAR_LIMIT, AUDIO_CACHE_PATH
from .exceptions import CommandError, PermissionsError, HelpfulError

load_opus_lib()


class SkipState:
    def __init__(self):
        self.skippers = set()
        self.skip_msgs = set()

    @property
    def skip_count(self):
        return len(self.skippers)

    def reset(self):
        self.skippers.clear()
        self.skip_msgs.clear()

    def add_skipper(self, skipper, msg):
        self.skippers.add(skipper)
        self.skip_msgs.add(msg)
        return self.skip_count


class Response:
    def __init__(self, content, reply=False, delete_after=0):
        self.content = content
        self.reply = reply
        self.delete_after = delete_after


class MusicBot(discord.Client):
    def __init__(self, config_file=ConfigDefaults.options_file, perms_file=PermissionsDefaults.perms_file):
        super().__init__()

        self.headers['user-agent'] += ' MusicBot/%s' % BOTVERSION

        self.players = {}
        self.voice_clients = {}
        self.voice_client_connect_lock = asyncio.Lock()
        self.voice_client_move_lock = asyncio.Lock()
        self.config = Config(config_file)
        self.permissions = Permissions(perms_file, grant_all=[self.config.owner_id])

        self.blacklist = set(load_file(self.config.blacklist_file))
        self.whitelist = set(load_file(self.config.whitelist_file))
        self.autoplaylist = load_file(self.config.auto_playlist_file)

        if not self.autoplaylist:
            print("Warning: Autoplaylist is empty, disabling.")
            self.config.auto_playlist = False

        # These aren't multiserver comptable, which is ok for now, but will have to be redone when multiserver is possible
        self.last_np_msg = None
        self.auto_paused = None

    # TODO: Add some sort of `denied` argument for a message to send when someone else tries to use it
    def owner_only(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            # Only allow the owner to use these commands
            orig_msg = self._get_variable('message')

            if not orig_msg or orig_msg.author.id == self.config.owner_id:
                return await func(self, *args, **kwargs)
            else:
                raise PermissionsError("only the owner can use this command", expire_in=30)

        return wrapper

    def _get_variable(self, name):
        stack = inspect.stack()
        try:
            for frames in stack:
                current_locals = frames[0].f_locals
                if name in current_locals:
                    return current_locals[name]
        finally:
            del stack

    def _fixg(self, x, dp=2):
        return ('{:.%sf}' % dp).format(x).rstrip('0').rstrip('.')

    def _get_owner(self, voice=False):
        if voice:
            for server in self.servers:
                for channel in server.channels:
                    for m in channel.voice_members:
                        if m.id == self.config.owner_id:
                            return m
        else:
            return discord.utils.find(lambda m: m.id == self.config.owner_id, self.get_all_members())

    def _delete_old_audiocache(self, path=AUDIO_CACHE_PATH):
        try:
            shutil.rmtree(path)
            return True
        except:
            try:
                os.rename(path, path + '__')
            except:
                return False
            try:
                shutil.rmtree(path)
            except:
                os.rename(path + '__', path)
                return False

        return True

    # TODO: autosummon option to a specific channel
    async def _auto_summon(self, channel=None):
        owner = self._get_owner(voice=True)
        if owner:
            await self.cmd_summon(owner.voice_channel, owner, None)
            return True
        else:
            return False

    async def _wait_delete_msg(self, message, after):
        await asyncio.sleep(after)
        await self.safe_delete_message(message)

    async def _check_ignore_non_voice(self, msg):
        vc = msg.server.me.voice_channel

        # If we've connected to a voice chat and we're in the same voice channel
        if not vc or vc == msg.author.voice_channel:
            return True
        else:
            raise PermissionsError(
                "you cannot use this command when not in the voice channel (%s)" % vc.name, expire_in=30)

    async def get_voice_client(self, channel):
        if isinstance(channel, Object):
            channel = self.get_channel(channel.id)

        if getattr(channel, 'type', ChannelType.text) != ChannelType.voice:
            raise AttributeError('Channel passed must be a voice channel')

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

            # TODO: Bug: the channel doesn't get updated when the bot is moved

            await voice_client.connect()
            return voice_client

    async def move_voice_client(self, channel):
        if isinstance(channel, Object):
            channel = self.get_channel(channel.id)

        if getattr(channel, 'type', ChannelType.text) != ChannelType.voice:
            raise AttributeError('Channel passed must be a voice channel')

        with await self.voice_client_move_lock:
            server = channel.server

            payload = {
                "op": 4,
                "d": {
                    "guild_id": server.id,
                    "channel_id": channel.id,
                    "self_mute": False,
                    "self_deaf": False
                }
            }

            await self.ws.send(utils.to_json(payload))
            self.voice_clients[server.id].channel = channel


    async def get_player(self, channel, create=False):
        server = channel.server

        if server.id not in self.players:
            if not create:
                raise CommandError(
                    'The bot is not in a voice channel.  '
                    'Use %ssummon to summon it to your voice channel.' % self.config.command_prefix)

            voice_client = await self.get_voice_client(channel)

            playlist = Playlist(self)
            player = MusicPlayer(self, voice_client, playlist) \
                .on('play', self.on_play) \
                .on('resume', self.on_resume) \
                .on('pause', self.on_pause) \
                .on('stop', self.on_stop) \
                .on('finished-playing', self.on_finished_playing) \
                .on('entry-added', self.on_entry_added)

            player.skip_state = SkipState()
            self.players[server.id] = player

        return self.players[server.id]

    async def on_play(self, player, entry):
        await self.update_now_playing(entry)
        player.skip_state.reset()

        channel = entry.meta.get('channel', None)
        author = entry.meta.get('author', None)

        if channel and author:
            if self.last_np_msg and self.last_np_msg.channel == channel:

                async for lmsg in self.logs_from(channel, limit=1):
                    if lmsg != self.last_np_msg and self.last_np_msg:
                        await self.safe_delete_message(self.last_np_msg)
                        self.last_np_msg = None
                    break  # This is probably redundant

            if self.config.now_playing_mentions:
                newmsg = '%s - your song **%s** is now playing in %s!' % (
                    entry.meta['author'].mention, entry.title, player.voice_client.channel.name)
            else:
                newmsg = 'Now playing in %s: **%s**' % (
                    player.voice_client.channel.name, entry.title)

            if self.last_np_msg:
                self.last_np_msg = await self.safe_edit_message(self.last_np_msg, newmsg, send_if_fail=True)
            else:
                self.last_np_msg = await self.safe_send_message(channel, newmsg)

    async def on_resume(self, entry, **_):
        await self.update_now_playing(entry)

    async def on_pause(self, entry, **_):
        await self.update_now_playing(entry, True)

    async def on_stop(self, **_):
        await self.update_now_playing()

    async def on_finished_playing(self, player, **_):
        if not player.playlist.entries and not player.current_entry and self.config.auto_playlist:
            while self.autoplaylist:
                song_url = choice(self.autoplaylist)
                info = await extract_info(player.playlist.loop, song_url, download=False, process=False)

                if not info:
                    self.autoplaylist.remove(song_url)
                    self.safe_print("[Info] Removing unplayable song from autoplaylist: %s" % song_url)
                    write_file(self.config.auto_playlist_file, self.autoplaylist)
                    continue

                if info.get('entries', None):  # or .get('_type', '') == 'playlist'
                    pass  # Wooo playlist
                    # Blarg how do I want to do this

                await player.playlist.add_entry(song_url, channel=None, author=None)
                break

            if not self.autoplaylist:
                print("[Warning] No playable songs in the autoplaylist, disabling.")
                self.config.auto_playlist = False

    async def on_entry_added(self, playlist, entry, **_):
        pass

    async def update_now_playing(self, entry=None, is_paused=False):
        game = None
        if entry:
            prefix = u'\u275A\u275A ' if is_paused else ''

            name = u'{}{}'.format(prefix, entry.title)[:128]
            game = discord.Game(name=name)

        await self.change_status(game)

    async def safe_send_message(self, dest, content, *, tts=False, expire_in=0, also_delete=None, quiet=False):
        msg = None
        try:
            msg = await self.send_message(dest, content, tts=tts)

            if msg and expire_in:
                asyncio.ensure_future(self._wait_delete_msg(msg, expire_in))

            if also_delete and isinstance(also_delete, discord.Message):
                asyncio.ensure_future(self._wait_delete_msg(also_delete, expire_in))

        except discord.Forbidden:
            if not quiet:
                self.safe_print("Warning: Cannot send message to %s, no permission" % dest.name)
        except discord.NotFound:
            if not quiet:
                self.safe_print("Warning: Cannot send message to %s, invalid channel?" % dest.name)

        return msg

    async def safe_delete_message(self, message, *, quiet=False):
        try:
            return await self.delete_message(message)

        except discord.Forbidden:
            if not quiet:
                self.safe_print("Warning: Cannot delete message \"%s\", no permission" % message.clean_content)
        except discord.NotFound:
            if not quiet:
                self.safe_print("Warning: Cannot delete message \"%s\", message not found" % message.clean_content)

    async def safe_edit_message(self, message, new, *, send_if_fail=False, quiet=False):
        try:
            return await self.edit_message(message, new)

        except discord.NotFound:
            if not quiet:
                self.safe_print("Warning: Cannot edit message \"%s\", message not found" % message.clean_content)
            if send_if_fail:
                if not quiet:
                    print("Sending instead")
                return await self.safe_send_message(message.channel, new)

    def safe_print(self, content, *, end='\n', flush=True):
        sys.stdout.buffer.write((content + end).encode('utf-8', 'replace'))
        if flush: sys.stdout.flush()

    # noinspection PyMethodOverriding
    def run(self):
        try:
            return super().run(self.config.username, self.config.password)

        except discord.errors.LoginFailure:
            raise HelpfulError("Bot cannot login, bad credentials.",
                               "Fix your Username or Password in the options file.  "
                               "Remember that each field should be on their own line.")


    async def on_ready(self):
        print('Connected!\n')

        self.safe_print("Bot:   %s/%s" % (self.user.id, self.user.name))

        owner = self._get_owner(voice=True) or self._get_owner()
        if owner:
            self.safe_print("Owner: %s/%s" % (owner.id, owner.name))
        else:
            print("Owner could not be found on any server (id: %s)" % self.config.owner_id)

        if self.config.owner_id == self.user.id:
            print("\n"
                  "[NOTICE] You have either set the OwnerID config option to the bot's id instead "
                  "of yours, or you've used your own credentials to log the bot in instead of the "
                  "bot's account (the bot needs its own account to work properly).")
        print()

        if self.servers:
            print('Server List:')
            [self.safe_print(' - ' + s.name) for s in self.servers]
        else:
            print("No servers have been joined yet.")

        print()

        if self.config.bound_channels:
            print("Bound to channels:")
            chlist = [self.get_channel(i) for i in self.config.bound_channels if i]
            [self.safe_print(' - %s/%s' % (ch.server.name.rstrip(), ch.name.lstrip())) for ch in chlist if ch]
        else:
            print("Not bound to any channels")

        print()

        # TODO: Make this prettier and easier to read (in the console)
        self.safe_print("Command prefix is %s" % self.config.command_prefix)
        print("Whitelist check is %s" % ['disabled', 'enabled'][self.config.white_list_check])
        print("Skip threshold at %s votes or %s%%" % (
        self.config.skips_required, self._fixg(self.config.skip_ratio_required * 100)))
        print("Now Playing message @mentions are %s" % ['disabled', 'enabled'][self.config.now_playing_mentions])
        print("Autosummon is %s" % ['disabled', 'enabled'][self.config.auto_summon])
        print("Auto-playlist is %s" % ['disabled', 'enabled'][self.config.auto_playlist])
        print("Downloaded songs will be %s after playback" % ['deleted', 'saved'][self.config.save_videos])
        print()

        # maybe option to leave the ownerid blank and generate a random command for the owner to use
        # wait_for_message is pretty neato

        if not self.config.save_videos and os.path.isdir(AUDIO_CACHE_PATH):
            if self._delete_old_audiocache():
                print("Deleting old audio cache")
            else:
                print("Could not delete old audio cache, moving on.")

        if self.config.auto_summon:
            print("Attempting to autosummon...", flush=True)

            as_ok = await self._auto_summon()

            if as_ok:
                print("Done!", flush=True)  # TODO: Change this to "Joined server/channel"
                if self.config.auto_playlist:
                    print("Starting auto-playlist")
                    await self.on_finished_playing(await self.get_player(owner.voice_channel))
            else:
                print("Owner not found in a voice channel, could not autosummon.")

        print()
        # t-t-th-th-that's all folks!

    async def cmd_help(self):
        """
        Usage:
            {command_prefix}help

        Prints a help message
        """

        helpmsg = "**Commands**\n```"
        commands = []

        # TODO: Get this to format nicely
        for att in dir(self):
            if att.startswith('cmd_') and att != 'cmd_help':
                command_name = att.replace('cmd_', '').lower()
                commands.append("{}{}".format(self.config.command_prefix, command_name))

        helpmsg += ", ".join(commands)
        helpmsg += "```"
        helpmsg += "https://github.com/SexualRhinoceros/MusicBot/wiki/Commands-list"

        return Response(helpmsg, reply=True, delete_after=60)

    async def cmd_whitelist(self, message, option, username):
        """
        Usage:
            {command_prefix}whitelist [ + | - | add | remove ] @UserName

        Adds or removes the user to the whitelist.
        When the whitelist is enabled, whitelisted users are permitted to use bot commands.
        """

        user_id = extract_user_id(username)
        if not user_id:
            raise CommandError('Invalid user specified')

        if option not in ['+', '-', 'add', 'remove']:
            raise CommandError('Invalid option "%s" specified, use +, -, add, or remove' % option)

        if option in ['+', 'add']:
            self.whitelist.add(user_id)
            write_file(self.config.whitelist_file, self.whitelist)

            return Response('user has been added to the whitelist', reply=True, delete_after=10)

        else:
            if user_id not in self.whitelist:
                return Response('user is not in the whitelist', reply=True, delete_after=10)

            else:
                self.whitelist.remove(user_id)
                write_file(self.config.whitelist_file, self.whitelist)

                return Response('user has been removed from the whitelist', reply=True, delete_after=10)

    async def cmd_blacklist(self, message, option, username):
        """
        Usage:
            {command_prefix}blacklist [ + | - | add | remove ] @UserName

        Adds or removes the user to the blacklist.
        Blacklisted users are forbidden from using bot commands. Blacklisting a user also removes them from the whitelist.
        """

        user_id = extract_user_id(username)
        if not user_id:
            raise CommandError('Invalid user specified')

        if str(user_id) == self.config.owner_id:
            return Response("The owner cannot be blacklisted.", delete_after=10)

        if option not in ['+', '-', 'add', 'remove']:
            raise CommandError('Invalid option "%s" specified, use +, -, add, or remove' % option)

        if option in ['+', 'add']:
            self.blacklist.add(user_id)
            write_file(self.config.blacklist_file, self.blacklist)

            if user_id in self.whitelist:
                self.whitelist.remove(user_id)
                write_file(self.config.whitelist_file, self.whitelist)
                return Response('user has been added to the blacklist and removed from the whitelist', reply=True,
                                delete_after=10)

            else:
                return Response('user has been added to the blacklist', reply=True, delete_after=10)

        else:
            if user_id not in self.blacklist:
                return Response('user is not in the blacklist', reply=True, delete_after=10)

            else:
                self.blacklist.remove(user_id)
                write_file(self.config.blacklist_file, self.blacklist)

                return Response('user has been removed from the blacklist', reply=True, delete_after=10)

    async def cmd_id(self, author, user_mentions):
        """
        Usage:
            {command_prefix}id [@user]

        Tells the user their id or the id of another user.
        """
        if not user_mentions:
            return Response('your id is `%s`' % author.id, reply=True, delete_after=35)
        else:
            usr = user_mentions[0]
            return Response("%s's id is `%s`" % (usr.name, usr.id), reply=True, delete_after=35)

    @owner_only
    async def cmd_joinserver(self, message, server_link):
        """
        Usage:
            {command_prefix}joinserver invite_link

        Asks the bot to join a server.
        """

        try:
            await self.accept_invite(server_link)
            return Response(":+1:")

        except:
            raise CommandError('Invalid URL provided:\n{}\n'.format(server_link))

    async def cmd_play(self, player, channel, author, permissions, leftover_args, song_url):
        """
        Usage:
            {command_prefix}play song_link
            {command_prefix}play text to search for

        Adds the song to the playlist.  If a link is not provided, the first
        result from a youtube search is added to the queue.
        """

        if permissions.max_songs and player.playlist.count_for_user(author) > permissions.max_songs:
            raise PermissionsError("You have reached your playlist item limit (%s)" % permissions.max_songs)

        await self.send_typing(channel)

        if leftover_args:
            song_url = ' '.join([song_url, *leftover_args])

        try:
            info = await extract_info(player.playlist.loop, song_url, download=False, process=False)
        except Exception as e:
            traceback.print_exc()
            raise CommandError("Error looking up %s:\n%s" % (song_url, e))

        if not info:
            raise CommandError("That video cannot be played.")

        if info.get('url', '').startswith('ytsearch'):
            # print("[Command:play] Searching for \"%s\"" % song_url)
            info = await extract_info(player.playlist.loop, song_url, download=False, process=True)

            if not info:
                raise CommandError(
                    "Error extracting info from search string, youtubedl returned no data.  "
                    "You may need to restart the bot if this continues to happen.")

            song_url = info['entries'][0]['webpage_url']
            info = await extract_info(player.playlist.loop, song_url, download=False, process=False)
            # Now I could just do: return await self.cmd_play(player, channel, author, song_url)
            # But this is probably fine

        if 'entries' in info:
            # I have to do exe extra checks anyways because you can request an arbritrary number of search results
            if not permissions.allow_playlists and ':search' in info['extractor'] and len(info['entries']) > 1:
                raise PermissionsError("You are not allowed to request playlists")

            # The only reason we would use this over `len(info['entries'])` is if we add `if _` to this one
            num_songs = sum(1 for _ in info['entries'])

            if permissions.max_playlist_length and num_songs > permissions.max_playlist_length:
                raise PermissionsError("Playlist has too many entries (%s > %s)" %
                                       (num_songs, permissions.max_playlist_length))

            # This is a little bit weird when it says (x + 0 > y), I might add the other check back in
            if permissions.max_songs and player.playlist.count_for_user(author) + num_songs > permissions.max_songs:
                raise PermissionsError("Playlist entries + your already queued songs exceed limit (%s + %s > %s)" %
                                       (num_songs, player.playlist.count_for_user(author), permissions.max_songs))

            if info['extractor'] == 'youtube:playlist':
                try:
                    return await self._cmd_ytplaylist(player, channel, author, permissions, song_url)
                except CommandError as e:
                    raise
                except Exception as e:
                    traceback.print_exc()
                    raise CommandError("Error queuing playlist:\n%s" % e)

            t0 = time.time()

            # My test was 1.2 seconds per song, but we maybe should fudge it a bit, unless we can
            # monitor it and edit the message with the estimated time, but that's some ADVANCED SHIT
            # I don't think we can hook into it anyways, so this will have to do.
            # It would probably be a thread to check a few playlists and get the speed from that
            # Different playlists might download at different speeds though
            wait_per_song = 1.2

            procmesg = await self.safe_send_message(channel,
                                                    'Gathering playlist information for {} songs{}'.format(
                                                        num_songs,
                                                        ', ETA: {} seconds'.format(self._fixg(
                                                            num_songs * wait_per_song)) if num_songs >= 10 else '.'))

            # We don't have a pretty way of doing this yet.  We need either a loop
            # that sends these every 10 seconds or a nice context manager.
            await self.send_typing(channel)

            # TODO: I can create an event emitter object instead, add event functions, and every play list might be asyncified
            #       Also have a "verify_entry" hook with the entry as an arg and returns the entry if its ok

            entry_list, position = await player.playlist.import_from(song_url, channel=channel, author=author)

            tnow = time.time()
            ttime = tnow - t0
            listlen = len(entry_list)
            drop_count = 0

            if permissions.max_song_length:
                for e in entry_list.copy():
                    if e.duration > permissions.max_song_length:
                        player.playlist.entries.remove(e)
                        entry_list.remove(e)
                        drop_count += 1
                        # Im pretty sure there's no situation where this would ever break
                        # Unless the first entry starts being played, which would make this a race condition
                if drop_count:
                    print("Dropped %s songs" % drop_count)

            print("Processed {} songs in {} seconds at {:.2f}s/song, {:+.2g}/song from expected ({}s)".format(
                listlen,
                self._fixg(ttime),
                ttime / listlen,
                ttime / listlen - wait_per_song,
                self._fixg(wait_per_song * num_songs))
            )

            await self.safe_delete_message(procmesg)

            if not listlen - drop_count:
                raise CommandError(
                    "No songs were added, all songs were over max duration (%ss)" % permissions.max_song_length)

            reply_text = "Enqueued **%s** songs to be played. Position in queue: %s"
            btext = str(listlen - drop_count)

        else:
            if permissions.max_song_length and info.get('duration', 0) > permissions.max_song_length:
                raise PermissionsError(
                    "Song duration exceeds limit (%s > %s)" % (info['duration'], permissions.max_song_length))

            entry, position = await player.playlist.add_entry(song_url, channel=channel, author=author)

            reply_text = "Enqueued **%s** to be played. Position in queue: %s"
            btext = entry.title

        if position == 1 and player.is_stopped:
            position = 'Up next!'
            reply_text %= (btext, position)

        else:
            try:
                time_until = await player.playlist.estimate_time_until(position, player)
                reply_text += ' - estimated time until playing: %s'
            except:
                traceback.print_exc()
                time_until = ''

            reply_text %= (btext, position, time_until)

        return Response(reply_text, delete_after=25)

    async def _cmd_ytplaylist(self, player, channel, author, permissions, playlist_url):
        """
        Secret handler to use the async wizardry to make playlist queuing non-"blocking"
        """

        await self.send_typing(channel)
        info = await extract_info(player.playlist.loop, playlist_url, download=False, process=False)

        if not info:
            raise CommandError("That playlist cannot be played.")

        num_songs = sum(1 for _ in info['entries'])
        t0 = time.time()

        busymsg = await self.safe_send_message(channel,
                                               "Processing %s songs..." % num_songs)  # TODO: From playlist_title
        await self.send_typing(channel)

        try:
            entries_added = await player.playlist.async_process_youtube_playlist(playlist_url, channel=channel,
                                                                                 author=author)
            # TODO: Add hook to be called after each song
            # TODO: Add permissions

        except Exception as e:
            traceback.print_exc()
            raise CommandError('Error handling playlist %s queuing.' % playlist_url)

        songs_processed = len(entries_added)
        drop_count = 0
        skipped = False

        if permissions.max_song_length:
            for e in entries_added.copy():
                if e.duration > permissions.max_song_length:
                    try:
                        player.playlist.entries.remove(e)
                        entries_added.remove(e)
                        drop_count += 1
                    except:
                        pass

            if drop_count:
                print("Dropped %s songs" % drop_count)

            if player.current_entry and player.current_entry.duration > permissions.max_song_length:
                await self.safe_delete_message(self.last_np_msg)
                self.last_np_msg = None
                skipped = True
                player.skip()
                entries_added.pop()

        await self.safe_delete_message(busymsg)

        songs_added = len(entries_added)
        tnow = time.time()
        ttime = tnow - t0
        wait_per_song = 1.2
        # TODO: actually calculate wait per song in the process function and return that too

        # This is technically inaccurate since bad songs are ignored but still take up time
        print("Processed {}/{} songs in {} seconds at {:.2f}s/song, {:+.2g}/song from expected ({}s)".format(
            songs_processed,
            num_songs,
            self._fixg(ttime),
            ttime / num_songs,
            ttime / num_songs - wait_per_song,
            self._fixg(wait_per_song * num_songs))
        )

        if not songs_added:
            basetext = "No songs were added, all songs were over max duration (%ss)" % permissions.max_song_length
            if skipped:
                basetext += "\nAdditionally, the current song was skipped for being too long."

            raise CommandError(basetext)

        return Response("Enqueued {} songs to be played in {} seconds".format(
            songs_added, self._fixg(ttime, 1)), delete_after=25)

    async def cmd_search(self, player, channel, author, permissions, leftover_args):
        """
        Usage:
            {command_prefix}search [service] [number] query

        Searches a service for a video and adds it to the queue.
        - service: any one of the following services:
            - youtube (yt) (default if unspecified)
            - soundcloud (sc)
            - yahoo (yh)
        - number: return a number of video results and waits for user to choose one
          - defaults to 1 if unspecified
          - note: If your search query starts with a number,
                  you must put your query in quotes
            - ex: {command_prefix}search 2 "I ran seagulls"
        """

        if permissions.max_songs and player.playlist.count_for_user(author) > permissions.max_songs:
            raise PermissionsError("You have reached your playlist item limit (%s)" % permissions.max_songs)

        def argch():
            if not leftover_args:
                raise CommandError("Please specify a search query.\n%s" % dedent(
                    self.cmd_search.__doc__.format(command_prefix=self.config.command_prefix)))

        argch()

        try:
            leftover_args = shlex.split(' '.join(leftover_args))
        except ValueError:
            raise CommandError("Please quote your search query properly.")

        service = 'youtube'
        items_requested = 1
        max_items = 10  # this can be whatever, but since ytdl uses about 1000, a small number might be better
        services = {
            'youtube': 'ytsearch',
            'soundcloud': 'scsearch',
            'yahoo': 'yvsearch',
            'yt': 'ytsearch',
            'sc': 'scsearch',
            'yh': 'yvsearch'
        }

        if leftover_args[0] in services:
            service = leftover_args.pop(0)
            argch()

        if leftover_args[0].isdigit():
            items_requested = int(leftover_args.pop(0))
            argch()

            if items_requested > max_items:
                raise CommandError("You cannot request more than %s videos" % max_items)

        # Look jake, if you see this and go "what the fuck are you doing"
        # and have a better idea on how to do this, i'd be delighted to know.
        # I don't want to just do ' '.join(leftover_args).strip("\"'")
        # Because that eats both quotes if they're there
        # where I only want to eat the outermost ones
        if leftover_args[0][0] in '\'"':
            lchar = leftover_args[0][0]
            leftover_args[0] = leftover_args[0].lstrip(lchar)
            leftover_args[-1] = leftover_args[-1].rstrip(lchar)

        search_query = '%s%s:%s' % (services[service], items_requested, ' '.join(leftover_args))

        m = await self.send_message(channel, "Searching for videos...")
        await self.send_typing(channel)

        info = await extract_info(player.playlist.loop, search_query, download=False, process=True)
        await self.safe_delete_message(m)

        if not info:
            return Response("No videos found")

        def check(m):
            return (
                m.content.lower()[0] in 'yn' or
                # hardcoded function name weeee
                m.content.lower().startswith('{}{}'.format(self.config.command_prefix, 'search')) or
                m.content.lower().startswith('exit'))

        for e in info['entries']:
            result_message = await self.safe_send_message(channel, "Result %s/%s: %s" % (
                info['entries'].index(e) + 1, len(info['entries']), e['webpage_url']))

            confirm_message = await self.safe_send_message(channel, "Is this ok? Type `y`, `n` or `exit`")
            response_message = await self.wait_for_message(30, author=author, channel=channel, check=check)

            if not response_message:
                await self.safe_delete_message(result_message)
                await self.safe_delete_message(confirm_message)
                return Response("Ok nevermind.", delete_after=30)

            # They started a new search query so lets clean up and bugger off
            elif response_message.content.startswith(self.config.command_prefix) or \
                    response_message.content.lower().startswith('exit'):

                await self.safe_delete_message(result_message)
                await self.safe_delete_message(confirm_message)
                return

            if response_message.content.lower().startswith('y'):
                await self.safe_delete_message(result_message)
                await self.safe_delete_message(confirm_message)
                await self.safe_delete_message(response_message)

                ok_message = await self.safe_send_message(channel, "Alright, coming up!")

                await self.cmd_play(player, channel, author, permissions, [], e['webpage_url'])
                await self.safe_delete_message(ok_message)

                return
            else:
                await self.safe_delete_message(result_message)
                await self.safe_delete_message(confirm_message)
                await self.safe_delete_message(response_message)

        return Response("Oh well :frowning:", delete_after=25)

    async def cmd_np(self, player, channel):
        """
        Usage:
            {command_prefix}np

        Displays the current song in chat.
        """

        if player.current_entry:
            if self.last_np_msg:
                await self.safe_delete_message(self.last_np_msg)
                self.last_np_msg = None

            song_progress = str(timedelta(seconds=player.progress)).lstrip('0').lstrip(':')
            song_total = str(timedelta(seconds=player.current_entry.duration)).lstrip('0').lstrip(':')
            prog_str = '`[%s/%s]`' % (song_progress, song_total)

            if player.current_entry.meta.get('channel', False) and player.current_entry.meta.get('author', False):
                np_text = "Now Playing: **%s** added by **%s** %s\n" % (
                    player.current_entry.title, player.current_entry.meta['author'].name, prog_str)
            else:
                np_text = "Now Playing: **%s** %s\n" % (player.current_entry.title, prog_str)

            self.last_np_msg = await self.safe_send_message(channel, np_text)
        else:
            return Response(
                'There are no songs queued! Queue something with {}play.'.format(self.config.command_prefix))

    async def cmd_summon(self, channel, author, voice_channel):
        """
        Usage:
            {command_prefix}summon

        Call the bot to the summoner's voice channel.
        """

        if not author.voice_channel:
            raise CommandError('You are not in a voice channel!')

        voice_client = self.voice_clients.get(channel.server.id, None)
        if voice_client:
            await self.move_voice_client(author.voice_channel)
            return

        chperms = author.voice_channel.permissions_for(author.voice_channel.server.me)

        if not chperms.connect:
            self.safe_print("Cannot join channel \"%s\", no permission." % author.voice_channel.name)
            return Response("```Cannot join channel \"%s\", no permission.```" % author.voice_channel.name,
                            delete_after=25)

        elif not chperms.speak:
            self.safe_print("Will not join channel \"%s\", no permission to speak." % author.voice_channel.name)
            return Response("```Will not join channel \"%s\", no permission to speak.```" % author.voice_channel.name,
                            delete_after=25)

        player = await self.get_player(author.voice_channel, create=True)

        if player.is_stopped:
            player.play()

        if self.config.auto_playlist:
            await self.on_finished_playing(player)

    async def cmd_pause(self, player):
        """
        Usage:
            {command_prefix}pause

        Pauses playback of the current song.
        """

        if player.is_playing:
            player.pause()

        else:
            raise CommandError('Player is not playing.')

    async def cmd_resume(self, player):
        """
        Usage:
            {command_prefix}resume

        Resumes playback of a paused song.
        """

        if player.is_paused:
            player.resume()

        else:
            raise CommandError('Player is not paused.')

    async def cmd_shuffle(self, player):
        """
        Usage:
            {command_prefix}shuffle

        Shuffles the playlist.
        """

        player.playlist.shuffle()
        return Response('*shuffleshuffleshuffle*', delete_after=10)

    async def cmd_clear(self, player, author):
        """
        Usage:
            {command_prefix}clear

        Clears the playlist.
        """

        player.playlist.clear()
        return Response(':put_litter_in_its_place:', delete_after=10)

    async def cmd_skip(self, player, channel, author, message, voice_channel):
        """
        Usage:
            {command_prefix}skip

        Skips the current song when enough votes are cast, or by the bot owner.
        """

        if player.is_stopped:
            raise CommandError("Can't skip! The player is not playing!")

        if not player.current_entry:  # Do more checks here to see
            print("Something strange is happening.  You might want to restart the bot if its not working.")

        if author.id == self.config.owner_id:
            player.skip() # check autopause stuff here
            return

        num_voice = sum(1 for m in voice_channel.voice_members if not (
            m.deaf or m.self_deaf or m.id in [self.config.owner_id, self.user.id]))

        num_skips = player.skip_state.add_skipper(author.id, message)

        skips_remaining = min(self.config.skips_required,
                              sane_round_int(num_voice * self.config.skip_ratio_required)) - num_skips

        if skips_remaining <= 0:
            player.skip() # check autopause stuff here
            return Response(
                'your skip for **{}** was acknowledged.'
                '\nThe vote to skip has been passed.{}'.format(
                    player.current_entry.title,
                    ' Next song coming up!' if player.playlist.peek() else ''
                ),
                reply=True,
                delete_after=10
            )

        else:
            # TODO: When a song gets skipped, delete the old x needed to skip messages
            return Response(
                'your skip for **{}** was acknowledged.'
                '\n**{}** more {} required to vote to skip this song.'.format(
                    player.current_entry.title,
                    skips_remaining,
                    'person is' if skips_remaining == 1 else 'people are'
                ),
                reply=True
            )

    async def cmd_volume(self, message, player, new_volume=None):
        """
        Usage:
            {command_prefix}volume (+/-)[volume]

        Sets the playback volume. Accepted values are from 1 to 100.
        Putting + or - before the volume will make the volume change relative to the current volume.
        """

        if not new_volume:
            return Response('Current volume: `%s%%`' % int(player.volume * 100), reply=True, delete_after=20)

        relative = False
        if new_volume[0] in '+-':
            relative = True

        try:
            new_volume = int(new_volume)

        except ValueError:
            raise CommandError('{} is not a valid number'.format(new_volume))

        if relative:
            vol_change = new_volume
            new_volume += (player.volume * 100)

        old_volume = int(player.volume * 100)

        if 0 < new_volume <= 100:
            player.volume = new_volume / 100.0

            return Response('updated volume from %d to %d' % (old_volume, new_volume), reply=True, delete_after=20)

        else:
            if relative:
                raise CommandError(
                    'Unreasonable volume change provided: {}{:+} -> {}%.  Provide a change between {} and {:+}.'.format(
                        old_volume, vol_change, old_volume + vol_change, 1 - old_volume, 100 - old_volume))
            else:
                raise CommandError(
                    'Unreasonable volume provided: {}%. Provide a value between 1 and 100.'.format(new_volume))

    async def cmd_queue(self, channel, player):
        """
        Usage:
            {command_prefix}queue

        Prints the current song queue.
        """

        lines = []
        unlisted = 0
        andmoretext = '* ... and %s more*' % ('x' * len(player.playlist.entries))

        if player.current_entry:
            song_progress = str(timedelta(seconds=player.progress)).lstrip('0').lstrip(':')
            song_total = str(timedelta(seconds=player.current_entry.duration)).lstrip('0').lstrip(':')
            prog_str = '`[%s/%s]`' % (song_progress, song_total)

            if player.current_entry.meta.get('channel', False) and player.current_entry.meta.get('author', False):
                lines.append("Now Playing: **%s** added by **%s** %s\n" % (
                    player.current_entry.title, player.current_entry.meta['author'].name, prog_str))
            else:
                lines.append("Now Playing: **%s** %s\n" % (player.current_entry.title, prog_str))

        for i, item in enumerate(player.playlist, 1):
            if item.meta.get('channel', False) and item.meta.get('author', False):
                nextline = '`{}.` **{}** added by **{}**'.format(i, item.title, item.meta['author'].name).strip()
            else:
                nextline = '`{}.` **{}**'.format(i, item.title).strip()

            currentlinesum = sum([len(x) + 1 for x in lines])  # +1 is for newline char

            if currentlinesum + len(nextline) + len(andmoretext) > DISCORD_MSG_CHAR_LIMIT:
                if currentlinesum + len(andmoretext):
                    unlisted += 1
                    continue

            lines.append(nextline)

        if unlisted:
            lines.append('\n*... and %s more*' % unlisted)

        if not lines:
            lines.append(
                'There are no songs queued! Queue something with {}play.'.format(self.config.command_prefix))

        message = '\n'.join(lines)
        return Response(message, delete_after=30)

    @owner_only  # TODO: improve this (users only clean up theirs, arg for all messages, etc, more control)
    async def cmd_clean(self, message, channel, author, amount):
        """
        Usage:
            {command_prefix}clean amount

        Removes amount messages the bot has posted in chat.
        """

        try:
            float(amount)  # lazy check
            amount = int(amount)
        except:
            return Response("enter a number.  NUMBER.  That means digits.  `5`.  Etc.", reply=True, delete_after=5)

        def is_possible_command_invoke(entry):
            valid_call = any(
                entry.content.startswith(prefix) for prefix in [self.config.command_prefix])  # can be expanded
            return valid_call and not entry.content[1:2].isspace()

        await self.safe_delete_message(message)

        msgs = 0
        delete_invokes = True
        async for entry in self.logs_from(channel, limit=int(amount)):
            if entry.author == self.user and entry != self.last_np_msg:
                await self.safe_delete_message(entry)
                msgs += 1

            if is_possible_command_invoke(entry) and delete_invokes:
                try:
                    await self.safe_delete_message(entry)
                except discord.Forbidden:
                    delete_invokes = False
                else:
                    msgs += 1

        # Becuase of how this works, you can do `clean 20` and <20 messages will get deleted

        return Response('Cleaned up {} message{}.'.format(msgs, '' if msgs == 1 else 's'), delete_after=10)

    async def cmd_listroles(self, server, author):
        """
        Usage:
            {command_prefix}listroles

        Lists the roles on the server for setting up permissions
        """

        lines = ['Role list for %s' % server.name, '```', '```']
        for role in server.roles:
            role.name = role.name.replace('@everyone', '@\u200Beveryone')  # ZWS for sneaky names
            nextline = role.id + " " + role.name

            if len('\n'.join(lines)) + len(nextline) < DISCORD_MSG_CHAR_LIMIT:
                lines.insert(len(lines) - 1, nextline)
            else:
                await self.send_message(author, '\n'.join(lines))
                lines = ['```', '```']

        await self.send_message(author, '\n'.join(lines))
        return Response(":mailbox_with_mail:", delete_after=20)

    async def cmd_perms(self, author, channel, server, permissions):
        '''
        Usage:
            {command_prefix}perms

        Sends the user a list of their permissions.
        '''

        lines = ['Command permissions in %s\n' % server.name, '```', '```']

        for perm in permissions.__dict__:
            if perm in ['user_list'] or permissions.__dict__[perm] == set():
                continue

            lines.insert(len(lines) - 1, "%s: %s" % (perm, permissions.__dict__[perm]))

        await self.send_message(author, '\n'.join(lines))
        return Response(":mailbox_with_mail:", delete_after=20)

    async def on_message(self, message):
        message_content = message.content.strip()
        if not message_content.startswith(self.config.command_prefix):
            return

        if message.author == self.user:
            self.safe_print("Ignoring command from myself (%s)" % message.content)
            return

        if self.config.bound_channels and message.channel.id not in self.config.bound_channels and not message.channel.is_private:
            return  # if I want to log this I just move it under the prefix check

        command, *args = message_content.split()  # Uh, doesn't this break prefixes with spaces in them (it doesn't, config parser already breaks them)
        command = command[len(self.config.command_prefix):].lower().strip()

        handler = getattr(self, 'cmd_%s' % command, None)
        if not handler:
            return

        if message.channel.is_private and command != 'joinserver' and message.author.id != self.config.owner_id:
            await self.send_message(message.channel, 'You cannot use this bot in private messages.')
            return

        if int(message.author.id) in self.blacklist and message.author.id != self.config.owner_id:
            self.safe_print("[User blacklisted] {0.id}/{0.name} ({1})".format(message.author, message_content))
            return

        elif self.config.white_list_check and int(
                message.author.id) not in self.whitelist and message.author.id != self.config.owner_id:
            self.safe_print("[User not whitelisted] {0.id}/{0.name} ({1})".format(message.author, message_content))
            return

        else:
            self.safe_print("[Command] {0.id}/{0.name} ({1})".format(message.author, message_content))

        user_permissions = self.permissions.for_user(message.author)

        argspec = inspect.signature(handler)
        params = argspec.parameters.copy()

        # noinspection PyBroadException
        try:
            if user_permissions.ignore_non_voice and command in user_permissions.ignore_non_voice:
                await self._check_ignore_non_voice(message)

            handler_kwargs = {}
            if params.pop('message', None):
                handler_kwargs['message'] = message

            if params.pop('channel', None):
                handler_kwargs['channel'] = message.channel

            if params.pop('author', None):
                handler_kwargs['author'] = message.author

            if params.pop('server', None):
                handler_kwargs['server'] = message.server

            if params.pop('player', None):
                handler_kwargs['player'] = await self.get_player(message.channel)

            if params.pop('permissions', None):
                handler_kwargs['permissions'] = user_permissions

            if params.pop('user_mentions', None):
                handler_kwargs['user_mentions'] = list(map(message.server.get_member, message.raw_mentions))

            if params.pop('channel_mentions', None):
                handler_kwargs['channel_mentions'] = list(map(message.server.get_channel, message.raw_channel_mentions))

            if params.pop('voice_channel', None):
                handler_kwargs['voice_channel'] = message.server.me.voice_channel

            if params.pop('leftover_args', None):
                handler_kwargs['leftover_args'] = args

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

            if message.author.id != self.config.owner_id:
                if user_permissions.command_whitelist and command not in user_permissions.command_whitelist:
                    raise PermissionsError(
                        "This command is not whitelisted for your group (%s)." % user_permissions.name,
                        expire_in=20)

                elif user_permissions.command_blacklist and command in user_permissions.command_blacklist:
                    raise PermissionsError(
                        "This command is blacklisted for your group (%s)." % user_permissions.name,
                        expire_in=20)

            if params:
                docs = getattr(handler, '__doc__', None)
                if not docs:
                    docs = 'Usage: {}{} {}'.format(
                        self.config.command_prefix,
                        command,
                        ' '.join(args_expected)
                    )

                docs = '\n'.join(l.strip() for l in docs.split('\n'))
                await self.safe_send_message(
                    message.channel,
                    '```\n%s\n```' % docs.format(command_prefix=self.config.command_prefix),
                    expire_in=60
                )
                return

            response = await handler(**handler_kwargs)
            if response and isinstance(response, Response):
                content = response.content
                if response.reply:
                    content = '%s, %s' % (message.author.mention, content)

                sentmsg = await self.safe_send_message(message.channel, content,
                                                       expire_in=response.delete_after)  # also_delete=message
                # TODO: Add options for deletion toggling

        except CommandError as e:
            await self.safe_send_message(message.channel, '```\n%s\n```' % e.message, expire_in=e.expire_in)

        except Exception as e:
            if self.config.debug_mode:
                await self.safe_send_message(message.channel, '```\n%s\n```' % traceback.format_exc())
            traceback.print_exc()

    async def on_voice_state_update(self, before, after):
        if before.voice_channel == after.voice_channel:
            return  # they didn't move channels

        my_voice_channel = after.server.me.voice_channel  # This should always work, right?

        if not my_voice_channel:
            return

        if before.voice_channel == my_voice_channel:
            joining = False
        elif after.voice_channel == my_voice_channel:
            joining = True
        else:
            return  # Not my channel

        if self.auto_paused is None:
            self.auto_paused = False
            return

        moving = before == before.server.me
        player = await self.get_player(my_voice_channel)

        if sum(1 for m in my_voice_channel.voice_members if m != after.server.me):
            if self.auto_paused and player.is_paused:
                print("[config:autopause] Unpausing")
                self.auto_paused = False
                player.resume()
        else:
            if not self.auto_paused and player.is_playing:
                print("[config:autopause] Pausing")
                self.auto_paused = True
                player.pause()


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
