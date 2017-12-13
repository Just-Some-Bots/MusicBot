#import pornhub as p
import os
import sys
import shlex
import random
import shutil
import inspect
import aiohttp
import discord
import asyncio
import traceback
import subprocess
import uuid
import aiohttp
import aiodns
import giphypop
import urllib.request
import json
import time 
import datetime


from discord.ext import commands
from giphypop import screensaver
from discord import utils
from discord.object import Object
from discord.enums import ChannelType
from discord.voice_client import VoiceClient
from discord.ext.commands.bot import _get_variable

from io import BytesIO, StringIO
from functools import wraps
from textwrap import dedent
from datetime import timedelta
from random import choice, shuffle
from collections import defaultdict
from time import sleep

from musicbot.playlist import Playlist
from musicbot.player import MusicPlayer
from musicbot.config import Config, ConfigDefaults
from musicbot.permissions import Permissions, PermissionsDefaults
from musicbot.utils import load_file, write_file, sane_round_int

from . import exceptions
from . import downloader
from .opus_loader import load_opus_lib
from .constants import VERSION as BOTVERSION
from .constants import DISCORD_MSG_CHAR_LIMIT, AUDIO_CACHE_PATH


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
		self.players = {}
		self.the_voice_clients = {}
		self.locks = defaultdict(asyncio.Lock)
		self.voice_client_connect_lock = asyncio.Lock()
		self.voice_client_move_lock = asyncio.Lock()

		self.config = Config(config_file)
		self.permissions = Permissions(perms_file, grant_all=[self.config.owner_id])

		self.prefixes = set(load_file(self.config.prefixes_file))
		self.whitelist = set(load_file(self.config.whitelist_file))
		self.blacklist = set(load_file(self.config.blacklist_file))
		self.autoplaylist = load_file(self.config.auto_playlist_file)
		self.downloader = downloader.Downloader(download_folder='audio_cache')
		self.user_warnings = 0

		self.exit_signal = None 
		self.init_ok = False
		self.cached_client_id = None
		self.server_names = list()
		self.startupdate = None

		if not self.autoplaylist:
			print("[%s][INFO] Autoplaylist is empty, disabling." % datetime.datetime.now())
			self.config.auto_playlist = False

		# TODO: Do these properly
		ssd_defaults = {'last_np_msg': None, 'auto_paused': False}
		self.server_specific_data = defaultdict(lambda: dict(ssd_defaults))

		super().__init__()
		self.aiosession = aiohttp.ClientSession(loop=self.loop)
		self.http.user_agent += ' MusicBot/%s' % BOTVERSION

	# TODO: Add some sort of `denied` argument for a message to send when someone else tries to use it
	def owner_only(func):
		@wraps(func)
		async def wrapper(self, *args, **kwargs):
			# Only allow the owner to use these commands
			orig_msg = _get_variable('message')

			if not orig_msg or orig_msg.author.id == self.config.owner_id:
				return await func(self, *args, **kwargs)
			else:
				raise exceptions.PermissionsError("O-only my real m-master can make me do that...", expire_in=30)

		return wrapper

	@staticmethod
	def _fixg(x, dp=2):
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

		return 

	# TODO: autosummon option to a specific channel
	async def _auto_summon(self):
		owner = self._get_owner(voice=True)
		if owner:
			self.safe_print("[%s][INFO] Found my owner in \"%s\", attempting to join..." % (datetime.datetime.now(), owner.voice_channel.name))
			# TODO: Effort
			await self.cmd_join(owner.voice_channel, owner, None)
			return owner.voice_channel

	async def _autojoin_channels(self, channels):
		joined_servers = []

		for channel in channels:
			if channel.server in joined_servers:
				print("[%s][WARNING] Already joined a channel in \"%s\", skipping \"%s\"." % (datetime.datetime.now(), channel.server.name, channel.name))
				continue

			if channel and channel.type == discord.ChannelType.voice:
				self.safe_print("[%s][INFO] Attempting to join \"%s\" in \"%s\"." % (datetime.datetime.now(), channel.name, channel.server.name))

				chperms = channel.permissions_for(channel.server.me)

				if not chperms.connect:
					self.safe_print("[%s][ERROR] Cannot join server \"%s\", no permissions to connect to channel \"%s\"." % (datetime.datetime.now(), channel.server.name, channel.name))
					continue

				elif not chperms.speak:
					self.safe_print("[%s][ERROR] Will not join server \"%s\", no permission to speak in channel \"%s\"." % (datetime.datetime.now(), channel.server.name, channel.name))
					continue

				try:
					player = await self.get_player(channel, create=True)

					if player.is_stopped:
						player.play()

					if self.config.auto_playlist:
						await self.on_player_finished_playing(player)

					joined_servers.append(channel.server)
				except Exception as e:
					if self.config.debug_mode:
						traceback.print_exc()
					print("[%s][ERROR] Failed to join server \"%s\" in channel \"%s\"." % (datetime.datetime.now(), channel.server.name, channel.name))

			elif channel:
				print("[%s][ERROR] Not joining the \"%s\" server, \"%s\" is a text channel." % (datetime.datetime.now(), channel.server.name, channel.name))

			else:
				print("[%s][ERROR] Invalid channel thing: " + channel % datetime.datetime.now())

	async def _wait_delete_msg(self, message, after):
		await asyncio.sleep(after)
		await self.safe_delete_message(message)

	# TODO: Check to see if I can just move this to on_message after the response check
	async def _manual_delete_check(self, message, *, quiet=False):
		if self.config.delete_invoking:
			await self.safe_delete_message(message, quiet=quiet)


	async def _check_ignore_non_voice(self, msg):
		vc = msg.server.me.voice_channel
		# If we've connected to a voice chat and we're in the same voice channel
		if not vc or vc == msg.author.voice_channel:
			return True
		else:
			raise exceptions.PermissionsError(
				"I c-can\'t do that o-outside of the \"%s\" channel m-master." % vc.name, expire_in=30)


	async def generate_invite_link(self, *, permissions=None, server=None):
		if not self.cached_client_id:
			appinfo = await self.application_info()
			self.cached_client_id = appinfo.id
		return discord.utils.oauth_url(self.cached_client_id, permissions=permissions, server=server)


	async def get_voice_client(self, channel):
		if isinstance(channel, Object):
			channel = self.get_channel(channel.id)
		if getattr(channel, 'type', ChannelType.text) != ChannelType.voice:
			raise AttributeError('I\'d ummm... p-prefer if that weren\'t a t-text channel m-master...')
		with await self.voice_client_connect_lock:
			server = channel.server
			if server.id in self.the_voice_clients:
				return self.the_voice_clients[server.id]
			s_id = self.ws.wait_for('VOICE_STATE_UPDATE', lambda d: d.get('user_id') == self.user.id)
			_voice_data = self.ws.wait_for('VOICE_SERVER_UPDATE', lambda d: True)
			await self.ws.voice_state(server.id, channel.id)
			s_id_data = await asyncio.wait_for(s_id, timeout=10, loop=self.loop)
			voice_data = await asyncio.wait_for(_voice_data, timeout=10, loop=self.loop)
			session_id = s_id_data.get('session_id')
			kwargs = {
				'user': self.user,
				'channel': channel,
				'data': voice_data,
				'loop': self.loop,
				'session_id': session_id,
				'main_ws': self.ws
			}
			voice_client = VoiceClient(**kwargs)
			self.the_voice_clients[server.id] = voice_client
			retries = 3
			for x in range(retries):
				try:
					print("[%s][INFO] Attempting connection with the server \"%s\" for the channel \"%s\"..." % (datetime.datetime.now(), channel.server.name, channel.name))
					await asyncio.wait_for(voice_client.connect(), timeout=10, loop=self.loop)
					print("[%s][INFO] Connection established with the server \"%s\" for the channel \"%s\"." % (datetime.datetime.now(), channel.server.name, channel.name))
					break
				except:
					traceback.print_exc()
					print("[%s][ERROR] Failed to connect with the server \"%s\" for the channel \"%s\, retrying (%s/%s)..." % (datetime.datetime.now(), channel.server.name, channel.name, x+1, retries))
					await asyncio.sleep(1)
					await self.ws.voice_state(server.id, None, self_mute=True)
					await asyncio.sleep(1)
					if x == retries-1:
						raise exceptions.HelpfulError(
							"Cannot establish connection to voice chat.  "
							"Something may be blocking outgoing UDP connections.",
							"This may be an issue with a firewall blocking UDP.  "
							"Figure out what is blocking UDP and disable it.  "
							"It's most likely a system firewall or overbearing anti-virus firewall.  "
						)
			return voice_client


	async def mute_voice_client(self, channel, mute):
		await self._update_voice_state(channel, mute=mute)


	async def deafen_voice_client(self, channel, deaf):
		await self._update_voice_state(channel, deaf=deaf)


	async def move_voice_client(self, channel):
		await self._update_voice_state(channel)


	async def reconnect_voice_client(self, server):
		if server.id not in self.the_voice_clients:
			return
		vc = self.the_voice_clients.pop(server.id)
		_paused = False
		player = None
		if server.id in self.players:
			player = self.players[server.id]
			if player.is_playing:
				player.pause()
				_paused = True
		try:
			await vc.disconnect()
		except:
			print("[%s][ERROR] Error disconnecting during reconnect." % datetime.datetime.now())
			traceback.print_exc()
		await asyncio.sleep(0.1)
		if player:
			new_vc = await self.get_voice_client(vc.channel)
			player.reload_voice(new_vc)
			if player.is_paused and _paused:
				player.resume()


	async def disconnect_voice_client(self, server):
		if server.id not in self.the_voice_clients:
			return
		if server.id in self.players:
			self.players.pop(server.id).kill()
		await self.the_voice_clients.pop(server.id).disconnect()


	async def disconnect_all_voice_clients(self):
		for vc in self.the_voice_clients.copy().values():
			await self.disconnect_voice_client(vc.channel.server)


	async def _update_voice_state(self, channel, *, mute=False, deaf=False):
		if isinstance(channel, Object):
			channel = self.get_channel(channel.id)
		if getattr(channel, 'type', ChannelType.text) != ChannelType.voice:
			raise AttributeError('I ummm... can\'t j-join a t-text channel m-master...')
		# I'm not sure if this lock is actually needed
		with await self.voice_client_move_lock:
			server = channel.server
			payload = {
				'op': 4,
				'd': {
					'guild_id': server.id,
					'channel_id': channel.id,
					'self_mute': mute,
					'self_deaf': deaf
				}
			}
			await self.ws.send(utils.to_json(payload))
			self.the_voice_clients[server.id].channel = channel


	async def get_player(self, channel, create=False) -> MusicPlayer:
		server = channel.server
		if server.id not in self.players:
			if not create:
				raise exceptions.CommandError(
					'I... I don\'t know where to d-do that m-master...'
					'\nUse %sjoin to g-guide me to your v-voice channel.' % self.config.command_prefix)
			voice_client = await self.get_voice_client(channel)
			playlist = Playlist(self)
			player = MusicPlayer(self, voice_client, playlist) \
				.on('play', self.on_player_play) \
				.on('resume', self.on_player_resume) \
				.on('pause', self.on_player_pause) \
				.on('stop', self.on_player_stop) \
				.on('finished-playing', self.on_player_finished_playing) \
				.on('entry-added', self.on_player_entry_added)
			player.skip_state = SkipState()
			self.players[server.id] = player
		return self.players[server.id]

	async def on_player_play(self, player, entry):
		await self.update_now_playing(entry) # Updates Neko's "Playing:___________" message
		player.skip_state.reset()            # Resets the votes for a skip
		channel = entry.meta.get('channel', None)
		author = entry.meta.get('author', None)
		if channel and author:
			last_np_msg = self.server_specific_data[channel.server]['last_np_msg']
			if last_np_msg and last_np_msg.channel == channel:
				async for lmsg in self.logs_from(channel, limit=1):
					if lmsg != last_np_msg and last_np_msg:
						await self.safe_delete_message(last_np_msg)
						self.server_specific_data[channel.server]['last_np_msg'] = None
					break  # This is probably redundant
			if self.config.now_playing_mentions:
				newmsg = ':smile_cat: **|** ***%s, your song*** __*`%s`*__ ***is now playing in*** __*`%s`*__***!***' % (
					entry.meta['author'].mention, entry.title, player.voice_client.channel.name)
			else:
				newmsg = ':smile_cat: **|** ***Now playing*** __*`%s`*__\n***Currently in*** __*`%s`*__***.***' % (
					entry.title, player.voice_client.channel.name)
			if self.server_specific_data[channel.server]['last_np_msg']:
				self.server_specific_data[channel.server]['last_np_msg'] = await self.safe_edit_message(last_np_msg, newmsg, send_if_fail=True)
			else:
				self.server_specific_data[channel.server]['last_np_msg'] = await self.safe_send_message(channel, newmsg)


	async def on_player_resume(self, entry, **_):
		await self.update_now_playing(entry)


	async def on_player_pause(self, entry, **_):
		await self.update_now_playing(entry)


	async def on_player_stop(self, **_):
		await self.update_now_playing()


	async def on_player_finished_playing(self, player, **_):
		if not player.playlist.entries and not player.current_entry and self.config.auto_playlist:
			while self.autoplaylist:
				song_url = random.choice(self.autoplaylist)
				info = await self.downloader.safe_extract_info(player.playlist.loop, song_url, download=False, process=False)
				if not info:
					self.autoplaylist.remove(song_url)
					self.safe_print("[%s][INFO] Removing unplayable song from autoplaylist: %s" % (datetime.datetime.now(), song_url))
					write_file(self.config.auto_playlist_file, self.autoplaylist)
					continue
				if info.get('entries', None):  # or .get('_type', '') == 'playlist'
					pass  # Wooo playlist
					# Blarg how do I want to do this
				# TODO: better checks here
				try:
					await player.playlist.add_entry(song_url, channel=None, author=None)
				except exceptions.ExtractionError as e:
					print("[ERROR] Error adding song from autoplaylist:", e)
					continue
				break
			if not self.autoplaylist:
				print("[%s][WARNING] No playable songs in the autoplaylist, disabling." % datetime.datetime.now())
				self.config.auto_playlist = False
		await self.update_now_playing()


	async def on_player_entry_added(self, playlist, entry, **_):
		pass
		
	async def update_now_playing(self, status_message=None, entry=None, is_paused=False):
		owner = self._get_owner(voice=True or False or None) or self._get_owner()
		ds = ['user', 'suicide', 'skipnow', 'glomp', 'invite', 'invite', 'ban', 'greet', '8ball', 'kick', 'snuggle', 'softban', 'pldump', 'listids', 'song', 'server', 'roles', 'server', 'test', 'play', 'ckiss', 'playlist', 'howl', 'search', 'skip', 'join', 'help', 'ping', 'roll', 'say', 'nugget', 'noodle', 'cookie', 'hug', 'kiss', 'cuddle', 'slap', 'lewd', 'punch', 'poke', 'pat', 'satan', 'coin', 'neko', 'fkiss', 'flirt', 'sob', 'leave', 'sex', 'succ', 'steal', 'kill', 'purr', 'rate', 'remove', 'moan', 'pout', 'pet', 'uptime', 'kawaii', 'leave', 'cleanup', 'playhits', 'playsad', 'playvamps', 'playlove', 'playnightcore', 'playanime', 'playdub', 'playbg', 'playlogic', 'cum', 'play', 'pause', 'resume', 'clear', 'repeat', 'pong', 'volume']
		game = discord.Game(name='\{} | with {}#{}'.format(random.choice(ds), owner.name, owner.discriminator), type=1, url="https://www.twitch.tv/subbub55")
		await self.change_presence(game=game, status=1, afk=False)

	async def cmd_eval(self, author, server, message, channel, mentions, code):
		    """
		    Usage: {command_prefix}eval "evaluation string"
		    runs a command thru the eval param for testing
		    """
		    if author.id == author.id:
		        result = None

		        try:
		            result = eval(code)
		        except Exception:
		            formatted_lines = traceback.format_exc().splitlines()
		            return Response('```py\n{}\n{}\n```'.format(formatted_lines[-1], '/n'.join(formatted_lines[4:-1])), reply=True)

		        if asyncio.iscoroutine(result):
		            result = await result

		        if result:
		            return Response('```Input: {}\nOutput: {}```'.format(code, result), reply=True)

		        return Response(':thumbsup:'.format(result), reply=True)
		    return

	async def cmd_exec(self, author, server, message, channel, mentions, code):
		    """
		    Usage: {command_prefix}evec py "evaluation string"
		    Runs a command thru the eval param for testing.
		    """
		    if author.id == self.config.owner_id:
		        old_stdout = sys.stdout
		        redirected_output = sys.stdout = StringIO()

		        try:
		            exec(code)
		        except Exception:
		            formatted_lines = traceback.format_exc().splitlines()
		            return Response('```py\n{}\n{}\n```'.format(formatted_lines[-1], '\n'.join(formatted_lines[4:-1])), reply=True)
		        finally:
		            sys.stdout = old_stdout

		        if redirected_output.getvalue():
		            return Response(redirected_output.getvalue(), reply=True)
		        return Response(":Input: {}\nOutput: {}".format(code), reply=True)
		    return
	@owner_only
	async def cmd_sync(self, message, channel, server, permissions, user_mentions):
		"""
		Usage:
			{command_prefix}sync
		await self.update_now_playing()
		"""
		await self.update_now_playing()
		await self.safe_send_message(channel, "Senpai {}, I've updated owner name and changed my now playing message. Are you proud?".format(message.author.name))

	async def cmd_roles(self, message, channel, permissions, server, user_mentions):
		"""
		Usage:
			{command_prefix}roles
		List the roles of the server highest to lowest.
		"""
		roles = ', '.join(r.name for r in message.author.server.role_hierarchy)
		await self.safe_send_message(channel, "__**Server Roles(Highest to lowest):**__ __***`{}`***__".format(roles))


	async def cmd_user(self, author, server, channel, message, user_mentions):
		"""
		Usage:
			{command_prefix}user [@USER]

		Provides some info on a user, if no-one mentioned returns info on message author.
		"""
		if not user_mentions:
			member = author
		else:
			member = user_mentions[0]

		voice = member.voice.voice_channel
		roles = ', '.join(r.name for r in member.roles)
		join_date = member.joined_at
		status = member.status
		game = member.game
		server = member.server
		nickname = member.nick
		color = member.colour
		top_role = member.top_role
		creation_date = member.created_at
		avatar = member.avatar_url if member.avatar_url else member.default_avatar_url
		user_id = message.author.id
		await self.safe_send_message(channel, "```Nim\nInfo On: {} in {}\n\nVoice: {}\nRoles: {}\nJoined: {}\nStatus: {}\nGame: {}\nNickname: {}\nColor: {}\nTop Role: {}\nCreated: {}\nUser ID: {}\nAvatar:``` {} \n".format(member, server, voice, roles, join_date, status, game, nickname, color, top_role, creation_date, user_id, avatar))


	@owner_only
	async def cmd_broadcast(self, args, leftover_args):
		"""
		Usage:
			{command_prefix}broadcast [MESSAGE]
		Sends a message to all servers the bot is on.
		"""
		if leftover_args:
			args = ' '.join([args, *leftover_args])
		for s in self.servers:
			await self.safe_send_message(s, args)
		await self.update_now_playing()

	async def cmd_ping(self, channel, message):
		            """
		            Usage:
		                {command_prefix}ping
		            Ping command to test the average latency between the server and the bot.
		            """
		            time_then = time.monotonic()
		            pinger = await self.safe_send_message(message.channel, '__*`Pinging...`*__')
		            ping = '%.2f' % (1000*(time.monotonic()-time_then))
		            await self.safe_edit_message(pinger, ':ping_pong: \n **Pong!** __**`' + ping + 'ms`**__')
		            await self.update_now_playing()

	async def cmd_pong(self, channel, message):
		            """
		            Usage:
		                {command_prefix}pong
		            Pong command to test the average latency between the server and the bot.
		            """
		            time_then = time.monotonic()
		            ponger = await self.safe_send_message(message.channel, '__*`Ponging...`*__')
		            pong = '%.2f' % (1000*(time.monotonic()-time_then))
		            await self.safe_edit_message(ponger, ':ping_pong: \n **Ping!** __**`' + pong + 'ms`**__')
		            await self.update_now_playing()

	async def cmd_cum(self, message, server, channel, permissions, user_mentions):
		"""
		Usage:
			{command_prefix}cum <@a valid user>
		Cum on yourself or others heh
		"""

		owner = self._get_owner(voice=True or False or None) or self._get_owner()
		if not user_mentions:
			lewd =  ['http://i3.kym-cdn.com/photos/images/newsfeed/000/936/092/af7.jpg', 'http://i.imgur.com/tkEOnku.jpg', 'http://i3.kym-cdn.com/photos/images/original/000/905/295/193.png', 'http://i.imgur.com/Kscx9g5.png', 'http://i3.kym-cdn.com/photos/images/original/000/897/703/b97.png', 'http://gallery.fanserviceftw.com/_images/a32b7d53651dcc3b76fcdc85a989c81b/9599%20-%20doushio%20makise_kurisu%20steins%3Bgate%20tagme.png', 'https://img.ifcdn.com/images/89ca6bd97bca8fabb4f3cb24f56e79b9ad020904e194f8cf99ff046d8da368a1_1.jpg', 'http://i2.kym-cdn.com/photos/images/newsfeed/000/888/789/f39.jpg', 'http://i1.kym-cdn.com/photos/images/original/000/988/917/ff8.jpg', 'http://i0.kym-cdn.com/photos/images/masonry/000/905/286/7ec.jpg','http://i1.kym-cdn.com/photos/images/facebook/000/794/434/6e7.gif']
			urllib.request.urlretrieve(random.choice(lewd), 'tmp.png')
			await self.safe_send_message(channel, "{}, has just came, :clap: good job dood! \n*Grab's a towel and clean's master's mess up* m-messy master.".format(message.author.name))
			await self.send_file(channel, 'tmp.png')
		for user in user_mentions.copy():
			if message.author.name == user.name:
				await self.safe_send_message(channel, "{}, you got cum all over yourself! Gross! \n*Get's you a towel and clean's you up being gentle* Next time be a little less mess master!.".format(message.author.name))
			elif user.name == self.user.name:
				await self.safe_send_message(channel, "{}, *blocks the cum shot with a towel* nope! Sorry but not allowed!".format(message.author.name))
			elif user.name == owner.name and not message.author.id == '336948766986862597':
				await self.safe_send_message(channel, ":heavy_multiplication_x: | no can do! ")
			else:
				lewd =  ['http://i3.kym-cdn.com/photos/images/newsfeed/000/936/092/af7.jpg', 'http://i.imgur.com/tkEOnku.jpg', 'http://i3.kym-cdn.com/photos/images/original/000/905/295/193.png', 'http://i.imgur.com/Kscx9g5.png', 'http://i3.kym-cdn.com/photos/images/original/000/897/703/b97.png', 'http://gallery.fanserviceftw.com/_images/a32b7d53651dcc3b76fcdc85a989c81b/9599%20-%20doushio%20makise_kurisu%20steins%3Bgate%20tagme.png', 'https://img.ifcdn.com/images/89ca6bd97bca8fabb4f3cb24f56e79b9ad020904e194f8cf99ff046d8da368a1_1.jpg', 'http://i2.kym-cdn.com/photos/images/newsfeed/000/888/789/f39.jpg', 'http://i1.kym-cdn.com/photos/images/original/000/988/917/ff8.jpg', 'http://i0.kym-cdn.com/photos/images/masonry/000/905/286/7ec.jpg','http://i1.kym-cdn.com/photos/images/facebook/000/794/434/6e7.gif']
				urllib.request.urlretrieve(random.choice(lewd), 'tmp.png')
				await self.safe_send_message(channel, "{}, just came on {}! Hehe naughty masters. \n*Goes and gets a towel and cleans the mess up for master's* Use a room next time!".format(message.author.name, user.name))
				await self.send_file(channel, 'tmp.png')
		os.remove('tmp.png')
		await self.update_now_playing()

	async def cmd_howl(self, message, server, channel, permissions, user_mentions):
		"""
		Usage:
			[command_prefix]howl <@a valid user>
		Howl or howl at other people. Awoo~
		"""
		if not user_mentions:
			await self.safe_send_message(channel, "{}, *howls loudly*! *awooo*!".format(message.author.name))
		else:
			for user in user_mentions.copy():
				if message.author.name == user.name:
					await self.safe_send_message(channel, "{}, *howls loudly* *awoo*!".format(message.author.name))
				elif user.name == self.user.name:
					await self.safe_send_message(channel, "{}, don't howl at me *smacks*".format(message.author.name))
				else:
					await self.safe_send_message(channel, "{} *howls at* {}!".format(message.author.mention, user.mention))
				await self.delete_messages(message)
				await self.update_now_playing()

	async def cmd_suicide(self, message, server, channel, permissions, user_mentions):
		"""
		Usage:
			{command_prefix}suicide
		kys
		"""
		await self.safe_send_message(channel, "{0}, has just killed themselves rip {0}".format(message.author.name))
		await self.safe_delete_message(message)
		await self.update_now_playing()


	#todo more gifs	
	async def cmd_bite(self, message, server, channel, permissions, user_mentions):
		"""
		Usage:
			{command_prefix}bite <@a valid user>
		Bite people >:)
		"""
		bite = ['https://media.giphy.com/media/pMT5VcMguh4Q0/giphy.gif', 'https://anime.aminoapps.com/page/blog/cute-bite-sweet-anime-girl-loli-big-eyes-kawai-lolicon/YMtb_u0GJaP06BMR2WReM3rKBVneYL', 'http://i.imgur.com/YCAzLzh.gif', 'https://78.media.tumblr.com/7e2cad3ab0432205cdd5c37fab83d977/tumblr_ojh7gzPyeB1uzwbyjo1_500.gif', 'https://media.tenor.com/videos/b6a549824362fc4f964b79d1d086b865/mp4', 'https://media1.tenor.com/images/a74770936aa6f1a766f9879b8bf1ec6b/tenor.gif', 'https://pa1.narvii.com/5965/95e6a157e606ce7e23fb4c7a7cd310c5f13d9d9a_hq.gif', 'https://vignette.wikia.nocookie.net/stevenuniverse-fanon/images/d/d1/Amethyst_bites_Pearl%27s_arm.gif/revision/latest?cb=20150513122650', 'http://i0.kym-cdn.com/photos/images/newsfeed/001/027/044/1cd.gif']
		url = random.choice(bite)
		urllib.request.urlretrieve(url, 'tmp.gif')
		if not user_mentions:
			await self.safe_send_message(channel, "OwO you've biten no-one...so you bite yourself! b-baka!~")
			await self.send_file(channel, 'tmp.gif')
		else:
			for user in user_mentions.copy():
				if message.author.name == user.name:
					await self.safe_send_message(channel, "why have you biten yourself! b-baka!~")
					await self.send_file(channel, 'tmp.gif')
				if user.name == self.user.name:
					await self.safe_send_message(channel, ":heavy_multiplication_x: **|** sorry you can't bite me!")
				else:
					await self.safe_send_message(channel, "{}, has biten {}!".format(message.author.name, user.mention))
					await self.send_file(channel, 'tmp.gif')
		await self.safe_delete_message(message)
		os.remove('tmp.gif')
		await self.update_now_playing()


	async def cmd_hug(self, message, server, channel, permissions, user_mentions):
		"""
		Usage:
			{command_prefix}hug <@a valid user>
		Get hugged by neko, hug neko, or hug someone.
		"""
		hug = ['http://25.media.tumblr.com/tumblr_m8223lqZCl1ra8wu5o1_500.gif','http://www.thehomeplanet.org/wp-content/uploads/2013/04/Bobby-Sam-Hug.gif','http://24.media.tumblr.com/tumblr_lw7r7vRUGN1qii6tmo1_500.gif', 'https://33.media.tumblr.com/680b69563aceba3df48b4483d007bce3/tumblr_mxre7hEX4h1sc1kfto1_500.gif', 'http://media.giphy.com/media/lrr9rHuoJOE0w/giphy.gif', 'https://38.media.tumblr.com/b004f301143edad269aa1d88d0f1e245/tumblr_mx084htXKO1qbvovho1_500.gif', 'http://img4.wikia.nocookie.net/__cb20130302231719/adventuretimewithfinnandjake/images/1/15/Tumblr_m066xoISk41r6owqs.gif', 'http://cdn.smosh.com/sites/default/files/ftpuploads/bloguploads/0413/epic-hugs-friends-anime.gif', 'http://1.bp.blogspot.com/-OpJBN3VvNVw/T7lmAw0HxFI/AAAAAAAAAfo/bGJks9CqbK8/s1600/HUG_K-On!+-+Kawaii.AMO.gif', 'http://media.tumblr.com/tumblr_m1oqhy8vrH1qfwmvy.gif', 'https://myanimelist.cdn-dena.com/s/common/uploaded_files/1461073447-335af6bf0909c799149e1596b7170475.gif','http://24.media.tumblr.com/49a21e182fcdfb3e96cc9d9421f8ee3f/tumblr_mr2oxyLdFZ1s7ewj9o1_500.gif', 'http://pa1.narvii.com/5774/3cb894f1d4bcb4a9c58a06ee2a7fcd1a11f9b0eb_hq.gif','http://media.tumblr.com/01949fb828854480b513a87fa4e8eee7/tumblr_inline_n5r8vyJZa61qc7mf8.gif','https://media.tenor.co/images/e07a54a316ea6581329a7ccba23aea2f/tenor.gif', 'http://media.giphy.com/media/aD1fI3UUWC4/giphy.gif', 'https://38.media.tumblr.com/3b6ccf23ecd9aeacfcce0add1462c7c0/tumblr_msxqo58vDq1se3f24o1_500.gif', 'https://myanimelist.cdn-dena.com/s/common/uploaded_files/1460992224-9f1cd0ad22217aecf4507f9068e23ebb.gif', 'http://1.bp.blogspot.com/-J9Byahz1TuQ/UdI9CslAyAI/AAAAAAAAQWI/_tfIGYSUzdA/s500/inyu5.gif', 'http://25.media.tumblr.com/tumblr_m0lgriUiVK1rqfhi2o1_500.gif', 'http://media.tumblr.com/tumblr_lknzmbIG1x1qb5zie.gif', 'http://mrwgifs.com/wp-content/uploads/2013/04/Snuggling-Cuddling-Anime-Girls-Gif-.gif', 'https://38.media.tumblr.com/b004f301143edad269aa1d88d0f1e245/tumblr_mx084htXKO1qbvovho1_500.gif', 'http://media.giphy.com/media/od5H3PmEG5EVq/giphy.gif', 'http://25.media.tumblr.com/671f27962ca544ef8907ec0132c49ad1/tumblr_mp8srnNcTy1sx93aso1_500.gif']
		url = random.choice(hug)
		urllib.request.urlretrieve(url, 'tmp.gif')
		if not user_mentions:
			await self.safe_send_message(channel,  "awhhh ;-; you look lonely " +  message.author.mention + ' here have a free hug from me :D ')
		else:
			for user in user_mentions.copy():
				if message.author.name == user.name:
					await self.safe_send_message(channel, message.author.mention + " has hu... oh, you tried hugging yourself, don't be sad ;-; *gives you a hug* ^o^")
				elif user.name == self.user.name:
					await self.safe_send_message(channel, "W-well I suppose hugs are alright " + message.author.mention + " but don't try and do anything else. *Accepts the hug and even hugs you back gently*")
				else:
					await self.safe_send_message(channel, message.author.mention + " *hugs* " +  user.mention)
		await self.send_file(channel, 'tmp.gif')
		await self.safe_delete_message(message)
		os.remove('tmp.gif')
		await self.update_now_playing()

	async def cmd_glomp(self, message, server, channel, permissions, user_mentions):
		"""
		Usage:
			{command_prefix}glomp <@a valid user>
		Get glomped by neko, glomp neko, or glomp somoene.
		"""
		hug = ['http://25.media.tumblr.com/tumblr_m8223lqZCl1ra8wu5o1_500.gif','http://www.thehomeplanet.org/wp-content/uploads/2013/04/Bobby-Sam-Hug.gif','http://24.media.tumblr.com/tumblr_lw7r7vRUGN1qii6tmo1_500.gif', 'https://33.media.tumblr.com/680b69563aceba3df48b4483d007bce3/tumblr_mxre7hEX4h1sc1kfto1_500.gif', 'http://media.giphy.com/media/lrr9rHuoJOE0w/giphy.gif', 'https://38.media.tumblr.com/b004f301143edad269aa1d88d0f1e245/tumblr_mx084htXKO1qbvovho1_500.gif', 'http://img4.wikia.nocookie.net/__cb20130302231719/adventuretimewithfinnandjake/images/1/15/Tumblr_m066xoISk41r6owqs.gif', 'http://cdn.smosh.com/sites/default/files/ftpuploads/bloguploads/0413/epic-hugs-friends-anime.gif', 'http://1.bp.blogspot.com/-OpJBN3VvNVw/T7lmAw0HxFI/AAAAAAAAAfo/bGJks9CqbK8/s1600/HUG_K-On!+-+Kawaii.AMO.gif', 'http://media.tumblr.com/tumblr_m1oqhy8vrH1qfwmvy.gif', 'https://myanimelist.cdn-dena.com/s/common/uploaded_files/1461073447-335af6bf0909c799149e1596b7170475.gif','http://24.media.tumblr.com/49a21e182fcdfb3e96cc9d9421f8ee3f/tumblr_mr2oxyLdFZ1s7ewj9o1_500.gif', 'http://pa1.narvii.com/5774/3cb894f1d4bcb4a9c58a06ee2a7fcd1a11f9b0eb_hq.gif','http://media.tumblr.com/01949fb828854480b513a87fa4e8eee7/tumblr_inline_n5r8vyJZa61qc7mf8.gif','https://media.tenor.co/images/e07a54a316ea6581329a7ccba23aea2f/tenor.gif', 'http://media.giphy.com/media/aD1fI3UUWC4/giphy.gif', 'https://38.media.tumblr.com/3b6ccf23ecd9aeacfcce0add1462c7c0/tumblr_msxqo58vDq1se3f24o1_500.gif', 'https://myanimelist.cdn-dena.com/s/common/uploaded_files/1460992224-9f1cd0ad22217aecf4507f9068e23ebb.gif', 'http://1.bp.blogspot.com/-J9Byahz1TuQ/UdI9CslAyAI/AAAAAAAAQWI/_tfIGYSUzdA/s500/inyu5.gif', 'http://25.media.tumblr.com/tumblr_m0lgriUiVK1rqfhi2o1_500.gif', 'http://media.tumblr.com/tumblr_lknzmbIG1x1qb5zie.gif', 'http://mrwgifs.com/wp-content/uploads/2013/04/Snuggling-Cuddling-Anime-Girls-Gif-.gif', 'https://38.media.tumblr.com/b004f301143edad269aa1d88d0f1e245/tumblr_mx084htXKO1qbvovho1_500.gif', 'http://media.giphy.com/media/od5H3PmEG5EVq/giphy.gif', 'http://25.media.tumblr.com/671f27962ca544ef8907ec0132c49ad1/tumblr_mp8srnNcTy1sx93aso1_500.gif']
		url = random.choice(hug)
		urllib.request.urlretrieve(url, 'tmp.gif')
		if not user_mentions:
			await self.safe_send_message(channel,  "*runs over and glomps* " +  message.author.mention)
		else:
			for user in user_mentions.copy():
				if message.author.name == user.name:
					await self.safe_send_message(channel, message.author.mention + " has glom... oh, you tried glomping yourself, don't be sad ;-; *gives you a hug* ^o^")
				elif user.name == self.user.name:
					await self.safe_send_message(channel, "*pat's your back shyly* h=hi there " + message.author.mention)
				else:
					await self.safe_send_message(channel, message.author.mention + " *glomps* " +  user.mention)
		await self.send_file(channel, 'tmp.gif')
		await self.safe_delete_message(message)
		os.remove('tmp.gif')
		await self.update_now_playing()

	async def cmd_kiss(self, message, server, channel, permissions, user_mentions):
		"""
		Usage:
			{command_prefix}kisss <@a valid user>
		Get a kiss on the cheek or kiss someone.
		"""
		kiss = ['http://media.giphy.com/media/FqBTvSNjNzeZG/giphy.gif', 'https://38.media.tumblr.com/d07fcdd5deb9d2cf1c8c44ffad04e274/tumblr_n2oqnslDSm1tv44eho1_500.gif', 'http://media.giphy.com/media/KmeIYo9IGBoGY/giphy.gif', 'http://25.media.tumblr.com/tumblr_mcf25oETLX1r0ydwlo1_500.gif', 'http://25.media.tumblr.com/tumblr_m88rxwNdCY1r6l8gpo1_500.gif', 'http://25.media.tumblr.com/ef9f2d6282f37026bff09f45757eda47/tumblr_mws4lpz9R41s3pk4mo1_500.gif#642927', 'http://media.giphy.com/media/kU586ictpGb0Q/giphy.gif', 'http://media.giphy.com/media/10i0tlqcYklEWY/giphy.gif', 'https://38.media.tumblr.com/bdea7d52f950d52e870c26d48a507481/tumblr_nq5xmrWkb21smg2oso1_500.gif', 'http://25.media.tumblr.com/f7bf9441a16b8837223a7f87ca16a0f1/tumblr_mga7rpNISY1rml571o1_500.gif', 'https://38.media.tumblr.com/6a0377e5cab1c8695f8f115b756187a8/tumblr_msbc5kC6uD1s9g6xgo1_500.gif', 'https://38.media.tumblr.com/54d820863ca93afd67460552bf0a01b8/tumblr_mmt5bk03k21so1hoto8_500.gif', 'http://25.media.tumblr.com/17e6890ca596eea98e00c86dfbadf0f6/tumblr_mz5gp8zQpO1sggrnxo1_500.gif', 'https://media.giphy.com/media/xTiTnKa9umn5skhyTK/giphy.gif', 'http://24.media.tumblr.com/b3d77735e349aefec4039e60eae51fd2/tumblr_mqc7j92TYp1rvkw6no1_500.gif', 'http://37.media.tumblr.com/6f8ff86f36a0c7fa6f6cf2b6c4b00663/tumblr_n4go91rApi1sfqkpto1_500.gif', 'http://geekparty.com/wp-content/uploads/2014/04/insta.gif', 'http://31.media.tumblr.com/tumblr_m3i48tDHTg1qefhtpo1_500.gif', 'http://i.imgur.com/xUF95bL.gif', 'http://31.media.tumblr.com/1e34fbdbfa86395d7adec1d3b675ba9b/tumblr_mxxdpuAoWU1slxwvro1_500.gif', 'http://s8.favim.com/orig/151119/akagami-no-shirayukihime-anime-boy-couple-Favim.com-3598058.gif']
		if not user_mentions:
			urllib.request.urlretrieve('https://33.media.tumblr.com/b867332ef4f014a1c6da99d5bd29bebb/tumblr_n35yy0Udsw1qbvovho1_500.gif', 'tmp.gif')
			await self.safe_send_message(channel,  "gives " +  message.author.mention + ' a kiss on the cheek')
		else:
			for user in user_mentions.copy():
				if message.author.name == user.name:
					urllib.request.urlretrieve('https://33.media.tumblr.com/b867332ef4f014a1c6da99d5bd29bebb/tumblr_n35yy0Udsw1qbvovho1_500.gif', 'tmp.gif')
					await self.safe_send_message(channel,  "Awhh ;-; you have no-one to kiss, don't be sad " +  message.author.mention + " *gives you a kiss on the cheek* don't worry you'll find someone ^o^")
					await self.send_file(channel, 'tmp.gif')
				elif user.name == self.user.name:
					urllib.request.urlretrieve('https://33.media.tumblr.com/b867332ef4f014a1c6da99d5bd29bebb/tumblr_n35yy0Udsw1qbvovho1_500.gif', 'tmp.gif')
					await self.safe_send_message(channel, message.author.mention + " Sorry I don't get in romantic relationships ;-; but you can have a cheek kiss ^o^")
					await self.send_file(channel, 'tmp.gif')
				else:
					url = random.choice(kiss)
					urllib.request.urlretrieve(url, 'tmp.gif')
					await self.safe_send_message(channel, message.author.mention + " *kisses* " +  user.mention)
					await self.send_file(channel, 'tmp.gif')
					await self.safe_delete_message(message)
					os.remove('tmp.gif')
					await self.update_now_playing()

	async def cmd_fkiss(self, message, server, channel, permissions, user_mentions):
		"""
		Usage:
			{command_prefix}fkisss <@a valid user>
		Get a kiss on the cheek or french kiss someone.
		"""
		fkiss = ['http://fanserviceftw.com/gallery/_images/38ae1c6bd36796a463e3b916a066e264/5092%20-%20animated_gif%20hasegawa_haruka%20kiss%20moyashimon%20oikawa_hazuki%20yuri.gif', 'http://i.myniceprofile.com/1503/150305.gif', 'http://images6.fanpop.com/image/photos/36100000/yuri-image-yuri-36185616-300-169.gif', 'http://media.giphy.com/media/514rRMooEn8ti/giphy.gif', 'http://stream1.gifsoup.com/view1/1537307/anime-kiss-12-o.gif', 'http://37.media.tumblr.com/53bf74a951fc87a0cc15686f5aadb769/tumblr_n14rfuvCe41sc1kfto1_500.gif', 'http://24.media.tumblr.com/d4f03ca449e3d51325e9ba0cc6a11b24/tumblr_mmjr3zHgmw1s6qc3bo1_500.gif', 'https://media.giphy.com/media/tiML8HAwHkWDm/giphy.gif', 'http://cdn.awwni.me/n0eo.gif']
		url = random.choice(fkiss)
		urllib.request.urlretrieve(url, 'tmp.gif')
		if not user_mentions:
			urllib.request.urlretrieve('https://33.media.tumblr.com/b867332ef4f014a1c6da99d5bd29bebb/tumblr_n35yy0Udsw1qbvovho1_500.gif', 'tmp.gif')
			await self.safe_send_message(channel,  "Gives " +  message.author.mention + ' a kiss on the cheek')
		else:
			for user in user_mentions.copy():
				if message.author.name == user.name:
					urllib.request.urlretrieve('https://33.media.tumblr.com/b867332ef4f014a1c6da99d5bd29bebb/tumblr_n35yy0Udsw1qbvovho1_500.gif', 'tmp.gif')
					await self.safe_send_message(channel, message.author.mention + " dee... OwO what's this? No-one to show your love to? I'm sorry that's a bummer >.< but don't worry I'm sure you'll fine someone ^o^ for now you can have a cheek kiss from me :D")
				elif user.name == self.user.name:
					urllib.request.urlretrieve('https://33.media.tumblr.com/b867332ef4f014a1c6da99d5bd29bebb/tumblr_n35yy0Udsw1qbvovho1_500.gif', 'tmp.gif')
					await self.safe_send_message(channel, message.author.mention + " Sorry I don't get in romantic relationships ;-; but you can have a cheek kiss ^o^")
				else:
					await self.safe_send_message(channel, message.author.mention + " *Deeply and passiontly kisses* " + user.mention + " *their eyes filled with lust as the two sets of lips collide together*")
		await self.send_file(channel, 'tmp.gif')
		await self.safe_delete_message(message)
		os.remove('tmp.gif')
		await self.update_now_playing()

	async def cmd_flirt(self, message, server, channel, permissions, user_mentions):
		"""
		Usage:
			{command_prefix}flirt <@a valid user>
		Get some hot :fire: pick-up lines and practice, or pick yourself up a hot anime grill for a  date.
		"""
		pickupline = ["Are you a tamale? ‘Cause you’re hot.",'You may fall from the sky, you may fall from a tree, but the best way to fall... is in love with me.', "Know what's on the menu? Me-n-u.", "Guess what I'm wearing? The smile you gave me.", "Do you believe in love at first sight, or should I walk by again?", "Can I borrow a kiss? I promise I'll give it back.", "If a fat man puts you in a bag at night, don't worry I told Santa I wanted you for Christmas.", "I'll be Burger King and you be McDonald's. I'll have it my way, and you'll be lovin' it.", "You're so beautiful you made me forget my pick up line.", "I'm no photographer, but I can picture us together.", "Are you a parking ticket? Because you've got FINE written all over you.", "Do I know you? Cause you look a lot like my next girlfriend.", "If I received a nickel for everytime I saw someone as beautiful as you, I'd have five cents.", "Did you have lucky charms for breakfast? Because you look magically delicious!", "You are so sweet you could put Hershey's out of business.", "It's a good thing I wore my gloves today; otherwise, you'd be too hot to handle.", "Did the sun come up or did you just smile at me?", "Was that an earthquake or did you just rock my world?", "You're so hot you must've started global warming.", "Damn girl, if you were a fruit, you'd be a FINEapple!", "Excuse me, if I go straight this way, will I be able to reach your heart?", "I must be a snowflake, because I've fallen for you.", "Was your Dad a baker? Because you've got a nice set of buns.", "We're like Little Ceasar's, we're Hot and Ready.", "Looks like you dropped something , My jaw!", "You are the reason Santa even has a naughty list.", "If I had a garden I'd put your two lips and my two lips together.", "Do you have a mirror in your pocket? 'Cause I could see myself in your pants.", "Somebody call the cops, because it's got to be illegal to look that good!", "I'm not drunk, I'm just intoxicated by you.", "If you were a laser you would be set on stunning.", "Could you please step away from the bar? You're melting all the ice!", "You must be a Snickers, because you satisfy me.", "Can you take me to the bakery? Because, I want a Cutiepie like you!", "If you were a library book, I would check you out.", "Apart from being sexy, what do you do for a living?", "I'm going to need a tall glass of cold water, cuz baby your making me HOT!", "What's your favorite silverware? Because I like to spoon!", "Baby, if you were words on a page, you’d be what they call fine print.", "Can I get your picture to prove to all my friends that angels really do exist?", "Don’t walk into that building — the sprinklers might go off!", "Hey, I lost my phone number … Can I have yours?", "Well, here I am. What are your other two wishes?", "Do you have a quarter? My mom told me to call her when I found the woman of my dreams.", "Do you have a band aid? I hurt my knee when I fell for you.", "The word of the day is legs. Let’s go back to my place and spread the word.", "You are so sweet you are giving me a toothache.", "Life without you would be like a broken pencil…pointless.", "My magic watch says that you don’t have on any underwear. Oh..oh.. you, you do? \nDamn! it must be 15 minutes fast", "You turn my software into hardware!", "You must be in a wrong place – the Miss Universe contest is over there."]
		if not user_mentions:
			await self.safe_send_message(channel, message.author.mention + '\n%s' % random.choice(pickupline))
			await self.safe_delete_message(message)
		else:
			for user in user_mentions.copy():
				if message.author.name == user.name:
					await self.safe_send_message(channel, message.author.mention + " *stands looking into a mirror rehearsing their pick-up-lines*" + "\n%s" % random.choice(pickupline))
					await self.safe_delete_message(message)
				elif user.name == self.user.name:
					await self.safe_send_message(channel, message.author.mention + "you know flirting with me won't do you any good right? I'm just some code -3- thanks for the thought though ^o^")
					await self.safe_delete_message(message)
				else:
					await self.safe_send_message(channel, message.author.mention + " to " +  user.mention + ' hey \n%s' % random.choice(pickupline))
					await self.safe_delete_message(message)		
		await self.update_now_playing()	

	async def cmd_ckiss(self, message, server, channel, permissions, user_mentions):
		"""
		Usage:
			{command_prefix}ckisss <@a valid user
		Get a kiss on the cheek or kiss someone on the cheek.
		"""
		ckiss = ['https://33.media.tumblr.com/b867332ef4f014a1c6da99d5bd29bebb/tumblr_n35yy0Udsw1qbvovho1_500.gif', 'http://i.imgur.com/QgfTZrS.gif', 'http://i.imgur.com/Z6V6mUE.mp4', 'http://orig00.deviantart.net/06a9/f/2015/054/a/a/cheekkainora_by_nikadonna-d8j8grg.gif', 'http://68.media.tumblr.com/2ced143e6bba445d359f982d0c3d659f/tumblr_n1ipntQonM1qbvovho8_500.gif', 'http://cdn.awwni.me/n3pg.gif', 'http://25.media.tumblr.com/3b8a73c70947679a6af56178762bdc1f/tumblr_mk8xzkenY71qzd219o1_500.gif', 'http://rs1099.pbsrc.com/albums/g399/Tantei-san/Conan-Kissonthecheek.gif~c200', 'https://i.giphy.com/media/12MEJ2ArZc23cY/source.gif', 'http://images6.fanpop.com/image/photos/32800000/Willis-kissing-Kari-and-Yolei-on-the-cheek-anime-32853445-500-250.gif', 'https://33.media.tumblr.com/90e09a6725fa20e59a69f2f7b2c4ad45/tumblr_n7wf3hH6rm1tv1jtto1_500.gif', 'http://data.whicdn.com/images/59643377/large.gif', 'https://38.media.tumblr.com/601f2d61d90e635968629bbb45a395e6/tumblr_nhd3g61Q6R1szhmk0o8_500.gif']
		url = random.choice(ckiss)
		urllib.request.urlretrieve(url, 'tmp.gif')
		if not user_mentions.copy():
			await self.safe_send_message(channel, "Awhh {} you don't have anyone to kiss on the cheek :( Don't worry! You can have one from me! :hugging:".format(message.author.mention))
		else:
			for user in user_mentions.copy():
				if message.author.name == user.name:
					await self.safe_send_message(channel,  "Awhh ;-; you have no-one to kiss on the cheek, don't be sad " +  message.author.mention + " *gives you a kiss on the cheek* don't worry you'll find someone ^o^")
				elif user.name == self.user.name:
					await self.safe_send_message(channel, message.author.mention + " vhsdbajkl *get's flustered* awhh thank chu <3")
				else:
					await self.safe_send_message(channel, "{0} *kisses {1} on the cheek.* *whispers* how cooot".format(message.author.mention, user.mention))
		await self.send_file(channel, 'tmp.gif')
		await self.safe_delete_message(message)
		os.remove('tmp.gif')
		await self.update_now_playing()
				
	async def cmd_pat(self, message, server, channel, permissions, user_mentions):
		"""
		Usage:
			{command_prefix}pat <@a valid user>
		Pat someone or get patted.
		"""
		pat = ['http://media.giphy.com/media/L2z7dnOduqEow/giphy.gif', 'http://33.media.tumblr.com/229ec0458891c4dcd847545c81e760a5/tumblr_mpfy232F4j1rxrpjzo1_r2_500.gif', 'https://media.giphy.com/media/12hvLuZ7uzvCvK/giphy.gif', 'http://i.imgur.com/eOJlnwP.gif', 'https://lh3.googleusercontent.com/-AGUIg-yZ5jE/VVUHX6vs6YI/AAAAAAAAIgA/d_kjvEtULJ0/w800-h450/Rikka.gif', 'http://pa1.narvii.com/5983/85777dd28aa87072ee5a9ed759ab0170b3c60992_hq.gif', 'https://media.giphy.com/media/xLm9fux5DSodq/giphy.gif', 'http://media.giphy.com/media/ye7OTQgwmVuVy/giphy.gif', 'http://37.media.tumblr.com/6c991608070a6056eb4390f9151d9c5e/tumblr_mprpthaR7f1rcag9ho1_500.gif', 'http://i.imgur.com/L8voKd1.gif', 'http://25.media.tumblr.com/tumblr_mckmheJJAZ1rqw7udo1_500.gif', 'http://33.media.tumblr.com/229ec0458891c4dcd847545c81e760a5/tumblr_mpfy232F4j1rxrpjzo1_r2_500.gif', 'http://24.media.tumblr.com/e6713de4cab8a28711835b6a339928b4/tumblr_mp0yr2VHQQ1rvdjx0o4_500.gif', 'https://33.media.tumblr.com/b8c4a62dc57062d7f9b16855a895ebe3/tumblr_mtg5mlcu0U1qbvovho1_500.gif', 'http://media.giphy.com/media/e7xQm1dtF9Zni/giphy.gif', 'http://25.media.tumblr.com/7026f9eba63fc60f8dbd7ba930dde430/tumblr_my4fqch4hS1qbvovho2_500.gif', 'http://i2.kym-cdn.com/photos/images/newsfeed/000/915/038/7e9.gif', 'http://25.media.tumblr.com/tumblr_m79ze5OKxk1rqon8do1_400.gif', 'https://media.giphy.com/media/igCbP09671uM0/giphy.gif', 'https://49.media.tumblr.com/fac1d9d768b722cec863b4172d10a765/tumblr_nbgidbQh9k1qbvovho1_500.gif', 'https://media.giphy.com/media/uw3fTCTNMbXAk/giphy.gif']
		url = random.choice(pat)
		urllib.request.urlretrieve(url, 'tmp.gif')
		if not user_mentions:
			await self.safe_send_message(channel,  "you look sad ;-; " +  message.author.mention + " *pats you gently on the head* don't worry I'm here for you.")
		else:
			for user in user_mentions.copy():
				if message.author.name == user.name:
					await self.safe_send_message(channel, message.author.mention + " awhh :crying_cat_face: you don't have a kitty to pat, ish oki you can pat me :sweat_smile:")
				elif user.name == self.user.name:
					await self.safe_send_message(channel, "Patting me is always a good idea *purrs loudly and nuzzles your hand happily* heh~")
				else:
					await self.safe_send_message(channel, message.author.mention + " *pats* " +  user.mention + '!')
		await self.send_file(channel, 'tmp.gif')
		await self.safe_delete_message(message)
		os.remove('tmp.gif')
		await self.update_now_playing()

	async def cmd_pet(self, message, server, channel, permissions, user_mentions):
		"""Usage
			{command_prefix}pet <@a valid user>
		Pet someone or get petted.
		"""
		pat = ['http://media.giphy.com/media/L2z7dnOduqEow/giphy.gif', 'http://33.media.tumblr.com/229ec0458891c4dcd847545c81e760a5/tumblr_mpfy232F4j1rxrpjzo1_r2_500.gif', 'https://media.giphy.com/media/12hvLuZ7uzvCvK/giphy.gif', 'http://i.imgur.com/eOJlnwP.gif', 'https://lh3.googleusercontent.com/-AGUIg-yZ5jE/VVUHX6vs6YI/AAAAAAAAIgA/d_kjvEtULJ0/w800-h450/Rikka.gif', 'http://pa1.narvii.com/5983/85777dd28aa87072ee5a9ed759ab0170b3c60992_hq.gif', 'https://media.giphy.com/media/xLm9fux5DSodq/giphy.gif', 'http://media.giphy.com/media/ye7OTQgwmVuVy/giphy.gif', 'http://37.media.tumblr.com/6c991608070a6056eb4390f9151d9c5e/tumblr_mprpthaR7f1rcag9ho1_500.gif', 'http://i.imgur.com/L8voKd1.gif', 'http://25.media.tumblr.com/tumblr_mckmheJJAZ1rqw7udo1_500.gif', 'http://33.media.tumblr.com/229ec0458891c4dcd847545c81e760a5/tumblr_mpfy232F4j1rxrpjzo1_r2_500.gif', 'http://24.media.tumblr.com/e6713de4cab8a28711835b6a339928b4/tumblr_mp0yr2VHQQ1rvdjx0o4_500.gif', 'https://33.media.tumblr.com/b8c4a62dc57062d7f9b16855a895ebe3/tumblr_mtg5mlcu0U1qbvovho1_500.gif', 'http://media.giphy.com/media/e7xQm1dtF9Zni/giphy.gif', 'http://25.media.tumblr.com/7026f9eba63fc60f8dbd7ba930dde430/tumblr_my4fqch4hS1qbvovho2_500.gif', 'http://i2.kym-cdn.com/photos/images/newsfeed/000/915/038/7e9.gif', 'http://25.media.tumblr.com/tumblr_m79ze5OKxk1rqon8do1_400.gif', 'https://media.giphy.com/media/igCbP09671uM0/giphy.gif', 'https://49.media.tumblr.com/fac1d9d768b722cec863b4172d10a765/tumblr_nbgidbQh9k1qbvovho1_500.gif', 'https://media.giphy.com/media/uw3fTCTNMbXAk/giphy.gif']
		url = random.choice(pat)
		urllib.request.urlretrieve(url, 'tmp.gif')
		if not user_mentions:
			await self.safe_send_message(channel,  "you look sad ;-; " +  message.author.mention + " *pets you gently* don't worry I'm here for you.")
		else:
			for user in user_mentions.copy():
				if message.author.name == user.name:
					await self.safe_send_message(channel, message.author.mention + " awhh :crying_cat_face: you don't have a kitty to pet, ish oki you can pet me :sweat_smile")
				elif user.name == self.user.name:
					await self.safe_send_message(channel, "Petting me is always a good idea *purrs loudly and nuzzles your hand happily* heh~")
				else:
					await self.safe_send_message(channel, message.author.mention + " *pets* " +  user.mention + '!')
		await self.send_file(channel, 'tmp.gif')
		await self.safe_delete_message(message)
		os.remove('tmp.gif')
		await self.update_now_playing()			
				
	async def cmd_poke(self, message, server, channel, permissions, user_mentions):
		"""
		Usage:
			{command_prefix} <@a valid user>
		Poke neko or be poked by neko, or poke your senpai for their attention.
		"""
		owner = self._get_owner(voice=True or False or None) or self._get_owner()
		poke = ['http://31.media.tumblr.com/tumblr_lkn1twb83X1qbq4v6o1_500.gif',  'http://31.media.tumblr.com/tumblr_lkn1twb83X1qbq4v6o1_500.gif', 'https://media.giphy.com/media/psbjVYmRVfYJO/source.gif', 'http://orig01.deviantart.net/8acf/f/2011/328/a/d/fsn_saber_poke_attack_by_foreverirritated-d4h5hca.gif', 'http://38.media.tumblr.com/0809478d6759a0a4b431755026f677a0/tumblr_ntpfvoxeoz1u03j02o1_500.gif', 'http://media.tumblr.com/tumblr_mbcbgwzVfX1rwuydr.gif', 'http://i.imgur.com/rxsyBWA.jpg', 'http://s.myniceprofile.com/myspacepic/797/79743.gif', 'http://orig08.deviantart.net/03fe/f/2013/037/f/d/cry__poke_by_kiwa007-d5u29cm.gif', 'http://media.giphy.com/media/aZSMD7CpgU4Za/giphy.gif', 'https://media.giphy.com/media/y8p6B6bgKHlL2/giphy.gif', 'http://25.media.tumblr.com/a5ca5fcd9295bdbef4d78ddd0ecd42a1/tumblr_msk55wmNLi1ssbvp5o1_500.gif', 'http://i.amz.mshcdn.com/H2EYB0TAi-gRkULJQ6sX4qCQHrU=/fit-in/850x850/2014%2F02%2F21%2Fe5%2Fnemo.fb061.gif', 'http://orig00.deviantart.net/e55e/f/2012/323/b/5/itachi_and_sasuke_poke_by_endless_summer181-d5lhhet.gif', 'http://stream1.gifsoup.com/view1/2370407/undertaker-poke-o.gif', 'http://i.imgur.com/Ksw63.gif', 'http://orig04.deviantart.net/6a27/f/2011/197/b/a/cute___poke___nyan_by_ifmalover-d3weqc0.gif', 'http://www.gifwave.com/media/571143_anime-shut-up-clannad-poke-anime-funny.gif']
		pat = ['http://media.giphy.com/media/L2z7dnOduqEow/giphy.gif', 'http://33.media.tumblr.com/229ec0458891c4dcd847545c81e760a5/tumblr_mpfy232F4j1rxrpjzo1_r2_500.gif', 'https://media.giphy.com/media/12hvLuZ7uzvCvK/giphy.gif', 'http://i.imgur.com/eOJlnwP.gif', 'https://lh3.googleusercontent.com/-AGUIg-yZ5jE/VVUHX6vs6YI/AAAAAAAAIgA/d_kjvEtULJ0/w800-h450/Rikka.gif', 'http://pa1.narvii.com/5983/85777dd28aa87072ee5a9ed759ab0170b3c60992_hq.gif', 'https://media.giphy.com/media/xLm9fux5DSodq/giphy.gif', 'http://media.giphy.com/media/ye7OTQgwmVuVy/giphy.gif', 'http://37.media.tumblr.com/6c991608070a6056eb4390f9151d9c5e/tumblr_mprpthaR7f1rcag9ho1_500.gif', 'http://i.imgur.com/L8voKd1.gif', 'http://25.media.tumblr.com/tumblr_mckmheJJAZ1rqw7udo1_500.gif', 'http://33.media.tumblr.com/229ec0458891c4dcd847545c81e760a5/tumblr_mpfy232F4j1rxrpjzo1_r2_500.gif', 'http://24.media.tumblr.com/e6713de4cab8a28711835b6a339928b4/tumblr_mp0yr2VHQQ1rvdjx0o4_500.gif', 'https://33.media.tumblr.com/b8c4a62dc57062d7f9b16855a895ebe3/tumblr_mtg5mlcu0U1qbvovho1_500.gif', 'http://media.giphy.com/media/e7xQm1dtF9Zni/giphy.gif', 'http://25.media.tumblr.com/7026f9eba63fc60f8dbd7ba930dde430/tumblr_my4fqch4hS1qbvovho2_500.gif', 'http://i2.kym-cdn.com/photos/images/newsfeed/000/915/038/7e9.gif', 'http://25.media.tumblr.com/tumblr_m79ze5OKxk1rqon8do1_400.gif', 'https://media.giphy.com/media/igCbP09671uM0/giphy.gif', 'https://49.media.tumblr.com/fac1d9d768b722cec863b4172d10a765/tumblr_nbgidbQh9k1qbvovho1_500.gif', 'https://media.giphy.com/media/uw3fTCTNMbXAk/giphy.gif']
		slap = ['http://orig11.deviantart.net/2d34/f/2013/339/1/2/golden_time_flower_slap_gif_by_paranoxias-d6wv007.gif', 'http://media.giphy.com/media/jLeyZWgtwgr2U/giphy.gif', 'http://rs1031.pbsrc.com/albums/y377/shinnidan/Toradora_-_Taiga_Slap.gif~c200', 'http://media.giphy.com/media/tMIWyF5GUrWwM/giphy.gif', 'http://www.animateit.net/data/media/243/aCC_AnimeAni2.gif', 'http://media.giphy.com/media/Zau0yrl17uzdK/giphy.gif', 'https://media.giphy.com/media/10Am8idu3qBYRy/giphy.gif', 'http://img-cache.cdn.gaiaonline.com/24f5017f9e5cb5a7c3a169a72d67c733/http://i797.photobucket.com/albums/yy257/MakeaLoves/Ryuuji%20n%20Taiga/Toradora_-_Taiga_Slap.gif', 'http://static1.wikia.nocookie.net/__cb20130131011839/adventuretimewithfinnandjake/images/c/cd/Slap.gif.gif', 'https://31.media.tumblr.com/dd5d751f86002fd4a544dcef7a9763d6/tumblr_inline_mya9hsvLZA1rbb2hd.gif', 'http://3.bp.blogspot.com/-CHYXl4bcgA0/UYGNzdDooBI/AAAAAAAADSY/MgmWVYn5ZR0/s400/2828+-+animated_gif+slap+umineko_no_naku_koro_ni+ushiromiya_maria+ushiromiya_rosa.gif', 'http://i.imgur.com/UXqzzab.gif', 'http://images6.fanpop.com/image/photos/32700000/Witch-slap-umineko-no-naku-koro-ni-32769187-500-283.gif', 'http://images2.fanpop.com/image/photos/9300000/Slap-Happy-futurama-9351667-352-240.gif', 'http://media.giphy.com/media/EpFsHUKK2MYvK/giphy.gif', 'http://ekladata.com/-vT5aTkK9ENUgyhqvNQfo7-Hids.gif', 'http://img.mrdrsr.net/slap.gif', 'http://fanaru.com/pandora-hearts/image/84052-pandora-hearts-pillow-slap.gif', 'https://media.giphy.com/media/XriT1FPiR1RRe/giphy.gif', 'http://i0.wp.com/haruhichan.com/wpblog/wp-content/uploads/Ryuuji-Takasu-x-Taiga-Aisaka-Toradora-anime-series-slap-haruhichan.com_.gif', 'https://media.giphy.com/media/1iw7RG8JbOmpq/giphy.gif', 'http://safebooru.org/images/363/5b1a06da49bd1eeccbf1f60428370c9b491b5156.gif?363332', 'https://artemisunfiltered.files.wordpress.com/2014/05/golden-time-nana-slap.gif', 'https://reallifeanime.files.wordpress.com/2014/06/akari-slap.gif', 'https://media.giphy.com/media/fNdolDfnVPKNi/giphy.gif', 'http://media.tumblr.com/tumblr_lx84j9KIBZ1qg12e8.gif','http://img.wonkette.com/wp-content/uploads/2013/07/107815-animated-animation-artist3asubjectnumber2394-fight-gif-sissy_slap_fight-trixie-twilight_sparkle.gif']
		if not user_mentions:
			urllib.request.urlretrieve(random.choice(poke), 'tmp.gif')
			await self.safe_send_message(channel,  "I'm bored *pokes* " +  message.author.mention + " unbore me")
		else:
			for user in user_mentions.copy():
				if message.author.name == user.name:
					urllib.request.urlretrieve(random.choice(pat), 'tmp.gif')
					await self.safe_send_message(channel, "So bored you're poking yourself huh? " + message.author.mention + " there there *pat pat*")
				elif user.name == self.user.name:
					urllib.request.urlretrieve(random.choice(slap), 'tmp.gif')
					await self.safe_send_message(channel, "*Slaps* " + message.author.mention + " dun poke me ;-;")
				elif user.name == owner.name and not message.author.id == '336948766986862597':
					await self.safe_send_message(channel, "Master doesn't wanna be poked >.>")
				else:
					urllib.request.urlretrieve(random.choice(poke), 'tmp.gif')
					await self.safe_send_message(channel, message.author.mention + " *pokes* " +  user.mention)
		await self.send_file(channel, 'tmp.gif')
		await self.safe_delete_message(message)
		os.remove('tmp.gif')
		await self.update_now_playing()

	async def cmd_kill(self, message, server, channel, permissons, user_mentions):
		"""
		Usage:
			{command_prefix} <@a valid user>
		Kill your enemies.
		"""
		owner = self._get_owner(voice=True or False or None) or self._get_owner()
		hug = ['http://25.media.tumblr.com/tumblr_m8223lqZCl1ra8wu5o1_500.gif','http://www.thehomeplanet.org/wp-content/uploads/2013/04/Bobby-Sam-Hug.gif','http://24.media.tumblr.com/tumblr_lw7r7vRUGN1qii6tmo1_500.gif', 'https://33.media.tumblr.com/680b69563aceba3df48b4483d007bce3/tumblr_mxre7hEX4h1sc1kfto1_500.gif', 'http://media.giphy.com/media/lrr9rHuoJOE0w/giphy.gif', 'https://38.media.tumblr.com/b004f301143edad269aa1d88d0f1e245/tumblr_mx084htXKO1qbvovho1_500.gif', 'http://img4.wikia.nocookie.net/__cb20130302231719/adventuretimewithfinnandjake/images/1/15/Tumblr_m066xoISk41r6owqs.gif', 'http://cdn.smosh.com/sites/default/files/ftpuploads/bloguploads/0413/epic-hugs-friends-anime.gif', 'http://1.bp.blogspot.com/-OpJBN3VvNVw/T7lmAw0HxFI/AAAAAAAAAfo/bGJks9CqbK8/s1600/HUG_K-On!+-+Kawaii.AMO.gif', 'http://media.tumblr.com/tumblr_m1oqhy8vrH1qfwmvy.gif', 'https://myanimelist.cdn-dena.com/s/common/uploaded_files/1461073447-335af6bf0909c799149e1596b7170475.gif','http://24.media.tumblr.com/49a21e182fcdfb3e96cc9d9421f8ee3f/tumblr_mr2oxyLdFZ1s7ewj9o1_500.gif', 'http://pa1.narvii.com/5774/3cb894f1d4bcb4a9c58a06ee2a7fcd1a11f9b0eb_hq.gif','http://media.tumblr.com/01949fb828854480b513a87fa4e8eee7/tumblr_inline_n5r8vyJZa61qc7mf8.gif','https://media.tenor.co/images/e07a54a316ea6581329a7ccba23aea2f/tenor.gif', 'http://media.giphy.com/media/aD1fI3UUWC4/giphy.gif', 'https://38.media.tumblr.com/3b6ccf23ecd9aeacfcce0add1462c7c0/tumblr_msxqo58vDq1se3f24o1_500.gif', 'https://myanimelist.cdn-dena.com/s/common/uploaded_files/1460992224-9f1cd0ad22217aecf4507f9068e23ebb.gif', 'http://1.bp.blogspot.com/-J9Byahz1TuQ/UdI9CslAyAI/AAAAAAAAQWI/_tfIGYSUzdA/s500/inyu5.gif', 'http://25.media.tumblr.com/tumblr_m0lgriUiVK1rqfhi2o1_500.gif', 'http://media.tumblr.com/tumblr_lknzmbIG1x1qb5zie.gif', 'http://mrwgifs.com/wp-content/uploads/2013/04/Snuggling-Cuddling-Anime-Girls-Gif-.gif', 'https://38.media.tumblr.com/b004f301143edad269aa1d88d0f1e245/tumblr_mx084htXKO1qbvovho1_500.gif', 'http://media.giphy.com/media/od5H3PmEG5EVq/giphy.gif', 'http://25.media.tumblr.com/671f27962ca544ef8907ec0132c49ad1/tumblr_mp8srnNcTy1sx93aso1_500.gif']
		kill_method = ['Snipe head shot!', 'Hammer to the head!', 'Stealth attack!', 'Lazers @_@', 'Rock hit!', "Stranglization!", 'Suffocation!']
		url = random.choice(hug)
		urllib.request.urlretrieve(url, 'tmp.gif')
		if not user_mentions:
			await self.safe_send_message(channel, message.author.mention + " who do you wish to kill?")
			await self.safe_delete_message(message)
		for user in user_mentions.copy():
			if message.author.name == user.name:
				await self.safe_send_message(channel, message.author.mention + " I'm sorry but I don't support suicide, it's a touchy subject but you can have a free hug!")
				await self.send_file(channel, 'tmp.gif')
			elif user.name == self.user.name:
				await self.safe_send_message(channel, message.author.mention + " Denied you can't kill me! Only my real master {} can do that!~".format(owner.name))
			elif user.name == owner.name:
				await self.safe_send_message(channel, ":heavy_multiplication_x:  | No killing my master >.>!")
			else:
				await self.safe_send_message(channel, message.author.mention + " has killed " + user.mention + " via: %s" % random.choice(kill_method))
		await self.safe_delete_message(message)
		os.remove('tmp.gif')
		await self.update_now_playing()


	async def cmd_sex(self, message, server, channel, permissions, user_mentions):
		"""
		Usage: 
			{command_prefix} <@a valid user>
		Have sex.
		"""
		lewd =  ['http://i3.kym-cdn.com/photos/images/newsfeed/000/936/092/af7.jpg', 'http://i.imgur.com/tkEOnku.jpg', 'http://i3.kym-cdn.com/photos/images/original/000/905/295/193.png', 'http://i.imgur.com/Kscx9g5.png', 'http://i3.kym-cdn.com/photos/images/original/000/897/703/b97.png', 'http://gallery.fanserviceftw.com/_images/a32b7d53651dcc3b76fcdc85a989c81b/9599%20-%20doushio%20makise_kurisu%20steins%3Bgate%20tagme.png', 'https://img.ifcdn.com/images/89ca6bd97bca8fabb4f3cb24f56e79b9ad020904e194f8cf99ff046d8da368a1_1.jpg', 'http://i2.kym-cdn.com/photos/images/newsfeed/000/888/789/f39.jpg', 'http://i1.kym-cdn.com/photos/images/original/000/988/917/ff8.jpg', 'http://i0.kym-cdn.com/photos/images/masonry/000/905/286/7ec.jpg','http://i1.kym-cdn.com/photos/images/facebook/000/794/434/6e7.gif']
		if not user_mentions:
			await self.safe_send_message(channel, message.author.mention + " You can't have sex with yourself b-baka")
		else:
			for user in user_mentions.copy():
				if message.author.name == user.name:
					await self.safe_send_message(channel, message.author.mention + " you can't have sex with yourself b-baka >.<")
				elif user.name == self.user.name:
					await self.safe_send_message(channel, message.author.mention + " s-sorry but I can't have sex with you >.<")
				else:
					urllib.request.urlretrieve(random.choice(lewd), 'tmp.gif')
					await self.safe_send_message(channel, message.author.mention + " goes to the dms and does lewd things with " + user.mention)
					await self.send_file(channel, 'tmp.gif')
					os.remove('tmp.gif')
		await self.safe_delete_message(message)
		await self.update_now_playing()

	async def cmd_succ(self, message, server, channel, permissions, user_mentions):
		"""
		Usage:
			{command_prefix}succ <@a valid user>
		Get succ or give succ, everyone loves a good succ.
		"""
		if not user_mentions:
			await self.safe_send_message(channel, "You want some good succ succ" + message.author.mention)
			await self.safe_delete_message(message)
		else:
			for user in user_mentions.copy():
				if message.author.name == user.name:
					await self.safe_send_message(channel, "You've started fapping m8 gg " + message.author.mention + '~')
					await self.safe_delete_message(message)
				elif user.name == self.user.name:
					await self.safe_send_message(channel, message.author.mention + " I dun think succing me is a good idea, might damage my circuits.")
					await self.safe_delete_message(message)
				else:
					await self.safe_send_message(channel, message.author.mention + " has given " + user.mention + " some good succ succ. Enjoy the succ " + user.name)
					await self.safe_delete_message(message)
		await self.update_now_playing()

	async def cmd_steal(self, message, server, channel, permissions, user_mentions):
		"""
		Usage:
			{command_prefix}steal [@a valid user]
		Steal your waifu or husbando
		"""
		owner = self._get_owner(voice=True or False or None) or self._get_owner()
		if not user_mentions:
			await self.safe_send_message(channel, "Who are you trying to steal " + message.author.mention + "?")
			await self.safe_delete_message(message)
		else:
			for user in user_mentions.copy():
				if message.author.name == user.name:
					await self.safe_send_message(channel, "I dun think you can steal yourself " + message.author.mention +"~")
					await self.safe_delete_message(message)
				elif user.name == self.user.name:
					await self.safe_send_message(channel, message.author.mention + " access denied >.< you can't steal me from my master {}".format(owner.name))
					await self.safe_delete_message(message)
				elif message.author.id == "335677038830682112":
					await self.safe_send_message(channel, message.author.mention + " has stolen " + user.mention + " :scream_cat:")
				elif user.name == owner.name and not message.author.id == '336948766986862597':
					await self.safe_send_message(channel, ":heavy_multiplication_x:  | Nuh-uh! No stealing my master!")
				else:
					await self.safe_send_message(channel, message.author.mention + " has stolen " + user.mention + " :scream_cat:")
					await self.safe_delete_message(message)
		await self.update_now_playing()

	async def cmd_cuddle(self, message, server, channel, permissions, user_mentions):
		"""
		Usage:
			{command_prefix}cuddle <@a valid user>
		Get cuddled or snuggle someone.
		"""
		owner = self._get_owner(voice=True or False or None) or self._get_owner() 
		cuddle = ['http://media.giphy.com/media/QlFyrikSI01Fe/giphy.gif', 'http://media.tumblr.com/01949fb828854480b513a87fa4e8eee7/tumblr_inline_n5r8vyJZa61qc7mf8.gif', 'http://media.giphy.com/media/Ki88u2LhvDhyE/giphy.gif', 'http://www.ohmagif.com/wp-content/uploads/2012/07/cute-puppy-cuddling-with-cat.gif', 'http://awesomegifs.com/wp-content/uploads/cat-and-dog-cuddling.gif', 'http://big.assets.huffingtonpost.com/cuddlecat.gif', 'http://25.media.tumblr.com/d9f3e83abe3e01d1174dae0a771750cd/tumblr_mi4ll7Rqqe1rqszceo1_400.gif', 'https://lh3.googleusercontent.com/-H8YQfmNXcus/UNH4jtH3gkI/AAAAAAAAGpA/FHslZSXRs6I/s233/141.gif', 'https://media.giphy.com/media/ipTpDF6TOdgc/giphy.gif', 'https://media.giphy.com/media/ztXa20eZi18oo/giphy.gif', 'http://www.rinchupeco.com/wp-content/uploads/2013/06/cuddle.gif', 'http://s2.favim.com/orig/36/ash-bed-hug-pikachu-pokemon-Favim.com-295600.gif']
		urllib.request.urlretrieve(random.choice(cuddle), 'tmp.gif')
		if not user_mentions:
			await self.safe_send_message(channel, message.author.mention + 'you look lonely ;-; have a free cuddle! ')
		else:
			for user in user_mentions.copy():
				if message.author.name == user.name:
					await self.safe_send_message(channel, message.author.mention + " awwhh ;-; you must be lonely :crying_cat_face: I'm sorry, don't worry though I'll cuddle you!")
				elif user.name == self.user.name:
					await self.safe_send_message(channel, message.author.mention + " yay! cuddles *purrrs happily and nuzzles you while cuddling,* I love cuddles heh :smiley_cat:")
				elif user.name == owner.name and not message.author.id == '336948766986862597':
					await self.safe_send_message(channel, "{}, *watches as you cuddle my senpai* better not do anything other than cuddle!".format(message.author.name))
				else:
					await self.safe_send_message(channel, message.author.mention + " *cuddles with* " +  user.mention)
		await self.send_file(channel, 'tmp.gif')
		await self.safe_delete_message(message)
		os.remove('tmp.gif')
		await self.update_now_playing()

	async def cmd_snuggle(self, message, server, channel, permissions, user_mentions):
		"""
		Usage:
			{command_prefix}snuggle <@a valid user>
		Get snuggled or snuggle someone.
		"""
		owner = self._get_owner(voice=True or False or None) or self._get_owner() 
		snuggle = ['http://media.giphy.com/media/QlFyrikSI01Fe/giphy.gif', 'http://media.tumblr.com/01949fb828854480b513a87fa4e8eee7/tumblr_inline_n5r8vyJZa61qc7mf8.gif', 'http://media.giphy.com/media/Ki88u2LhvDhyE/giphy.gif', 'http://www.ohmagif.com/wp-content/uploads/2012/07/cute-puppy-cuddling-with-cat.gif', 'http://awesomegifs.com/wp-content/uploads/cat-and-dog-cuddling.gif', 'http://big.assets.huffingtonpost.com/cuddlecat.gif', 'http://25.media.tumblr.com/d9f3e83abe3e01d1174dae0a771750cd/tumblr_mi4ll7Rqqe1rqszceo1_400.gif', 'https://lh3.googleusercontent.com/-H8YQfmNXcus/UNH4jtH3gkI/AAAAAAAAGpA/FHslZSXRs6I/s233/141.gif', 'https://media.giphy.com/media/ipTpDF6TOdgc/giphy.gif', 'https://media.giphy.com/media/ztXa20eZi18oo/giphy.gif', 'http://www.rinchupeco.com/wp-content/uploads/2013/06/cuddle.gif', 'http://s2.favim.com/orig/36/ash-bed-hug-pikachu-pokemon-Favim.com-295600.gif']
		urllib.request.urlretrieve(random.choice(snuggle), 'tmp.gif')
		if not user_mentions:
			await self.safe_send_message(channel, message.author.mention + "awwwh you have no-one to snuggle ;-; I\'ll snuggle you!")
		else:
			for user in user_mentions.copy():
				if message.author.name == user.name:
					await self.safe_send_message(channel, message.author.mention + " awwhh ;-; you must be lonely :crying_cat_face: don't worry I got you *snuggles you*")
				elif user.name == self.user.name:
					await self.safe_send_message(channel, message.author.mention + " yay! cuddles *purrrs happily and nuzzles you while cuddling,* I love snuggles heh :smiley_cat:")
				elif user.name == owner.name and not message.author.id == '336948766986862597':
					await self.safe_send_message(channel, "{}, *watches as you snuggle my senpai* better not do anything other than cuddle!".format(message.author.name))
				else:
					await self.safe_send_message(channel, message.author.mention + " *snuggles with* " +  user.mention)
		await self.send_file(channel, 'tmp.gif')
		await self.safe_delete_message(message)
		os.remove('tmp.gif')
		await self.update_now_playing()



	async def cmd_server(self, message, channel, permissions):
		"""
		Usage:
			{command_prefix}server
		Gives you some useful information about the server you used the command from.
		"""
		server = message.author.server
		members = 0
		bots = 0

		for member in server.members:
			if not member.bot:
				members = members + 1
			else:
				bots = bots + 1

		name = server.name
		roles = len(server.roles)
		emojis = len(server.emojis)
		region = server.region
		afk_timeout = server.afk_timeout/60
		afk_channel = server.afk_channel
		channels = len(server.channels)
		owner = server.owner
		icon = server.icon_url
		serverid = server.id
		is_large = server.large
		default_channel = server.default_channel
		creation_date = server.created_at

		await self.safe_send_message(channel, "```Nim\nInfo for {}\n\nMembers: {}\nBots: {}\nTotal Roles: {}\nNumber of emotes: {}\nServer Region: {}\nTime Till Afk: {} minutes\nChannels: {}\nAfk Channel: {}\nIs Large: {}\nDefault Channel: {}\nServer ID: {}\nServer Owner: {}\nCreated: {}\nIcon:``` {}".format(name, members, bots, roles, emojis, region, afk_timeout, channels, afk_channel, is_large, default_channel, serverid, owner,creation_date, icon)) 

	async def cmd_slap(self, message, server, channel, permissions, user_mentions):
		"""
		Usage:
			{command_prefix}slap <@a valid user>
		Slap someone or get cuddled.
		"""
		owner = self._get_owner(voice=True or False or None) or self._get_owner()
		slap = ['http://orig11.deviantart.net/2d34/f/2013/339/1/2/golden_time_flower_slap_gif_by_paranoxias-d6wv007.gif', 'http://media.giphy.com/media/jLeyZWgtwgr2U/giphy.gif', 'http://rs1031.pbsrc.com/albums/y377/shinnidan/Toradora_-_Taiga_Slap.gif~c200', 'http://media.giphy.com/media/tMIWyF5GUrWwM/giphy.gif', 'http://www.animateit.net/data/media/243/aCC_AnimeAni2.gif', 'http://media.giphy.com/media/Zau0yrl17uzdK/giphy.gif', 'https://media.giphy.com/media/10Am8idu3qBYRy/giphy.gif', 'http://static1.wikia.nocookie.net/__cb20130131011839/adventuretimewithfinnandjake/images/c/cd/Slap.gif.gif', 'https://31.media.tumblr.com/dd5d751f86002fd4a544dcef7a9763d6/tumblr_inline_mya9hsvLZA1rbb2hd.gif', 'http://3.bp.blogspot.com/-CHYXl4bcgA0/UYGNzdDooBI/AAAAAAAADSY/MgmWVYn5ZR0/s400/2828+-+animated_gif+slap+umineko_no_naku_koro_ni+ushiromiya_maria+ushiromiya_rosa.gif', 'http://i.imgur.com/UXqzzab.gif', 'http://images6.fanpop.com/image/photos/32700000/Witch-slap-umineko-no-naku-koro-ni-32769187-500-283.gif', 'http://images2.fanpop.com/image/photos/9300000/Slap-Happy-futurama-9351667-352-240.gif', 'http://media.giphy.com/media/EpFsHUKK2MYvK/giphy.gif', 'http://ekladata.com/-vT5aTkK9ENUgyhqvNQfo7-Hids.gif', 'http://img.mrdrsr.net/slap.gif', 'http://fanaru.com/pandora-hearts/image/84052-pandora-hearts-pillow-slap.gif', 'https://media.giphy.com/media/XriT1FPiR1RRe/giphy.gif', 'http://i0.wp.com/haruhichan.com/wpblog/wp-content/uploads/Ryuuji-Takasu-x-Taiga-Aisaka-Toradora-anime-series-slap-haruhichan.com_.gif', 'https://media.giphy.com/media/1iw7RG8JbOmpq/giphy.gif', 'http://safebooru.org/images/363/5b1a06da49bd1eeccbf1f60428370c9b491b5156.gif?363332', 'https://artemisunfiltered.files.wordpress.com/2014/05/golden-time-nana-slap.gif', 'https://reallifeanime.files.wordpress.com/2014/06/akari-slap.gif', 'https://media.giphy.com/media/fNdolDfnVPKNi/giphy.gif', 'http://media.tumblr.com/tumblr_lx84j9KIBZ1qg12e8.gif','http://img.wonkette.com/wp-content/uploads/2013/07/107815-animated-animation-artist3asubjectnumber2394-fight-gif-sissy_slap_fight-trixie-twilight_sparkle.gif']
		cuddle = ['http://media.giphy.com/media/QlFyrikSI01Fe/giphy.gif', 'http://media.tumblr.com/01949fb828854480b513a87fa4e8eee7/tumblr_inline_n5r8vyJZa61qc7mf8.gif', 'http://media.giphy.com/media/Ki88u2LhvDhyE/giphy.gif', 'http://www.ohmagif.com/wp-content/uploads/2012/07/cute-puppy-cuddling-with-cat.gif', 'http://awesomegifs.com/wp-content/uploads/cat-and-dog-cuddling.gif', 'http://big.assets.huffingtonpost.com/cuddlecat.gif', 'http://25.media.tumblr.com/d9f3e83abe3e01d1174dae0a771750cd/tumblr_mi4ll7Rqqe1rqszceo1_400.gif', 'https://lh3.googleusercontent.com/-H8YQfmNXcus/UNH4jtH3gkI/AAAAAAAAGpA/FHslZSXRs6I/s233/141.gif', 'https://media.giphy.com/media/ipTpDF6TOdgc/giphy.gif', 'https://media.giphy.com/media/ztXa20eZi18oo/giphy.gif', 'http://www.rinchupeco.com/wp-content/uploads/2013/06/cuddle.gif', 'http://s2.favim.com/orig/36/ash-bed-hug-pikachu-pokemon-Favim.com-295600.gif']
		if not user_mentions:
			url = random.choice(slap)
			await self.safe_send_message(channel,  "*Slaps* " +  message.author.mention)
		else:
			for user in user_mentions.copy():
				if user.name == owner.name:
					await self.safe_send_message(channel, "{}, you can't slap my owner >:( *blocks* denied!".format(message.author.mention))
				elif message.author.name == user.name:
					url = random.choice(cuddle)
					await self.safe_send_message(channel, message.author.mention + " self harm isn't good >.< you really shouldn't do that baka! Have this instead")
				elif user.name == self.user.name:
					await self.safe_send_message(channel, message.author.mention + " *blocks* heh, chu can't slap mai *stick tongue out at you and giggles* ")
					await self.safe_delete_message(message)
					return
				else:
					url = random.choice(slap)
					await self.safe_send_message(channel, message.author.mention + ' slapped ' +  user.mention)
			urllib.request.urlretrieve(url, 'tmp.gif')
			await self.send_file(channel, 'tmp.gif')
			await self.safe_delete_message(message)
			await self.update_now_playing()

	async def cmd_punch(self, message, server, channel, permissions, user_mentions):
		"""
		Usage:
			{command_prefix}punch <@ a valid user>
		Punch people or get hugged.
		"""
		owner = self._get_owner(voice=True or False or None ) or self._get_owner()
		hug = ['http://25.media.tumblr.com/tumblr_m8223lqZCl1ra8wu5o1_500.gif','http://www.thehomeplanet.org/wp-content/uploads/2013/04/Bobby-Sam-Hug.gif','http://24.media.tumblr.com/tumblr_lw7r7vRUGN1qii6tmo1_500.gif', 'https://33.media.tumblr.com/680b69563aceba3df48b4483d007bce3/tumblr_mxre7hEX4h1sc1kfto1_500.gif', 'http://media.giphy.com/media/lrr9rHuoJOE0w/giphy.gif', 'https://38.media.tumblr.com/b004f301143edad269aa1d88d0f1e245/tumblr_mx084htXKO1qbvovho1_500.gif', 'http://img4.wikia.nocookie.net/__cb20130302231719/adventuretimewithfinnandjake/images/1/15/Tumblr_m066xoISk41r6owqs.gif', 'http://cdn.smosh.com/sites/default/files/ftpuploads/bloguploads/0413/epic-hugs-friends-anime.gif', 'http://1.bp.blogspot.com/-OpJBN3VvNVw/T7lmAw0HxFI/AAAAAAAAAfo/bGJks9CqbK8/s1600/HUG_K-On!+-+Kawaii.AMO.gif', 'http://media.tumblr.com/tumblr_m1oqhy8vrH1qfwmvy.gif', 'https://myanimelist.cdn-dena.com/s/common/uploaded_files/1461073447-335af6bf0909c799149e1596b7170475.gif','http://24.media.tumblr.com/49a21e182fcdfb3e96cc9d9421f8ee3f/tumblr_mr2oxyLdFZ1s7ewj9o1_500.gif', 'http://pa1.narvii.com/5774/3cb894f1d4bcb4a9c58a06ee2a7fcd1a11f9b0eb_hq.gif','http://media.tumblr.com/01949fb828854480b513a87fa4e8eee7/tumblr_inline_n5r8vyJZa61qc7mf8.gif','https://media.tenor.co/images/e07a54a316ea6581329a7ccba23aea2f/tenor.gif', 'http://media.giphy.com/media/aD1fI3UUWC4/giphy.gif', 'https://38.media.tumblr.com/3b6ccf23ecd9aeacfcce0add1462c7c0/tumblr_msxqo58vDq1se3f24o1_500.gif', 'https://myanimelist.cdn-dena.com/s/common/uploaded_files/1460992224-9f1cd0ad22217aecf4507f9068e23ebb.gif', 'http://1.bp.blogspot.com/-J9Byahz1TuQ/UdI9CslAyAI/AAAAAAAAQWI/_tfIGYSUzdA/s500/inyu5.gif', 'http://25.media.tumblr.com/tumblr_m0lgriUiVK1rqfhi2o1_500.gif', 'http://media.tumblr.com/tumblr_lknzmbIG1x1qb5zie.gif', 'http://mrwgifs.com/wp-content/uploads/2013/04/Snuggling-Cuddling-Anime-Girls-Gif-.gif', 'https://38.media.tumblr.com/b004f301143edad269aa1d88d0f1e245/tumblr_mx084htXKO1qbvovho1_500.gif', 'http://media.giphy.com/media/od5H3PmEG5EVq/giphy.gif', 'http://25.media.tumblr.com/671f27962ca544ef8907ec0132c49ad1/tumblr_mp8srnNcTy1sx93aso1_500.gif']
		punch = ['https://media.tenor.co/images/c22ccca9bccec97234cfa3f0147c32a9/raw', 'https://media.giphy.com/media/11zD6xIdX4UOfS/giphy.gif', 'https://media.tenor.co/images/c119c32b931abd9c9d6471839d0e35f2/raw', 'http://media3.giphy.com/media/LdsJrFnANh6HS/giphy.gif', 'http://media.giphy.com/media/mLn5AIQK2WEwg/giphy.gif', 'https://media.tenor.co/images/9117e543eb665a49ae73fd960c5f7d57/raw', 'https://media.giphy.com/media/Z5zuypybI5dYc/giphy.gif', 'https://media.giphy.com/media/10Im1VWMHQYfQI/giphy.gif', 'http://24.media.tumblr.com/tumblr_llzoy4WqVw1qd9kxeo1_500.gif', 'http://i.imgur.com/t7UzKxg.gif', 'http://ohn1.slausworks.netdna-cdn.com/newohnblog/wp-content/uploads/2013/09/punch_anime.gif']
		if not user_mentions:
			url = random.choice(punch)
			urllib.request.urlretrieve(url, 'tmp.gif')
			await self.safe_send_message(channel,  "*Punches* " +  message.author.mention)
			await self.send_file(channel, 'tmp.gif')
		for user in user_mentions.copy():
			if message.author.name == user.name:
				url = random.choice(hug)
				urllib.request.urlretrieve(url, 'tmp.gif')
				await self.safe_send_message(channel, message.author.mention + " ermm punching yourself can't be a good thing.. *Stops your from doing it and then hugs you gently* it'll be oki, don't beat yourself up now ;-;")
				await self.send_file(channel, 'tmp.gif')
			elif user.name == self.user.name:
				url = random.choice(hug)
				urllib.request.urlretrieve(url, 'tmp.gif')
				await self.safe_send_message(channel, message.author.mention + " denied :heavy_multiplication_x:  punching me is a no-no :yum: you can have a hug though")
				await self.send_file(channel, 'tmp.gif')
			elif user.name == owner.name:
				await self.safe_send_message(channel, ":heavy_multiplication_x:  | Denied! You can't punch my owner!")
			else:
				url = random.choice(punch)
				urllib.request.urlretrieve(url, 'tmp.gif')
				await self.safe_send_message(channel, message.author.mention + ' punched ' +  user.mention)
				await self.send_file(channel, 'tmp.gif')
		await self.safe_delete_message(message)
		os.remove('tmp.gif')
		await self.update_now_playing()

	async def cmd_nugget(self, message, server, channel, permissions, user_mentions):
		"""
		Usage:
			{command_prefix}nugget <@ a valid user>
		Give nuggets :D
		"""
		if not user_mentions:
			await self.safe_send_message(channel,  "*gives chicken nuggets to* " +  message.author.mention)
		for user in user_mentions.copy():
				await self.safe_send_message(channel, message.author.mention + ' gave ' +  user.mention + ' chicken nuggets')
		urllib.request.urlretrieve('http://33.media.tumblr.com/c0c7cd77cee82090947f1f738c4d2146/tumblr_nc02kn3I5k1rnn5yuo1_500.gif', 'tmp.gif')
		await self.send_file(channel, 'tmp.gif')
		await self.safe_delete_message(message)
		os.remove('tmp.gif')
		await self.update_now_playing()

	async def cmd_noodle(self, message, server, channel, permissions, user_mentions):
		"""
		Usage:
			{command_prefix}noodle <a valid user>
		Give noodles ^0^ *slurip slurp* yummy~
		"""
		if not user_mentions:
			urllib.request.urlretrieve('https://media.giphy.com/media/R6oW8JAJxqRxe/giphy.gif', 'tmp.gif')
			await self.safe_send_message(channel,  "*sending noodles* to " +  message.author.mention)
			await self.send_file(channel, 'tmp.gif')
			await self.safe_delete_message(message)
			os.remove('tmp.gif')
			await self.update_now_playing()
		for user in user_mentions.copy():
				urllib.request.urlretrieve('https://media.giphy.com/media/R6oW8JAJxqRxe/giphy.gif', 'tmp.gif')
				await self.safe_send_message(channel, message.author.mention + ' sent noodles to ' +  user.mention)
				await self.send_file(channel, 'tmp.gif')
				await self.safe_delete_message(message)
				os.remove('tmp.gif')
				await self.update_now_playing()
	
	async def cmd_cookie(self, message, server, channel, permissions, user_mentions):
		"""
		Usage:
			{command_prefix}cookie <@ valid user>
		Cookie nomming quest?
		"""
		if not user_mentions:
			urllib.request.urlretrieve('http://cogdogblog.com/wp-content/uploads/2011/11/cookieloving.gif', 'tmp.gif')
			await self.safe_send_message(channel,  "Take some cookies " +  message.author.mention + ' ^o^')
			await self.send_file(channel, 'tmp.gif')
			await self.safe_delete_message(message)
			os.remove('tmp.gif')
			await self.update_now_playing()
		for user in user_mentions.copy():
				urllib.request.urlretrieve('https://s3.amazonaws.com/images1.vat19.com/nams-bits/nams-bits-perfect-gift.gif', 'tmp.gif')
				await self.safe_send_message(channel, message.author.mention  + ' gave a cookie to ' +  user.mention)
				await self.send_file(channel, 'tmp.gif')
				await self.safe_delete_message(message)
				os.remove('tmp.gif')
				await self.update_now_playing()
	"""
	async def cmd_giphy(self, server, channel, message, search=None):
		
		Usage:
			{command_prefix}giphy "search content"
	
		temp = message.content
		if len(temp[5:].strip()) > 0:
			try:
				g = giphypop.Giphy()
				query = [x for x in g.search(phrase='{}'.format(temp))]
				result = random.choice(query).media_url
				urllib.request.urlretrieve(result, 'tmp.gif')
				await self.send_file(channel, 'tmp.gif')
				await self.safe_delete_message(message)
				os.remove('tmp.gif')
				await self.update_now_playing()
			except discord.Forbidden:
				await self.safe_send_message(channel, "Well something went wrong.")
		else:
			return
	"""

	async def cmd_neko(self, server, channel, message):
		"""
		Usage:
			{command_prefix}neko
		Get a cute neko picture from Giphy
		"""
		g = giphypop.Giphy()
		query = [x for x in g.search(phrase='kawaii neko')]
		result = random.choice(query).media_url
		urllib.request.urlretrieve(result, 'tmp.gif')
		await self.send_file(channel, 'tmp.gif')
		await self.safe_delete_message(message)
		os.remove('tmp.gif')
		await self.update_now_playing()		    

	async def cmd_kawaii(self, server, channel, message):
		"""
		Usage:
			{command_prefix}kawaii
		Get's a kawaii image from Giphy
		"""
		g = giphypop.Giphy()
		query = [x for x in g.search(phrase='kawaii')]
		result = random.choice(query).media_url
		urllib.request.urlretrieve(result, 'tmp.gif')
		await self.send_file(channel, 'tmp.gif')
		await self.safe_delete_message(message)
		os.remove('tmp.gif')
		await self.update_now_playing()
			
	async def cmd_pout(self, server, channel, message):
		"""
		Usage:
			{command_prefix}pout
		Get's a pouting image from Giphy
		"""
		g = giphypop.Giphy()
		query = [x for x in g.search(phrase='anime pout')]
		result = random.choice(query).media_url
		urllib.request.urlretrieve(result, 'tmp.gif')
		await self.send_file(channel, 'tmp.gif')
		await self.safe_delete_message(message)
		os.remove('tmp.gif')
		await self.update_now_playing()

	async def cmd_purr(self, message, server, channel, permissions, user_mentions):
		"""
		Usage:
			{command_prefix}purr
		Purr.
		"""
		await self.safe_send_message(channel, message.author.mention + " *has purred loudly and happily*")
		await self.safe_delete_message(message)
		await self.update_now_playing()			

	async def cmd_moan(self, message, server, channel, permissions, user_mentions):
		"""
		Usage
			{command_prefix}moan
		Moan....
		"""
		lewd =  ['http://i3.kym-cdn.com/photos/images/newsfeed/000/936/092/af7.jpg', 'http://i.imgur.com/tkEOnku.jpg', 'http://i3.kym-cdn.com/photos/images/original/000/905/295/193.png', 'http://i.imgur.com/Kscx9g5.png', 'http://i3.kym-cdn.com/photos/images/original/000/897/703/b97.png', 'http://gallery.fanserviceftw.com/_images/a32b7d53651dcc3b76fcdc85a989c81b/9599%20-%20doushio%20makise_kurisu%20steins%3Bgate%20tagme.png', 'https://img.ifcdn.com/images/89ca6bd97bca8fabb4f3cb24f56e79b9ad020904e194f8cf99ff046d8da368a1_1.jpg', 'http://i2.kym-cdn.com/photos/images/newsfeed/000/888/789/f39.jpg', 'http://i1.kym-cdn.com/photos/images/original/000/988/917/ff8.jpg', 'http://i0.kym-cdn.com/photos/images/masonry/000/905/286/7ec.jpg','http://i1.kym-cdn.com/photos/images/facebook/000/794/434/6e7.gif']
		urllib.request.urlretrieve(random.choice(lewd), 'tmp.png')
		await self.safe_send_message(channel, message.author.mention + ", has moaned..**lewdly**")
		await self.send_file(channel, 'tmp.png')
		await self.safe_delete_message(message)
		os.remove('tmp.png')
		await self.update_now_playing()

	async def cmd_8ball(self, message, server, channel, permissions, user_mentions):
		"""
		Usage:
			{command_prefix}8ball "Yes or no question"
		Ask the magic 8ball quesitons.
		"""
		answers = ["It is certain", " It is decidedly so", "Without a doubt", "Yes definitely", "You may rely on it", "As I see it, yes", "Most likely", "Outlook good", "Yes", "Signs point to yes", "Reply hazy try again", "Ask again later", "Better not tell you now", "Cannot predict now", "Concentrate and ask again", "Don't count on it", "My reply is no", "My sources say no", "Outlook not so good", "Very doubtful"]
		await self.safe_send_message(channel, "{0}, {1}.".format(message.author.name, random.choice(answers)))
		await self.update_now_playing()

	async def cmd_repeat(self, player, channel, message, server, permissions, user_mentions):
		"""
		Usage:
			{command_prefix}repeat
		Cycles through the repeat options. Default is no repeat, switchable to repeat all or repeat current song.
		"""
		if player.is_stopped:
			raise exceptions.CommandError("M-master, {} I'm not playing any music!".format(message.author.name))


		player.repeat()
		if player.is_repeatAll:
			await self.safe_send_message(channel, ":repeat: **|** m-master {}, the player has been changed to __**`All`**__".format(message.author.name))
		if player.is_repeatSingle:
			await self.safe_send_message(channel, ":repeat_one: **|** m-master {}, the player has been changed to __**`Single`**__".format(message.author.name))
		if player.is_repeatNone:
			await self.safe_send_message(channel, ":play_pause: **|** m-master {}, the player has been changed to __**`None`**__".format(message.author.name))

	async def cmd_help(self, server, channel, message, author, user_mentions, command=None):
		owner = self._get_owner(voice=True or False or None) or self._get_owner()
		if command:
			cmd = getattr(self, 'cmd_' + command, None)
			if cmd and not hasattr(cmd, 'dev_cmd'):
				return Response(
					"```\n{}```".format(
						dedent(cmd.__doc__)
						).format(command_prefix=self.config.command_prefix),
		          )
			else:
				return Response("No such command", delete_after=10)

		else:
			if not message.author == owner:
				await self.safe_send_message(channel, "```Prolog\n[Fun Commands] \nroll, say, nugget, noodle, 8ball, cookie, hug, glomp, bite, kiss, fkiss, ckiss, greet, kawaii, cuddle, snuggle, howl, slap, lewd, punch, poke, pat, satan, coin, neko, flirt, sob, sex, succ, steal, kill, suicide, purr, rate, moan, pout, pet, and cum. \n\n[Information Commands]\nuser, invite, listids, test, help, ping, pong, uptime, roles, and server. \n\n[Music Commands] \nsong, play, playlist, search, skip, join, leave, remove, playhits, playsad, playvamps, playlove, playnightcore, playdub, playbg, playlogic, pause, repeat, volume, pldump, resume, and clear. \n\n[Admin Commands]\nkick, ban, softban, playnow, and skipnow\n\n[Other Commands]\ncleanup\n\nPlease note all commands start with \ and will not work otherwise. Commands are not case sensitive. If you need other help, or have a question. Ask, {}#{}```".format(owner.name, owner.discriminator))
			else:
				await self.safe_send_message(channel, "Senpai, you already know all my commands...but here *pouts, upset that you can't remmeber!*\n```Prolog\n[Fun Commands] \nroll, say, nugget, noodle, 8ball, cookie, hug, glomp, bite, kiss, fkiss, ckiss, greet, kawaii, cuddle, snuggle, howl, slap, lewd, punch, poke, pat, satan, coin, neko, flirt, sob, sex, succ, steal, kill, suicide, purr, rate, moan, pout, pet, and cum. \n\n[Information Commands]\nuser, invite, listids, test, help, ping, pong, uptime, roles, and server. \n\n[Music Commands] \nsong, play, playlist, search, skip, join, leave, remove, playhits, playsad, playvamps, playlove, playnightcore, playdub, playbg, playlogic, pause, repeat, volume, pldump, resume, and clear. \n\n[Admin Commands]\nkick, ban, softban, playnow, and skipnow\n\n[Owner Commands]\nrestart, shutdown, broadcast, setavatar, sync, serverlist, and setname \n\n[Other Commands]\ncleanup\n\nPlease note all commands start with \ and will not work otherwise. Commands are not case sensitive. If you need other help, or have a question. Ask, {}#{}```".format(owner.name, owner.discriminator))
		await self.update_now_playing()

	async def cmd_leaveserver(self, id):
		    """
		    Usage:
		        {command_prefix}leaveserver <id>
		    Removes the bot from a specific server via ID
		    """
		    target = self.get_server(id)
		    if target is None:
		        raise exceptions.CommandError('The server {} does not exist'.format(id), expire_in=30)
		    else:
		        await self.leave_server(target)
		        return Response("Left server successfully: {0.name} ({0.id})".format(target))

	async def cmd_test(self, server, channel, message):
		"""
		Usage:
			{command_prefix}test
		Am I online?
		"""
		output = await self.safe_send_message(message.channel, "I'm a-alive m-master")
		await self.update_now_playing()



	async def cmd_skipnow(self, player, channel, author, message, permissions, voice_channel):
		    """  
		    Usage:
		        {command_prefix}skipnow
		    Skips the current song without a vote.
		    """
		    managem_perms = lambda u: channel.permissions_for(u).manage_messages
		    if not managem_perms(author):
		    	await self.safe_send_message(channel, "M-master {} you don't have the `manage messages` permissions on this server, get someone with this permission to be able to use this!".format(message.author.name))
		    	return
		    else:
		    	if player.is_stopped:
		    	        raise exceptions.CommandError("M-master I can't skip, I'm not playing any music!")

		    	if player.is_paused:
		    		raise exceptions.CommandError("M-master I can't skip, I'm pawsed!")

		    	if not player.current_entry:
		    		if player.playlist.peek():
		    			if player.playlist.peek()._is_downloading:
		    			 # print(player.playlist.peek()._waiting_futures[0].__dict__)
		    			 return Response("M-master the next song (%s) is downloading, please wait." % player.playlist.peek().title)

		    			elif player.playlist.peek().is_downloaded:
		    				print("M-master the next song will be displayed soon~")
		    			else:
		    				await self.safe_send_message(channel, "Oh noes! Something went wrong :scream_cat:")
		    	else:
		    		print(channel, "[INFO] Song: {}Skipped by: {} Time: {}".format(player.current_entry.title, message.author.name, datetime.datetime.now().strftime("%a %b %d %Y %H:%M:%S")))

		    	if player.is_playing:
		    		player.skip()
		    		await self._manual_delete_check(message)
		    		if player.is_playing:
		    			await self.safe_send_message(channel, "M-master {} you've forced skiped {}!".format(message.author.name, player.current_entry.title))


	async def cmd_promote(self, player, author, channel, message, position=None):
		    			    """
		    			    Usage:
		    			        {command_prefix}promote
		    			        {command_prefix}promote [song position]

		    			    Promotes the last song in the queue to the front. 
		    			    If you specify a position in the queue, it promotes the song at that position to the front.
		    			    """
		    			    managem_perms = lambda u: channel.permissions_for(u).manage_messages
		    			    if not managem_perms(author):
		    			    	await self.safe_send_message(channel, "M-master {} you don't have the `manage messages` permissions on this server, get someone with this permission to be able to use this!".format(message.author.name))
		    			    	return
		    			    else:

			    			    if player.is_stopped:
			    			        raise exceptions.CommandError("Can't modify the queue! The player is not playing!", expire_in=20)
			    			    
			    			    length = len(player.playlist.entries)

			    			    if length < 2:
			    			        raise exceptions.CommandError("Can't promote! Please add at least 2 songs to the queue!", expire_in=20)

			    			    if not position:
			    			        entry = player.playlist.promote_last()
			    			    else:
			    			        try:
			    			            position = int(position)
			    			        except ValueError:
			    			            raise exceptions.CommandError("This is not a valid song number! Please choose a song \
			    			                number between 2 and %s!" % length, expire_in=20)

			    			        if position == 1:
			    			            raise exceptions.CommandError("This song is already at the top of the queue!", expire_in=20)
			    			        if position < 1 or position > length:                
			    			            raise exceptions.CommandError("Can't promote a song not in the queue! Please choose a song \
			    			                number between 2 and %s!" % length, expire_in=20)

			    			        entry = player.playlist.promote_position(position)

			    			    reply_text = "Promoted **%s** to the :top: of the queue. Estimated time until playing: %s"
			    			    btext = entry.title

			    			    try:
			    			        time_until = await player.playlist.estimate_time_until(1, player)
			    			    except:
			    			        traceback.print_exc()
			    			        time_until = ''

			    			    reply_text %= (btext, time_until)

			    			    return Response(reply_text, delete_after=30)



	async def cmd_playnow(self, player, channel, author, message, permissions, leftover_args, song_url):
			        """
			        Usage:
			            {command_prefix}playnow song_link
			            {command_prefix}playnow text to search for

			        Stops the currently playing song and immediately plays the song requested. \
			        If a link is not provided, the first result from a youtube search is played.
			        """

			        managem_perms = lambda u: channel.permissions_for(u).manage_messages
			        song_url = song_url.strip('<>')

			        if not managem_perms(author):
			        	await self.safe_send_message(channel, "M-master {} you don't have the `manage messages` permissions on this server, get someone with this permission to be able to use this!".format(message.author.name))
			        	return
			        else:
				        if permissions.max_songs and player.playlist.count_for_user(author) >= permissions.max_songs:
				            raise exceptions.PermissionsError(
				                "You have reached your enqueued song limit m-master (%s)" % permissions.max_songs, expire_in=30
				            )

				        await self.send_typing(channel)

				        if leftover_args:
				            song_url = ' '.join([song_url, *leftover_args])

				        try:
				            info = await self.downloader.extract_info(player.playlist.loop, song_url, download=False, process=False)
				        except Exception as e:
				            raise exceptions.CommandError(e, expire_in=30)

				        if not info:
				            raise exceptions.CommandError("That video c-cannot be played, m-master.", expire_in=30)

				        # abstract the search handling away from the user
				        # our ytdl options allow us to use search strings as input urls
				        if info.get('url', '').startswith('ytsearch'):
				            # print("[Command:play] Searching for \"%s\"" % song_url)
				            info = await self.downloader.extract_info(
				                player.playlist.loop,
				                song_url,
				                download=False,
				                process=True,    # ASYNC LAMBDAS WHEN
				                on_error=lambda e: asyncio.ensure_future(
				                    self.safe_send_message(channel, "```\n%s\n```" % e, expire_in=120), loop=self.loop),
				                retry_on_error=True
				            )

				            if not info:
				                raise exceptions.CommandError(
				                    "Error extracting info from search string, youtubedl returned no data.  "
				                    "You may need to restart the bot if this continues to happen.", expire_in=30
				                )

				            if not all(info.get('entries', [])):
				                # empty list, no data
				                return

				            song_url = info['entries'][0]['webpage_url']
				            info = await self.downloader.extract_info(player.playlist.loop, song_url, download=False, process=False)
				            # Now I could just do: return await self.cmd_play(player, channel, author, song_url)
				            # But this is probably fine

				        # TODO: Possibly add another check here to see about things like the bandcamp issue
				        # TODO: Where ytdl gets the generic extractor version with no processing, but finds two different urls

				        if 'entries' in info:
				            raise exceptions.CommandError("I c-can't playnow p-playlist m-master, you have to do a single song >.<", expire_in=30)
				        else:
				            if permissions.max_song_length and info.get('duration', 0) > permissions.max_song_length:
				                raise exceptions.PermissionsError(
				                    "Your song request exceeds my duration limit of (%s > %s)" % (info['duration'], permissions.max_song_length),
				                    expire_in=30
				                )

				            try:
				                entry, position = await player.playlist.add_entry(song_url, channel=channel, author=author)
				                await self.safe_send_message(channel, "Enqueued __**`%s`**__ to be played. \nPosition in queue: **Up next!**" % entry.title, expire_in=20)
				                # Get the song ready now, otherwise race condition where finished-playing will fire before
				                # the song is finished downloading, which will then cause another song from autoplaylist to
				                # be added to the queue
				                await entry.get_ready_future()

				            except exceptions.WrongEntryTypeError as e:
				                if e.use_url == song_url:
				                    print("[Warning] Determined incorrect entry type, but suggested url is the same.  Help.")

				                if self.config.debug_mode:
				                    print("[Info] Assumed url \"%s\" was a single entry, was actually a playlist" % song_url)
				                    print("[Info] Using \"%s\" instead" % e.use_url)

				                return await self.cmd_playnow(player, channel, author, permissions, leftover_args, e.use_url)

				            if position > 1:
				                player.playlist.promote_last()
				            if player.is_playing:
				                player.skip()

				        # return Response(reply_text, delete_after=30)

	@owner_only
	async def cmd_serverlist(self, server, channel, message):
		"""
		Usage:
			{command_prefix}serverlist
		Gives a list of servers the bot is on, if permissions are True then creates an instant invite
		"""
		perms = lambda u: channel.permissions_for(u).create_instant_invite
		if perms == True:
			servers = '\n'.join('{} | {} | {}'.format(s.name, s.id, self.create_invite) for s in list(self.servers))
			date = datetime.datetime.now().strftime("%a %b %d %Y %H:%M:%S")
			await self.safe_send_message(channel, '%s servers as of {0}\n\n{1}'.format(date, servers) % len(self.servers))
			await self.update_now_playing()
		else:
			pass


	async def cmd_ban(self, server, message, channel, author, user_mentions, delete_message_days=1, reason=None): 
		"""
		Usage:
		    {command_prefix}ban [@USER] "reason"

		Ban's a member from the server.
		"""
		ban_perms = lambda u: channel.permissions_for(u).ban_members

		if not user_mentions:
		    await self.safe_send_message(channel, "{}, awh master you got me excited I was ready to swing the ban hammer D: plz mention someone for me to ban. `{}ban @a valid user`".format(message.author.name, command_prefix))
			
		else:
		    if not ban_perms(author):
		    	await self.safe_send_message(channel, 'M-master you have no permissions to ban on this server D:')
		    	return

		    try:
		        member = user_mentions[0]
		        await self.ban(member)
		        await self.safe_send_message(channel, "M-master {0}, I've  succesfully banned {1} from {2}.\nReason: {3}".format(author.name, member.name, author.server, reason))
		    except discord.Forbidden:
		        await self.safe_send_message(channel, "Looks like something went wrong, make sure I have the proper permissions to ban!")

	async def cmd_kick(self, server, message, channel, author, user_mentions, reason=None): 
		"""
		Usage:
		    {command_prefix}kick [@USER] ["reason"]

		Kick's a member from the server.
		"""
		kick_perms = lambda u: channel.permissions_for(u).kick_members

		if not user_mentions:
		    await self.safe_send_message(channel, "{} you're a tease >.> I was ready to kick the baddie! Please make sure your doing it right: `{}kick @a valid user".format(message.author.name, command_prefix))
			
		else:
		    if not kick_perms(author):
		    	await self.safe_send_message(channel, 'M-master you have no permissions to kick on this server D:')
		    	return

		    try:
		        member = user_mentions[0]
		        await self.kick(member)
		        await self.safe_send_message(channel, "M-master {0}, I've  succesfully kicked {1} from {2}.\nReason: {3}".format(author.name, member.name, author.server, reason))
		    except discord.Forbidden:
		        await self.safe_send_message(channel, "Looks like something went wrong, make sure I have the proper permissions to kick!")


	async def cmd_softban(self, server, message, channel, author, user_mentions, delete_message_days=7, reason=None): 
		"""
		Usage:
		    {command_prefix}softban [@USER] "reason"

		Ban's a member from the server then immediatly unbans to remove messages.
		"""
		ban_perms = lambda u: channel.permissions_for(u).ban_members	

		if not user_mentions:
		    await self.safe_send_message(channel, "{}, awh master you got me excited I was ready to swing the ban hammer D: plz mention someone for me to ban. `\{}softban @a valid user`".format(message.author.name, command_prefix))
		else:
		    if not ban_perms(author):
		    	await self.safe_send_message(channel, 'M-master you have no permissions to ban on this server D:')
		    	return

		    try:
		        member = user_mentions[0]
		        server = message.server
		        user = member
		        await self.ban(member)
		        await self.safe_send_message(channel, "M-master {0}, I've  succesfully softbanned {1} from {2}\nReason: {3}.".format(author.name, member.name, author.server, reason))
		        await self.unban(server, user)
		    except discord.Forbidden:
		        await self.safe_send_message(channel, "Looks like something went wrong, make sure I have the proper permissions to ban!")


	async def cmd_remove(self, player, leftover_args, index):
		    """
		    Usage:
		        {command_prefix}remove [index]
		    Remove a song at the given index from the queue. 
		    Use {command_prefix}queue to see the list of queued songs and their indices.
		    """
		    try:
		        index = int(' '.join([index, *leftover_args]))
		        playlist_size = len(player.playlist.entries)
		        if index > playlist_size:
		            if(playlist_size > 1):
		                reply_text = "There are only **`%s`** songs in the playlist m-master"
		                reply_text %= (playlist_size)
		                return Response(reply_text)
		            elif(playlist_size == 1):
		                reply_text = "There is only **`%s`** song in the playlist m-master"
		                reply_text %= (playlist_size)
		                return Response(reply_text)
		            else:
		                reply_text = "There aren't any songs in the playlist m-master"
		                return Response(reply_text)

		        entry = await player.playlist.remove_entry(index)
		        reply_text = "Removed __**`%s`**__ from the playlist"
		        reply_text %= (entry.title)

		        return Response(reply_text)
		    except ValueError:
		        reply_text = "Must specify an index to remove (AKA a number)"

		        return Response(reply_text)
		        await self.update_now_playing()

	async def cmd_lewd(self, server, channel, message):
		"""
		Usage:
			{command_prefix}lewd
		Tell people how lewd the chat is.
		"""
		lewd =  ['http://i3.kym-cdn.com/photos/images/newsfeed/000/936/092/af7.jpg', 'http://i.imgur.com/tkEOnku.jpg', 'http://i3.kym-cdn.com/photos/images/original/000/905/295/193.png', 'http://i.imgur.com/Kscx9g5.png', 'http://i3.kym-cdn.com/photos/images/original/000/897/703/b97.png', 'http://gallery.fanserviceftw.com/_images/a32b7d53651dcc3b76fcdc85a989c81b/9599%20-%20doushio%20makise_kurisu%20steins%3Bgate%20tagme.png', 'https://img.ifcdn.com/images/89ca6bd97bca8fabb4f3cb24f56e79b9ad020904e194f8cf99ff046d8da368a1_1.jpg', 'http://i2.kym-cdn.com/photos/images/newsfeed/000/888/789/f39.jpg', 'http://i1.kym-cdn.com/photos/images/original/000/988/917/ff8.jpg', 'http://i0.kym-cdn.com/photos/images/masonry/000/905/286/7ec.jpg','http://i1.kym-cdn.com/photos/images/facebook/000/794/434/6e7.gif']
		urllib.request.urlretrieve(random.choice(lewd), 'tmp.png')
		await self.send_file(channel, 'tmp.png')
		os.remove('tmp.png')
		await self.safe_delete_message(message)
		await self.update_now_playing()

	async def cmd_sob(self, server, channel, message, permissions, user_mentions):
		"""
		Usage:
			{command_prefix}sob
		Tell people how sad you are by sobbing, don't worry Neko will give you pats
		"""
		sob =  ['http://24.media.tumblr.com/b7ae6c694085e0b294cdd938278c70c7/tumblr_mpupx1krXM1s3jc4vo1_400.gif', 'http://media.giphy.com/media/ZlWplgoWyskQo/giphy.gif', 'http://mrwgifs.com/wp-content/uploads/2013/05/Dramatic-Crying-In-Anime-Gif.gif', 'http://24.media.tumblr.com/4b53f4cf45e7f72910ca5120f19a8aa8/tumblr_mnzdt6fGen1s645eto1_500.gif', 'https://38.media.tumblr.com/b6d6e61e7adb56ab4283c9f96fe67163/tumblr_mqvjmqrMqs1spu46io1_500.gif', 'http://gif-finder.com/wp-content/uploads/2015/07/Anime-girl-crying.gif', 'https://s-media-cache-ak0.pinimg.com/originals/69/fc/82/69fc828893e612d86fc7bb85862be96e.gif', 'http://25.media.tumblr.com/c65a4af4ff032d1ca06350b66a1e819c/tumblr_mtxk6zVzaa1sogk1do1_r1_500.gif', 'http://media.giphy.com/media/ROF8OQvDmxytW/giphy.gif', 'http://media.giphy.com/media/QUKkvRTIYLgMo/giphy.gif', 'http://media.tumblr.com/tumblr_mdaindozZF1ryvbtl.gif', 'https://31.media.tumblr.com/b307cca19d29eb1625bd841e661c0f59/tumblr_mvjhgmknl91stfs7go1_500.gif', 'http://media1.giphy.com/media/4pk6ba2LUEMi4/giphy.gif']
		urllib.request.urlretrieve(random.choice(sob), 'tmp.gif')
		await self.safe_send_message(channel, message.author.mention + " is now sobbing poor thing ;-; *pat pat*")
		await self.send_file(channel, 'tmp.gif')
		os.remove('tmp.gif')
		await self.safe_delete_message(message)
		await self.update_now_playing()

	async def cmd_master(self, server, channel, message):
		"""
		Usage:
			{command_prefix}master
		Ask me who my master is.
		"""
		owner = self._get_owner()
		await self.safe_send_message(channel, "***Who's my master?*** **{}#{}** ***is of course~***".format(owner.name, owner.discriminator))
		await self.safe_send_message(message)
		await self.update_now_playing()
    
	async def cmd_satan(self, server, channel, message):
		"""
		Usage:
			{command_prefix}satan
		Illuminati confirmed
		"""
		await self.safe_delete_message(message)
		await self.safe_send_message(message.channel, ':six: :six: :six: \n:japanese_goblin: **|** Satan is here~')
		await self.update_now_playing()

	async def cmd_uptime(self, server, channel, permissions, message, user_mentions):
		"""
		Usage:
			{command_prefix}uptime
		Ask me how long I've been running.
		"""
		await self.safe_send_message(message.channel, "{}, {}".format(message.author.name, self.startupdate))
		await self.update_now_playing()

	async def cmd_coin(self, server, channel, message):
		"""
		Usage:
			{command_prefix}coin
		Make neko flip a coin and settle arguments.
		"""
		urllib.request.urlretrieve('http://lamcdn.net/hopesandfears.com/post-cover/2ysvBXMxJaAQzUVeSUBj7A-default.gif', 'tmp.gif')
		coin = ['**heads!**', '**tails!**']
		await self.send_file(channel, 'tmp.gif')
		await asyncio.sleep(1)
		output = await self.safe_send_message(message.channel, '**You flipped a c-coin and got,** ' + random.choice(coin))	
		await self.safe_delete_message(message)
		os.remove('tmp.gif')
		await self.update_now_playing()

	async def cmd_rate(self, message, server, member, channel, permissions, user_mentions):
		"""
		Usage:
			{command_prefix}rate <@ a valid user>
		Rate your waifu's and husbando's
		"""
		owner = self._get_owner()
		rating = random.randint(70, 100)
		if not user_mentions:
			await self.safe_send_message(channel, "{0}, I'd rate you {1} out of 100!".format(message.author.mention, rating))
			member = author
		else:
			for user in user_mentions.copy(): 
				if user.name == self.user.name:
					await self.safe_send_message(channel, message.author.mention + ", I'm 10000000x10 out of 100 for sures")
				elif user.name == owner.name:
					await self.safe_send_message(channel, message.author.mention + " my senpai is unratable she's just that op~")
				else:
					rating = random.randint(70, 100)
					await self.safe_send_message(channel, "{0}, I'd rate {1}, {2} out of 100!".format(message.author.mention, user.mention, rating))
		await self.safe_delete_message(message)
		await self.update_now_playing()

	async def cmd_roll(self, server, channel, message, dice = 1):
		"""
		Usage:
			{command_prefix}roll (NUMBER OF DIE)
		Roll a random integer from 1-6 with one or more specified die.
		Defauts to one if no number is specified.
		"""
		output = await self.safe_send_message(message.channel, ':smile_cat: **|** ***Rolling...***')
		total = 0
		for x in range(0, 5):
			rolls = ' '
			for y in range(0, int(dice)):
				number = ' '
				z = random.randint(1, 6)
				if z == 1:
					number = ':one:'
				elif z == 2:
					number = ':two:'
				elif z == 3:
					number = ':three:'
				elif z == 4:
					number = ':four:'
				elif z == 5:
					number = ':five:'
				elif z == 6:
					number = ':six:'
				else:
					number = ':sos:'
				if x == 4:
					total = total + z
				rolls = rolls + number
				await asyncio.sleep(0.15)
			await self.safe_edit_message(output, ':smirk_cat: **|** ' + rolls)
		await self.safe_edit_message(output, rolls + '\n:smile_cat: **|** ***The s-sum is:*** __*`%s`*__' % total)
		await self.update_now_playing()

		
	async def cmd_say(self, server, channel, message):
		"""
		Usage:
			{command_prefix}say [MESSAGE]
		Makes Neko repeat what you say~
		"""
		temp = message.content
		if len(temp[5:].strip()) > 0:
			await self.safe_delete_message(message)
			await self.safe_send_message(message.channel, temp[5:])
			await self.update_now_playing()

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
				self.safe_print("[%s][ERROR] Cannot send message to \"%s\", no permission." % (datetime.datetime.now(), dest.name))
		except discord.NotFound:
			if not quiet:
				self.safe_print("[%s][ERROR] Cannot send message to \"%s\", invalid channel?" % (datetime.datetime.now(), dest.name))
		return msg


	async def safe_delete_message(self, message, *, quiet=False):
		try:
			return await self.delete_message(message)
		except discord.Forbidden:
			if not quiet:
				self.safe_print("[%s][ERROR] Cannot delete message \"%s\", no permission." % (datetime.datetime.now(), message.clean_content))
		except discord.NotFound:
			if not quiet:
				self.safe_print("[%s][ERROR] Cannot delete message \"%s\", message not found." % (datetime.datetime.now(), message.clean_content))


	async def safe_edit_message(self, message, new, *, send_if_fail=False, quiet=False):
		try:
			return await self.edit_message(message, new)
		except discord.NotFound:
			if not quiet:
				self.safe_print("[%s][WARNING] Cannot edit message \"%s\", message not found." % (datetime.datetime.now(), message.clean_content))
			if send_if_fail:
				if not quiet:
					print("Sending instead")
				return await self.safe_send_message(message.channel, new)

	def safe_print(self, content, *, end='\n', flush=True):
		sys.stdout.buffer.write((content + end).encode('utf-8', 'replace'))
		if flush: sys.stdout.flush()

	async def send_typing(self, destination):
		try:
			return await super().send_typing(destination)
		except discord.Forbidden:
			if self.config.debug_mode:
				print("[%s][ERROR] Could not send typing to %s, no permssion." % (datetime.datetime.now(), destination))

	async def edit_profile(self, **fields):
		if self.user.bot:
			return await super().edit_profile(**fields)
		else:
			return await super().edit_profile(self.config._password,**fields)

	def _cleanup(self):
		try:
			self.loop.run_until_complete(self.logout())
		except: # Can be ignored
			pass

		pending = asyncio.Task.all_tasks()
		gathered = asyncio.gather(*pending)

		try:
			gathered.cancel()
			self.loop.run_until_complete(gathered)
			gathered.exception()
		except: # Can be ignored
			pass

	# noinspection PyMethodOverriding
	def run(self):
		try:
			self.loop.run_until_complete(self.start(*self.config.auth))

		except discord.errors.LoginFailure:
			# Add if token, else
			raise exceptions.HelpfulError(
				"Bot cannot login, bad credentials.",
				"Fix your Email or Password or Token in the options file.  "
				"Remember that each field should be on their own line.")

		finally:
			try:
				self._cleanup()
			except Exception as e:
				print("[%s][ERROR] Error in cleanup:" % datetime.datetime.now(), e)

			self.loop.close()
			if self.exit_signal:
				raise self.exit_signal

	async def logout(self):
		await self.disconnect_all_voice_clients()
		return await super().logout()

	async def on_error(self, event, *args, **kwargs):
		ex_type, ex, stack = sys.exc_info()

		if ex_type == exceptions.HelpfulError:
			print("[%s][ERROR] Exception in" % datetime.datetime.now(), event)
			print(ex.message)

			await asyncio.sleep(2)  # don't ask
			await self.logout()

		elif issubclass(ex_type, exceptions.Signal):
			self.exit_signal = ex_type
			await self.logout()

		else:
			traceback.print_exc()

	async def on_resumed(self):
		for vc in self.the_voice_clients.values():
			vc.main_ws = self.ws

	async def on_ready(self):
		print('\rConnected!  Musicbot v%s\n' % BOTVERSION)
		self.startupdate = datetime.datetime.now().strftime("I've been running since: %a %b %d %Y %H:%M:%S EST.")

		if self.config.owner_id == self.user.id:
			raise exceptions.HelpfulError(
				"[%s][WARNING] Your OwnerID is incorrect or you've used the wrong credentials.",

				"The bot needs its own account to function.  "
				"The OwnerID is the id of the owner, not the bot.  "
				"Figure out which one is which and use the correct information." % datetime.datetime.now())

		self.init_ok = True

		self.safe_print("[INFO] Bot:%s/%s#%s" % (self.user.id, self.user.name, self.user.discriminator))

		owner = self._get_owner(voice=True) or self._get_owner()
		if owner and self.servers:
			self.safe_print("[INFO] Owner: %s/%s#%s" % (owner.id, owner.name, owner.discriminator))
			servers = '\n'.join('{} | {}'.format(s.name, s.id) for s in list(self.servers))
			date = datetime.datetime.now().strftime("%a %b %d %Y %H:%M:%S")
			print('%s servers as of {0}:\n{1}'.format(date, servers) % len(self.servers))
			await self.update_now_playing()


		elif self.servers:
			print("[WARNING] Owner could not be found on any server (id: %s)\n" % (self.config.owner_id))
			servers = '\n'.join('{} | {}'.format(s.name, s.id) for s in list(self.servers))
			date = datetime.datetime.now().strftime("%a %b %d %Y %H:%M:%S")
			print('%s servers as of {0}:\n{1}'.format(date, servers) % len(self.servers))
			await self.update_now_playing()

		else:
			print("[%s][WARNING] Owner unknown, bot is not on any servers." % datetime.datetime.now())
			if self.user.bot:
				print("\n[%s][INFO] To make the bot join a server, paste this link in your browser." % datetime.datetime.now())
				print("Note: You should be logged into your main account and have \n"
					  "manage server permissions on the server you want the bot to join.\n")
				print("[%s][Error]" + 'https://discordapp.com/oauth2/authorize?client_id=366772786573869058&scope=bot&permissions=536210479 ' % datetime.datetime.now())

		print()

		if self.config.bound_channels:
			chlist = set(self.get_channel(i) for i in self.config.bound_channels if i)
			chlist.discard(None)
			invalids = set()

			invalids.update(c for c in chlist if c.type == discord.ChannelType.voice)
			chlist.difference_update(invalids)
			self.config.bound_channels.difference_update(invalids)

			print("[%s][INFO] Bound to text channels:" % datetime.datetime.now())
			[self.safe_print(' - \"%s\" for channel \"%s\"' % (ch.server.name.strip(), ch.name.strip())) for ch in chlist if ch]

			if invalids and self.config.debug_mode:
				print("\n[%s][WARNING] Not binding to voice channels:" % datetime.datetime.now())
				[self.safe_print(' - \"%s\" for channel \"%s\"' % (ch.server.name.strip(), ch.name.strip())) for ch in invalids if ch]

			print()

		else:
			print("[%s][WARNING] Not bound to any text channels" % datetime.datetime.now())

		if self.config.autojoin_channels:
			chlist = set(self.get_channel(i) for i in self.config.autojoin_channels if i)
			chlist.discard(None)
			invalids = set()

			invalids.update(c for c in chlist if c.type == discord.ChannelType.text)
			chlist.difference_update(invalids)
			self.config.autojoin_channels.difference_update(invalids)

			print("[%s][INFO] Autojoining voice chanels:" % datetime.datetime.now())
			[self.safe_print(' - \"%s\" for channel \"%s\"' % (ch.server.name.strip(), ch.name.strip())) for ch in chlist if ch]

			if invalids and self.config.debug_mode:
				print("\n[%s][ERROR] Cannot join text channels:" % datetime.datetime.now())
				[self.safe_print(' - \"%s\" for channel \"%s\"' % (ch.server.name.strip(), ch.name.strip())) for ch in invalids if ch]

			autojoin_channels = chlist

		else:
			print("[%s][WARNING] Not autojoining any voice channels" % datetime.datetime.now())
			autojoin_channels = set()

		print()
		print("[%s][INFO] Options:" % datetime.datetime.now())

		self.safe_print("  Command prefix: " + self.config.command_prefix)
		print("  Default volume: %s%%" % int(self.config.default_volume * 100))
		print("  Skip threshold: %s votes or %s%%" % (
			self.config.skips_required, self._fixg(self.config.skip_ratio_required * 100)))
		print("  Now Playing @mentions: " + ['Disabled', 'Enabled'][self.config.now_playing_mentions])
		print("  Auto-Summon: " + ['Disabled', 'Enabled'][self.config.auto_summon])
		print("  Auto-Playlist: " + ['Disabled', 'Enabled'][self.config.auto_playlist])
		print("  Auto-Pause: " + ['Disabled', 'Enabled'][self.config.auto_pause])
		print("  Delete Messages: " + ['Disabled', 'Enabled'][self.config.delete_messages])
		if self.config.delete_messages:
			print("    Delete Invoking: " + ['Disabled', 'Enabled'][self.config.delete_invoking])
		print("  Debug Mode: " + ['Disabled', 'Enabled'][self.config.debug_mode])
		print("  Downloaded songs will be %s" % ['deleted', 'saved'][self.config.save_videos])
		print()

		# maybe option to leave the ownerid blank and generate a random command for the owner to use
		# wait_for_message is pretty neato
		await self.update_now_playing()

		if not self.config.save_videos and os.path.isdir(AUDIO_CACHE_PATH):
			if self._delete_old_audiocache():
				print("[%s][INFO] Deleting old audio cache" % datetime.datetime.now())
			else:
				print("[%s][WARNING] Could not delete old audio cache, moving on." % datetime.datetime.now())

		if self.config.autojoin_channels:
			await self._autojoin_channels(autojoin_channels)

		elif self.config.auto_summon:
			print("[%s][INFO] Attempting to autosummon..." % datetime.datetime.now(), flush=True)

			# waitfor + get value
			owner_vc = await self._auto_summon()

			if owner_vc:
				print("[%s][INFO] Joined channel \"%s\"." % (datetime.datetime.now(), owner.voice_channel.name))
				if self.config.auto_playlist:
					print("[%s][INFO] Starting auto-playlist." % datetime.datetime.now())
					await self.on_player_finished_playing(await self.get_player(owner_vc))
			else:
				print("[%s][WARNING] Owner not found in a voice channel, could not autosummon." % datetime.datetime.now())

		print()
		try:
			os.remove('tmp.gif')
		except:
			print("File not found, moving on.")
			return
			
		# t-t-th-th-that's all folks!

	async def cmd_blacklist(self, message, user_mentions, option, something):
		"""
		Usage:
			{command_prefix}blacklist [+|-|add|remove] [@USER] (@USER2...)

		Add or remove users to the blacklist.
		Blacklisted users are forbidden from using bot commands.
		"""

		if not user_mentions:
			raise exceptions.CommandError("No m-masters listed.", expire_in=20)

		if option not in ['+', '-', 'add', 'remove']:
			raise exceptions.CommandError(
				'Invalid option "%s" specified, use +, -, add, or remove' % option, expire_in=20
			)

		for user in user_mentions.copy():
			if user.id == self.config.owner_id:
				print("[%s][WARNING] The owner cannot be blacklisted." % datetime.datetime.now())
				user_mentions.remove(user)
				await self.update_now_playing()

		old_len = len(self.blacklist)

		if option in ['+', 'add']:
			self.blacklist.update(user.id for user in user_mentions)

			write_file(self.config.blacklist_file, self.blacklist)

			return Response(
				':smirk_cat: **|** ***%s m-masters have been added to the blacklist***' % (len(self.blacklist) - old_len),
				reply=True, delete_after=10
			)

		else:
			if self.blacklist.isdisjoint(user.id for user in user_mentions):
				return Response(':pouting_cat: **|** ***None of those m-masters are in the blacklist.***', reply=True, delete_after=10)
				await self.update_now_playing()

			else:
				self.blacklist.difference_update(user.id for user in user_mentions)
				write_file(self.config.blacklist_file, self.blacklist)

				return Response(
					':smile_cat: **|** ***%s m-masters have been removed from the blacklist***' % (old_len - len(self.blacklist)),
					reply=True, delete_after=10
				)


	async def cmd_whitelist(self, message, user_mentions, option, something):
		"""
		Usage:
			{command_prefix}whitelist +|-|add|remove @USER (@USER2...)

		Add or remove users to the whitelist.
		Whitelisted users are the only ones allowed to use bot commands.
		"""

		if not user_mentions:
			raise exceptions.CommandError("No m-masters listed.", expire_in=20)

		if option not in ['+', '-', 'add', 'remove']:
			raise exceptions.CommandError(
				'Invalid option "%s" specified, use +, -, add, or remove' % option, expire_in=20
			)

		for user in user_mentions.copy():
			if user.id == self.config.owner_id:
				print("[%s][WARNING] The owner cannot be whitelisted." % datetime.datetime.now())
				user_mentions.remove(user)
				await self.update_now_playing()

		old_len = len(self.whitelist)

		if option in ['+', 'add']:
			self.whitelist.update(user.id for user in user_mentions)

			write_file(self.config.whitelist_file, self.whitelist)

			return Response(
				':smirk_cat: **|** ***%s m-masters have been added to the whitelist.***' % (len(self.whitelist) - old_len),
				reply=True, delete_after=10
			)

		else:
			if self.whitelist.isdisjoint(user.id for user in user_mentions):
				return Response(':pouting_cat: **|** ***None of those m-masters are in the whitelist.***', reply=True, delete_after=10)

			else:
				self.whitelist.difference_update(user.id for user in user_mentions)
				write_file(self.config.blacklist_file, self.whitelist)

				return Response(
					':smile_cat: **|** ***%s m-masters have been removed from the whitelist.***' % (old_len - len(self.whitelist)),
					reply=True, delete_after=10
				)

	async def cmd_greet(self, message, server, channel, permissions, user_mentions):
		"""
		Usage:
			{command_prefix}greet
		Greets a member. This is kinda useless.
		"""
		if not user_mentions:
			await self.safe_send_message(channel, "Welcome to __**`{}`**__! A beautiful and friendly server, where you can expect to make lots of friends! Please find the rules channel and give it a read! If there is also a information channel, I'd check that out as well! Thanks for stopping in and we hope you enjoy your stay here and stick around!".format(message.author.server))
		else:
			for user in user_mentions.copy():
				if message.author.name == user.name:
					await self.safe_send_message(channel, "M-master {}, your already in the server you baka!".format(message.author.name))
				elif user.name == self.user.name:
					await self.safe_send_message(channel, "M-master {}, nice try but I'm already in the server D: thanks though <3!~".format(message.author.name))
				else:
					await self.safe_send_message(channel, "Welcome to __**`{0}`**__, {1}! A beautiful and friendly server, where you can expect to make lots of friends! Please find the rules channel and give it a read! If there is also a information channel, I'd check that out as well! Thanks for stopping in and we hope you enjoy your stay here and stick around!".format(message.author.server, user.mention))


	async def cmd_invite(self, message, server_link=None):
		"""
		Usage:
			{command_prefix}invite invite_link

		Asks the bot to join a server.  Note: Bot accounts cannot use invite links.
		"""

		if self.user.bot:
			url = await self.generate_invite_link()
			return Response(
				":smiley_cat: **|** ***I c-can serve other m-masters if you want m-me to~  Click h-here to invite me th-there: \nhttps://discordapp.com/oauth2/authorize?client_id=366772786573869058&scope=bot&permissions=536210479***",
				reply=True, delete_after=30
			)
		try:
			if server_link:
			    await self.accept_invite(server_link)
			    return Response(":thumbsup:")

		except:
			raise exceptions.CommandError('Invalid URL provided:\n{}\n'.format(server_link), expire_in=30)

	async def cmd_play(self, player, channel, author, permissions, leftover_args, song_url):
		"""
		Usage:
			{command_prefix}play link-to-a-song
			{command_prefix}play text to search for

		Adds the song to the playlist.  If a link is not provided, the first
		result from a youtube search is added to the queue.
		"""
		song_url = song_url.strip('<>')

		if permissions.max_songs and player.playlist.count_for_user(author) >= permissions.max_songs:
			raise exceptions.PermissionsError(
				"Y-you have reached your r-request limit m-master (%s)" % permissions.max_songs, expire_in=30
			)

		await self.send_typing(channel)

		if leftover_args:
			song_url = ' '.join([song_url, *leftover_args])

		try:
			info = await self.downloader.extract_info(player.playlist.loop, song_url, download=False, process=False)
		except Exception as e:
			raise exceptions.CommandError(e, expire_in=30)

		if not info:
			raise exceptions.CommandError("Th-that video cannot be p-played m-master.", expire_in=30)

		# abstract the search handling away from the user
		# our ytdl options allow us to use search strings as input urls
		if info.get('url', '').startswith('ytsearch'):
			# print("[Command:play] Searching for \"%s\"" % song_url)
			info = await self.downloader.extract_info(
				player.playlist.loop,
				song_url,
				download=False,
				process=True,    # ASYNC LAMBDAS WHEN
				on_error=lambda e: asyncio.ensure_future(
					self.safe_send_message(channel, "```\n%s\n```" % e, expire_in=120), loop=self.loop),
				retry_on_error=True
			)

			if not info:
				raise exceptions.CommandError(
					"Error extracting info f-from search string, youtubedl returned no d-data.  "
					"I m-may need to rest if th-this continues to happen.", expire_in=30
				)

			if not all(info.get('entries', [])):
				# empty list, no data
				return

			song_url = info['entries'][0]['webpage_url']
			info = await self.downloader.extract_info(player.playlist.loop, song_url, download=False, process=False)
			# Now I could just do: return await self.cmd_play(player, channel, author, song_url)
			# But this is probably fine

		# TODO: Possibly add another check here to see about things like the bandcamp issue
		# TODO: Where ytdl gets the generic extractor version with no processing, but finds two different urls

		if 'entries' in info:
			# I have to do exe extra checks anyways because you can request an arbitrary number of search results
			if not permissions.allow_playlists and ':search' in info['extractor'] and len(info['entries']) > 1:
				raise exceptions.PermissionsError("You\'re n-not allowed to t-tell me to do th-that m-master.", expire_in=30)

			# The only reason we would use this over `len(info['entries'])` is if we add `if _` to this one
			num_songs = sum(1 for _ in info['entries'])

			if permissions.max_playlist_length and num_songs > permissions.max_playlist_length:
				raise exceptions.PermissionsError(
					"Th-that list is way too m-much for me m-master! (%s > %s)" % (num_songs, permissions.max_playlist_length),
					expire_in=30
				)

			# This is a little bit weird when it says (x + 0 > y), I might add the other check back in
			if permissions.max_songs and player.playlist.count_for_user(author) + num_songs > permissions.max_songs:
				raise exceptions.PermissionsError(
					"I-I\'m at my l-limit for your queue m-master, I can\'t t-take anymore from you for n-now... (%s + %s > %s)" % (
						num_songs, player.playlist.count_for_user(author), permissions.max_songs),
					expire_in=30
				)

			if info['extractor'].lower() in ['youtube:playlist', 'soundcloud:set', 'bandcamp:album']:
				try:
					return await self._cmd_play_playlist_async(player, channel, author, permissions, song_url, info['extractor'])
				except exceptions.CommandError:
					raise
				except Exception as e:
					traceback.print_exc()
					raise exceptions.CommandError("I th-think I messed up somehow w-with the list \n%s" % e, expire_in=30)

			t0 = time.time()

			# My test was 1.2 seconds per song, but we maybe should fudge it a bit, unless we can
			# monitor it and edit the message with the estimated time, but that's some ADVANCED SHIT
			# I don't think we can hook into it anyways, so this will have to do.
			# It would probably be a thread to check a few playlists and get the speed from that
			# Different playlists might download at different speeds though
			wait_per_song = 1.2

			procmesg = await self.safe_send_message(
				channel,
				'[{}][INFO] Gathering playlist information for {} songs{}'.format(
					datetime.datetime.now(),
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
					print("[%s][WARNING] Dropped %s songs" % (datetime.datetime.now(), drop_count))

			print("[{}][INFO] Processed {} songs in {} seconds at {:.2f}s/song, {:+.2g}/song from expected ({}s)".format(
				datetime.datetime.now(), 
				listlen,
				self._fixg(ttime),
				ttime / listlen,
				ttime / listlen - wait_per_song,
				self._fixg(wait_per_song * num_songs))
			)

			await self.safe_delete_message(procmesg)

			if not listlen - drop_count:
				raise exceptions.CommandError(
					"Sorry m-master, I c-can\'t handle its full l-length... (%ss)" % permissions.max_song_length,
					expire_in=30
				)

			reply_text = ":smiley_cat: **|** ***Enqueued*** __*%s*__ ***for me to p-play.\nI\'ll g-get to it in*** __*%s*__ ***songs~***"
			btext = str(listlen - drop_count)

		else:
			if permissions.max_song_length and info.get('duration', 0) > permissions.max_song_length:
				raise exceptions.PermissionsError(
					"Sorry m-master, that exceeds my l-limits... (%s > %s)" % (info['duration'], permissions.max_song_length),
					expire_in=30
				)

			try:
				entry, position = await player.playlist.add_entry(song_url, channel=channel, author=author)

			except exceptions.WrongEntryTypeError as e:
				if e.use_url == song_url:
					print("[%s][WARNING] Determined incorrect entry type, but suggested url is the same.  Help." % datetime.datetime.now())

				if self.config.debug_mode:
					print("[%s][INFO] Assumed url \"%s\" was a single entry, was actually a playlist" % (datetime.datetime.now(), song_url))
					print("[%s][INFO] Using \"%s\" instead" % (datetime.datetime.now(), e.use_url))

				return await self.cmd_play(player, channel, author, permissions, leftover_args, e.use_url)

			reply_text = ":smiley_cat: **|** ***Enqueued*** __*`%s`*__ ***to be p-played.\nI\'ll play th-that*** %s"
			btext = entry.title

		if position == 1 and player.is_stopped:
			position = '***__next__!***'
			reply_text %= (btext, position)

		else:
			try:
				time_until = await player.playlist.estimate_time_until(position, player)
				reply_text += '***after*** __*`%s`*__ ***more audio tr-tracks.***'
			except:
				traceback.print_exc()
				
				time_until = ''

			reply_text %= (btext, '***in*** __*`'+str(time_until)+'`*__', position)

		return Response(reply_text, delete_after=30)

	async def _cmd_play_playlist_async(self, player, channel, author, permissions, playlist_url, extractor_type):
		"""
		Secret handler to use the async wizardry to make playlist queuing non-"blocking"
		"""

		await self.send_typing(channel)
		info = await self.downloader.extract_info(player.playlist.loop, playlist_url, download=False, process=False)

		if not info:
			raise exceptions.CommandError("I\'m sorry m-master... I can't s-seem to do th-that~")

		num_songs = sum(1 for _ in info['entries'])
		t0 = time.time()

		busymsg = await self.safe_send_message(
			channel, ":kissing_cat: **|** ***Processing*** __*`%s`*__ ***songs...***" % num_songs)  # TODO: From playlist_title
		await self.send_typing(channel)

		entries_added = 0
		if extractor_type == 'youtube:playlist':
			try:
				entries_added = await player.playlist.async_process_youtube_playlist(
					playlist_url, channel=channel, author=author)
				# TODO: Add hook to be called after each song
				# TODO: Add permissions

			except Exception:
				traceback.print_exc()
				raise exceptions.CommandError('I c-couldn\'t queue %s for s-some reason.' % playlist_url, expire_in=30)

		elif extractor_type.lower() in ['soundcloud:set', 'bandcamp:album']:
			try:
				entries_added = await player.playlist.async_process_sc_bc_playlist(
					playlist_url, channel=channel, author=author)
				# TODO: Add hook to be called after each song
				# TODO: Add permissions

			except Exception:
				traceback.print_exc()
				raise exceptions.CommandError('I c-couldn\'t queue %s for s-some reason.' % playlist_url, expire_in=30)


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
				print("[%s][WARNING] Dropped %s songs" % (datetime.datetime.now(), drop_count))

			if player.current_entry and player.current_entry.duration > permissions.max_song_length:
				await self.safe_delete_message(self.server_specific_data[channel.server]['last_np_msg'])
				self.server_specific_data[channel.server]['last_np_msg'] = None
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
		print("[INFO] Processed {}/{} songs in {} seconds at {:.2f}s/song, {:+.2g}/song from expected ({}s)".format(
			songs_processed,
			num_songs,
			self._fixg(ttime),
			ttime / num_songs,
			ttime / num_songs - wait_per_song,
			self._fixg(wait_per_song * num_songs))
		)

		if not songs_added:
			basetext = "[%s][WARNING] No songs were added, all songs were over max duration (%ss)" % (datetime.datetime.now(), permissions.max_song_length)
			if skipped:
				basetext += "\nAdditionally, the current song was skipped for being too long."

			raise exceptions.CommandError(basetext, expire_in=30)

		return Response(":smirk_cat: **|** ***Enqueued*** __*`{}`*__ ***songs to be played in*** __*`{}`*__ ***seconds.***".format(
			songs_added, self._fixg(ttime, 1)), delete_after=30)

	async def cmd_search(self, player, channel, author, permissions, leftover_args):
		"""
		Usage:
			{command_prefix}search SERVICE RESULTS SEARCH

		Searches a service for a video and adds it to the queue.
		- SERVICE: any one of the following services:
			- YouTube (yt) (default if unspecified)
			- SoundCloud (sc)
			- Yahoo (yh)
		- RESULTS: return a number of video results and waits for user to choose one
		  - defaults to 1 if unspecified
		  - note: If your search query starts with a number,
				  you must put your query in quotes
			- ex: {command_prefix}search 2 "I'm gonna show you crazy Nightcore"
		"""

		if permissions.max_songs and player.playlist.count_for_user(author) > permissions.max_songs:
			raise exceptions.PermissionsError(
				"I\'ve r-reached my maximum i-item limit m-master... (%s)" % permissions.max_songs,
				expire_in=30
			)

		def argcheck():
			if not leftover_args:
				raise exceptions.CommandError(
					"Please specify a search query.\n%s" % dedent(
						self.cmd_search.__doc__.format(command_prefix=self.config.command_prefix)),
					expire_in=60
				)

		argcheck()

		try:
			leftover_args = shlex.split(' '.join(leftover_args))
		except ValueError:
			raise exceptions.CommandError("Please quote your search query properly.", expire_in=30)

		service = 'youtube'
		items_requested = 3
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
			argcheck()

		if leftover_args[0].isdigit():
			items_requested = int(leftover_args.pop(0))
			argcheck()

			if items_requested > max_items:
				raise exceptions.CommandError("You c-cannot search for more th-than %s things m-master!" % max_items)

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

		search_msg = await self.send_message(channel, ":kissing_cat: **|** ***I'm l-looking...***")
		await self.send_typing(channel)

		try:
			info = await self.downloader.extract_info(player.playlist.loop, search_query, download=False, process=True)

		except Exception as e:
			await self.safe_edit_message(search_msg, str(e), send_if_fail=True)
			return
		else:
			await self.safe_delete_message(search_msg)

		if not info:
			return Response(":crying_cat_face: **|** ***S-sorry m-master, no videos c-could be fetched...***", delete_after=30)

		def check(m):
			return (
				m.content.lower()[0] in 'yn' or
				# hardcoded function name weeee
				m.content.lower().startswith('{}{}'.format(self.config.command_prefix, 'search')) or
				m.content.lower().startswith('exit'))

		for e in info['entries']:
			result_message = await self.safe_send_message(channel, "***Result %s of %s:*** %s" % (
				info['entries'].index(e) + 1, len(info['entries']), e['webpage_url']))

			confirm_message = await self.safe_send_message(channel, ":kissing_cat: **|** ***Is this okay m-master?*** *Type `y`, `n` or `exit`*")
			response_message = await self.wait_for_message(30, author=author, channel=channel, check=check)

			if not response_message:
				await self.safe_delete_message(result_message)
				await self.safe_delete_message(confirm_message)
				return Response(":crying_cat_face: **|** ***Okay n-nevermind~***", delete_after=30)

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

				await self.cmd_play(player, channel, author, permissions, [], e['webpage_url'])

				return Response(":smile_cat: **|** ***Alright, coming right up m-master~!***", delete_after=30)
			else:
				await self.safe_delete_message(result_message)
				await self.safe_delete_message(confirm_message)
				await self.safe_delete_message(response_message)

		return Response(":crying_cat_face: **|** ***Oh well...***", delete_after=30)

	async def cmd_song(self, player, channel, server, message):
		"""
		Usage:
			{command_prefix}song

		Displays the current song in chat.
		"""

		if player.current_entry:
			if self.server_specific_data[server]['last_np_msg']:
				await self.safe_delete_message(self.server_specific_data[server]['last_np_msg'])
				self.server_specific_data[server]['last_np_msg'] = None

			song_progress = str(timedelta(seconds=player.progress)).lstrip('0').lstrip(':')
			song_total = str(timedelta(seconds=player.current_entry.duration)).lstrip('0').lstrip(':')
			prog_str = '`[%s/%s]`' % (song_progress, song_total)

			if player.current_entry.meta.get('channel', False) and player.current_entry.meta.get('author', False):
				np_text = ":smile_cat: **|** ***Now playing:***__*`%s`*__\n***Commanded by:*** __*`%s`*__\n***My progress:*** **`%s`**" % (
					player.current_entry.title, player.current_entry.meta['author'].name, prog_str)
			else:
				np_text = ":smile_cat: **|** ***Now playing:***__*`%s`*__\n***My progress:*** `%s`" % (player.current_entry.title, prog_str)

			self.server_specific_data[server]['last_np_msg'] = await self.safe_send_message(channel, np_text)
			await self._manual_delete_check(message)
		else:
			return Response(
				':scream_cat: **|** ***There isn\'t a-anything I\'m doing m-master... Tell m-me what to do using `{}play`.***'.format(self.config.command_prefix),
				delete_after=30
			)

	async def cmd_link(self, server, player, channel, message, permissions, user_mentions):
		"""
		Useage:
			{command_prefix}link
		Gives you a link to the song currently playing
		"""
		await self.safe_send_message(channel, "{}, Here's the link to __*`{}`*__ m-master! \n{}".format(message.author.name, player.current_entry.title, player.current_entry.url))
		await self.safe_delete_message(message)
		await self.update_now_playing()



	async def cmd_join(self, channel, author, message, voice_channel, user_mentions):
		"""
		Usage:
			{command_prefix}join
		Call the bot to the summoner's voice channel.
		"""

		if not author.voice_channel:
			raise exceptions.CommandError('You are not in a voice channel!')

		voice_client = self.the_voice_clients.get(channel.server.id, None)
		if voice_client and voice_client.channel.server == author.voice_channel.server:
			await self.move_voice_client(author.voice_channel)
			await self.safe_send_message(channel, "{}, I've joined and established a connection with __**`{}`**__".format(message.author.name, author.voice_channel.name))
			await self.update_now_playing()
			return

		# move to _verify_vc_perms?
		chperms = author.voice_channel.permissions_for(author.voice_channel.server.me)

		if not chperms.connect:
			self.safe_print("[%s][WARNING]Cannot join channel \"%s\", no permission." % (datetime.datetime.now(), author.voice_channel.name))
			return Response(
				"```I c-can\'t join \"%s\", I\'m n-not allowed.```" % author.voice_channel.name,
				delete_after=25
			)

		elif not chperms.speak:
			self.safe_print("[%s][WARNING] Will not join channel \"%s\", no permission to speak." % (datetime.datetime.now(), author.voice_channel.name))
			return Response(
				"```I c-can\'t join \"%s\", I can\'t s-speak...```" % author.voice_channel.name,
				delete_after=25
			)

		player = await self.get_player(author.voice_channel, create=True)

		if player.is_stopped:
			await self.safe_send_message(channel, "{}, I've joined and established a connection with __**`{}`**__".format(message.author.name, author.voice_channel.name))
			player.play()
			await self.update_now_playing()

		if self.config.auto_playlist:
			await self.on_player_finished_playing(player)

	async def cmd_pause(self, player, message, server, channel, permissions, user_mentions):
		"""
		Usage:
			{command_prefix}pause
		Pauses playback of the current song.
		"""

		if player.is_playing:
			await self.safe_send_message(channel, message.author.mention + " has paused music playback, use %sresume to resume" % self.config.command_prefix)
			await self.update_now_playing()
			player.pause()

		else:
			raise exceptions.CommandError('I\'m not p-playing anything m-master, queue something with %splay' % self.config.command_prefix, expire_in=30)

	async def cmd_resume(self, player, message, server, channel, permissions, user_mentions):
		"""
		Usage:
			{command_prefix}resume
		Resumes playback of a paused song.
		"""

		if player.is_paused:
			await self.safe_send_message(channel, "Resuming music playback, " + message.author.mention + ", use %spause to pause" % self.config.command_prefix)
			await self.update_now_playing()
			player.resume()
		else:
			raise exceptions.CommandError('I\'m already doing that m-master...', expire_in=30)

	async def cmd_playhits(self, channel, player, message, author, permissions, user_mentions):
		"""
		Usage
			[command_prefix]playhits
		Starts an auto playlist of hit songs linked here ``
		"""
		await self.safe_send_message(channel, "{}, starting `hits` playlist.".format(message.author.name))
		await self.cmd_play(player, channel, author, permissions, [], song_url='https://www.youtube.com/playlist?list=PLx0sYbCqOb8TBPRdmBHs5Iftvv9TPboYG')

	async def cmd_playvamps(self, channel, player, message, author, permissions, user_mentions):
		"""
		Usage
			[command_prefix]playvamps
		Starts an auto playlist of Vamp songs linked here ``
		"""
		await self.safe_send_message(channel, "{}, starting `The Vamps` playlist!".format(message.author.name))
		await self.cmd_play(player, channel, author, permissions, [], song_url='https://www.youtube.com/playlist?list=PLrFYFjhPeDLa0oEQPnd_8d7vrSSqatCCx')

	async def cmd_playlove(self, channel, player, message, author, permissions, user_mentions):
		"""
		Usage
			[command_prefix]playlove
		Starts an auto playlist of love songs linked here ``
		"""
		await self.safe_send_message(channel, "{}, starting `cute love songs` playlist! <3~".format(message.author.name))
		await self.cmd_play(player, channel, author, permissions, [], song_url='https://www.youtube.com/playlist?list=PLi8Ca0H-BLi4drbjhFf2KuFKqt9f8g4pC')

	async def cmd_playnightcore(self, channel, player, message, author, permissions, user_mentions):
		"""
		Usage
			[command_prefix]play
		Starts an auto playlist of nightcore mashup songs linked here ``
		"""
		await self.safe_send_message(channel, "{}, starting `Nightcore` playlist!".format(message.author.name))
		await self.cmd_play(player, channel, author, permissions, [], song_url='https://www.youtube.com/playlist?list=PLBjhmdjwU6_o_REEy423TMOFh4wro-JDv')

	async def cmd_playanime(self, channel, player, message, author, permissions, user_mentions):
		"""
		Usage
			[command_prefix]playanime
		Starts an auto playlist of anime songs linked here ``
		"""
		await self.safe_send_message(channel, "{}, starting `Anime` playlist!".format(message.author.name))
		await self.cmd_play(player, channel, author, permissions, [], song_url='https://www.youtube.com/playlist?list=PL0qJTCwqrAenBfISaZ86b9ocYHIUl8tXu')
		await self.safe_delete_message(message)

	async def cmd_playsad(self, channel, player, message, author, permissions, user_mentions):
		"""
		Usage
			[command_prefix]playsad
		Starts an auto playlist of sad themed songs linked here ``
		"""
		await self.safe_send_message(channel, "{}, starting `sad` playlist!".format(message.author.name))
		await self.cmd_play(player, channel, author, permissions, [], song_url='https://www.youtube.com/playlist?list=PLi8Ca0H-BLi6GMqd89d40Z1xBkYTMeh01')

	async def cmd_playbedtime(self, channel, player, message, author, permissions, user_mentions):
		"""
		Usage
			[command_prefix]play
		Starts an auto playlist of songs linked to stimulate anxietyt reduction and induce sleep songs linked here ``
		"""
		await self.safe_send_message(channel, "{}, starting `bedtime` playlist!".format(message.author.name))
		await self.cmd_play(player, channel, author, permissions, [], song_url='https://www.youtube.com/playlist?list=PLi8Ca0H-BLi4NRdtj55L1RW-IDl8s5-pj&jct=wnmAeRA2dMfrapuv3NeQGKl1pkyFLg')

	async def cmd_playdub(self, channel, player, message, author, permissions, user_mentions):
		"""
		Usage
			[command_prefix]playdub
		Starts an auto playlist of dubstep songs linked here ``
		"""
		await self.safe_send_message(channel, "{}, starting `dubstep` playlist!".format(message.author.name))
		await self.cmd_play(player, channel, author, permissions, [], song_url='https://www.youtube.com/playlist?list=PLxGj5zdsQ1WsMkV1qvReTiexVAgTisXew')

	async def cmd_playbg(self, channel, player, message, author, permissions, user_mentions):
		"""
		Usage
			[command_prefix]playbg
		Starts an auto playlist of background songs linked here ``
		"""
		await self.safe_send_message(channel, "{}, starting `background` music playlist!".format(message.author.name))
		await self.cmd_play(player, channel, author, permissions, [], song_url='https://www.youtube.com/playlist?list=PLAE6EB41B485F610A')

	async def cmd_playhiphop(self,channel, player, message, author, permissions, user_mentions):
		"""
		Usage
			[command_prefix]playhiphop
		Starts an auto playlist of hip-hop songs linked here ``
		"""
		await self.safe_send_message(channel, "{}, starting `Current hip-hip/new rap music` playlist!".format(message.author.name))
		await self.cmd_play(player, channel, author, permissions, [], song_url='https://www.youtube.com/watch?v=SC4xMk98Pdc&list=PLw-VjHDlEOgsIgak3vJ7mrcy-OscZ6OAs')

	async def cmd_playlogic(self,channel, player, message, author, permissions, user_mentions):
		"""
		Usage
			[command_prefix]playlogic
		Starts an auto playlist of songs by Logic the rapper songs linked here ``
		"""
		await self.safe_send_message(channel, "{}, starting `logic` playlist!".format(message.author.name))
		await self.cmd_play(player, channel, author, permissions, [], song_url='https://www.youtube.com/playlist?list=PLad7omy-Nv2Af20oUOWzOX7-wLgMiOcLQ')
		await self.safe_delete_message(message)

	async def cmd_shuffle(self, channel, player, message, author, user_mentions):
		"""
		Usage:
			{command_prefix}shuffle
			{command_prefix}mix

		Shuffles the playlist.
		"""

		player.playlist.shuffle()

		cards = [':one:',':two:',':three:',':four:']
		hand = await self.safe_send_message(channel, ' '.join(cards))
		await asyncio.sleep(0.6)

		for x in range(4):
			shuffle(cards)
			await self.safe_edit_message(hand, ' '.join(cards))
			await asyncio.sleep(0.6)

		await self.safe_delete_message(hand, quiet=True)
		return Response("**Playlist Shuffled**"+ message.author.mention + ":ok_hand:", delete_after=15)

	async def cmd_clear(self, player, author, message, user_mentions):
		"""
		Usage:
			{command_prefix}clear

		Clears the playlist.
		"""

		player.playlist.clear()
		return Response(':crying_cat_face: **|** I\'ve c-cleared my queue,' + message.author.mention, delete_after=20)
		await self.update_now_playing()
		await self.safe_delete_message(message)

	async def cmd_skip(self, player, channel, author, message, permissions, voice_channel):
		"""
		Usage:
			{command_prefix}skip
			{command_prefix}next

		Skips the current song when enough votes are cast, or by the bot owner.
		"""

		if player.is_stopped:
			raise exceptions.CommandError(":scream_cat:**|** I\'m not even doing anything m-master~!", expire_in=20)

		if not player.current_entry:
			if player.playlist.peek():
				if player.playlist.peek()._is_downloading:
					# print(player.playlist.peek()._waiting_futures[0].__dict__)
					return Response("I\'m s-still writing \"%s\" down m-master..." % player.playlist.peek().title)

				elif player.playlist.peek().is_downloaded:
					print("[%s][INFO] The next song will be played shortly.  Please wait." % datetime.datetime.now())
				else:
					print("[%s][WARNING] Something odd is happening.  "
						  "You might want to restart the bot if it doesn't start working." % datetime.datetime.now())
			else:
				print("[%s][WARNING] Something strange is happening.  "
					  "You might want to restart the bot if it doesn't start working." % datetime.datetime.now())


		# TODO: ignore person if they're deaf or take them out of the list or something?
		# Currently is recounted if they vote, deafen, then vote

		num_voice = sum(1 for m in voice_channel.voice_members if not (
			m.deaf or m.self_deaf or m.id in [self.config.owner_id, self.user.id]))

		num_skips = player.skip_state.add_skipper(author.id, message)

		skips_remaining = min(self.config.skips_required,
							  sane_round_int(num_voice * self.config.skip_ratio_required)) - num_skips

		if skips_remaining <= 0:
			player.skip()  # check autopause stuff here
			return Response(
				':smiley_cat: **|** ***Your skip for*** __*`{}`*__ ***was acknowledged.***'
				'\n***The vote to skip has been passed.***{}'.format(
					player.current_entry.title,
					' ***I\'ll d-do that r-right away!***' if player.playlist.peek() else ''
				),
				reply=True,
				delete_after=20
			)

		else:
			# TODO: When a song gets skipped, delete the old x needed to skip messages
			return Response(
				':smiley_cat: **|** ***Your skip for*** __*`{}`*__ ***was acknowledged.***'
				'\n__*`{}`*__ ***more {} r-required for m-me to do it.***'.format(
					player.current_entry.title,
					skips_remaining,
					'master is' if skips_remaining == 1 else 'masters are'
				),
				reply=True,
				delete_after=20
			)



	async def cmd_volume(self, message, server, channel, permissions, user_mentions, player, new_volume=None):
		"""
		Usage:
			{command_prefix}volume (+/-)[volume]
			{command_prefix}sound (+/-)[volume]
			{command_prefix}level (+/-)[volume]

		Sets the playback volume. Accepted values are from 1 to 500.
		Putting + or - before the volume will make the volume change relative to the current volume.
		"""

		if not new_volume:
			return Response('\n:smiley_cat: **|** ***Currently speaking at `%s%%`***' % int(player.volume * 100), reply=True, delete_after=20)

		relative = False
		if new_volume[0] in '+-':
			relative = True

		try:
			new_volume = int(new_volume)

		except ValueError:
			raise exceptions.CommandError('{} is not a valid number.'.format(new_volume), expire_in=20)

		if relative:
			vol_change = new_volume
			new_volume += (player.volume * 100)

		old_volume = int(player.volume * 100)

		if 0 < new_volume <= 500:
			player.volume = new_volume / 100.0

			return Response('\n:smile_cat: **|** ***I\'ll try to s-speak from `%d%%` to `%d%%` now m-master~***' % (old_volume, new_volume), reply=True, delete_after=20)

		else:
			if relative:
				raise exceptions.CommandError(
					'Ã°Å¸ËœÂ½ | Unreasonable volume change provided: {}{:+} -> {}%.  Provide a change between {} and {:+}.'.format(
						old_volume, vol_change, old_volume + vol_change, 1 - old_volume, 100 - old_volume), expire_in=20)
			else:
				raise exceptions.CommandError(
					'Ã°Å¸ËœÂ½ | Unreasonable volume provided: {}%. Provide a value between 1 and 500.***'.format(new_volume), expire_in=20)

	async def cmd_ap(self, channel, author, player, voice_channel):
		"""
		Usage:
		{command_prefix}ap

			Toggle the autoplaylist on and off
		"""
		self.config.auto_playlist = not self.config.auto_playlist
		await self.safe_send_message(channel, "The autoplaylist is now " + ['disabled', 'enabled'][self.config.auto_playlist])
		if not player.playlist.entries and not player.current_entry and self.config.auto_playlist: #if nothing is queued, start a song
			song_url = random.choice(self.autoplaylist)
			await player.playlist.add_entry(song_url, channel=None, author=None)

	async def cmd_playlist(self, channel, player):
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
			prog_str = '`[Progress: %s/%s]`' % (song_progress, song_total)

			if player.current_entry.meta.get('channel', False) and player.current_entry.meta.get('author', False):
				lines.append("***Now Playing:*** __*`%s`*__ ***added by*** __*`%s`*__ __*`%s`*__\n" % (
					player.current_entry.title, player.current_entry.meta['author'].name, prog_str))
			else:
				lines.append("***Now Playing:*** __*`%s`*__ __*`%s`*__\n" % (player.current_entry.title, prog_str))

		for i, item in enumerate(player.playlist, 1):
			if item.meta.get('channel', False) and item.meta.get('author', False):
				nextline = '`{}.` **{}** added **\"{}\"**'.format(i, item.meta['author'].name, item.title).strip()
			else:
				nextline = '`{}.` **{}**'.format(i, item.title).strip()

			currentlinesum = sum(len(x) + 1 for x in lines)  # +1 is for newline char

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

	async def cmd_cleanup(self, message, channel, server, author, search_range=100):
		"""
		Usage:
			{command_prefix}clean [range]

		Removes up to [range] messages the bot has posted in chat. Default: 100, Max: 1000
		"""

		try:
			float(search_range)  # lazy check
			search_range = min(int(search_range), 1000)
		except:
			return Response("enter a number.  NUMBER.  That means digits.  `15`.  Etc.", reply=True, delete_after=8)

		await self.safe_delete_message(message, quiet=True)

		def is_possible_command_invoke(entry):
			valid_call = any(
				entry.content.startswith(prefix) for prefix in [self.config.command_prefix])  # can be expanded
			return valid_call and not entry.content[1:2].isspace()

		delete_invokes = True
		delete_all = channel.permissions_for(author).manage_messages or self.config.owner_id == author.id

		def check(message):
			if is_possible_command_invoke(message) and delete_invokes:
				return delete_all or message.author == author
			return message.author == self.user

		if self.user.bot:
			if channel.permissions_for(server.me).manage_messages:
				deleted = await self.purge_from(channel, check=check, limit=search_range, before=message)
				return Response('Cleaned up {} message{}.'.format(len(deleted), 's' * bool(deleted)), delete_after=15)

		deleted = 0
		async for entry in self.logs_from(channel, search_range, before=message):
			if entry == self.server_specific_data[channel.server]['last_np_msg']:
				continue

			if entry.author == self.user:
				await self.safe_delete_message(entry)
				deleted += 1
				await asyncio.sleep(0.21)

			if is_possible_command_invoke(entry) and delete_invokes:
				if delete_all or entry.author == author:
					try:
						await self.delete_message(entry)
						await asyncio.sleep(0.21)
						deleted += 1

					except discord.Forbidden:
						delete_invokes = False
					except discord.HTTPException:
						pass

		return Response('Cleaned up {} message{}.'.format(deleted, 's' * bool(deleted)), delete_after=15)

		def searchSong(self, song_name):
			print("[Lyrics] Song name: " + song_name)
			encondedsongname = urllib.parse.quote_plus(song_name)
			print("[Lyrics] Search url: " + encondedsongname)
			page = requests.get('http://lyrics.wikia.com/wiki/Special:Search?query=' + encondedsongname)
			tree = html.fromstring(page.content)
			songs = tree.xpath('//li[@class="result"]/article/h1/a/text()')

	async def cmd_pldump(self, message, server, song_url, channel, permissions, user_mentions):
		"""
		Usage:
			{command_prefix}pldump url

		Dumps the individual urls of a playlist
		"""
		owner = self._get_owner()
		output = await self.safe_send_message(message.channel, "{0} your playlist has beed noted ^o^ and my master will be alerted. \n{1}".format(message.author.mention, owner.mention))


		try:
			info = await self.downloader.extract_info(self.loop, song_url.strip('<>'), download=False, process=False)
		except Exception as e:
			raise exceptions.CommandError("Could not extract info from input url\n%s\n" % e, expire_in=25)

		if not info:
			raise exceptions.CommandError("Could not extract info from input url, no data.", expire_in=25)

		if not info.get('entries', None):
			# TODO: Retarded playlist checking
			# set(url, webpageurl).difference(set(url))

			if info.get('url', None) != info.get('webpage_url', info.get('url', None)):
				raise exceptions.CommandError("This does not seem to be a playlist.", expire_in=25)
			else:
				return await self.cmd_pldump(channel, info.get(''))

		linegens = defaultdict(lambda: None, **{
			"youtube":    lambda d: 'https://www.youtube.com/watch?v=%s' % d['id'],
			"soundcloud": lambda d: d['url'],
			"bandcamp":   lambda d: d['url']
		})

		exfunc = linegens[info['extractor'].split(':')[0]]

		if not exfunc:
			raise exceptions.CommandError("Could not extract info from input url, unsupported playlist type.", expire_in=25)

		with BytesIO() as fcontent:
			for item in info['entries']:
				fcontent.write(exfunc(item).encode('utf8') + b'\n')

			fcontent.seek(0)
			await self.send_file(channel, fcontent, filename='playlist.txt', content="Here's the url dump for <%s>" % song_url)

	async def cmd_listids(self, server, author, leftover_args, cat='all'):
		"""
		Usage:
			{command_prefix}listids [categories]

		Lists the ids for various things.  Categories are:
		   all, users, roles, channels
		"""

		cats = ['channels', 'roles', 'users']

		if cat not in cats and cat != 'all':
			return Response(
				"Valid categories: " + ' '.join(['`%s`' % c for c in cats]),
				reply=True,
				delete_after=25
			)

		if cat == 'all':
			requested_cats = cats
		else:
			requested_cats = [cat] + [c.strip(',') for c in leftover_args]

		data = ['Your ID: %s' % author.id]

		for cur_cat in requested_cats:
			rawudata = None

			if cur_cat == 'users':
				data.append("\nUser IDs:")
				rawudata = ['%s #%s: %s' % (m.name, m.discriminator, m.id) for m in server.members]

			elif cur_cat == 'roles':
				data.append("\nRole IDs:")
				rawudata = ['%s: %s' % (r.name, r.id) for r in server.roles]

			elif cur_cat == 'channels':
				data.append("\nText Channel IDs:")
				tchans = [c for c in server.channels if c.type == discord.ChannelType.text]
				rawudata = ['%s: %s' % (c.name, c.id) for c in tchans]

				rawudata.append("\nVoice Channel IDs:")
				vchans = [c for c in server.channels if c.type == discord.ChannelType.voice]
				rawudata.extend('%s: %s' % (c.name, c.id) for c in vchans)

			if rawudata:
				data.extend(rawudata)

		with BytesIO() as sdata:
			sdata.writelines(d.encode('utf8') + b'\n' for d in data)
			sdata.seek(0)

			# TODO: Fix naming (Discord20API-ids.txt)
			await self.send_file(author, sdata, filename='%s-ids-%s.txt' % (server.name.replace(' ', '_'), cat))

		return Response(":mailbox_with_mail:", delete_after=20)


	async def cmd_perms(self, author, channel, server, permissions):
		"""
		Usage:
			{command_prefix}perms

		Sends the user a list of their permissions.
		"""

		lines = ['Command permissions in %s\n' % server.name, '```', '```']

		for perm in permissions.__dict__:
			if perm in ['user_list'] or permissions.__dict__[perm] == set():
				continue

			lines.insert(len(lines) - 1, "%s: %s" % (perm, permissions.__dict__[perm]))

		await self.send_message(author, '\n'.join(lines))
		return Response(":mailbox_with_mail:", delete_after=20)
		await self.update_now_playing()
		await self.safe_delete_message(message)


	@owner_only
	async def cmd_setname(self, leftover_args, name):
		"""
		Usage:
			{command_prefix}setname name

		Changes the bot's username.
		Note: This operation is limited by discord to twice per hour.
		"""

		name = ' '.join([name, *leftover_args])

		try:
			await self.edit_profile(username=name)
		except Exception as e:
			raise exceptions.CommandError(e, expire_in=20)

		return Response(":ok_hand:", delete_after=20)

	async def cmd_setnick(self, server, channel, leftover_args, nick):
		"""
		Usage:
			{command_prefix}setnick nick

		Changes the bot's nickname.
		"""

		if not channel.permissions_for(server.me).change_nickname:
			raise exceptions.CommandError("Unable to change nickname: no permission.")

		nick = ' '.join([nick, *leftover_args])

		try:
			await self.change_nickname(server.me, nick)
		except Exception as e:
			raise exceptions.CommandError(e, expire_in=20)

		return Response(":ok_hand:", delete_after=20)

	@owner_only
	async def cmd_setavatar(self, message, url=None):
		"""
		Usage:
			{command_prefix}setavatar [url]

		Changes the bot's avatar.
		Attaching a file and leaving the url parameter blank also works.
		"""

		if message.attachments:
			thing = message.attachments[0]['url']
		else:
			thing = url.strip('<>')

		try:
			with aiohttp.Timeout(10):
				async with self.aiosession.get(thing) as res:
					await self.edit_profile(avatar=await res.read())

		except Exception as e:
			raise exceptions.CommandError("Unable to change avatar: %s" % e, expire_in=20)

		return Response(":ok_hand:", delete_after=20)


	async def cmd_leave(self, server, channel, message, author, permissions, player, voice_channel, user_mentions):
		"""
		Usage:
			{command_prefix}leave
		Makes the bot leave the voice channel it is in for that server.
		"""
		await self.disconnect_voice_client(server)
		await self.update_now_playing()
		return Response("{}, I've left the voice channel __**`{}`**__".format(message.author.name, player.voice_client.channel.name))
		await self.safe_delete_message(message)

	async def cmd_restart(self, channel, message, server, permissions, user_mentions):
		"""
		Usage
			{command_prefix}restart
		Restarts the bot, making it leave all voice channels, this also opens a new command prompt, with any saved changes to bot.py.
		"""
		for s in self.servers:
			await self.safe_send_message(channel, message.author.name+ " has restarted the bot. Sorry for the inconvience.")
			await self.disconnect_all_voice_clients()
			p = subprocess.Popen('runbot.bat', creationflags=subprocess.CREATE_NEW_CONSOLE)
			raise exceptions.TerminateSignal
			await self.safe_delete_message(message)

	async def cmd_shutdown(self, channel, server, message, permissions, user_mentions):
		"""
		Usage
			{command_prefix}shutdown
		Shutsdown the bot, making it leave all the voice channels and ending the pipline connection.
		"""
		await self.safe_send_message(channel, ":crying_cat_face: **|** ***B-bye senpai " + message.author.mention + "... S-see you later I hope~***")
		await self.disconnect_all_voice_clients()
		raise exceptions.TerminateSignal
		await self.safe_delete_message(message)

	async def on_message(self, message):
		await self.wait_until_ready()

		message_content = message.content.strip()
		if not message_content.startswith(self.config.command_prefix):
			return

		if self.config.bound_channels and message.channel.id not in self.config.bound_channels and not message.channel.is_private:
			return  # if I want to log this I just move it under the prefix check

		command, *args = message_content.split()  # Uh, doesn't this break prefixes with spaces in them (it doesn't, config parser already breaks them)
		command = command[len(self.config.command_prefix):].lower().strip()

		handler = getattr(self, 'cmd_%s' % command, None)
		if not handler:
			return



		if message.author.id in self.blacklist and message.author.id != self.config.owner_id:
			self.safe_print("[INFO] Blacklisting user {0.id}/{0.name} ({1})".format(message.author, message_content))
			return
		
		if message.author.id in self.whitelist and message.author.id != self.config.owner_id:
			self.safe_print("[INFO] Whitelisting user {0.id}/{0.name} ({1})".format(message.author, message_content))
			return

		else:
			self.safe_print("[INFO] Command {0.id}/{0.name} ({1})".format(message.author, message_content))

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
				if message.channel.is_private:
					handler_kwargs['user_mentions'] = message.channel.recipients
				else:
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
					raise exceptions.PermissionsError(
						"This command is not enabled for your group (%s)." % user_permissions.name,
						expire_in=20)

				elif user_permissions.command_blacklist and command in user_permissions.command_blacklist:
					raise exceptions.PermissionsError(
						"This command is disabled for your group (%s)." % user_permissions.name,
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

				sentmsg = await self.safe_send_message(
					message.channel, content,
					expire_in=response.delete_after if self.config.delete_messages else 0,
					also_delete=message if self.config.delete_invoking else None
				)

		except (exceptions.CommandError, exceptions.HelpfulError, exceptions.ExtractionError) as e:
			print("{0.__class__}: {0.message}".format(e))

			expirein = e.expire_in if self.config.delete_messages else None
			alsodelete = message if self.config.delete_invoking else None

			await self.safe_send_message(
				message.channel,
				'```\n%s\n```' % e.message,
				expire_in=expirein,
				also_delete=alsodelete
			)

		except exceptions.Signal:
			raise

		except Exception:
			traceback.print_exc()
			if self.config.debug_mode:
				await self.safe_send_message(message.channel, '```\n%s\n```' % traceback.format_exc())

	async def on_voice_state_update(self, before, after):
		if not all([before, after]):
			return

		if before.voice_channel == after.voice_channel:
			return

		if before.server.id not in self.players:
			return

		my_voice_channel = after.server.me.voice_channel  # This should always work, right?

		if not my_voice_channel:
			return

		if before.voice_channel == my_voice_channel:
			joining = False
		elif after.voice_channel == my_voice_channel:
			joining = True
		else:
			return  # Not my channel

		moving = before == before.server.me

		auto_paused = self.server_specific_data[after.server]['auto_paused']
		player = await self.get_player(my_voice_channel)

		if after == after.server.me and after.voice_channel:
			player.voice_client.channel = after.voice_channel

		if not self.config.auto_pause:
			return

		if sum(1 for m in my_voice_channel.voice_members if m != after.server.me):
			if auto_paused and player.is_paused:
				print("[%s][INFO] Unpausing" % datetime.datetime.now())
				self.server_specific_data[after.server]['auto_paused'] = False
				player.resume()
		else:
			if not auto_paused and player.is_playing:
				print("[%s][INFO] Pausing" % datetime.datetime.now())
				self.server_specific_data[after.server]['auto_paused'] = True
				player.pause()

	async def on_server_update(self, before:discord.Server, after:discord.Server):
		if before.region != after.region:
			self.safe_print("[%s][INFO] \"%s\" changed regions: %s -> %s" % (datetime.datetime.now(), after.name, before.region, after.region))

			await self.reconnect_voice_client(after)


if __name__ == '__main__':
	bot = MusicBot()
	bot.run()
