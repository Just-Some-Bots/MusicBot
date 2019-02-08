from discord import VoiceChannel, Member
from .utils import add_method
from .constructs import SkipState
import logging

log = logging.getLogger(__name__)

class ManagedVC:
    def __init__(self, vc: VoiceChannel):
        self._vc = vc
        self._player = None

    def _init_player(self, player: MusicPlayer):
        player = player.on('play', self.on_player_play) \
                       .on('resume', self.on_player_resume) \
                       .on('pause', self.on_player_pause) \
                       .on('stop', self.on_player_stop) \
                       .on('finished-playing', self.on_player_finished_playing) \
                       .on('entry-added', self.on_player_entry_added) \
                       .on('error', self.on_player_error)

        player.skip_state = SkipState()

        self._player = player

        return player

    async def kill_player(self):
        pass

    async def on_player_play(self, player: MusicPlayer, entry):
        log.debug('Running on_player_play')
        await self.update_now_playing_status(entry)
        player.skip_state.reset()

        # This is the one event where its ok to serialize autoplaylist entries
        await self.serialize_queue(player.voice_client.channel.guild)

        if self.config.write_current_song:
            await self.write_current_song(player.voice_client.channel.guild, entry)

        channel = entry.meta.get('channel', None)
        author = entry.meta.get('author', None)

        if channel and author:
            last_np_msg = self.server_specific_data[channel.guild]['last_np_msg']
            if last_np_msg and last_np_msg.channel == channel:

                async for lmsg in channel.history(limit=1):
                    if lmsg != last_np_msg and last_np_msg:
                        await self.safe_delete_message(last_np_msg)
                        self.server_specific_data[channel.guild]['last_np_msg'] = None
                    break  # This is probably redundant

            author_perms = self.permissions.for_user(author)

            if author not in player.voice_client.channel.members and author_perms.skip_when_absent:
                newmsg = 'Skipping next song in `%s`: `%s` added by `%s` as queuer not in voice' % (
                    player.voice_client.channel.name, entry.title, entry.meta['author'].name)
                player.skip()
            elif self.config.now_playing_mentions:
                newmsg = '%s - your song `%s` is now playing in `%s`!' % (
                    entry.meta['author'].mention, entry.title, player.voice_client.channel.name)
            else:
                newmsg = 'Now playing in `%s`: `%s` added by `%s`' % (
                    player.voice_client.channel.name, entry.title, entry.meta['author'].name)

            if self.server_specific_data[channel.guild]['last_np_msg']:
                self.server_specific_data[channel.guild]['last_np_msg'] = await self.safe_edit_message(last_np_msg, newmsg, send_if_fail=True)
            else:
                self.server_specific_data[channel.guild]['last_np_msg'] = await self.safe_send_message(channel, newmsg)

        # TODO: Check channel voice state?

    async def on_player_resume(self, player: MusicPlayer, entry, **_):
        log.debug('Running on_player_resume')
        await self.update_now_playing_status(entry)

    async def on_player_pause(self, player: MusicPlayer, entry, **_):
        log.debug('Running on_player_pause')
        await self.update_now_playing_status(entry, True)
        # await self.serialize_queue(player.voice_client.channel.guild)

    async def on_player_stop(self, player: MusicPlayer, **_):
        log.debug('Running on_player_stop')
        await self.update_now_playing_status()

    async def on_player_finished_playing(self, player: MusicPlayer, **_):
        log.debug('Running on_player_finished_playing')
        def _autopause(player):
            if self._check_if_empty(player.voice_client.channel):
                log.info("Player finished playing, autopaused in empty channel")

                player.pause()
                self.server_specific_data[player.voice_client.channel.guild]['auto_paused'] = True

        if not player.playlist.entries and not player.current_entry and self.config.auto_playlist:
            if not player.autoplaylist:
                if not self.autoplaylist:
                    # TODO: When I add playlist expansion, make sure that's not happening during this check
                    log.warning("No playable songs in the autoplaylist, disabling.")
                    self.config.auto_playlist = False
                else:
                    log.debug("No content in current autoplaylist. Filling with new music...")
                    player.autoplaylist = list(self.autoplaylist)

            while player.autoplaylist:
                if self.config.auto_playlist_random:
                    random.shuffle(player.autoplaylist)
                    song_url = random.choice(player.autoplaylist)
                else:
                    song_url = player.autoplaylist[0]
                player.autoplaylist.remove(song_url)

                info = {}

                try:
                    info = await self.downloader.extract_info(player.playlist.loop, song_url, download=False, process=False)
                except downloader.youtube_dl.utils.DownloadError as e:
                    if 'YouTube said:' in e.args[0]:
                        # url is bork, remove from list and put in removed list
                        log.error("Error processing youtube url:\n{}".format(e.args[0]))

                    else:
                        # Probably an error from a different extractor, but I've only seen youtube's
                        log.error("Error processing \"{url}\": {ex}".format(url=song_url, ex=e))

                    await self.remove_from_autoplaylist(song_url, ex=e, delete_from_ap=self.config.remove_ap)
                    continue

                except Exception as e:
                    log.error("Error processing \"{url}\": {ex}".format(url=song_url, ex=e))
                    log.exception()

                    self.autoplaylist.remove(song_url)
                    continue

                if info.get('entries', None):  # or .get('_type', '') == 'playlist'
                    log.debug("Playlist found but is unsupported at this time, skipping.")
                    # TODO: Playlist expansion

                # Do I check the initial conditions again?
                # not (not player.playlist.entries and not player.current_entry and self.config.auto_playlist)

                if self.config.auto_pause:
                    player.once('play', lambda player, **_: _autopause(player))

                try:
                    await player.playlist.add_entry(song_url, channel=None, author=None)
                except exceptions.ExtractionError as e:
                    log.error("Error adding song from autoplaylist: {}".format(e))
                    log.debug('', exc_info=True)
                    continue

                break

            if not self.autoplaylist:
                # TODO: When I add playlist expansion, make sure that's not happening during this check
                log.warning("No playable songs in the autoplaylist, disabling.")
                self.config.auto_playlist = False

        else: # Don't serialize for autoplaylist events
            await self.serialize_queue(player.voice_client.channel.guild)

        if not player.is_stopped and not player.is_dead:
            player.play(_continue=True)

    async def on_player_entry_added(self, player: MusicPlayer, playlist, entry, **_):
        log.debug('Running on_player_entry_added')
        if entry.meta.get('author') and entry.meta.get('channel'):
            await self.serialize_queue(player.voice_client.channel.guild)

    async def on_player_error(self, player: MusicPlayer, entry, ex, **_):
        if 'channel' in entry.meta:
            await self.safe_send_message(
                entry.meta['channel'],
                "```\nError from FFmpeg:\n{}\n```".format(ex)
            )
        else:
            log.exception("Player error", exc_info=ex)

    def is_empty(self, exclude_me = True, exclude_deaf = False):
        def check(member: Member):
            if exclude_me and member == self._vc.guild.me:
                return False

            if exclude_deaf and any([member.voice.deaf, member.voice.self_deaf]):
                return False

            return True

        return not sum(1 for m in self._vc.members if check(m))

    async def get_voice_client(self):
        if self._vc.guild.voice_client:
            return self._vc.guild.voice_client
        else:
            return await self._vc.connect(timeout=60, reconnect=True)

    async def disconnect_voice_client(self):
        pass

    async def set_voice_state(self, *, mute=False, deaf=False):
        await self._vc.ws.voice_state(self._vc.guild.id, self._vc.id, mute, deaf)
        # I hope I don't have to set the channel here
        # instead of waiting for the event to update it

    async def write_current_song(self, *, dir=None):
        """
        Writes the current song to file
        """
        player = self._player
        if not player:
            return

        if dir is None:
            dir = 'data/%s/current.txt' % self._vc.guild.id

        async with self.aiolocks['current_song' + ':' + str(self._vc.guild.id)]:
            log.debug("Writing current song for %s", self._vc.guild.id)

            with open(dir, 'w', encoding='utf8') as f:
                f.write(self._player._current_entry.title)

