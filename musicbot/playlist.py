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
        プレイリストは、再生される曲のリストを管理します。
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

    async def add_entry(self, song_url, **meta):
        """
            再生するsong_urlを検証して追加します。これで曲のダウンロードは開始されません。

            エントリとそのキュー内の位置を返します。

            ：param song_url：プレイリストに追加する曲のURL。
            ：param meta：プレイリストエントリに追加する追加メタデータ。
        """

        try:
            info = await self.downloader.extract_info(self.loop, song_url, download=False)
        except Exception as e:
            raise ExtractionError('{}から情報を抽出できませんでした\n \n {}'.format(song_url, e))

        if not info:
            raise ExtractionError('%sから情報を抽出できませんでした' % song_url)

        # TODO: Sort out what happens next when this happens
        if info.get('_type', None) == 'playlist':
            raise WrongEntryTypeError("これはプレイリストです。", True, info.get('webpage_url', None) or info.get('url', None))

        if info.get('is_live', False):
            return await self.add_stream_entry(song_url, info=info, **meta)

        # TODO: Extract this to its own function
        if info['extractor'] in ['generic', 'Dropbox']:
            log.debug('ジェネリックエクストラクタ、またはDropboxを検出しました')
            try:
                headers = await get_header(self.bot.aiosession, info['url'])
                content_type = headers.get('CONTENT-TYPE')
                log.debug("コンテンツタイプ{}を取得しました".format(content_type))
            except Exception as e:
                log.warning("url {}({})のコンテンツタイプを取得できませんでした".format(song_url, e))
                content_type = None

            if content_type:
                if content_type.startswith(('application/', 'image/')):
                    if not any(x in content_type for x in ('/ogg', '/octet-stream')):
                        # How does a server say `application/ogg` what the actual fuck
                        raise ExtractionError("url%sのコンテンツタイプ\"%s\"が無効です" % (content_type, song_url))

                elif content_type.startswith('text/html') and info['extractor'] == 'generic':
                    log.warning("Got text/html for content-type, this might be a stream.")
                    return await self.add_stream_entry(song_url, info=info, **meta)  # TODO: Check for shoutcast/icecast

                elif not content_type.startswith(('audio/', 'video/')):
                    log.warning("疑問のあるコンテンツタイプ\"{}\"のURL {}".format(content_type, song_url))

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
                    log.debug("コンテンツが直接ストリームであると仮定します")

                elif e.exc_info[0] == URLError:
                    if os.path.exists(os.path.abspath(song_url)):
                        raise ExtractionError("これはストリームではなく、ファイルパスです。")

                    else: # it might be a file path that just doesn't exist
                        raise ExtractionError("無効入力: {0.exc_info[0]}: {0.exc_info[1].reason}".format(e))

                else:
                    # traceback.print_exc()
                    raise ExtractionError("不明なエラー:{}".format(e))

            except Exception as e:
                log.error('{}({})から情報を抽出できませんでした。直接'.format(song_url, e), exc_info=True)

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
            `playlist_url`から曲をインポートし、再生するようにキューに入れます。

            エンキューされた `entries`のリストを返します。

            ：param playlist_url：個々のURLに分割され、プレイリストに追加されるプレイリストURL
            ：param meta：プレイリストエントリに追加する追加メタデータ
        """
        position = len(self.entries) + 1
        entry_list = []

        try:
            info = await self.downloader.safe_extract_info(self.loop, playlist_url, download=False)
        except Exception as e:
            raise ExtractionError('{}から情報を抽出できませんでした\n \n {}'.format(playlist_url, e))

        if not info:
            raise ExtractionError('%sから情報を抽出できませんでした' % playlist_url)

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
                    log.warning("アイテムを追加できませんでした", exc_info=e)
                    log.debug("項目:{}".format(item), exc_info=True)
            else:
                baditems += 1

        if baditems:
            log.info("{}の不良エントリをスキップしました。".format(baditems))

        return entry_list, position

    async def async_process_youtube_playlist(self, playlist_url, **meta):
        """
            `playlist_url`のyoutubeプレイリストのリンクを疑わしい非同期の方法で処理します。

            ：param playlist_url：個々のURLに分割され、プレイリストに追加されるプレイリストURL
            ：param meta：プレイリストエントリに追加する追加メタデータ
        """

        try:
            info = await self.downloader.safe_extract_info(self.loop, playlist_url, download=False, process=False)
        except Exception as e:
            raise ExtractionError('{}から情報を抽出できませんでした\n \n {}'.format(playlist_url, e))

        if not info:
            raise ExtractionError('%sから情報を抽出できませんでした' % playlist_url)

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
            log.info("{}の不正なエントリをスキップしました".format(baditems))

        return gooditems

    async def async_process_sc_bc_playlist(self, playlist_url, **meta):
        """
            `playlist_url`のsoundcloud setとbancdamp albumリンクを、疑わしい非同期の方法で処理します。

            ：param playlist_url：個々のURLに分割され、プレイリストに追加されるプレイリストURL
            ：param meta：プレイリストエントリに追加する追加メタデータ
        """

        try:
            info = await self.downloader.safe_extract_info(self.loop, playlist_url, download=False, process=False)
        except Exception as e:
            raise ExtractionError('{}から情報を抽出できませんでした\n \n {}'.format(playlist_url, e))

        if not info:
            raise ExtractionError('%sから情報を抽出できませんでした' % playlist_url)

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
                    log.error("エントリの追加エラー{}".format(entry_data['id']), exc_info=e)
            else:
                baditems += 1

        if baditems:
            log.info("%sの不正なエントリをスキップしました".format(baditems))

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
            次の曲を返すコルーチン、または再生する曲が残っていない場合はNoneを返します。

            さらに、predownload_nextがTrueに設定されている場合、次のファイルをダウンロードしようとします
            演奏される歌 - 私たちがそれを得るまでに準備が整うように。
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
            再生予定の次のエントリを返します。
        """
        if self.entries:
            return self.entries[0]

    async def estimate_time_until(self, position, player):
        """
           (非常に)待ち時間が「位置付け」するまでの時間を計算します
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
        # log.debug("プレイリストのデシリアライズ")
        pl = cls(bot)

        for entry in raw_json['entries']:
            pl.entries.append(entry)

        # TODO: create a function to init downloading (since we don't do it here)?
        return pl

