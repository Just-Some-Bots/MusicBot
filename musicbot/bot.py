import time
import inspect
import traceback
import asyncio
import discord

from discord import utils
from discord.enums import ChannelType
from discord.object import Object
from discord.voice_client import VoiceClient

from random import choice
from functools import wraps
from datetime import timedelta

from musicbot.config import Config, ConfigDefaults
from musicbot.player import MusicPlayer
from musicbot.playlist import Playlist
from musicbot.utils import load_file, extract_user_id, write_file

from .downloader import extract_info
from .exceptions import CommandError, HelpfulError
from .constants import DISCORD_MSG_CHAR_LIMIT
from .opus_loader import load_opus_lib


VERSION = '1.9.5'

load_opus_lib()


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
    def __init__(self, config_file=ConfigDefaults.options_file):
        super().__init__()

        self.players = {}
        self.voice_clients = {}
        self.voice_client_connect_lock = asyncio.Lock()
        self.config = Config(config_file)

        self.blacklist = set(load_file(self.config.blacklist_file))
        self.whitelist = set(load_file(self.config.whitelist_file))
        self.autoplaylist = load_file(self.config.auto_playlist_file)

        if not self.autoplaylist:
            print("Warning: Autoplaylist is empty, disabling.")
            self.config.auto_playlist = False

        self.last_np_msg = None


    def ignore_non_voice(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            # if bot is in a voice channel, user is in the same voice channel, OK
            # else, return Response saying "ignoring"

            # Ye olde hack to dig up the origional message argument
            orig_msg = self._get_variable('message')

            # There is no "message" var, lets get outta here
            if not orig_msg:
                return await func(self, *args, **kwargs)

            vc = self.voice_clients.get(orig_msg.server.id, None)

            # If we've connected to a voice chat and we're in the same voice channel
            if not vc or (vc and vc.channel == orig_msg.author.voice_channel):
                return await func(self, *args, **kwargs)
            else:
                return Response("you cannot use this command when not in the voice channel", reply=True, delete_after=20)

        return wrapper

    # TODO: Add some sort of `denied` argument for a message to send when someone else tries to use it
    def owner_only(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            # Only allow the owner to use these commands
            orig_msg = self._get_variable('message')

            if not orig_msg or orig_msg.author.id == self.config.owner_id:
                return await func(self, *args, **kwargs)
            else:
                return Response("only the owner can use this command", reply=True, delete_after=20)

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

    # TODO: autosummon option to a specific channel
    async def _auto_summon(self, channel=None):
        owner = discord.utils.find(lambda m: m.id == self.config.owner_id and m.voice_channel, self.get_all_members())

        if owner:
            await self.handle_summon(owner.voice_channel, owner)
            return True
        else:
            print("Owner not found in a voice channel, could not autosummon.")
            return False

    def _fixg(self, x, dp=2):
        return ('{:.%sf}' % dp).format(x).rstrip('0').rstrip('.')


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

            await voice_client.connect()
            return voice_client

    async def get_player(self, channel, create=False):
        server = channel.server

        if server.id not in self.players:
            if not create:
                raise CommandError(
                    'Player does not exist. It has not been summoned yet into a voice channel.  '
                    'Use %ssummon to summon it to your voice channel.' % self.config.command_prefix)

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

    async def on_play(self, player, entry):
        await self.update_now_playing(entry)
        player.skip_state.reset()

        channel = entry.meta.get('channel', None)
        author = entry.meta.get('author', None)

        if channel and author:
            if self.last_np_msg and self.last_np_msg.channel == channel:

                async for lmsg in self.logs_from(channel, limit=1):
                    if lmsg.author != self.user:
                        await self.safe_delete_message(self.last_np_msg)
                        self.last_np_msg = None
                    break # This is probably redundant

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
        if not (player.playlist.entries and player.current_entry) and self.config.auto_playlist:
            while self.autoplaylist:
                song_url = choice(self.autoplaylist)
                info = await extract_info(player.playlist.loop, song_url, download=False, process=False)

                if not info:
                    self.autoplaylist.remove(song_url)
                    print("[Info] Removing unplayable song from autoplaylist: %s" % song_url)
                    write_file(self.config.auto_playlist_file, self.autoplaylist)
                    continue

                await player.playlist.add_entry(song_url, channel=None, author=None)

            if not self.auto_playlist:
                print("[Warning] No playable songs in the autoplaylist, disabling.")
                self.config.auto_playlist = False


    async def update_now_playing(self, entry=None, is_paused=False):
        game = None
        if entry:
            prefix = u'\u275A\u275A ' if is_paused else ''

            name = u'{}{}'.format(prefix, entry.title)[:128]
            game = discord.Game(name=name)

        await self.change_status(game)

    # TODO: Change these to check then send
    async def safe_send_message(self, dest, content, *, tts=False):
        try:
            return await self.send_message(dest, content, tts=tts)
        except discord.Forbidden:
            print("Error: Cannot send message to %s, no permission" % dest.name)
        except discord.NotFound:
            print("Warning: Cannot send message to %s, invalid channel?" % dest.name)

    async def safe_delete_message(self, message):
        try:
            return await self.delete_message(message)
        except discord.Forbidden:
            print("Error: Cannot delete message \"%s\", no permission" % message.clean_content)
        except discord.NotFound:
            print("Warning: Cannot delete message \"%s\", message not found" % message.clean_content)

    async def safe_edit_message(self, message, new, *, send_if_fail=False):
        try:
            return await self.edit_message(message, new)
        except discord.NotFound:
            print("Warning: Cannot edit message \"%s\", message not found" % message.clean_content)
            if send_if_fail:
                print("Sending instead")
                return await self.safe_send_message(message.channel, new)


    # noinspection PyMethodOverriding
    def run(self):
        return super().run(self.config.username, self.config.password)

    async def on_ready(self):
        print('Connected!\n')
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
        print("Whitelist check is %s" % ['disabled', 'enabled'][self.config.white_list_check])
        print("Skip threshold at %s votes or %s%%" % (self.config.skips_required, self._fixg(self.config.skip_ratio_required*100)))
        print("Now Playing message @mentions are %s" % ['disabled', 'enabled'][self.config.now_playing_mentions])
        print("Autosummon is %s" % ['disabled', 'enabled'][self.config.auto_summon])
        print("Auto-playlist is %s" % ['disabled', 'enabled'][self.config.auto_playlist])
        print("Downloaded songs will be %s after playback" % ['deleted', 'saved'][self.config.save_videos])
        print()

        if self.servers:
            print('--Server List--')
            [print(s) for s in self.servers]
        else:
            print("No servers have been joined yet.")

        print()

        # maybe option to leave the ownerid blank and generate a random command for the owner to use
        # wait_for_message is pretty neato

        if self.config.auto_summon:
            as_ok = await self._auto_summon()

            if self.config.auto_playlist and as_ok:
                # TODO: Clean this up
                owner = discord.utils.find(lambda m: m.id == self.config.owner_id and m.voice_channel, self.get_all_members())
                await self.on_finished_playing(await self.get_player(owner.voice_channel))


    async def handle_help(self):
        """
        Usage: {command_prefix}help
        Prints a help message
        """

        helpmsg = "**Commands**\n```"
        commands = []

        # TODO: Get this to format nicely
        for att in dir(self):
            if att.startswith('handle_') and att != 'handle_help':
                command_name = att.replace('handle_', '').lower()
                commands.append("{}{}".format(self.config.command_prefix, command_name))

        helpmsg += ", ".join(commands)
        helpmsg += "```"
        helpmsg += "https://github.com/SexualRhinoceros/MusicBot/wiki/Commands-list"

        return Response(helpmsg, reply=True, delete_after=60)

    @owner_only
    async def handle_whitelist(self, message, option, username):
        """
        Usage: {command_prefix}whitelist [ + | - | add | remove ] @UserName
        Adds or removes the user to the whitelist. When the whitelist is enabled,
        whitelisted users are permitted to use bot commands.
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

    @owner_only
    async def handle_blacklist(self, message, option, username):
        """
        Usage: {command_prefix}blacklist [ + | - | add | remove ] @UserName
        Adds or removes the user to the blacklist. Blacklisted users are forbidden from
        using bot commands. Blacklisting a user also removes them from the whitelist.
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
                return Response('user has been added to the blacklist and removed from the whitelist', reply=True, delete_after=10)

            else:
                return Response('user has been added to the blacklist', reply=True, delete_after=10)

        else:
            if user_id not in self.blacklist:
                return Response('user is not in the blacklist', reply=True, delete_after=10)

            else:
                self.blacklist.remove(user_id)
                write_file(self.config.blacklist_file, self.blacklist)

                return Response('user has been removed from the blacklist', reply=True, delete_after=10)

    async def handle_id(self, author):
        """
        Usage: {command_prefix}id
        Tells the user their id.
        """

        return Response('your id is `%s`' % author.id, reply=True)

    @owner_only
    async def handle_joinserver(self, message, server_link):
        """
        Usage {command_prefix}joinserver [Server Link]
        Asks the bot to join a server. [todo: add info about if it breaks or whatever]
        """

        try:
            await self.accept_invite(server_link)

        except:
            raise CommandError('Invalid URL provided:\n{}\n'.format(server_link))

    @ignore_non_voice
    async def handle_play(self, player, channel, author, song_url):
        """
        Usage {command_prefix}play [song link]
        Adds the song to the playlist.
        """

        try:
            await self.send_typing(channel)

            info = await extract_info(player.playlist.loop, song_url, download=False, process=False)

            if not info:
                raise CommandError("That video cannot be played.")

            is_playlist = 'entries' in info

            if is_playlist and info['extractor'] == 'youtube:playlist':
                return await self._handle_ytplaylist(player, channel, author, song_url)

            if is_playlist:
                t0 = time.time()

                # My test was 1.2 seconds per song, but we maybe should fudge it a bit, unless we can
                # monitor it and edit the message with the estimated time, but that's some ADVANCED SHIT
                # I don't think we can hook into it anyways, so this will have to do.
                # It would probably be a thread to check a few playlists and get the speed from that
                # Different playlists might download at different speeds though
                wait_per_song = 1.2

                num_songs = sum(1 for _ in info['entries'])

                procmesg = await self.safe_send_message(channel,
                    'Gathering playlist information for {} songs{}'.format(
                        num_songs,
                        ', ETA: {} seconds'.format(self._fixg(num_songs*wait_per_song)) if num_songs >= 10 else '.'))

                # We don't have a pretty way of doing this yet.  We need either a loop
                # that sends these every 10 seconds or a nice context manager.
                await self.send_typing(channel)

                entry_list, position = await player.playlist.import_from(song_url, channel=channel, author=author)
                entry = entry_list[0]

                tnow = time.time()
                ttime = tnow - t0
                listlen = len(entry_list)

                print("Processed {} songs in {} seconds at {:.2f}s/song, {:+.2g}/song from expected ({}s)".format(
                    listlen,
                    self._fixg(ttime),
                    ttime/listlen,
                    ttime/listlen - wait_per_song,
                    self._fixg(wait_per_song*num_songs))
                )

                await self.delete_message(procmesg)

                reply_text = "Enqueued **%s** songs to be played. Position in queue: %s"
                btext = listlen

            else:
                entry, position = await player.playlist.add_entry(song_url, channel=channel, author=author)

                reply_text = "Enqueued **%s** to be played. Position in queue: %s"
                btext = entry.title

            if position == 1 and player.is_stopped:
                position = 'Up next!'
                reply_text %= (btext, position)

            else:
                time_until = await player.playlist.estimate_time_until(position, player)

                reply_text += ' - estimated time until playing: %s'
                reply_text %= (btext, position, time_until)

            return Response(reply_text, delete_after=25)

        except Exception as e:
            traceback.print_exc()
            raise CommandError('Unable to queue up song at %s to be played.' % song_url)

    async def _handle_ytplaylist(self, player, channel, author, playlist_url):
        """
        I hope this shit works
        """

        await self.send_typing(channel)
        info = await extract_info(player.playlist.loop, playlist_url, download=False, process=False)

        if not info:
            raise CommandError("That playlist cannot be played.")

        num_songs = sum(1 for _ in info['entries'])
        t0 = time.time()

        busymsg = await self.safe_send_message(channel, "Processing %s songs..." % num_songs)
        await self.send_typing(channel)

        try:
            songs_added = await player.playlist.async_process_youtube_playlist(playlist_url, channel=channel, author=author)
            # TODO: Add hook to be called after each song

        except Exception as e:
            traceback.print_exc()
            raise CommandError('Error handling playlist %s queuing.' % playlist_url)

        await self.safe_delete_message(busymsg)

        tnow = time.time()
        ttime = tnow - t0
        wait_per_song = 1.2
        # TODO: actually calculate wait per song in the process function and return that too

        # This is technically inaccurate since bad songs are ignored but still take up time
        print("Processed {}/{} songs in {} seconds at {:.2f}s/song, {:+.2g}/song from expected ({}s)".format(
            songs_added,
            num_songs,
            self._fixg(ttime),
            ttime/num_songs,
            ttime/num_songs - wait_per_song,
            self._fixg(wait_per_song*num_songs))
        )

        return Response("Enqueued {} songs to be played in {} seconds".format(
            songs_added, self._fixg(ttime, 1)), delete_after=25)


    @ignore_non_voice
    async def handle_summon(self, channel, author):
        """
        Usage {command_prefix}summon
        This command is for summoning the bot into your voice channel [but it should do it automatically the first time]
        """

        if self.voice_clients:
            raise CommandError("Multiple servers not supported at this time.")

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
            raise CommandError('You are not in a voice channel!')

        chperms = channel.permissions_for(channel.server.me)

        if not chperms.connect:
            print("Cannot join channel \"%s\", no permission." % channel.name)
            return Response("```Cannot join channel \"%s\", no permission.```" % channel.name, delete_after=15)

        elif not chperms.speak:
            print("Will not join channel \"%s\", no permission to speak." % channel.name)
            return Response("```Will not join channel \"%s\", no permission to speak.```" % channel.name, delete_after=15)

        # if moving:
        #     await self.move_member(channel.server.me, channel)
        #     return Response('ok?')

        player = await self.get_player(channel, create=True)

        if player.is_stopped:
            player.play()

        if self.config.auto_playlist:
            # TODO: Clean this up
            await self.on_finished_playing(await self.get_player(author.voice_channel))

    @ignore_non_voice
    async def handle_pause(self, player):
        """
        Usage {command_prefix}pause
        Pauses playback of the current song. [todo: should make sure it works fine when used inbetween songs]
        """

        if player.is_playing:
            player.pause()

        else:
            raise CommandError('Player is not playing.')

    @ignore_non_voice
    async def handle_resume(self, player):
        """
        Usage {command_prefix}resume
        Resumes playback of a paused song.
        """

        if player.is_paused:
            player.resume()

        else:
            raise CommandError('Player is not paused.')

    @ignore_non_voice
    async def handle_shuffle(self, player):
        """
        Usage {command_prefix}shuffle
        Shuffles the playlist.
        """

        player.playlist.shuffle()
        return Response('*shuffleshuffleshuffle*', delete_after=10)

    @owner_only
    async def handle_clear(self, player, author):
        """
        Usage {command_prefix}clear
        Clears the playlist.
        """

        player.playlist.clear()

    @ignore_non_voice
    async def handle_skip(self, player, channel, author):
        """
        Usage {command_prefix}skip
        Skips the current song when enough votes are cast, or by the bot owner.
        """

        if player.is_stopped or player.is_paused: # TODO: pausing and skipping a song breaks /something/, i'm not sure what
            raise CommandError("Can't skip! The player is not playing!")

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

    @ignore_non_voice
    async def handle_volume(self, message, new_volume=None):
        """
        Usage {command_prefix}volume (+/-)[volume]
        Sets the playback volume. Accepted values are from 1 to 100.
        Putting + or - before the volume will make the volume change relative to the current volume.
        """

        player = await self.get_player(message.channel)

        if not new_volume:
            return Response('Current volume: `%s%%`' % int(player.volume * 100), reply=True, delete_after=10)

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

            return Response('updated volume from %d to %d' % (old_volume, new_volume), reply=True, delete_after=10)

        else:
            if relative:
                raise CommandError(
                    'Unreasonable volume change provided: {}{:+} -> {}%.  Provide a change between {} and {:+}.'.format(
                        old_volume, vol_change, old_volume + vol_change, 1 - old_volume, 100 - old_volume))
            else:
                raise CommandError(
                    'Unreasonable volume provided: {}%. Provide a value between 1 and 100.'.format(new_volume))

    async def handle_queue(self, channel):
        """
        Usage {command_prefix}queue
        Prints the current song queue.
        """

        player = await self.get_player(channel)

        lines = []
        unlisted = 0
        andmoretext = '* ... and %s more*' % ('x'*len(player.playlist.entries))

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

            currentlinesum = sum([len(x)+1 for x in lines]) # +1 is for newline char

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

    @owner_only
    async def handle_clean(self, channel, author, amount=100):
        """
        Usage {command_prefix}clean [amount=100]
        Removes [amount] messages the bot has posted in chat.
        """

        try:
            float(amount) # lazy check
            amount = int(amount)
        except:
            return Response("that's not real number", reply=True, delete_after=15)

        def is_possible_command_invoke(entry):
            valid_call = any(entry.content.startswith(prefix) for prefix in [self.config.command_prefix]) # can be expanded
            return valid_call and not entry.content[1:2].isspace()

        msgs = 0
        delete_invokes = True
        async for entry in self.logs_from(channel, limit=int(amount)):
            if entry.author == self.user and entry != self.last_np_msg:
                await self.safe_delete_message(entry)
                msgs += 1

            if is_possible_command_invoke(entry) and delete_invokes:
                try:
                    await self.delete_message(entry)
                except discord.Forbidden:
                    delete_invokes = False
                else:
                    msgs += 1

        return Response('Cleaned up {} message{}.'.format(msgs, '' if msgs == 1 else 's'), delete_after=20)


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

            if params.pop('server', None):
                handler_kwargs['server'] = message.server

            if params.pop('player', None):
                handler_kwargs['player'] = await self.get_player(message.channel)

            if params.pop('user_mentions', None):
                handler_kwargs['user_mentions'] = list(map(message.server.get_member, message.raw_mentions))

            if params.pop('channel_mentions', None):
                handler_kwargs['channel_mentions'] = list(map(message.server.get_channel, message.raw_channel_mentions))

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
                await self.safe_send_message(
                    message.channel,
                    '```\n%s\n```' % docs.format(command_prefix=self.config.command_prefix)
                )
                return

            response = await handler(**handler_kwargs)
            if response and isinstance(response, Response):
                content = response.content
                if response.reply:
                    content = '%s, %s' % (message.author.mention, content)

                sentmsg = await self.safe_send_message(message.channel, content)

                # TODO: Add options for deletion toggling
                if sentmsg and response.delete_after > 0:
                    try:
                        await asyncio.sleep(response.delete_after)
                        await self.delete_message(sentmsg)
                    except discord.NotFound:
                        print("[Warning] Message slated for deletion has already been deleted")
                    except discord.Forbidden:
                        pass

        except CommandError as e:
            await self.safe_send_message(message.channel, '```\n%s\n```' % e.message)

        except Exception as e:
            if self.config.debug_mode:
                await self.safe_send_message(message.channel, '```\n%s\n```' % traceback.format_exc())
            traceback.print_exc()




    # async def on_voice_state_update(self, before, after):
    #     print("Voice status update for", after)
    #     print(before.voice_channel, '->', after.voice_channel)


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
