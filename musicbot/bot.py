import asyncio
import discord
import traceback
import inspect
import time

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
from .constants import DISCORD_MSG_CHAR_LIMIT
from .opus_loader import load_opus_lib

VERSION = '2.0'

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
    def __init__(self, content, reply=False, delete_incoming=False):
        self.content = content
        self.reply = reply
        self.delete_incoming = delete_incoming


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
                raise CommandError('Player does not exist. It has not been summoned yet into a voice channel.')

            voice_client = await self.get_voice_client(channel)

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

        if self.config.now_playing_mentions:
            self.loop.create_task(self.send_message(entry.meta['channel'], '%s - your song **%s** is now playing in %s!' % (
                entry.meta['author'].mention, entry.title, player.voice_client.channel.name
            )))
        else:
            self.loop.create_task(self.send_message(entry.meta['channel'], 'Now playing in %s: **%s**' % (
                player.voice_client.channel.name, entry.title
            )))
        #
        # Uh, that print in the channel the song was added from, doesn't it?  I guess just not saying anything is fine?

    def on_resume(self, entry, **_):
        self.update_now_playing(entry)

    def on_pause(self, entry, **_):
        self.update_now_playing(entry, True)

    def on_stop(self, **_):
        self.update_now_playing()

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
        print('Connected!\n')
        print('Username: ' + self.user.name)
        print('ID: ' + self.user.id)
        print('--Server List--')
        for server in self.servers:
            print(server.name) # If the server has ~FUN~ characters in its name, windows breaks because codecs
        print()

    async def handle_whitelist(self, message, username):
        """
        Usage: {command_prefix}whitelist @UserName
        Adds the user to the whitelist, permitting them to add songs.
        """
        user_id = extract_user_id(username)
        if not user_id:
            raise CommandError('Invalid user specified')

        self.whitelist.add(str(user_id))
        write_file('whitelist.txt', self.whitelist)
        # TODO: Respond with "user has been added to the list?"

    async def handle_blacklist(self, message, username):
        """
        Usage: {command_prefix}blacklist @UserName
        Adds the user to the blacklist, forbidding them from using bot commands.
        """
        user_id = extract_user_id(username)
        if not user_id:
            raise CommandError('Invalid user specified')

        self.blacklist.add(str(user_id))
        write_file('blacklist.txt', self.blacklist)
        # TODO: Respond with "user has been added to the list?"

    async def handle_id(self, author):
        """
        Usage: {command_prefix}id
        Tells the user their id.
        """
        return Response('Your id is `%s`' % author.id, reply=True)

    async def handle_joinserver(self, message, server_link):
        """
        Usage {command_prefix}joinserver [Server Link]
        Asks the bot to join a server. [todo: add info about if it breaks or whatever]
        """
        try:
            await self.accept_invite(server_link)

        except:
            raise CommandError('Invalid URL provided:\n{}\n'.format(server_link))

    async def handle_play(self, player, channel, author, song_url):
        """
        Usage {command_prefix}play [song link]
        Adds the song to the playlist.
        """

        try:
            await self.send_typing(channel)

            reply_text = "Enqueued **%s** to be played. Position in queue: %s"

            if 'playlist?list' in song_url:
                print('Playlist song url:', song_url)

                t0 = time.time()

                # My test was 1.2 seconds per song, but we maybe should fudge it a bit, unless we can
                # monitor it and edit the message with the estimated time, but that's some ADVANCED SHIT
                # I don't think we can hook into it anyways, so this will have to do.
                wait_per_song = 1.2

                info = await extract_info(player.playlist.loop, song_url, download=False, process=False)
                num_songs = sum(1 for _ in info['entries'])

                # This message can be deleted after playlist processing is done.
                await self.send_message(channel,
                    'Gathering playlist information for {} songs{}'.format(
                        num_songs,
                        ', ETA: {:g} seconds'.format(num_songs*wait_per_song) if num_songs >= 10 else '.'))

                # We don't have a pretty way of doing this yet.  We need either a loop
                # that sends these every 10 seconds or a nice context manager.
                await self.send_typing(channel)

                entry_list, position = await player.playlist.import_from(song_url, channel=channel, author=author)
                entry = entry_list[0]

                tnow = time.time()
                ttime = tnow - t0

                print("Processed {} songs in {:.2g} seconds at {:.2f}s/song, {:+.2g}/song from expected".format(
                    len(entry_list), ttime, ttime/len(entry_list), ttime/len(entry_list) - wait_per_song))

            else:
                entry, position = await player.playlist.add_entry(song_url, channel=channel, author=author)

            # Still need to subtract the played duration of the current song from this
            time_until = await player.playlist.estimate_time_until(position)

            if position == 1 and player.is_stopped:
                position = 'Up next!'
                reply_text = reply_text % (entry.title, position)
            else:
                reply_text += ' - estimated time until playing: %s'
                reply_text = reply_text % (entry.title, position, time_until)
                # TODO: Subtract time the current song has been playing for\

            return Response(reply_text, reply=True)

        except Exception as e:
            traceback.print_exc()
            raise CommandError('Unable to queue up song at %s to be played.' % song_url)

    async def handle_summon(self, channel, author):
        """
        Usage {command_prefix}summon
        This command is for summoning the bot into your voice channel [but it should do it automatically the first time]
        """
        if self.voice_clients:
            raise CommandError("Multiple servers not supported at this time.")

        server = channel.server

        channel = None
        for channel in server.channels:
            if discord.utils.get(channel.voice_members, id=author.id):
                break

        if not channel:
            raise CommandError('You are not in a voice channel!')

        player = await self.get_player(channel, create=True)

        if player.is_stopped:
            player.play()

    async def handle_pause(self, player):
        """
        Usage {command_prefix}pause
        Pauses playback of the current song. [todo: should make sure it works fine when used inbetween songs]
        """

        if player.is_playing:
            player.pause()

        else:
            raise CommandError('Player is not playing.')

    async def handle_resume(self, player):
        """
        Usage {command_prefix}resume
        Resumes playback of a paused song.
        """
        if player.is_paused:
            player.resume()

        else:
            raise CommandError('Player is not paused.')

    async def handle_shuffle(self, player):
        """
        Usage {command_prefix}shuffle
        Shuffles the playlist.
        """
        player.playlist.shuffle()

    async def handle_skip(self, player, channel, author):
        """
        Usage {command_prefix}skip
        Skips the current song when enough votes are cast, or by the bot owner.
        """

        if player.is_stopped: # TODO: or player.is_paused?
            raise CommandError("Can't skip! The player is not playing!")

        if author.id == self.config.owner_id:
            player.skip()
            return

        voice_channel = player.voice_client.channel

        num_voice = sum(1 for m in voice_channel.voice_members if not (m.deaf or m.self_deaf))
        num_skips = player.skip_state.add_skipper(author.id)

        skips_remaining = min(self.config.skips_required, int(num_voice * self.config.skip_ratio_required)) - num_skips

        # TODO: Should we discount the ownerid since they don't really count towards the skip count?

        if skips_remaining <= 0:
            player.skip()
            return Response(
                'your skip for **{}** was acknowledged.'
                '\nThe vote to skip has been passed.{}'.format(
                    player.current_entry.title,
                    ' Next song coming up!' if player.playlist.peek() else ''
                ),
                reply=True
            )

        else:
            return Response(
                'your skip for **{}** was acknowledged.'
                '\n**{}** more {} required to vote to skip this song.'.format(
                    player.current_entry.title,
                    skips_remaining,
                    'person is' if skips_remaining == 1 else 'people are'
                ),
                reply=True
            )

    async def handle_volume(self, message, new_volume=None):
        """
        Usage {command_prefix}volume (+/-)[volume]
        Sets the playback volume. Accepted values are from 1 to 100.
        Putting + or - before the volume will make the volume change relative to the current volume.
        """

        player = await self.get_player(message.channel)

        if not new_volume:
            return Response('Current volume: `%s%%`' % int(player.volume * 100), reply=True)

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

            return Response('updated volume from %d to %d' % (old_volume, new_volume), reply=True)

        else:
            if relative:
                raise CommandError(
                    'Unreasonable volume change provided: {}{:+} -> {}%.  Provide a change between {} and {:+}.'.format(
                        old_volume, vol_change, old_volume + vol_change, 1 - old_volume, 100 - old_volume))
            else:
                raise CommandError(
                    'Unreasonable volume provided: {}%. Provide a value between 1 and 100.'.format(new_volume))

    async def handle_queue(self, channel):
        player = await self.get_player(channel)

        lines = []
        unlisted = 0

        for i, item in enumerate(player.playlist, 1):
            nextline = '{}) **{}** added by **{}**'.format(i, item.title, item.meta['author'].name).strip()
            currentlinesum = sum([len(x)+1 for x in lines]) # +1 is for newline char

            # This is fine I guess, don't need to worry too much about trying to squeeze as much in as possible
            if currentlinesum + len(nextline) + len('* ... and xxx more*') > DISCORD_MSG_CHAR_LIMIT:
                if currentlinesum + len('* ... and xxx more*'):
                    unlisted += 1
                    continue

            lines.append(nextline)

        if unlisted:
            lines.append('\n*... and %s more*' % unlisted)

        if not lines:
            lines.append(
                'There are no songs queued! Queue something with {}play.'.format(self.config.command_prefix))

        message = '\n'.join(lines)
        return Response(message)

    async def on_message(self, message):
        if message.author == self.user:
            return

        if message.channel.is_private:
            await self.send_message(message.channel, 'You cannot use this bot in private messages.')

        message_content = message.content.strip()
        if not message_content.startswith(self.config.command_prefix):
            return

        command, *args = message_content.split()

        command = command[len(self.config.command_prefix):].lower().strip()

        handler = getattr(self, 'handle_%s' % command, None)
        if not handler:
            return

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
                handler_kwargs['player'] = await self.get_player(message.channel)

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

                await self.send_message(message.channel, content)

                if response.delete_incoming:
                    self.delete_message(message)

        except CommandError as e:
            await self.send_message(message.channel, '```\n%s\n```' % e.message)

        except:
            await self.send_message(message.channel, '```\n%s\n```' % traceback.format_exc())
            traceback.print_exc()


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

  AUTO SUMMON OPTION
'''
