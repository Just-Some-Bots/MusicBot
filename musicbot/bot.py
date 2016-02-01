import time
import inspect
import traceback
import asyncio
import discord

from discord import utils
from discord.enums import ChannelType
from discord.object import Object
from discord.voice_client import VoiceClient

from musicbot.config import Config
from musicbot.player import MusicPlayer
from musicbot.playlist import Playlist
from musicbot.utils import load_file, load_json, write_json

from .downloader import extract_info
from .exceptions import CommandError
from .constants import DISCORD_MSG_CHAR_LIMIT
from .opus_loader import load_opus_lib

from random import choice
from datetime import timedelta

# if sys.platform.startswith('win'):
#     import win_unicode_console
#     win_unicode_console.enable()

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

        self.bot_config = load_json(self.config.config_file)
        self.backuplist = load_file(self.config.backup_playlist_file)

        self.last_np_msg = None

    def can_use(self, channel, user, command=None, ownerOnlyFlag=False):
        perms = user.permissions_in(channel)
        if user.id == self.config.owner_id:
            return True
        if not self.config.white_list_check and ownerOnlyFlag == False:
            return True
        try:
            for role in user.roles:
                try:
                    if command:
                        try:
                            if role.id in self.bot_config[0][command][1] or user.id in self.bot_config[0][command][0]:
                                return True
                        except:
                            pass
                    if perms.manage_roles:
                        return True
                except:
                    pass
        except:
            return False

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
        self.update_now_playing(entry)
        player.skip_state.reset()

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
                newmsg = '%s - your song **%s** is now playing in %s!' % (
                    entry.meta['author'].mention, entry.title, player.voice_client.channel.name)
            else:
                newmsg = 'Now playing in %s: **%s**' % (
                    player.voice_client.channel.name, entry.title)

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
            try:
                await player.playlist.add_entry(song_url, channel=None, author=None)
            except Exception as e:
                print('\n\nUnable to queue up song at %s to be played.\n' % song_url)
                traceback.print_exc()


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
        print()

        if self.servers:
            print('--Server List--')
            [print(s) for s in self.servers]
        else:
            print("No servers have been joined yet.")

        print()

        # maybe option to leave the ownerid blank and generate a random command for the owner to use

        if self.config.auto_summon:
            as_ok = await self._auto_summon()

            if self.config.auto_playlist and as_ok:
                await self.on_finished_playing(await self.get_player(self._get_owner_voice_channel()))


    # TODO: autosummon option to a specific channel
    async def _auto_summon(self):
        channel = self._get_owner_voice_channel()
        if channel:
            await self.handle_summon(channel, discord.Object(id=str(self.config.owner_id)), flag=True)
            return True
        else:
            print("Owner not found in a voice channel, could not autosummon.")
            return False

    def _get_owner_voice_channel(self):
        for server in self.servers:
            for channel in server.channels:
                if discord.utils.get(channel.voice_members, id=self.config.owner_id):
                    return channel

    def _fixg(self, x, dp=2):
        return ('{:.%sf}' % dp).format(x).rstrip('0').rstrip('.')


    async def handle_help(self, channel, author):
        """
        Usage: {command_prefix}help
        Prints a help message
        """
        if self.can_use(channel, author, command='help'):
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

    async def handle_perms(self, channel, server, author, mentions, switch, command, role_to_add=None):
        """
        Usage: {command_prefix}perms [ + | - | add | remove | clear ] [command] [@UserName / Role Name]
        Adds or removes the user(s) / role to the whitelist. When the whitelist is enabled,
        whitelisted users are permitted to use bot commands.
        """
        if self.can_use(channel, author, command='perms'):
            if switch not in ['add', 'remove', '+', '-', 'clear']:
                raise CommandError('Invalid option "%s" specified, use allow, deny, or clear' % switch)
            if switch in ['add', '+']:
                if not command:
                    raise CommandError('Invalid syntax, command required for `{}` statements'.format(switch))
                handler = getattr(self, 'handle_%s' % command, None)
                if not handler:
                    raise CommandError('Invalid command "%s" specified, please use an active command' % switch)
                if mentions:
                    for users in mentions:
                        if command in self.bot_config[0]:
                            self.bot_config[0][command][0].append(users.id)
                        else:
                            self.bot_config[0][command] = [[users.id], []]
                    write_json('./config/config.json', self.bot_config)
                    return Response('perms successfully given', reply=True, delete_after=10)
                else:
                    try:
                        role = discord.utils.get(server.roles, name=role_to_add)
                        if not role:
                            int('this')
                        if command in self.bot_config[0]:
                            self.bot_config[0][command][1].append(role.id)
                        else:
                            self.bot_config[0][command] = [[], [role.id]]
                        write_json('./config/config.json', self.bot_config)
                        return Response('perms successfully given', reply=True, delete_after=10)
                    except:
                        raise CommandError('Invalid user / role specified : {}'.format(role_to_add))
            elif switch in ['remove', '-']:
                if not command:
                    raise CommandError('Invalid syntax, command required for `{}` statements'.format(switch))
                handler = getattr(self, 'handle_%s' % command, None)
                if not handler:
                    raise CommandError('Invalid command "%s" specified, please use an active command' % switch)
                if mentions:
                    for users in mentions:
                        if command in self.bot_config[0]:
                            self.bot_config[0][command][0].remove(users.id)
                        else:
                            raise CommandError('User `{}` not whitelisted for command `{}`'.format(role_to_add.name, command))
                    write_json('./config/config.json', self.bot_config)
                    return Response('perms successfully removed', reply=True, delete_after=10)
                else:
                    try:
                        role = discord.utils.get(server.roles, name=role_to_add)
                        if not role:
                            int('this')
                        if command in self.bot_config[0]:
                            self.bot_config[0][command][1].remove(role.id)
                            write_json('./config/config.json', self.bot_config)
                            return Response('perms successfully removed', reply=True, delete_after=10)
                        else:
                            raise CommandError('User `{}` not whitelisted for command `{}`'.format(role_to_add.name, command))
                    except:
                        raise CommandError('Invalid user / role specified : {}'.format(role_to_add))
            else:
                if command:
                    raise CommandError('Invalid syntax, command not used in `clear` statements')
                if mentions:
                    for users in mentions:
                        for command, user_role_list in self.bot_config[0]:
                            if users.id in user_role_list[0]:
                                self.bot_config[0][command][0].remove(users.id)
                    write_json('./config/config.json', self.bot_config)
                    return Response('perms successfully removed', reply=True, delete_after=10)
                else:
                    try:
                        role = discord.utils.get(server.roles, name=role_to_add)
                        if not role:
                            int('this')
                        for command, user_role_list in self.bot_config[0]:
                            if role.id in user_role_list[1]:
                                self.bot_config[0][command][1].remove(role.id)
                                write_json('./config/config.json', self.bot_config)
                                return Response('perms successfully removed', reply=True, delete_after=10)
                    except:
                        raise CommandError('Invalid user / role specified : {}'.format(role_to_add))


    async def handle_id(self, channel, author):
        """
        Usage: {command_prefix}id
        Tells the user their id.
        """
        if self.can_use(channel, author, command='id'):
            return Response('your id is `%s`' % author.id, reply=True)

    async def handle_joinserver(self, channel, author, server_link):
        """
        Usage {command_prefix}joinserver [Server Link]
        Asks the bot to join a server. [todo: add info about if it breaks or whatever]
        """
        try:
            if self.can_use(channel, author, command='joinserver', ownerOnlyFlag=True):
                await self.accept_invite(server_link)

        except:
            raise CommandError('Invalid URL provided:\n{}\n'.format(server_link))

    async def handle_play(self, player, channel, author, song_url):
        """
        Usage {command_prefix}play [song link]
        Adds the song to the playlist.
        """
        if self.can_use(channel, author, command='play'):
            try:
                await self.send_typing(channel)

                reply_text = "Enqueued **%s** to be played. Position in queue: %s"

                info = await extract_info(player.playlist.loop, song_url, download=False, process=False)

                if not info:
                    raise CommandError("That video cannot be played.")

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
                    listlen = len(entry_list)

                    print("Processed {} songs in {} seconds at {:.2f}s/song, {:+.2g}/song from expected ({}s)".format(
                        listlen, '{:.2f}'.format(ttime).rstrip('0').rstrip('.'), ttime/listlen,
                        ttime/listlen - wait_per_song, wait_per_song*num_songs)
                    )

                    await self.delete_message(procmesg)

                else:
                    entry, position = await player.playlist.add_entry(song_url, channel=channel, author=author)

                time_until = await player.playlist.estimate_time_until(position, player)

                if position == 1 and player.is_stopped:
                    position = 'Up next!'
                    reply_text = reply_text % (entry.title, position)
                else:
                    reply_text += ' - estimated time until playing: %s'
                    reply_text = reply_text % (entry.title, position, time_until)
                    # TODO: Subtract time the current song has been playing for

                return Response(reply_text, reply=True, delete_after=15)

            except Exception as e:
                traceback.print_exc()
                raise CommandError('Unable to queue up song at %s to be played.' % song_url)

    async def handle_summon(self, channel, author, flag=False):
        """
        Usage {command_prefix}summon
        This command is for summoning the bot into your voice channel [but it should do it automatically the first time]
        """
        if flag or self.can_use(channel, author, command='summon'):
            server = channel.server
            moving = False
            if server.id in self.players:
                moving = True
                print("Already in channel, moving")

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

            if not chperms.connect:
                print("Cannot join channel \"%s\", no permission." % channel.name)
                return Response("```Cannot join channel \"%s\", no permission.```" % channel.name, delete_after=15)

            elif not chperms.speak:
                print("Will not join channel \"%s\", no permission to speak." % channel.name)
                return Response("```Will not join channel \"%s\", no permission to speak.```" % channel.name, delete_after=15)

            if moving:
                try:
                    await self.join_voice_channel(channel)
                except:
                    pass
                return Response('Switched to channel `{}`!'.format(channel.name))

            player = await self.get_player(channel, create=True)

            if player.is_stopped:
                player.play()

    async def handle_pause(self, channel, author, player):
        """
        Usage {command_prefix}pause
        Pauses playback of the current song. [todo: should make sure it works fine when used inbetween songs]
        """
        if self.can_use(channel, author, command='pause'):
            if player.is_playing:
                player.pause()

            else:
                raise CommandError('Player is not playing.')

    async def handle_resume(self, channel, author, player):
        """
        Usage {command_prefix}resume
        Resumes playback of a paused song.
        """
        if self.can_use(channel, author, command='resume'):
            if player.is_paused:
                player.resume()

            else:
                raise CommandError('Player is not paused.')

    async def handle_shuffle(self, channel, author, player):
        """
        Usage {command_prefix}shuffle
        Shuffles the playlist.
        """
        if self.can_use(channel, author, command='shuffle'):
            player.playlist.shuffle()
            return Response('*shuffleshuffleshuffle*', delete_after=10)

    async def handle_clear(self, channel, player, author):
        """
        Usage {command_prefix}clear
        Clears the playlist.
        """
        if self.can_use(channel, author, command='clear', ownerOnlyFlag=True):
            player.playlist.clear()
            return

    async def handle_skip(self, player, channel, author):
        """
        Usage {command_prefix}skip
        Skips the current song when enough votes are cast, or by the bot owner.
        """
        if self.can_use(channel, author, command='skip'):
            if player.is_stopped or player.is_paused:  # TODO: pausing and skipping a song breaks /something/, i'm not sure what
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

    async def handle_volume(self, channel, author, new_volume=None):
        """
        Usage {command_prefix}volume (+/-)[volume]
        Sets the playback volume. Accepted values are from 1 to 100.
        Putting + or - before the volume will make the volume change relative to the current volume.
        """
        if self.can_use(channel, author, command='volume'):
            player = await self.get_player(channel)

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

    async def handle_queue(self, channel, author):
        """
        Usage {command_prefix}queue
        Prints the current song queue.
        """
        if self.can_use(channel, author, command='queue'):
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

    async def handle_ignore(self, message, server, author, channel, switch, target_channel):
        """
        Usage {command_prefix}ignore [ + | - | add | remove ] [#channel]
        Makes the bot ignore the specified channel
        """
        if self.can_use(channel, author, command='ignore', ownerOnlyFlag=True):
            if switch not in ['add', 'remove', '+', '-']:
                raise CommandError('Invalid option "%s" specified, use allow, deny, or clear' % switch)
            if switch in ['add', '+']:
                try:
                    target_channel_obj = discord.utils.get(server.channels, id=target_channel)
                    if not target_channel_obj:
                        int('this')
                    self.bot_config[1].append(target_channel_obj.id)
                    write_json('./config/config.json', self.bot_config)
                    return Response('channel `{}` is now being ignored!'.format(target_channel_obj.name), reply=True, delete_after=10)
                except:
                    raise CommandError('Invalid Channel: {}'.format(target_channel))
            else:
                try:
                    target_channel_obj = discord.utils.get(server.channels, id=target_channel)
                    if not target_channel_obj:
                        int('this')
                    self.bot_config[1].remove(target_channel_obj.id)
                    write_json('./config/config.json', self.bot_config)
                    return Response('channel `{}` no longer being ignored!'.format(target_channel_obj.name), reply=True, delete_after=10)
                except:
                    raise CommandError('Invalid Channel: {}'.format(target_channel))

    async def handle_eval(self, author, server, message, channel, mentions, eval_string):
        """
        Usage: {command_prefix}eval "evaluation string"
        runs a command thru the eval param for testing
        """
        if self.can_use(channel, author, command='ignore', ownerOnlyFlag=True):
            this = eval(eval_string)
            return Response('```{}```'.format(this), reply=True)
        return

    async def handle_clean(self, message, author, amount):
        """
        Usage {command_prefix}clean amount
        Removes [amount] messages the bot has posted in chat.
        """
        pass



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

        for arg in args:
                if arg.startswith('<@'):
                    args.remove(arg)
                if arg.startswith('<#'):
                    pos = args.index(arg)
                    arg = arg.replace('<#', '').replace('>', '')
                    args[pos] = arg

        command = command[len(self.config.command_prefix):].lower().strip()

        handler = getattr(self, 'handle_%s' % command, None)
        if not handler:
            return

        if message.channel.id in self.bot_config[1] and message.author.id != self.config.owner_id:
            return

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

            if params.pop('mentions', None):
                handler_kwargs['mentions'] = message.mentions

            if params.pop('server', None):
                handler_kwargs['server'] = message.server

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
                try:
                    await self.send_message(
                        message.channel,
                            '```\n%s\n```' % docs.format(command_prefix=self.config.command_prefix)
                    )
                except discord.Forbidden:
                    print('Cannot send message to \"{}\" due to lack of permissions'.format(message.channel))
                return

            response = await handler(**handler_kwargs)
            if response and isinstance(response, Response):
                content = response.content
                if response.reply:
                    content = '%s, %s' % (message.author.mention, content)

                try:
                    sentmsg = await self.send_message(message.channel, content)

                    if response.delete_after > 0 and self.config.auto_delete:
                        await asyncio.sleep(response.delete_after)
                        try:
                            await self.delete_message(sentmsg)
                        except discord.Forbidden:
                            print('Cannot delete messages due to lack of permissions')
                except discord.Forbidden:
                    print('Cannot send message to \"{}\" due to lack of permissions'.format(message.channel))

        except CommandError as e:
            try:
                if self.config.report_errors:
                    await self.send_message(message.channel, '```\n%s\n```' % e.message)
            except discord.Forbidden:
                print('Cannot send message to \"{}\" due to lack of permissions'.format(message.channel))

        except:
            try:
                if self.config.report_errors:
                    await self.send_message(message.channel, '```\n%s\n```' % traceback.format_exc())
            except discord.Forbidden:
                print('Cannot send message to \"{}\" due to lack of permissions'.format(message.channel))
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

'''
