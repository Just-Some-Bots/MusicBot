import importlib
import random
import re

from ..utils import (
    age_restricted,
    bug_reports_message,
    classproperty,
    write_string,
)

# These bloat the lazy_extractors, so allow them to passthrough silently
ALLOWED_CLASSMETHODS = {'get_testcases', 'extract_from_webpage'}
_WARNED = False


class LazyLoadMetaClass(type):
    def __getattr__(cls, name):
        global _WARNED
        if ('_real_class' not in cls.__dict__
                and name not in ALLOWED_CLASSMETHODS and not _WARNED):
            _WARNED = True
            write_string('WARNING: Falling back to normal extractor since lazy extractor '
                         f'{cls.__name__} does not have attribute {name}{bug_reports_message()}\n')
        return getattr(cls.real_class, name)


class LazyLoadExtractor(metaclass=LazyLoadMetaClass):
    @classproperty
    def real_class(cls):
        if '_real_class' not in cls.__dict__:
            cls._real_class = getattr(importlib.import_module(cls._module), cls.__name__)
        return cls._real_class

    def __new__(cls, *args, **kwargs):
        instance = cls.real_class.__new__(cls.real_class)
        instance.__init__(*args, **kwargs)
        return instance

    _module = None
    IE_DESC = None
    SEARCH_KEY = None
    _VALID_URL = None
    _WORKING = True
    _ENABLED = True
    _NETRC_MACHINE = None
    age_limit = 0

    @classmethod
    def ie_key(cls):
        """A string for getting the InfoExtractor with get_info_extractor"""
        return cls.__name__[:-2]

    @classmethod
    def working(cls):
        """Getter method for _WORKING."""
        return cls._WORKING

    @classmethod
    def description(cls, *, markdown=True, search_examples=None):
        """Description of the extractor"""
        desc = ''
        if cls._NETRC_MACHINE:
            if markdown:
                desc += f' [<abbr title="netrc machine"><em>{cls._NETRC_MACHINE}</em></abbr>]'
            else:
                desc += f' [{cls._NETRC_MACHINE}]'
        if cls.IE_DESC is False:
            desc += ' [HIDDEN]'
        elif cls.IE_DESC:
            desc += f' {cls.IE_DESC}'
        if cls.SEARCH_KEY:
            desc += f'; "{cls.SEARCH_KEY}:" prefix'
            if search_examples:
                _COUNTS = ('', '5', '10', 'all')
                desc += f' (e.g. "{cls.SEARCH_KEY}{random.choice(_COUNTS)}:{random.choice(search_examples)}")'
        if not cls.working():
            desc += ' (**Currently broken**)' if markdown else ' (Currently broken)'

        # Escape emojis. Ref: https://github.com/github/markup/issues/1153
        name = (' - **%s**' % re.sub(r':(\w+:)', ':\u200B\\g<1>', cls.IE_NAME)) if markdown else cls.IE_NAME
        return f'{name}:{desc}' if desc else name

    @classmethod
    def suitable(cls, url):
        """Receives a URL and returns True if suitable for this IE."""
        # This function must import everything it needs (except other extractors),
        # so that lazy_extractors works correctly
        return cls._match_valid_url(url) is not None

    @classmethod
    def _match_valid_url(cls, url):
        if cls._VALID_URL is False:
            return None
        # This does not use has/getattr intentionally - we want to know whether
        # we have cached the regexp for *this* class, whereas getattr would also
        # match the superclass
        if '_VALID_URL_RE' not in cls.__dict__:
            cls._VALID_URL_RE = re.compile(cls._VALID_URL)
        return cls._VALID_URL_RE.match(url)

    @classmethod
    def _match_id(cls, url):
        return cls._match_valid_url(url).group('id')

    @classmethod
    def get_temp_id(cls, url):
        try:
            return cls._match_id(url)
        except (IndexError, AttributeError):
            return None

    @classmethod
    def is_suitable(cls, age_limit):
        """Test whether the extractor is generally suitable for the given age limit"""
        return not age_restricted(cls.age_limit, age_limit)


class LazyLoadSearchExtractor(LazyLoadExtractor):
    pass


class YoutubeBaseInfoExtractor(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.youtube'
    IE_NAME = 'YoutubeBaseInfoExtract'


class YoutubeIE(YoutubeBaseInfoExtractor):
    _module = 'yt_dlp.extractor.youtube'
    IE_NAME = 'youtube'
    IE_DESC = 'YouTube'
    _VALID_URL = '(?x)^\n                     (\n                         (?:https?://|//)                                    # http(s):// or protocol-independent URL\n                         (?:(?:(?:(?:\\w+\\.)?[yY][oO][uU][tT][uU][bB][eE](?:-nocookie|kids)?\\.com|\n                            (?:www\\.)?deturl\\.com/www\\.youtube\\.com|\n                            (?:www\\.)?pwnyoutube\\.com|\n                            (?:www\\.)?hooktube\\.com|\n                            (?:www\\.)?yourepeat\\.com|\n                            tube\\.majestyc\\.net|\n                            (?:www\\.)?redirect\\.invidious\\.io|(?:(?:www|dev)\\.)?invidio\\.us|(?:www\\.)?invidious\\.pussthecat\\.org|(?:www\\.)?invidious\\.zee\\.li|(?:www\\.)?invidious\\.ethibox\\.fr|(?:www\\.)?invidious\\.3o7z6yfxhbw7n3za4rss6l434kmv55cgw2vuziwuigpwegswvwzqipyd\\.onion|(?:www\\.)?osbivz6guyeahrwp2lnwyjk2xos342h4ocsxyqrlaopqjuhwn2djiiyd\\.onion|(?:www\\.)?u2cvlit75owumwpy4dj2hsmvkq7nvrclkpht7xgyye2pyoxhpmclkrad\\.onion|(?:(?:www|no)\\.)?invidiou\\.sh|(?:(?:www|fi)\\.)?invidious\\.snopyta\\.org|(?:www\\.)?invidious\\.kabi\\.tk|(?:www\\.)?invidious\\.mastodon\\.host|(?:www\\.)?invidious\\.zapashcanon\\.fr|(?:www\\.)?(?:invidious(?:-us)?|piped)\\.kavin\\.rocks|(?:www\\.)?invidious\\.tinfoil-hat\\.net|(?:www\\.)?invidious\\.himiko\\.cloud|(?:www\\.)?invidious\\.reallyancient\\.tech|(?:www\\.)?invidious\\.tube|(?:www\\.)?invidiou\\.site|(?:www\\.)?invidious\\.site|(?:www\\.)?invidious\\.xyz|(?:www\\.)?invidious\\.nixnet\\.xyz|(?:www\\.)?invidious\\.048596\\.xyz|(?:www\\.)?invidious\\.drycat\\.fr|(?:www\\.)?inv\\.skyn3t\\.in|(?:www\\.)?tube\\.poal\\.co|(?:www\\.)?tube\\.connect\\.cafe|(?:www\\.)?vid\\.wxzm\\.sx|(?:www\\.)?vid\\.mint\\.lgbt|(?:www\\.)?vid\\.puffyan\\.us|(?:www\\.)?yewtu\\.be|(?:www\\.)?yt\\.elukerio\\.org|(?:www\\.)?yt\\.lelux\\.fi|(?:www\\.)?invidious\\.ggc-project\\.de|(?:www\\.)?yt\\.maisputain\\.ovh|(?:www\\.)?ytprivate\\.com|(?:www\\.)?invidious\\.13ad\\.de|(?:www\\.)?invidious\\.toot\\.koeln|(?:www\\.)?invidious\\.fdn\\.fr|(?:www\\.)?watch\\.nettohikari\\.com|(?:www\\.)?invidious\\.namazso\\.eu|(?:www\\.)?invidious\\.silkky\\.cloud|(?:www\\.)?invidious\\.exonip\\.de|(?:www\\.)?invidious\\.riverside\\.rocks|(?:www\\.)?invidious\\.blamefran\\.net|(?:www\\.)?invidious\\.moomoo\\.de|(?:www\\.)?ytb\\.trom\\.tf|(?:www\\.)?yt\\.cyberhost\\.uk|(?:www\\.)?kgg2m7yk5aybusll\\.onion|(?:www\\.)?qklhadlycap4cnod\\.onion|(?:www\\.)?axqzx4s6s54s32yentfqojs3x5i7faxza6xo3ehd4bzzsg2ii4fv2iid\\.onion|(?:www\\.)?c7hqkpkpemu6e7emz5b4vyz7idjgdvgaaa3dyimmeojqbgpea3xqjoid\\.onion|(?:www\\.)?fz253lmuao3strwbfbmx46yu7acac2jz27iwtorgmbqlkurlclmancad\\.onion|(?:www\\.)?invidious\\.l4qlywnpwqsluw65ts7md3khrivpirse744un3x7mlskqauz5pyuzgqd\\.onion|(?:www\\.)?owxfohz4kjyv25fvlqilyxast7inivgiktls3th44jhk3ej3i7ya\\.b32\\.i2p|(?:www\\.)?4l2dgddgsrkf2ous66i6seeyi6etzfgrue332grh2n7madpwopotugyd\\.onion|(?:www\\.)?w6ijuptxiku4xpnnaetxvnkc5vqcdu7mgns2u77qefoixi63vbvnpnqd\\.onion|(?:www\\.)?kbjggqkzv65ivcqj6bumvp337z6264huv5kpkwuv6gu5yjiskvan7fad\\.onion|(?:www\\.)?grwp24hodrefzvjjuccrkw3mjq4tzhaaq32amf33dzpmuxe7ilepcmad\\.onion|(?:www\\.)?hpniueoejy4opn7bc4ftgazyqjoeqwlvh2uiku2xqku6zpoa4bf5ruid\\.onion|(?:www\\.)?piped\\.kavin\\.rocks|(?:www\\.)?piped\\.tokhmi\\.xyz|(?:www\\.)?piped\\.syncpundit\\.io|(?:www\\.)?piped\\.mha\\.fi|(?:www\\.)?watch\\.whatever\\.social|(?:www\\.)?piped\\.garudalinux\\.org|(?:www\\.)?piped\\.rivo\\.lol|(?:www\\.)?piped-libre\\.kavin\\.rocks|(?:www\\.)?yt\\.jae\\.fi|(?:www\\.)?piped\\.mint\\.lgbt|(?:www\\.)?il\\.ax|(?:www\\.)?piped\\.esmailelbob\\.xyz|(?:www\\.)?piped\\.projectsegfau\\.lt|(?:www\\.)?piped\\.privacydev\\.net|(?:www\\.)?piped\\.palveluntarjoaja\\.eu|(?:www\\.)?piped\\.smnz\\.de|(?:www\\.)?piped\\.adminforge\\.de|(?:www\\.)?watch\\.whatevertinfoil\\.de|(?:www\\.)?piped\\.qdi\\.fi|\n                            youtube\\.googleapis\\.com)/                        # the various hostnames, with wildcard subdomains\n                         (?:.*?\\#/)?                                          # handle anchor (#/) redirect urls\n                         (?:                                                  # the various things that can precede the ID:\n                             (?:(?:v|embed|e|shorts)/(?!videoseries|live_stream))  # v/ or embed/ or e/ or shorts/\n                             |(?:                                             # or the v= param in all its forms\n                                 (?:(?:watch|movie)(?:_popup)?(?:\\.php)?/?)?  # preceding watch(_popup|.php) or nothing (like /?v=xxxx)\n                                 (?:\\?|\\#!?)                                  # the params delimiter ? or # or #!\n                                 (?:.*?[&;])??                                # any other preceding param (like /?s=tuff&v=xxxx or ?s=tuff&amp;v=V36LpHqtcDY)\n                                 v=\n                             )\n                         ))\n                         |(?:\n                            youtu\\.be|                                        # just youtu.be/xxxx\n                            vid\\.plus|                                        # or vid.plus/xxxx\n                            zwearz\\.com/watch|                                # or zwearz.com/watch/xxxx\n                            (?:www\\.)?redirect\\.invidious\\.io|(?:(?:www|dev)\\.)?invidio\\.us|(?:www\\.)?invidious\\.pussthecat\\.org|(?:www\\.)?invidious\\.zee\\.li|(?:www\\.)?invidious\\.ethibox\\.fr|(?:www\\.)?invidious\\.3o7z6yfxhbw7n3za4rss6l434kmv55cgw2vuziwuigpwegswvwzqipyd\\.onion|(?:www\\.)?osbivz6guyeahrwp2lnwyjk2xos342h4ocsxyqrlaopqjuhwn2djiiyd\\.onion|(?:www\\.)?u2cvlit75owumwpy4dj2hsmvkq7nvrclkpht7xgyye2pyoxhpmclkrad\\.onion|(?:(?:www|no)\\.)?invidiou\\.sh|(?:(?:www|fi)\\.)?invidious\\.snopyta\\.org|(?:www\\.)?invidious\\.kabi\\.tk|(?:www\\.)?invidious\\.mastodon\\.host|(?:www\\.)?invidious\\.zapashcanon\\.fr|(?:www\\.)?(?:invidious(?:-us)?|piped)\\.kavin\\.rocks|(?:www\\.)?invidious\\.tinfoil-hat\\.net|(?:www\\.)?invidious\\.himiko\\.cloud|(?:www\\.)?invidious\\.reallyancient\\.tech|(?:www\\.)?invidious\\.tube|(?:www\\.)?invidiou\\.site|(?:www\\.)?invidious\\.site|(?:www\\.)?invidious\\.xyz|(?:www\\.)?invidious\\.nixnet\\.xyz|(?:www\\.)?invidious\\.048596\\.xyz|(?:www\\.)?invidious\\.drycat\\.fr|(?:www\\.)?inv\\.skyn3t\\.in|(?:www\\.)?tube\\.poal\\.co|(?:www\\.)?tube\\.connect\\.cafe|(?:www\\.)?vid\\.wxzm\\.sx|(?:www\\.)?vid\\.mint\\.lgbt|(?:www\\.)?vid\\.puffyan\\.us|(?:www\\.)?yewtu\\.be|(?:www\\.)?yt\\.elukerio\\.org|(?:www\\.)?yt\\.lelux\\.fi|(?:www\\.)?invidious\\.ggc-project\\.de|(?:www\\.)?yt\\.maisputain\\.ovh|(?:www\\.)?ytprivate\\.com|(?:www\\.)?invidious\\.13ad\\.de|(?:www\\.)?invidious\\.toot\\.koeln|(?:www\\.)?invidious\\.fdn\\.fr|(?:www\\.)?watch\\.nettohikari\\.com|(?:www\\.)?invidious\\.namazso\\.eu|(?:www\\.)?invidious\\.silkky\\.cloud|(?:www\\.)?invidious\\.exonip\\.de|(?:www\\.)?invidious\\.riverside\\.rocks|(?:www\\.)?invidious\\.blamefran\\.net|(?:www\\.)?invidious\\.moomoo\\.de|(?:www\\.)?ytb\\.trom\\.tf|(?:www\\.)?yt\\.cyberhost\\.uk|(?:www\\.)?kgg2m7yk5aybusll\\.onion|(?:www\\.)?qklhadlycap4cnod\\.onion|(?:www\\.)?axqzx4s6s54s32yentfqojs3x5i7faxza6xo3ehd4bzzsg2ii4fv2iid\\.onion|(?:www\\.)?c7hqkpkpemu6e7emz5b4vyz7idjgdvgaaa3dyimmeojqbgpea3xqjoid\\.onion|(?:www\\.)?fz253lmuao3strwbfbmx46yu7acac2jz27iwtorgmbqlkurlclmancad\\.onion|(?:www\\.)?invidious\\.l4qlywnpwqsluw65ts7md3khrivpirse744un3x7mlskqauz5pyuzgqd\\.onion|(?:www\\.)?owxfohz4kjyv25fvlqilyxast7inivgiktls3th44jhk3ej3i7ya\\.b32\\.i2p|(?:www\\.)?4l2dgddgsrkf2ous66i6seeyi6etzfgrue332grh2n7madpwopotugyd\\.onion|(?:www\\.)?w6ijuptxiku4xpnnaetxvnkc5vqcdu7mgns2u77qefoixi63vbvnpnqd\\.onion|(?:www\\.)?kbjggqkzv65ivcqj6bumvp337z6264huv5kpkwuv6gu5yjiskvan7fad\\.onion|(?:www\\.)?grwp24hodrefzvjjuccrkw3mjq4tzhaaq32amf33dzpmuxe7ilepcmad\\.onion|(?:www\\.)?hpniueoejy4opn7bc4ftgazyqjoeqwlvh2uiku2xqku6zpoa4bf5ruid\\.onion|(?:www\\.)?piped\\.kavin\\.rocks|(?:www\\.)?piped\\.tokhmi\\.xyz|(?:www\\.)?piped\\.syncpundit\\.io|(?:www\\.)?piped\\.mha\\.fi|(?:www\\.)?watch\\.whatever\\.social|(?:www\\.)?piped\\.garudalinux\\.org|(?:www\\.)?piped\\.rivo\\.lol|(?:www\\.)?piped-libre\\.kavin\\.rocks|(?:www\\.)?yt\\.jae\\.fi|(?:www\\.)?piped\\.mint\\.lgbt|(?:www\\.)?il\\.ax|(?:www\\.)?piped\\.esmailelbob\\.xyz|(?:www\\.)?piped\\.projectsegfau\\.lt|(?:www\\.)?piped\\.privacydev\\.net|(?:www\\.)?piped\\.palveluntarjoaja\\.eu|(?:www\\.)?piped\\.smnz\\.de|(?:www\\.)?piped\\.adminforge\\.de|(?:www\\.)?watch\\.whatevertinfoil\\.de|(?:www\\.)?piped\\.qdi\\.fi\n                         )/\n                         |(?:www\\.)?cleanvideosearch\\.com/media/action/yt/watch\\?videoId=\n                         )\n                     )?                                                       # all until now is optional -> you can pass the naked ID\n                     (?P<id>[0-9A-Za-z_-]{11})                                # here is it! the YouTube video ID\n                     (?(1).+)?                                                # if we found the ID, everything can follow\n                     (?:\\#|$)'
    age_limit = 18

    @classmethod
    def suitable(cls, url):
        from ..utils import parse_qs

        qs = parse_qs(url)
        if qs.get('list', [None])[0]:
            return False
        return super().suitable(url)


class YoutubeTabBaseInfoExtractor(YoutubeBaseInfoExtractor):
    _module = 'yt_dlp.extractor.youtube'
    IE_NAME = 'YoutubeTabBaseInfoExtract'


class YoutubeClipIE(YoutubeTabBaseInfoExtractor):
    _module = 'yt_dlp.extractor.youtube'
    IE_NAME = 'youtube:clip'
    _VALID_URL = 'https?://(?:www\\.)?youtube\\.com/clip/(?P<id>[^/?#]+)'


class YoutubeFavouritesIE(YoutubeBaseInfoExtractor):
    _module = 'yt_dlp.extractor.youtube'
    IE_NAME = 'youtube:favorites'
    IE_DESC = 'YouTube liked videos; ":ytfav" keyword (requires cookies)'
    _VALID_URL = ':ytfav(?:ou?rite)?s?'


class YoutubeNotificationsIE(YoutubeTabBaseInfoExtractor):
    _module = 'yt_dlp.extractor.youtube'
    IE_NAME = 'youtube:notif'
    IE_DESC = 'YouTube notifications; ":ytnotif" keyword (requires cookies)'
    _VALID_URL = ':ytnotif(?:ication)?s?'


class YoutubeFeedsInfoExtractor(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.youtube'
    IE_NAME = 'youtube:feeds'


class YoutubeHistoryIE(YoutubeFeedsInfoExtractor):
    _module = 'yt_dlp.extractor.youtube'
    IE_NAME = 'youtube:history'
    IE_DESC = 'Youtube watch history; ":ythis" keyword (requires cookies)'
    _VALID_URL = ':ythis(?:tory)?'


class YoutubeTabIE(YoutubeTabBaseInfoExtractor):
    _module = 'yt_dlp.extractor.youtube'
    IE_NAME = 'youtube:tab'
    IE_DESC = 'YouTube Tabs'
    _VALID_URL = '(?x:\n        https?://\n            (?:\\w+\\.)?\n            (?:\n                youtube(?:kids)?\\.com|\n                (?:www\\.)?redirect\\.invidious\\.io|(?:(?:www|dev)\\.)?invidio\\.us|(?:www\\.)?invidious\\.pussthecat\\.org|(?:www\\.)?invidious\\.zee\\.li|(?:www\\.)?invidious\\.ethibox\\.fr|(?:www\\.)?invidious\\.3o7z6yfxhbw7n3za4rss6l434kmv55cgw2vuziwuigpwegswvwzqipyd\\.onion|(?:www\\.)?osbivz6guyeahrwp2lnwyjk2xos342h4ocsxyqrlaopqjuhwn2djiiyd\\.onion|(?:www\\.)?u2cvlit75owumwpy4dj2hsmvkq7nvrclkpht7xgyye2pyoxhpmclkrad\\.onion|(?:(?:www|no)\\.)?invidiou\\.sh|(?:(?:www|fi)\\.)?invidious\\.snopyta\\.org|(?:www\\.)?invidious\\.kabi\\.tk|(?:www\\.)?invidious\\.mastodon\\.host|(?:www\\.)?invidious\\.zapashcanon\\.fr|(?:www\\.)?(?:invidious(?:-us)?|piped)\\.kavin\\.rocks|(?:www\\.)?invidious\\.tinfoil-hat\\.net|(?:www\\.)?invidious\\.himiko\\.cloud|(?:www\\.)?invidious\\.reallyancient\\.tech|(?:www\\.)?invidious\\.tube|(?:www\\.)?invidiou\\.site|(?:www\\.)?invidious\\.site|(?:www\\.)?invidious\\.xyz|(?:www\\.)?invidious\\.nixnet\\.xyz|(?:www\\.)?invidious\\.048596\\.xyz|(?:www\\.)?invidious\\.drycat\\.fr|(?:www\\.)?inv\\.skyn3t\\.in|(?:www\\.)?tube\\.poal\\.co|(?:www\\.)?tube\\.connect\\.cafe|(?:www\\.)?vid\\.wxzm\\.sx|(?:www\\.)?vid\\.mint\\.lgbt|(?:www\\.)?vid\\.puffyan\\.us|(?:www\\.)?yewtu\\.be|(?:www\\.)?yt\\.elukerio\\.org|(?:www\\.)?yt\\.lelux\\.fi|(?:www\\.)?invidious\\.ggc-project\\.de|(?:www\\.)?yt\\.maisputain\\.ovh|(?:www\\.)?ytprivate\\.com|(?:www\\.)?invidious\\.13ad\\.de|(?:www\\.)?invidious\\.toot\\.koeln|(?:www\\.)?invidious\\.fdn\\.fr|(?:www\\.)?watch\\.nettohikari\\.com|(?:www\\.)?invidious\\.namazso\\.eu|(?:www\\.)?invidious\\.silkky\\.cloud|(?:www\\.)?invidious\\.exonip\\.de|(?:www\\.)?invidious\\.riverside\\.rocks|(?:www\\.)?invidious\\.blamefran\\.net|(?:www\\.)?invidious\\.moomoo\\.de|(?:www\\.)?ytb\\.trom\\.tf|(?:www\\.)?yt\\.cyberhost\\.uk|(?:www\\.)?kgg2m7yk5aybusll\\.onion|(?:www\\.)?qklhadlycap4cnod\\.onion|(?:www\\.)?axqzx4s6s54s32yentfqojs3x5i7faxza6xo3ehd4bzzsg2ii4fv2iid\\.onion|(?:www\\.)?c7hqkpkpemu6e7emz5b4vyz7idjgdvgaaa3dyimmeojqbgpea3xqjoid\\.onion|(?:www\\.)?fz253lmuao3strwbfbmx46yu7acac2jz27iwtorgmbqlkurlclmancad\\.onion|(?:www\\.)?invidious\\.l4qlywnpwqsluw65ts7md3khrivpirse744un3x7mlskqauz5pyuzgqd\\.onion|(?:www\\.)?owxfohz4kjyv25fvlqilyxast7inivgiktls3th44jhk3ej3i7ya\\.b32\\.i2p|(?:www\\.)?4l2dgddgsrkf2ous66i6seeyi6etzfgrue332grh2n7madpwopotugyd\\.onion|(?:www\\.)?w6ijuptxiku4xpnnaetxvnkc5vqcdu7mgns2u77qefoixi63vbvnpnqd\\.onion|(?:www\\.)?kbjggqkzv65ivcqj6bumvp337z6264huv5kpkwuv6gu5yjiskvan7fad\\.onion|(?:www\\.)?grwp24hodrefzvjjuccrkw3mjq4tzhaaq32amf33dzpmuxe7ilepcmad\\.onion|(?:www\\.)?hpniueoejy4opn7bc4ftgazyqjoeqwlvh2uiku2xqku6zpoa4bf5ruid\\.onion|(?:www\\.)?piped\\.kavin\\.rocks|(?:www\\.)?piped\\.tokhmi\\.xyz|(?:www\\.)?piped\\.syncpundit\\.io|(?:www\\.)?piped\\.mha\\.fi|(?:www\\.)?watch\\.whatever\\.social|(?:www\\.)?piped\\.garudalinux\\.org|(?:www\\.)?piped\\.rivo\\.lol|(?:www\\.)?piped-libre\\.kavin\\.rocks|(?:www\\.)?yt\\.jae\\.fi|(?:www\\.)?piped\\.mint\\.lgbt|(?:www\\.)?il\\.ax|(?:www\\.)?piped\\.esmailelbob\\.xyz|(?:www\\.)?piped\\.projectsegfau\\.lt|(?:www\\.)?piped\\.privacydev\\.net|(?:www\\.)?piped\\.palveluntarjoaja\\.eu|(?:www\\.)?piped\\.smnz\\.de|(?:www\\.)?piped\\.adminforge\\.de|(?:www\\.)?watch\\.whatevertinfoil\\.de|(?:www\\.)?piped\\.qdi\\.fi\n            )/\n            (?:\n                (?P<channel_type>channel|c|user|browse)/|\n                (?P<not_channel>\n                    feed/|hashtag/|\n                    (?:playlist|watch)\\?.*?\\blist=\n                )|\n                (?!(?:channel|c|user|playlist|watch|w|v|embed|e|watch_popup|clip|shorts|movies|results|search|shared|hashtag|trending|explore|feed|feeds|browse|oembed|get_video_info|iframe_api|s/player|source|storefront|oops|index|account|t/terms|about|upload|signin|logout)\\b)  # Direct URLs\n            )\n            (?P<id>[^/?\\#&]+)\n    )'

    @classmethod
    def suitable(cls, url):
        return False if YoutubeIE.suitable(url) else super().suitable(url)


class YoutubeLivestreamEmbedIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.youtube'
    IE_NAME = 'YoutubeLivestreamEmbed'
    IE_DESC = 'YouTube livestream embeds'
    _VALID_URL = 'https?://(?:\\w+\\.)?youtube\\.com/embed/live_stream/?\\?(?:[^#]+&)?channel=(?P<id>[^&#]+)'


class YoutubePlaylistIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.youtube'
    IE_NAME = 'youtube:playlist'
    IE_DESC = 'YouTube playlists'
    _VALID_URL = '(?x)(?:\n                        (?:https?://)?\n                        (?:\\w+\\.)?\n                        (?:\n                            (?:\n                                youtube(?:kids)?\\.com|\n                                (?:www\\.)?redirect\\.invidious\\.io|(?:(?:www|dev)\\.)?invidio\\.us|(?:www\\.)?invidious\\.pussthecat\\.org|(?:www\\.)?invidious\\.zee\\.li|(?:www\\.)?invidious\\.ethibox\\.fr|(?:www\\.)?invidious\\.3o7z6yfxhbw7n3za4rss6l434kmv55cgw2vuziwuigpwegswvwzqipyd\\.onion|(?:www\\.)?osbivz6guyeahrwp2lnwyjk2xos342h4ocsxyqrlaopqjuhwn2djiiyd\\.onion|(?:www\\.)?u2cvlit75owumwpy4dj2hsmvkq7nvrclkpht7xgyye2pyoxhpmclkrad\\.onion|(?:(?:www|no)\\.)?invidiou\\.sh|(?:(?:www|fi)\\.)?invidious\\.snopyta\\.org|(?:www\\.)?invidious\\.kabi\\.tk|(?:www\\.)?invidious\\.mastodon\\.host|(?:www\\.)?invidious\\.zapashcanon\\.fr|(?:www\\.)?(?:invidious(?:-us)?|piped)\\.kavin\\.rocks|(?:www\\.)?invidious\\.tinfoil-hat\\.net|(?:www\\.)?invidious\\.himiko\\.cloud|(?:www\\.)?invidious\\.reallyancient\\.tech|(?:www\\.)?invidious\\.tube|(?:www\\.)?invidiou\\.site|(?:www\\.)?invidious\\.site|(?:www\\.)?invidious\\.xyz|(?:www\\.)?invidious\\.nixnet\\.xyz|(?:www\\.)?invidious\\.048596\\.xyz|(?:www\\.)?invidious\\.drycat\\.fr|(?:www\\.)?inv\\.skyn3t\\.in|(?:www\\.)?tube\\.poal\\.co|(?:www\\.)?tube\\.connect\\.cafe|(?:www\\.)?vid\\.wxzm\\.sx|(?:www\\.)?vid\\.mint\\.lgbt|(?:www\\.)?vid\\.puffyan\\.us|(?:www\\.)?yewtu\\.be|(?:www\\.)?yt\\.elukerio\\.org|(?:www\\.)?yt\\.lelux\\.fi|(?:www\\.)?invidious\\.ggc-project\\.de|(?:www\\.)?yt\\.maisputain\\.ovh|(?:www\\.)?ytprivate\\.com|(?:www\\.)?invidious\\.13ad\\.de|(?:www\\.)?invidious\\.toot\\.koeln|(?:www\\.)?invidious\\.fdn\\.fr|(?:www\\.)?watch\\.nettohikari\\.com|(?:www\\.)?invidious\\.namazso\\.eu|(?:www\\.)?invidious\\.silkky\\.cloud|(?:www\\.)?invidious\\.exonip\\.de|(?:www\\.)?invidious\\.riverside\\.rocks|(?:www\\.)?invidious\\.blamefran\\.net|(?:www\\.)?invidious\\.moomoo\\.de|(?:www\\.)?ytb\\.trom\\.tf|(?:www\\.)?yt\\.cyberhost\\.uk|(?:www\\.)?kgg2m7yk5aybusll\\.onion|(?:www\\.)?qklhadlycap4cnod\\.onion|(?:www\\.)?axqzx4s6s54s32yentfqojs3x5i7faxza6xo3ehd4bzzsg2ii4fv2iid\\.onion|(?:www\\.)?c7hqkpkpemu6e7emz5b4vyz7idjgdvgaaa3dyimmeojqbgpea3xqjoid\\.onion|(?:www\\.)?fz253lmuao3strwbfbmx46yu7acac2jz27iwtorgmbqlkurlclmancad\\.onion|(?:www\\.)?invidious\\.l4qlywnpwqsluw65ts7md3khrivpirse744un3x7mlskqauz5pyuzgqd\\.onion|(?:www\\.)?owxfohz4kjyv25fvlqilyxast7inivgiktls3th44jhk3ej3i7ya\\.b32\\.i2p|(?:www\\.)?4l2dgddgsrkf2ous66i6seeyi6etzfgrue332grh2n7madpwopotugyd\\.onion|(?:www\\.)?w6ijuptxiku4xpnnaetxvnkc5vqcdu7mgns2u77qefoixi63vbvnpnqd\\.onion|(?:www\\.)?kbjggqkzv65ivcqj6bumvp337z6264huv5kpkwuv6gu5yjiskvan7fad\\.onion|(?:www\\.)?grwp24hodrefzvjjuccrkw3mjq4tzhaaq32amf33dzpmuxe7ilepcmad\\.onion|(?:www\\.)?hpniueoejy4opn7bc4ftgazyqjoeqwlvh2uiku2xqku6zpoa4bf5ruid\\.onion|(?:www\\.)?piped\\.kavin\\.rocks|(?:www\\.)?piped\\.tokhmi\\.xyz|(?:www\\.)?piped\\.syncpundit\\.io|(?:www\\.)?piped\\.mha\\.fi|(?:www\\.)?watch\\.whatever\\.social|(?:www\\.)?piped\\.garudalinux\\.org|(?:www\\.)?piped\\.rivo\\.lol|(?:www\\.)?piped-libre\\.kavin\\.rocks|(?:www\\.)?yt\\.jae\\.fi|(?:www\\.)?piped\\.mint\\.lgbt|(?:www\\.)?il\\.ax|(?:www\\.)?piped\\.esmailelbob\\.xyz|(?:www\\.)?piped\\.projectsegfau\\.lt|(?:www\\.)?piped\\.privacydev\\.net|(?:www\\.)?piped\\.palveluntarjoaja\\.eu|(?:www\\.)?piped\\.smnz\\.de|(?:www\\.)?piped\\.adminforge\\.de|(?:www\\.)?watch\\.whatevertinfoil\\.de|(?:www\\.)?piped\\.qdi\\.fi\n                            )\n                            /.*?\\?.*?\\blist=\n                        )?\n                        (?P<id>(?:(?:PL|LL|EC|UU|FL|RD|UL|TL|PU|OLAK5uy_)[0-9A-Za-z-_]{10,}|RDMM|WL|LL|LM))\n                     )'

    @classmethod
    def suitable(cls, url):
        if YoutubeTabIE.suitable(url):
            return False
        from ..utils import parse_qs
        qs = parse_qs(url)
        if qs.get('v', [None])[0]:
            return False
        return super().suitable(url)


class YoutubeRecommendedIE(YoutubeFeedsInfoExtractor):
    _module = 'yt_dlp.extractor.youtube'
    IE_NAME = 'youtube:recommended'
    IE_DESC = 'YouTube recommended videos; ":ytrec" keyword'
    _VALID_URL = 'https?://(?:www\\.)?youtube\\.com/?(?:[?#]|$)|:ytrec(?:ommended)?'


class YoutubeSearchDateIE(YoutubeTabBaseInfoExtractor, LazyLoadSearchExtractor):
    _module = 'yt_dlp.extractor.youtube'
    IE_NAME = 'youtube:search:date'
    IE_DESC = 'YouTube search, newest videos first'
    SEARCH_KEY = 'ytsearchdate'
    _VALID_URL = 'ytsearchdate(?P<prefix>|[1-9][0-9]*|all):(?P<query>[\\s\\S]+)'


class YoutubeSearchIE(YoutubeTabBaseInfoExtractor, LazyLoadSearchExtractor):
    _module = 'yt_dlp.extractor.youtube'
    IE_NAME = 'youtube:search'
    IE_DESC = 'YouTube search'
    SEARCH_KEY = 'ytsearch'
    _VALID_URL = 'ytsearch(?P<prefix>|[1-9][0-9]*|all):(?P<query>[\\s\\S]+)'


class YoutubeSearchURLIE(YoutubeTabBaseInfoExtractor):
    _module = 'yt_dlp.extractor.youtube'
    IE_NAME = 'youtube:search_url'
    IE_DESC = 'YouTube search URLs with sorting and filter support'
    _VALID_URL = 'https?://(?:www\\.)?youtube\\.com/(?:results|search)\\?([^#]+&)?(?:search_query|q)=(?:[^&]+)(?:[&#]|$)'


class YoutubeMusicSearchURLIE(YoutubeTabBaseInfoExtractor):
    _module = 'yt_dlp.extractor.youtube'
    IE_NAME = 'youtube:music:search_url'
    IE_DESC = 'YouTube music search URLs with selectable sections, e.g. #songs'
    _VALID_URL = 'https?://music\\.youtube\\.com/search\\?([^#]+&)?(?:search_query|q)=(?:[^&]+)(?:[&#]|$)'


class YoutubeSubscriptionsIE(YoutubeFeedsInfoExtractor):
    _module = 'yt_dlp.extractor.youtube'
    IE_NAME = 'youtube:subscriptions'
    IE_DESC = 'YouTube subscriptions feed; ":ytsubs" keyword (requires cookies)'
    _VALID_URL = ':ytsub(?:scription)?s?'


class YoutubeStoriesIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.youtube'
    IE_NAME = 'youtube:stories'
    IE_DESC = 'YouTube channel stories; "ytstories:" prefix'
    _VALID_URL = 'ytstories:UC(?P<id>[A-Za-z0-9_-]{21}[AQgw])$'


class YoutubeTruncatedIDIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.youtube'
    IE_NAME = 'youtube:truncated_id'
    IE_DESC = False
    _VALID_URL = 'https?://(?:www\\.)?youtube\\.com/watch\\?v=(?P<id>[0-9A-Za-z_-]{1,10})$'


class YoutubeTruncatedURLIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.youtube'
    IE_NAME = 'youtube:truncated_url'
    IE_DESC = False
    _VALID_URL = '(?x)\n        (?:https?://)?\n        (?:\\w+\\.)?[yY][oO][uU][tT][uU][bB][eE](?:-nocookie)?\\.com/\n        (?:watch\\?(?:\n            feature=[a-z_]+|\n            annotation_id=annotation_[^&]+|\n            x-yt-cl=[0-9]+|\n            hl=[^&]*|\n            t=[0-9]+\n        )?\n        |\n            attribution_link\\?a=[^&]+\n        )\n        $\n    '


class YoutubeYtBeIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.youtube'
    IE_NAME = 'YoutubeYtBe'
    IE_DESC = 'youtu.be'
    _VALID_URL = 'https?://youtu\\.be/(?P<id>[0-9A-Za-z_-]{11})/*?.*?\\blist=(?P<playlist_id>(?:(?:PL|LL|EC|UU|FL|RD|UL|TL|PU|OLAK5uy_)[0-9A-Za-z-_]{10,}|RDMM|WL|LL|LM))'


class YoutubeYtUserIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.youtube'
    IE_NAME = 'youtube:user'
    IE_DESC = 'YouTube user videos; "ytuser:" prefix'
    _VALID_URL = 'ytuser:(?P<id>.+)'


class YoutubeWatchLaterIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.youtube'
    IE_NAME = 'youtube:watchlater'
    IE_DESC = 'Youtube watch later list; ":ytwatchlater" keyword (requires cookies)'
    _VALID_URL = ':ytwatchlater'


class YoutubeShortsAudioPivotIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.youtube'
    IE_NAME = 'youtube:shorts:pivot:audio'
    IE_DESC = 'YouTube Shorts audio pivot (Shorts using audio of a given video)'
    _VALID_URL = 'https?://(?:www\\.)?youtube\\.com/source/(?P<id>[\\w-]{11})/shorts'


class ABCIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.abc'
    IE_NAME = 'abc.net.au'
    _VALID_URL = 'https?://(?:www\\.)?abc\\.net\\.au/(?:news|btn)/(?:[^/]+/){1,4}(?P<id>\\d{5,})'


class ABCIViewIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.abc'
    IE_NAME = 'abc.net.au:iview'
    _VALID_URL = 'https?://iview\\.abc\\.net\\.au/(?:[^/]+/)*video/(?P<id>[^/?#]+)'


class ABCIViewShowSeriesIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.abc'
    IE_NAME = 'abc.net.au:iview:showseries'
    _VALID_URL = 'https?://iview\\.abc\\.net\\.au/show/(?P<id>[^/]+)(?:/series/\\d+)?$'


class AbcNewsIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.abcnews'
    IE_NAME = 'abcnews'
    _VALID_URL = 'https?://abcnews\\.go\\.com/(?:[^/]+/)+(?P<display_id>[0-9a-z-]+)/story\\?id=(?P<id>\\d+)'


class AMPIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.amp'
    IE_NAME = 'AMP'


class AbcNewsVideoIE(AMPIE):
    _module = 'yt_dlp.extractor.abcnews'
    IE_NAME = 'abcnews:video'
    _VALID_URL = '(?x)\n                    https?://\n                        (?:\n                            abcnews\\.go\\.com/\n                            (?:\n                                (?:[^/]+/)*video/(?P<display_id>[0-9a-z-]+)-|\n                                video/(?:embed|itemfeed)\\?.*?\\bid=\n                            )|\n                            fivethirtyeight\\.abcnews\\.go\\.com/video/embed/\\d+/\n                        )\n                        (?P<id>\\d+)\n                    '


class ABCOTVSIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.abcotvs'
    IE_NAME = 'abcotvs'
    IE_DESC = 'ABC Owned Television Stations'
    _VALID_URL = 'https?://(?P<site>abc(?:7(?:news|ny|chicago)?|11|13|30)|6abc)\\.com(?:(?:/[^/]+)*/(?P<display_id>[^/]+))?/(?P<id>\\d+)'


class ABCOTVSClipsIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.abcotvs'
    IE_NAME = 'abcotvs:clips'
    _VALID_URL = 'https?://clips\\.abcotvs\\.com/(?:[^/]+/)*video/(?P<id>\\d+)'


class AbemaTVBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.abematv'
    IE_NAME = 'AbemaTVBase'


class AbemaTVIE(AbemaTVBaseIE):
    _module = 'yt_dlp.extractor.abematv'
    IE_NAME = 'AbemaTV'
    _VALID_URL = 'https?://abema\\.tv/(?P<type>now-on-air|video/episode|channels/.+?/slots)/(?P<id>[^?/]+)'
    _NETRC_MACHINE = 'abematv'


class AbemaTVTitleIE(AbemaTVBaseIE):
    _module = 'yt_dlp.extractor.abematv'
    IE_NAME = 'AbemaTVTitle'
    _VALID_URL = 'https?://abema\\.tv/video/title/(?P<id>[^?/]+)'


class AcademicEarthCourseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.academicearth'
    IE_NAME = 'AcademicEarth:Course'
    _VALID_URL = '^https?://(?:www\\.)?academicearth\\.org/playlists/(?P<id>[^?#/]+)'


class ACastBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.acast'
    IE_NAME = 'ACastBase'


class ACastIE(ACastBaseIE):
    _module = 'yt_dlp.extractor.acast'
    IE_NAME = 'acast'
    _VALID_URL = '(?x)\n                    https?://\n                        (?:\n                            (?:(?:embed|www)\\.)?acast\\.com/|\n                            play\\.acast\\.com/s/\n                        )\n                        (?P<channel>[^/]+)/(?P<id>[^/#?]+)\n                    '


class ACastChannelIE(ACastBaseIE):
    _module = 'yt_dlp.extractor.acast'
    IE_NAME = 'acast:channel'
    _VALID_URL = '(?x)\n                    https?://\n                        (?:\n                            (?:www\\.)?acast\\.com/|\n                            play\\.acast\\.com/s/\n                        )\n                        (?P<id>[^/#?]+)\n                    '

    @classmethod
    def suitable(cls, url):
        return False if ACastIE.suitable(url) else super(ACastChannelIE, cls).suitable(url)


class AcFunVideoBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.acfun'
    IE_NAME = 'AcFunVideoBase'


class AcFunVideoIE(AcFunVideoBaseIE):
    _module = 'yt_dlp.extractor.acfun'
    IE_NAME = 'AcFunVideo'
    _VALID_URL = 'https?://www\\.acfun\\.cn/v/ac(?P<id>[_\\d]+)'


class AcFunBangumiIE(AcFunVideoBaseIE):
    _module = 'yt_dlp.extractor.acfun'
    IE_NAME = 'AcFunBangumi'
    _VALID_URL = 'https?://www\\.acfun\\.cn/bangumi/(?P<id>aa[_\\d]+)'


class ADNIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.adn'
    IE_NAME = 'ADN'
    IE_DESC = 'Animation Digital Network'
    _VALID_URL = 'https?://(?:www\\.)?(?:animation|anime)digitalnetwork\\.fr/video/[^/]+/(?P<id>\\d+)'
    _NETRC_MACHINE = 'animationdigitalnetwork'


class AdobeConnectIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.adobeconnect'
    IE_NAME = 'AdobeConnect'
    _VALID_URL = 'https?://\\w+\\.adobeconnect\\.com/(?P<id>[\\w-]+)'


class AdobeTVBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.adobetv'
    IE_NAME = 'AdobeTVBase'


class AdobeTVEmbedIE(AdobeTVBaseIE):
    _module = 'yt_dlp.extractor.adobetv'
    IE_NAME = 'adobetv:embed'
    _VALID_URL = 'https?://tv\\.adobe\\.com/embed/\\d+/(?P<id>\\d+)'


class AdobeTVIE(AdobeTVBaseIE):
    _module = 'yt_dlp.extractor.adobetv'
    IE_NAME = 'adobetv'
    _VALID_URL = 'https?://tv\\.adobe\\.com/(?:(?P<language>fr|de|es|jp)/)?watch/(?P<show_urlname>[^/]+)/(?P<id>[^/]+)'


class AdobeTVPlaylistBaseIE(AdobeTVBaseIE):
    _module = 'yt_dlp.extractor.adobetv'
    IE_NAME = 'AdobeTVPlaylistBase'


class AdobeTVShowIE(AdobeTVPlaylistBaseIE):
    _module = 'yt_dlp.extractor.adobetv'
    IE_NAME = 'adobetv:show'
    _VALID_URL = 'https?://tv\\.adobe\\.com/(?:(?P<language>fr|de|es|jp)/)?show/(?P<id>[^/]+)'


class AdobeTVChannelIE(AdobeTVPlaylistBaseIE):
    _module = 'yt_dlp.extractor.adobetv'
    IE_NAME = 'adobetv:channel'
    _VALID_URL = 'https?://tv\\.adobe\\.com/(?:(?P<language>fr|de|es|jp)/)?channel/(?P<id>[^/]+)(?:/(?P<category_urlname>[^/]+))?'


class AdobeTVVideoIE(AdobeTVBaseIE):
    _module = 'yt_dlp.extractor.adobetv'
    IE_NAME = 'adobetv:video'
    _VALID_URL = 'https?://video\\.tv\\.adobe\\.com/v/(?P<id>\\d+)'


class AdobePassIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.adobepass'
    IE_NAME = 'AdobePass'


class TurnerBaseIE(AdobePassIE):
    _module = 'yt_dlp.extractor.turner'
    IE_NAME = 'TurnerBase'


class AdultSwimIE(TurnerBaseIE):
    _module = 'yt_dlp.extractor.adultswim'
    IE_NAME = 'AdultSwim'
    _VALID_URL = 'https?://(?:www\\.)?adultswim\\.com/videos/(?P<show_path>[^/?#]+)(?:/(?P<episode_path>[^/?#]+))?'


class AeonCoIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.aeonco'
    IE_NAME = 'AeonCo'
    _VALID_URL = 'https?://(?:www\\.)?aeon\\.co/videos/(?P<id>[^/?]+)'


class AfreecaTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.afreecatv'
    IE_NAME = 'afreecatv'
    IE_DESC = 'afreecatv.com'
    _VALID_URL = '(?x)\n                    https?://\n                        (?:\n                            (?:(?:live|afbbs|www)\\.)?afreeca(?:tv)?\\.com(?::\\d+)?\n                            (?:\n                                /app/(?:index|read_ucc_bbs)\\.cgi|\n                                /player/[Pp]layer\\.(?:swf|html)\n                            )\\?.*?\\bnTitleNo=|\n                            vod\\.afreecatv\\.com/(PLAYER/STATION|player)/\n                        )\n                        (?P<id>\\d+)\n                    '
    _NETRC_MACHINE = 'afreecatv'


class AfreecaTVLiveIE(AfreecaTVIE):
    _module = 'yt_dlp.extractor.afreecatv'
    IE_NAME = 'afreecatv:live'
    IE_DESC = 'afreecatv.com'
    _VALID_URL = 'https?://play\\.afreeca(?:tv)?\\.com/(?P<id>[^/]+)(?:/(?P<bno>\\d+))?'
    _NETRC_MACHINE = 'afreecatv'


class AfreecaTVUserIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.afreecatv'
    IE_NAME = 'afreecatv:user'
    _VALID_URL = 'https?://bj\\.afreeca(?:tv)?\\.com/(?P<id>[^/]+)/vods/?(?P<slug_type>[^/]+)?'


class TokFMAuditionIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.agora'
    IE_NAME = 'tokfm:audition'
    _VALID_URL = '(?:https?://audycje\\.tokfm\\.pl/audycja/|tokfm:audition:)(?P<id>\\d+),?'


class TokFMPodcastIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.agora'
    IE_NAME = 'tokfm:podcast'
    _VALID_URL = '(?:https?://audycje\\.tokfm\\.pl/podcast/|tokfm:podcast:)(?P<id>\\d+),?'


class WyborczaPodcastIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.agora'
    IE_NAME = 'WyborczaPodcast'
    _VALID_URL = '(?x)\n        https?://(?:www\\.)?(?:\n            wyborcza\\.pl/podcast(?:/0,172673\\.html)?|\n            wysokieobcasy\\.pl/wysokie-obcasy/0,176631\\.html\n        )(?:\\?(?:[^&#]+?&)*podcast=(?P<id>\\d+))?\n    '


class WyborczaVideoIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.agora'
    IE_NAME = 'wyborcza:video'
    _VALID_URL = '(?:wyborcza:video:|https?://wyborcza\\.pl/(?:api-)?video/)(?P<id>\\d+)'


class AirMozillaIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.airmozilla'
    IE_NAME = 'AirMozilla'
    _VALID_URL = 'https?://air\\.mozilla\\.org/(?P<id>[0-9a-z-]+)/?'


class AlJazeeraIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.aljazeera'
    IE_NAME = 'AlJazeera'
    _VALID_URL = 'https?://(?P<base>\\w+\\.aljazeera\\.\\w+)/(?P<type>programs?/[^/]+|(?:feature|video|new)s)?/\\d{4}/\\d{1,2}/\\d{1,2}/(?P<id>[^/?&#]+)'


class AlphaPornoIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.alphaporno'
    IE_NAME = 'AlphaPorno'
    _VALID_URL = 'https?://(?:www\\.)?alphaporno\\.com/videos/(?P<id>[^/]+)'
    age_limit = 18


class AmaraIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.amara'
    IE_NAME = 'Amara'
    _VALID_URL = 'https?://(?:www\\.)?amara\\.org/(?:\\w+/)?videos/(?P<id>\\w+)'


class AluraIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.alura'
    IE_NAME = 'Alura'
    _VALID_URL = 'https?://(?:cursos\\.)?alura\\.com\\.br/course/(?P<course_name>[^/]+)/task/(?P<id>\\d+)'
    _NETRC_MACHINE = 'alura'


class AluraCourseIE(AluraIE):
    _module = 'yt_dlp.extractor.alura'
    IE_NAME = 'AluraCourse'
    _VALID_URL = 'https?://(?:cursos\\.)?alura\\.com\\.br/course/(?P<id>[^/]+)'
    _NETRC_MACHINE = 'aluracourse'

    @classmethod
    def suitable(cls, url):
        return False if AluraIE.suitable(url) else super(AluraCourseIE, cls).suitable(url)


class AmazonStoreIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.amazon'
    IE_NAME = 'AmazonStore'
    _VALID_URL = 'https?://(?:www\\.)?amazon\\.(?:[a-z]{2,3})(?:\\.[a-z]{2})?/(?:[^/]+/)?(?:dp|gp/product)/(?P<id>[^/&#$?]+)'


class AmericasTestKitchenIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.americastestkitchen'
    IE_NAME = 'AmericasTestKitchen'
    _VALID_URL = 'https?://(?:www\\.)?americastestkitchen\\.com/(?:cooks(?:country|illustrated)/)?(?P<resource_type>episode|videos)/(?P<id>\\d+)'


class AmericasTestKitchenSeasonIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.americastestkitchen'
    IE_NAME = 'AmericasTestKitchenSeason'
    _VALID_URL = 'https?://(?:www\\.)?americastestkitchen\\.com(?P<show>/cookscountry)?/episodes/browse/season_(?P<id>\\d+)'


class AngelIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.angel'
    IE_NAME = 'Angel'
    _VALID_URL = 'https?://(?:www\\.)?angel\\.com/watch/(?P<series>[^/?#]+)/episode/(?P<id>[\\w-]+)/season-(?P<season_number>\\d+)/episode-(?P<episode_number>\\d+)/(?P<title>[^/?#]+)'


class AnvatoIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.anvato'
    IE_NAME = 'Anvato'
    _VALID_URL = 'anvato:(?P<access_key_or_mcp>[^:]+):(?P<id>\\d+)'


class AllocineIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.allocine'
    IE_NAME = 'Allocine'
    _VALID_URL = 'https?://(?:www\\.)?allocine\\.fr/(?:article|video|film)/(?:fichearticle_gen_carticle=|player_gen_cmedia=|fichefilm_gen_cfilm=|video-)(?P<id>[0-9]+)(?:\\.html)?'


class AliExpressLiveIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.aliexpress'
    IE_NAME = 'AliExpressLive'
    _VALID_URL = 'https?://live\\.aliexpress\\.com/live/(?P<id>\\d+)'


class Alsace20TVBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.alsace20tv'
    IE_NAME = 'Alsace20TVBase'


class Alsace20TVIE(Alsace20TVBaseIE):
    _module = 'yt_dlp.extractor.alsace20tv'
    IE_NAME = 'Alsace20TV'
    _VALID_URL = 'https?://(?:www\\.)?alsace20\\.tv/(?:[\\w-]+/)+[\\w-]+-(?P<id>[\\w]+)'


class Alsace20TVEmbedIE(Alsace20TVBaseIE):
    _module = 'yt_dlp.extractor.alsace20tv'
    IE_NAME = 'Alsace20TVEmbed'
    _VALID_URL = 'https?://(?:www\\.)?alsace20\\.tv/emb/(?P<id>[\\w]+)'


class APAIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.apa'
    IE_NAME = 'APA'
    _VALID_URL = '(?P<base_url>https?://[^/]+\\.apa\\.at)/embed/(?P<id>[\\da-f]{8}-[\\da-f]{4}-[\\da-f]{4}-[\\da-f]{4}-[\\da-f]{12})'


class AparatIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.aparat'
    IE_NAME = 'Aparat'
    _VALID_URL = 'https?://(?:www\\.)?aparat\\.com/(?:v/|video/video/embed/videohash/)(?P<id>[a-zA-Z0-9]+)'


class AppleConnectIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.appleconnect'
    IE_NAME = 'AppleConnect'
    _VALID_URL = 'https?://itunes\\.apple\\.com/\\w{0,2}/?post/(?:id)?sa\\.(?P<id>[\\w-]+)'


class AppleTrailersIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.appletrailers'
    IE_NAME = 'appletrailers'
    _VALID_URL = 'https?://(?:www\\.|movie)?trailers\\.apple\\.com/(?:trailers|ca)/(?P<company>[^/]+)/(?P<movie>[^/]+)'


class AppleTrailersSectionIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.appletrailers'
    IE_NAME = 'appletrailers:section'
    _VALID_URL = 'https?://(?:www\\.)?trailers\\.apple\\.com/#section=(?P<id>justadded|exclusive|justhd|mostpopular|moviestudios)'


class ApplePodcastsIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.applepodcasts'
    IE_NAME = 'ApplePodcasts'
    _VALID_URL = 'https?://podcasts\\.apple\\.com/(?:[^/]+/)?podcast(?:/[^/]+){1,2}.*?\\bi=(?P<id>\\d+)'


class ArchiveOrgIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.archiveorg'
    IE_NAME = 'archive.org'
    IE_DESC = 'archive.org video and audio'
    _VALID_URL = 'https?://(?:www\\.)?archive\\.org/(?:details|embed)/(?P<id>[^?#]+)(?:[?].*)?$'


class YoutubeWebArchiveIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.archiveorg'
    IE_NAME = 'web.archive:youtube'
    IE_DESC = 'web.archive.org saved youtube videos, "ytarchive:" prefix'
    _VALID_URL = '(?x)(?:(?P<prefix>ytarchive:)|\n            (?:https?://)?web\\.archive\\.org/\n            (?:web/)?(?:(?P<date>[0-9]{14})?[0-9A-Za-z_*]*/)?  # /web and the version index is optional\n            (?:https?(?::|%3[Aa])//)?(?:\n                (?:\\w+\\.)?youtube\\.com(?::(?:80|443))?/watch(?:\\.php)?(?:\\?|%3[fF])(?:[^\\#]+(?:&|%26))?v(?:=|%3[dD])  # Youtube URL\n                |(?:wayback-fakeurl\\.archive\\.org/yt/)  # Or the internal fake url\n            )\n        )(?P<id>[0-9A-Za-z_-]{11})\n        (?(prefix)\n            (?::(?P<date2>[0-9]{14}))?$|\n            (?:%26|[#&]|$)\n        )'


class ArcPublishingIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.arcpublishing'
    IE_NAME = 'ArcPublishing'
    _VALID_URL = 'arcpublishing:(?P<org>[a-z]+):(?P<id>[\\da-f]{8}-(?:[\\da-f]{4}-){3}[\\da-f]{12})'


class ArkenaIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.arkena'
    IE_NAME = 'Arkena'
    _VALID_URL = '(?x)\n                        https?://\n                            (?:\n                                video\\.(?:arkena|qbrick)\\.com/play2/embed/player\\?|\n                                play\\.arkena\\.com/(?:config|embed)/avp/v\\d/player/media/(?P<id>[^/]+)/[^/]+/(?P<account_id>\\d+)\n                            )\n                        '


class ARDMediathekBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ard'
    IE_NAME = 'ARDMediathekBase'


class ARDBetaMediathekIE(ARDMediathekBaseIE):
    _module = 'yt_dlp.extractor.ard'
    IE_NAME = 'ARDBetaMediathek'
    _VALID_URL = '(?x)https://\n        (?:(?:beta|www)\\.)?ardmediathek\\.de/\n        (?:(?P<client>[^/]+)/)?\n        (?:player|live|video|(?P<playlist>sendung|sammlung))/\n        (?:(?P<display_id>(?(playlist)[^?#]+?|[^?#]+))/)?\n        (?P<id>(?(playlist)|Y3JpZDovL)[a-zA-Z0-9]+)\n        (?(playlist)/(?P<season>\\d+)?/?(?:[?#]|$))'


class ARDIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ard'
    IE_NAME = 'ARD'
    _VALID_URL = '(?P<mainurl>https?://(?:www\\.)?daserste\\.de/(?:[^/?#&]+/)+(?P<id>[^/?#&]+))\\.html'


class ARDMediathekIE(ARDMediathekBaseIE):
    _module = 'yt_dlp.extractor.ard'
    IE_NAME = 'ARD:mediathek'
    _VALID_URL = '^https?://(?:(?:(?:www|classic)\\.)?ardmediathek\\.de|mediathek\\.(?:daserste|rbb-online)\\.de|one\\.ard\\.de)/(?:.*/)(?P<video_id>[0-9]+|[^0-9][^/\\?]+)[^/\\?]*(?:\\?.*)?'

    @classmethod
    def suitable(cls, url):
        return False if ARDBetaMediathekIE.suitable(url) else super(ARDMediathekIE, cls).suitable(url)


class ArteTVBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.arte'
    IE_NAME = 'ArteTVBase'


class ArteTVIE(ArteTVBaseIE):
    _module = 'yt_dlp.extractor.arte'
    IE_NAME = 'ArteTV'
    _VALID_URL = '(?x)\n                    (?:https?://\n                        (?:\n                            (?:www\\.)?arte\\.tv/(?P<lang>fr|de|en|es|it|pl)/videos|\n                            api\\.arte\\.tv/api/player/v\\d+/config/(?P<lang_2>fr|de|en|es|it|pl)\n                        )\n                    |arte://program)\n                        /(?P<id>\\d{6}-\\d{3}-[AF]|LIVE)\n                    '


class ArteTVEmbedIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.arte'
    IE_NAME = 'ArteTVEmbed'
    _VALID_URL = 'https?://(?:www\\.)?arte\\.tv/player/v\\d+/index\\.php\\?.*?\\bjson_url=.+'


class ArteTVPlaylistIE(ArteTVBaseIE):
    _module = 'yt_dlp.extractor.arte'
    IE_NAME = 'ArteTVPlaylist'
    _VALID_URL = 'https?://(?:www\\.)?arte\\.tv/(?P<lang>fr|de|en|es|it|pl)/videos/(?P<id>RC-\\d{6})'


class ArteTVCategoryIE(ArteTVBaseIE):
    _module = 'yt_dlp.extractor.arte'
    IE_NAME = 'ArteTVCategory'
    _VALID_URL = 'https?://(?:www\\.)?arte\\.tv/(?P<lang>fr|de|en|es|it|pl)/videos/(?P<id>[\\w-]+(?:/[\\w-]+)*)/?\\s*$'

    @classmethod
    def suitable(cls, url):
        return (
            not any(ie.suitable(url) for ie in (ArteTVIE, ArteTVPlaylistIE, ))
            and super().suitable(url))


class ArnesIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.arnes'
    IE_NAME = 'video.arnes.si'
    IE_DESC = 'Arnes Video'
    _VALID_URL = 'https?://video\\.arnes\\.si/(?:[a-z]{2}/)?(?:watch|embed|api/(?:asset|public/video))/(?P<id>[0-9a-zA-Z]{12})'


class AsianCrushBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.asiancrush'
    IE_NAME = 'AsianCrushBase'


class AsianCrushIE(AsianCrushBaseIE):
    _module = 'yt_dlp.extractor.asiancrush'
    IE_NAME = 'AsianCrush'
    _VALID_URL = 'https?://(?:www\\.)?(?P<host>(?:(?:asiancrush|yuyutv|midnightpulp)\\.com|(?:cocoro|retrocrush)\\.tv))/video/(?:[^/]+/)?0+(?P<id>\\d+)v\\b'
    age_limit = 13


class AsianCrushPlaylistIE(AsianCrushBaseIE):
    _module = 'yt_dlp.extractor.asiancrush'
    IE_NAME = 'AsianCrushPlaylist'
    _VALID_URL = 'https?://(?:www\\.)?(?P<host>(?:(?:asiancrush|yuyutv|midnightpulp)\\.com|(?:cocoro|retrocrush)\\.tv))/series/0+(?P<id>\\d+)s\\b'


class AtresPlayerIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.atresplayer'
    IE_NAME = 'AtresPlayer'
    _VALID_URL = 'https?://(?:www\\.)?atresplayer\\.com/[^/]+/[^/]+/[^/]+/[^/]+/(?P<display_id>.+?)_(?P<id>[0-9a-f]{24})'
    _NETRC_MACHINE = 'atresplayer'


class AtScaleConfEventIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.atscaleconf'
    IE_NAME = 'AtScaleConfEvent'
    _VALID_URL = 'https?://(?:www\\.)?atscaleconference\\.com/events/(?P<id>[^/&$?]+)'


class ATTTechChannelIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.atttechchannel'
    IE_NAME = 'ATTTechChannel'
    _VALID_URL = 'https?://techchannel\\.att\\.com/play-video\\.cfm/([^/]+/)*(?P<id>.+)'


class ATVAtIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.atvat'
    IE_NAME = 'ATVAt'
    _VALID_URL = 'https?://(?:www\\.)?atv\\.at/tv/(?:[^/]+/){2,3}(?P<id>.*)'


class AudiMediaIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.audimedia'
    IE_NAME = 'AudiMedia'
    _VALID_URL = 'https?://(?:www\\.)?audi-mediacenter\\.com/(?:en|de)/audimediatv/(?:video/)?(?P<id>[^/?#]+)'


class AudioBoomIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.audioboom'
    IE_NAME = 'AudioBoom'
    _VALID_URL = 'https?://(?:www\\.)?audioboom\\.com/(?:boos|posts)/(?P<id>[0-9]+)'


class AudiodraftBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.audiodraft'
    IE_NAME = 'AudiodraftBase'


class AudiodraftCustomIE(AudiodraftBaseIE):
    _module = 'yt_dlp.extractor.audiodraft'
    IE_NAME = 'Audiodraft:custom'
    _VALID_URL = 'https?://(?:[-\\w]+)\\.audiodraft\\.com/entry/(?P<id>\\d+)'


class AudiodraftGenericIE(AudiodraftBaseIE):
    _module = 'yt_dlp.extractor.audiodraft'
    IE_NAME = 'Audiodraft:generic'
    _VALID_URL = 'https?://www\\.audiodraft\\.com/contests/[^/#]+#entries&eid=(?P<id>\\d+)'


class AudiomackIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.audiomack'
    IE_NAME = 'audiomack'
    _VALID_URL = 'https?://(?:www\\.)?audiomack\\.com/(?:song/|(?=.+/song/))(?P<id>[\\w/-]+)'


class AudiomackAlbumIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.audiomack'
    IE_NAME = 'audiomack:album'
    _VALID_URL = 'https?://(?:www\\.)?audiomack\\.com/(?:album/|(?=.+/album/))(?P<id>[\\w/-]+)'


class AudiusBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.audius'
    IE_NAME = 'AudiusBase'


class AudiusIE(AudiusBaseIE):
    _module = 'yt_dlp.extractor.audius'
    IE_NAME = 'Audius'
    IE_DESC = 'Audius.co'
    _VALID_URL = '(?x)https?://(?:www\\.)?(?:audius\\.co/(?P<uploader>[\\w\\d-]+)(?!/album|/playlist)/(?P<title>\\S+))'


class AudiusTrackIE(AudiusIE):
    _module = 'yt_dlp.extractor.audius'
    IE_NAME = 'audius:track'
    IE_DESC = 'Audius track ID or API link. Prepend with "audius:"'
    _VALID_URL = '(?x)(?:audius:)(?:https?://(?:www\\.)?.+/v1/tracks/)?(?P<track_id>\\w+)'


class AudiusPlaylistIE(AudiusBaseIE):
    _module = 'yt_dlp.extractor.audius'
    IE_NAME = 'audius:playlist'
    IE_DESC = 'Audius.co playlists'
    _VALID_URL = 'https?://(?:www\\.)?audius\\.co/(?P<uploader>[\\w\\d-]+)/(?:album|playlist)/(?P<title>\\S+)'


class AudiusProfileIE(AudiusPlaylistIE):
    _module = 'yt_dlp.extractor.audius'
    IE_NAME = 'audius:artist'
    IE_DESC = 'Audius.co profile/artist pages'
    _VALID_URL = 'https?://(?:www)?audius\\.co/(?P<id>[^\\/]+)/?(?:[?#]|$)'


class AWAANIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.awaan'
    IE_NAME = 'AWAAN'
    _VALID_URL = 'https?://(?:www\\.)?(?:awaan|dcndigital)\\.ae/(?:#/)?show/(?P<show_id>\\d+)/[^/]+(?:/(?P<id>\\d+)/(?P<season_id>\\d+))?'


class AWAANBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.awaan'
    IE_NAME = 'AWAANBase'


class AWAANVideoIE(AWAANBaseIE):
    _module = 'yt_dlp.extractor.awaan'
    IE_NAME = 'awaan:video'
    _VALID_URL = 'https?://(?:www\\.)?(?:awaan|dcndigital)\\.ae/(?:#/)?(?:video(?:/[^/]+)?|media|catchup/[^/]+/[^/]+)/(?P<id>\\d+)'


class AWAANLiveIE(AWAANBaseIE):
    _module = 'yt_dlp.extractor.awaan'
    IE_NAME = 'awaan:live'
    _VALID_URL = 'https?://(?:www\\.)?(?:awaan|dcndigital)\\.ae/(?:#/)?live/(?P<id>\\d+)'


class AWAANSeasonIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.awaan'
    IE_NAME = 'awaan:season'
    _VALID_URL = 'https?://(?:www\\.)?(?:awaan|dcndigital)\\.ae/(?:#/)?program/(?:(?P<show_id>\\d+)|season/(?P<season_id>\\d+))'


class AZMedienIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.azmedien'
    IE_NAME = 'AZMedien'
    IE_DESC = 'AZ Medien videos'
    _VALID_URL = '(?x)\n                    https?://\n                        (?:www\\.|tv\\.)?\n                        (?P<host>\n                            telezueri\\.ch|\n                            telebaern\\.tv|\n                            telem1\\.ch|\n                            tvo-online\\.ch\n                        )/\n                        [^/]+/\n                        (?P<id>\n                            [^/]+-(?P<article_id>\\d+)\n                        )\n                        (?:\n                            \\#video=\n                            (?P<kaltura_id>\n                                [_0-9a-z]+\n                            )\n                        )?\n                    '


class BaiduVideoIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.baidu'
    IE_NAME = 'BaiduVideo'
    IE_DESC = '百度视频'
    _VALID_URL = 'https?://v\\.baidu\\.com/(?P<type>[a-z]+)/(?P<id>\\d+)\\.htm'


class BanByeBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.banbye'
    IE_NAME = 'BanByeBase'


class BanByeIE(BanByeBaseIE):
    _module = 'yt_dlp.extractor.banbye'
    IE_NAME = 'BanBye'
    _VALID_URL = 'https?://(?:www\\.)?banbye.com/(?:en/)?watch/(?P<id>\\w+)'


class BanByeChannelIE(BanByeBaseIE):
    _module = 'yt_dlp.extractor.banbye'
    IE_NAME = 'BanByeChannel'
    _VALID_URL = 'https?://(?:www\\.)?banbye.com/(?:en/)?channel/(?P<id>\\w+)'


class BandcampIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.bandcamp'
    IE_NAME = 'Bandcamp'
    _VALID_URL = 'https?://(?P<uploader>[^/]+)\\.bandcamp\\.com/track/(?P<id>[^/?#&]+)'


class BandcampAlbumIE(BandcampIE):
    _module = 'yt_dlp.extractor.bandcamp'
    IE_NAME = 'Bandcamp:album'
    _VALID_URL = 'https?://(?:(?P<subdomain>[^.]+)\\.)?bandcamp\\.com/album/(?P<id>[^/?#&]+)'

    @classmethod
    def suitable(cls, url):
        return (False
                if BandcampWeeklyIE.suitable(url) or BandcampIE.suitable(url)
                else super(BandcampAlbumIE, cls).suitable(url))


class BandcampWeeklyIE(BandcampIE):
    _module = 'yt_dlp.extractor.bandcamp'
    IE_NAME = 'Bandcamp:weekly'
    _VALID_URL = 'https?://(?:www\\.)?bandcamp\\.com/?\\?(?:.*?&)?show=(?P<id>\\d+)'


class BandcampUserIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.bandcamp'
    IE_NAME = 'Bandcamp:user'
    _VALID_URL = 'https?://(?!www\\.)(?P<id>[^.]+)\\.bandcamp\\.com(?:/music)?/?(?:[#?]|$)'


class BannedVideoIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.bannedvideo'
    IE_NAME = 'BannedVideo'
    _VALID_URL = 'https?://(?:www\\.)?banned\\.video/watch\\?id=(?P<id>[0-f]{24})'


class BBCCoUkIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.bbc'
    IE_NAME = 'bbc.co.uk'
    IE_DESC = 'BBC iPlayer'
    _VALID_URL = '(?x)\n                    https?://\n                        (?:www\\.)?bbc\\.co\\.uk/\n                        (?:\n                            programmes/(?!articles/)|\n                            iplayer(?:/[^/]+)?/(?:episode/|playlist/)|\n                            music/(?:clips|audiovideo/popular)[/#]|\n                            radio/player/|\n                            sounds/play/|\n                            events/[^/]+/play/[^/]+/\n                        )\n                        (?P<id>(?:[pbml][\\da-z]{7}|w[\\da-z]{7,14}))(?!/(?:episodes|broadcasts|clips))\n                    '
    _NETRC_MACHINE = 'bbc'


class BBCCoUkArticleIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.bbc'
    IE_NAME = 'bbc.co.uk:article'
    IE_DESC = 'BBC articles'
    _VALID_URL = 'https?://(?:www\\.)?bbc\\.co\\.uk/programmes/articles/(?P<id>[a-zA-Z0-9]+)'


class BBCCoUkIPlayerPlaylistBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.bbc'
    IE_NAME = 'BBCCoUkIPlayerPlaylistBase'


class BBCCoUkIPlayerEpisodesIE(BBCCoUkIPlayerPlaylistBaseIE):
    _module = 'yt_dlp.extractor.bbc'
    IE_NAME = 'bbc.co.uk:iplayer:episodes'
    _VALID_URL = 'https?://(?:www\\.)?bbc\\.co\\.uk/iplayer/episodes/(?P<id>(?:[pbml][\\da-z]{7}|w[\\da-z]{7,14}))'


class BBCCoUkIPlayerGroupIE(BBCCoUkIPlayerPlaylistBaseIE):
    _module = 'yt_dlp.extractor.bbc'
    IE_NAME = 'bbc.co.uk:iplayer:group'
    _VALID_URL = 'https?://(?:www\\.)?bbc\\.co\\.uk/iplayer/group/(?P<id>(?:[pbml][\\da-z]{7}|w[\\da-z]{7,14}))'


class BBCCoUkPlaylistBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.bbc'
    IE_NAME = 'BBCCoUkPlaylistBase'


class BBCCoUkPlaylistIE(BBCCoUkPlaylistBaseIE):
    _module = 'yt_dlp.extractor.bbc'
    IE_NAME = 'bbc.co.uk:playlist'
    _VALID_URL = 'https?://(?:www\\.)?bbc\\.co\\.uk/programmes/(?P<id>(?:[pbml][\\da-z]{7}|w[\\da-z]{7,14}))/(?:episodes|broadcasts|clips)'


class BBCIE(BBCCoUkIE):
    _module = 'yt_dlp.extractor.bbc'
    IE_NAME = 'bbc'
    IE_DESC = 'BBC'
    _VALID_URL = '(?x)\n        https?://(?:www\\.)?(?:\n            bbc\\.(?:com|co\\.uk)|\n            bbcnewsd73hkzno2ini43t4gblxvycyac5aw4gnv7t2rccijh7745uqd\\.onion|\n            bbcweb3hytmzhn5d532owbu6oqadra5z3ar726vq5kgwwn6aucdccrad\\.onion\n        )/(?:[^/]+/)+(?P<id>[^/#?]+)'
    _NETRC_MACHINE = 'bbc'

    @classmethod
    def suitable(cls, url):
        EXCLUDE_IE = (BBCCoUkIE, BBCCoUkArticleIE, BBCCoUkIPlayerEpisodesIE, BBCCoUkIPlayerGroupIE, BBCCoUkPlaylistIE)
        return (False if any(ie.suitable(url) for ie in EXCLUDE_IE)
                else super(BBCIE, cls).suitable(url))


class BeegIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.beeg'
    IE_NAME = 'Beeg'
    _VALID_URL = 'https?://(?:www\\.)?beeg\\.(?:com(?:/video)?)/-?(?P<id>\\d+)'
    age_limit = 18


class BehindKinkIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.behindkink'
    IE_NAME = 'BehindKink'
    _VALID_URL = 'https?://(?:www\\.)?behindkink\\.com/(?P<year>[0-9]{4})/(?P<month>[0-9]{2})/(?P<day>[0-9]{2})/(?P<id>[^/#?_]+)'
    age_limit = 18


class BellMediaIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.bellmedia'
    IE_NAME = 'BellMedia'
    _VALID_URL = '(?x)https?://(?:www\\.)?\n        (?P<domain>\n            (?:\n                ctv|\n                tsn|\n                bnn(?:bloomberg)?|\n                thecomedynetwork|\n                discovery|\n                discoveryvelocity|\n                sciencechannel|\n                investigationdiscovery|\n                animalplanet|\n                bravo|\n                mtv|\n                space|\n                etalk|\n                marilyn\n            )\\.ca|\n            (?:much|cp24)\\.com\n        )/.*?(?:\\b(?:vid(?:eoid)?|clipId)=|-vid|~|%7E|/(?:episode)?)(?P<id>[0-9]{6,})'


class BeatportIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.beatport'
    IE_NAME = 'Beatport'
    _VALID_URL = 'https?://(?:www\\.|pro\\.)?beatport\\.com/track/(?P<display_id>[^/]+)/(?P<id>[0-9]+)'


class BerufeTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.berufetv'
    IE_NAME = 'BerufeTV'
    _VALID_URL = 'https?://(?:www\\.)?web\\.arbeitsagentur\\.de/berufetv/[^?#]+/film;filmId=(?P<id>[\\w-]+)'


class MTVServicesInfoExtractor(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.mtv'
    IE_NAME = 'MTVServicesInfoExtract'


class BetIE(MTVServicesInfoExtractor):
    _module = 'yt_dlp.extractor.bet'
    IE_NAME = 'Bet'
    _VALID_URL = 'https?://(?:www\\.)?bet\\.com/(?:[^/]+/)+(?P<id>.+?)\\.html'


class BFIPlayerIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.bfi'
    IE_NAME = 'bfi:player'
    _VALID_URL = 'https?://player\\.bfi\\.org\\.uk/[^/]+/film/watch-(?P<id>[\\w-]+)-online'


class BFMTVBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.bfmtv'
    IE_NAME = 'BFMTVBase'


class BFMTVIE(BFMTVBaseIE):
    _module = 'yt_dlp.extractor.bfmtv'
    IE_NAME = 'bfmtv'
    _VALID_URL = 'https?://(?:www\\.)?bfmtv\\.com/(?:[^/]+/)*[^/?&#]+_V[A-Z]-(?P<id>\\d{12})\\.html'


class BFMTVLiveIE(BFMTVIE):
    _module = 'yt_dlp.extractor.bfmtv'
    IE_NAME = 'bfmtv:live'
    _VALID_URL = 'https?://(?:www\\.)?bfmtv\\.com/(?P<id>(?:[^/]+/)?en-direct)'


class BFMTVArticleIE(BFMTVBaseIE):
    _module = 'yt_dlp.extractor.bfmtv'
    IE_NAME = 'bfmtv:article'
    _VALID_URL = 'https?://(?:www\\.)?bfmtv\\.com/(?:[^/]+/)*[^/?&#]+_A[A-Z]-(?P<id>\\d{12})\\.html'


class BibelTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.bibeltv'
    IE_NAME = 'BibelTV'
    _VALID_URL = 'https?://(?:www\\.)?bibeltv\\.de/mediathek/videos/(?:crn/)?(?P<id>\\d+)'


class BigflixIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.bigflix'
    IE_NAME = 'Bigflix'
    _VALID_URL = 'https?://(?:www\\.)?bigflix\\.com/.+/(?P<id>[0-9]+)'


class BigoIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.bigo'
    IE_NAME = 'Bigo'
    _VALID_URL = 'https?://(?:www\\.)?bigo\\.tv/(?:[a-z]{2,}/)?(?P<id>[^/]+)'


class BildIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.bild'
    IE_NAME = 'Bild'
    IE_DESC = 'Bild.de'
    _VALID_URL = 'https?://(?:www\\.)?bild\\.de/(?:[^/]+/)+(?P<display_id>[^/]+)-(?P<id>\\d+)(?:,auto=true)?\\.bild\\.html'


class BilibiliBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.bilibili'
    IE_NAME = 'BilibiliBase'


class BiliBiliIE(BilibiliBaseIE):
    _module = 'yt_dlp.extractor.bilibili'
    IE_NAME = 'BiliBili'
    _VALID_URL = 'https?://www\\.bilibili\\.com/video/[aAbB][vV](?P<id>[^/?#&]+)'


class BiliBiliBangumiIE(BilibiliBaseIE):
    _module = 'yt_dlp.extractor.bilibili'
    IE_NAME = 'BiliBiliBangumi'
    _VALID_URL = '(?x)https?://www\\.bilibili\\.com/bangumi/play/(?P<id>(?:ss|ep)\\d+)'


class BiliBiliBangumiMediaIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.bilibili'
    IE_NAME = 'BiliBiliBangumiMedia'
    _VALID_URL = 'https?://www\\.bilibili\\.com/bangumi/media/md(?P<id>\\d+)'


class BiliBiliSearchIE(LazyLoadSearchExtractor):
    _module = 'yt_dlp.extractor.bilibili'
    IE_NAME = 'BiliBiliSearch'
    IE_DESC = 'Bilibili video search'
    SEARCH_KEY = 'bilisearch'
    _VALID_URL = 'bilisearch(?P<prefix>|[1-9][0-9]*|all):(?P<query>[\\s\\S]+)'


class BilibiliCategoryIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.bilibili'
    IE_NAME = 'Bilibili category extractor'
    _VALID_URL = 'https?://www\\.bilibili\\.com/v/[a-zA-Z]+\\/[a-zA-Z]+'


class BilibiliAudioBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.bilibili'
    IE_NAME = 'BilibiliAudioBase'


class BilibiliAudioIE(BilibiliAudioBaseIE):
    _module = 'yt_dlp.extractor.bilibili'
    IE_NAME = 'BilibiliAudio'
    _VALID_URL = 'https?://(?:www\\.)?bilibili\\.com/audio/au(?P<id>\\d+)'


class BilibiliAudioAlbumIE(BilibiliAudioBaseIE):
    _module = 'yt_dlp.extractor.bilibili'
    IE_NAME = 'BilibiliAudioAlbum'
    _VALID_URL = 'https?://(?:www\\.)?bilibili\\.com/audio/am(?P<id>\\d+)'


class BiliBiliPlayerIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.bilibili'
    IE_NAME = 'BiliBiliPlayer'
    _VALID_URL = 'https?://player\\.bilibili\\.com/player\\.html\\?.*?\\baid=(?P<id>\\d+)'


class BilibiliSpaceBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.bilibili'
    IE_NAME = 'BilibiliSpaceBase'


class BilibiliSpaceVideoIE(BilibiliSpaceBaseIE):
    _module = 'yt_dlp.extractor.bilibili'
    IE_NAME = 'BilibiliSpaceVideo'
    _VALID_URL = 'https?://space\\.bilibili\\.com/(?P<id>\\d+)(?P<video>/video)?/?(?:[?#]|$)'


class BilibiliSpaceAudioIE(BilibiliSpaceBaseIE):
    _module = 'yt_dlp.extractor.bilibili'
    IE_NAME = 'BilibiliSpaceAudio'
    _VALID_URL = 'https?://space\\.bilibili\\.com/(?P<id>\\d+)/audio'


class BilibiliSpacePlaylistIE(BilibiliSpaceBaseIE):
    _module = 'yt_dlp.extractor.bilibili'
    IE_NAME = 'BilibiliSpacePlaylist'
    _VALID_URL = 'https?://space.bilibili\\.com/(?P<mid>\\d+)/channel/collectiondetail\\?sid=(?P<sid>\\d+)'


class BiliIntlBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.bilibili'
    IE_NAME = 'BiliIntlBase'
    _NETRC_MACHINE = 'biliintl'


class BiliIntlIE(BiliIntlBaseIE):
    _module = 'yt_dlp.extractor.bilibili'
    IE_NAME = 'BiliIntl'
    _VALID_URL = 'https?://(?:www\\.)?bili(?:bili\\.tv|intl\\.com)/(?:[a-zA-Z]{2}/)?(play/(?P<season_id>\\d+)/(?P<ep_id>\\d+)|video/(?P<aid>\\d+))'
    _NETRC_MACHINE = 'biliintl'


class BiliIntlSeriesIE(BiliIntlBaseIE):
    _module = 'yt_dlp.extractor.bilibili'
    IE_NAME = 'BiliIntlSeries'
    _VALID_URL = 'https?://(?:www\\.)?bili(?:bili\\.tv|intl\\.com)/(?:[a-zA-Z]{2}/)?play/(?P<id>\\d+)/?(?:[?#]|$)'
    _NETRC_MACHINE = 'biliintl'


class BiliLiveIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.bilibili'
    IE_NAME = 'BiliLive'
    _VALID_URL = 'https?://live.bilibili.com/(?P<id>\\d+)'


class BioBioChileTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.biobiochiletv'
    IE_NAME = 'BioBioChileTV'
    _VALID_URL = 'https?://(?:tv|www)\\.biobiochile\\.cl/(?:notas|noticias)/(?:[^/]+/)+(?P<id>[^/]+)\\.shtml'


class BitChuteIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.bitchute'
    IE_NAME = 'BitChute'
    _VALID_URL = 'https?://(?:www\\.)?bitchute\\.com/(?:video|embed|torrent/[^/]+)/(?P<id>[^/?#&]+)'


class BitChuteChannelIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.bitchute'
    IE_NAME = 'BitChuteChannel'
    _VALID_URL = 'https?://(?:www\\.)?bitchute\\.com/(?P<type>channel|playlist)/(?P<id>[^/?#&]+)'


class BitwaveReplayIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.bitwave'
    IE_NAME = 'bitwave:replay'
    _VALID_URL = 'https?://(?:www\\.)?bitwave\\.tv/(?P<user>\\w+)/replay/(?P<id>\\w+)/?$'


class BitwaveStreamIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.bitwave'
    IE_NAME = 'bitwave:stream'
    _VALID_URL = 'https?://(?:www\\.)?bitwave\\.tv/(?P<id>\\w+)/?$'


class BIQLEIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.biqle'
    IE_NAME = 'BIQLE'
    _VALID_URL = 'https?://(?:www\\.)?biqle\\.(?:com|org|ru)/watch/(?P<id>-?\\d+_\\d+)'


class BlackboardCollaborateIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.blackboardcollaborate'
    IE_NAME = 'BlackboardCollaborate'
    _VALID_URL = '(?x)\n                        https?://\n                        (?P<region>[a-z-]+)\\.bbcollab\\.com/\n                        (?:\n                            collab/ui/session/playback/load|\n                            recording\n                        )/\n                        (?P<id>[^/]+)'


class BleacherReportIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.bleacherreport'
    IE_NAME = 'BleacherReport'
    _VALID_URL = 'https?://(?:www\\.)?bleacherreport\\.com/articles/(?P<id>\\d+)'


class BleacherReportCMSIE(AMPIE):
    _module = 'yt_dlp.extractor.bleacherreport'
    IE_NAME = 'BleacherReportCMS'
    _VALID_URL = 'https?://(?:www\\.)?bleacherreport\\.com/video_embed\\?id=(?P<id>[0-9a-f-]{36}|\\d{5})'


class BloggerIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.blogger'
    IE_NAME = 'blogger.com'
    _VALID_URL = 'https?://(?:www\\.)?blogger\\.com/video\\.g\\?token=(?P<id>.+)'


class BloombergIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.bloomberg'
    IE_NAME = 'Bloomberg'
    _VALID_URL = 'https?://(?:www\\.)?bloomberg\\.com/(?:[^/]+/)*(?P<id>[^/?#]+)'


class BokeCCBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.bokecc'
    IE_NAME = 'BokeCCBase'


class BokeCCIE(BokeCCBaseIE):
    _module = 'yt_dlp.extractor.bokecc'
    IE_NAME = 'BokeCC'
    _VALID_URL = 'https?://union\\.bokecc\\.com/playvideo\\.bo\\?(?P<query>.*)'


class BongaCamsIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.bongacams'
    IE_NAME = 'BongaCams'
    _VALID_URL = 'https?://(?P<host>(?:[^/]+\\.)?bongacams\\d*\\.(?:com|net))/(?P<id>[^/?&#]+)'
    age_limit = 18


class BostonGlobeIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.bostonglobe'
    IE_NAME = 'BostonGlobe'
    _VALID_URL = '(?i)https?://(?:www\\.)?bostonglobe\\.com/.*/(?P<id>[^/]+)/\\w+(?:\\.html)?'


class BoxIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.box'
    IE_NAME = 'Box'
    _VALID_URL = 'https?://(?:[^.]+\\.)?app\\.box\\.com/s/(?P<shared_name>[^/]+)/file/(?P<id>\\d+)'


class BooyahBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.booyah'
    IE_NAME = 'BooyahBase'


class BooyahClipsIE(BooyahBaseIE):
    _module = 'yt_dlp.extractor.booyah'
    IE_NAME = 'BooyahClips'
    _VALID_URL = 'https?://booyah.live/clips/(?P<id>\\d+)'


class BpbIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.bpb'
    IE_NAME = 'Bpb'
    IE_DESC = 'Bundeszentrale für politische Bildung'
    _VALID_URL = 'https?://(?:www\\.)?bpb\\.de/mediathek/(?P<id>[0-9]+)/'


class BRIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.br'
    IE_NAME = 'BR'
    IE_DESC = 'Bayerischer Rundfunk'
    _VALID_URL = '(?P<base_url>https?://(?:www\\.)?br(?:-klassik)?\\.de)/(?:[a-z0-9\\-_]+/)+(?P<id>[a-z0-9\\-_]+)\\.html'


class BRMediathekIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.br'
    IE_NAME = 'BRMediathek'
    IE_DESC = 'Bayerischer Rundfunk Mediathek'
    _VALID_URL = 'https?://(?:www\\.)?br\\.de/mediathek//?video/(?:[^/?&#]+?-)?(?P<id>av:[0-9a-f]{24})'


class BravoTVIE(AdobePassIE):
    _module = 'yt_dlp.extractor.bravotv'
    IE_NAME = 'BravoTV'
    _VALID_URL = 'https?://(?:www\\.)?(?P<req_id>bravotv|oxygen)\\.com/(?:[^/]+/)+(?P<id>[^/?#]+)'


class BreakIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.breakcom'
    IE_NAME = 'Break'
    _VALID_URL = 'https?://(?:www\\.)?break\\.com/video/(?P<display_id>[^/]+?)(?:-(?P<id>\\d+))?(?:[/?#&]|$)'
    age_limit = 13


class BreitBartIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.breitbart'
    IE_NAME = 'BreitBart'
    _VALID_URL = 'https?:\\/\\/(?:www\\.)breitbart.com/videos/v/(?P<id>[^/]+)'


class BrightcoveLegacyIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.brightcove'
    IE_NAME = 'brightcove:legacy'
    _VALID_URL = '(?:https?://.*brightcove\\.com/(services|viewer).*?\\?|brightcove:)(?P<query>.*)'


class BrightcoveNewIE(AdobePassIE):
    _module = 'yt_dlp.extractor.brightcove'
    IE_NAME = 'brightcove:new'
    _VALID_URL = 'https?://players\\.brightcove\\.net/(?P<account_id>\\d+)/(?P<player_id>[^/]+)_(?P<embed>[^/]+)/index\\.html\\?.*(?P<content_type>video|playlist)Id=(?P<video_id>\\d+|ref:[^&]+)'


class BandaiChannelIE(BrightcoveNewIE):
    _module = 'yt_dlp.extractor.bandaichannel'
    IE_NAME = 'bandaichannel'
    _VALID_URL = 'https?://(?:www\\.)?b-ch\\.com/titles/(?P<id>\\d+/\\d+)'


class BusinessInsiderIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.businessinsider'
    IE_NAME = 'BusinessInsider'
    _VALID_URL = 'https?://(?:[^/]+\\.)?businessinsider\\.(?:com|nl)/(?:[^/]+/)*(?P<id>[^/?#&]+)'


class BundesligaIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.bundesliga'
    IE_NAME = 'Bundesliga'
    _VALID_URL = 'https?://(?:www\\.)?bundesliga\\.com/[a-z]{2}/bundesliga/videos(?:/[^?]+)?\\?vid=(?P<id>[a-zA-Z0-9]{8})'


class BuzzFeedIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.buzzfeed'
    IE_NAME = 'BuzzFeed'
    _VALID_URL = 'https?://(?:www\\.)?buzzfeed\\.com/[^?#]*?/(?P<id>[^?#]+)'


class BYUtvIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.byutv'
    IE_NAME = 'BYUtv'
    _VALID_URL = 'https?://(?:www\\.)?byutv\\.org/(?:watch|player)/(?!event/)(?P<id>[0-9a-f-]+)(?:/(?P<display_id>[^/?#&]+))?'


class C56IE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.c56'
    IE_NAME = '56.com'
    _VALID_URL = 'https?://(?:(?:www|player)\\.)?56\\.com/(?:.+?/)?(?:v_|(?:play_album.+-))(?P<textid>.+?)\\.(?:html|swf)'


class CableAVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.cableav'
    IE_NAME = 'CableAV'
    _VALID_URL = 'https://cableav\\.tv/(?P<id>[a-zA-Z0-9]+)'


class CallinIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.callin'
    IE_NAME = 'Callin'
    _VALID_URL = 'https?://(?:www\\.)?callin\\.com/(episode)/(?P<id>[-a-zA-Z]+)'


class CaltransIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.caltrans'
    IE_NAME = 'Caltrans'
    _VALID_URL = 'https?://(?:[^/]+\\.)?ca\\.gov/vm/loc/[^/]+/(?P<id>[a-z0-9_]+)\\.htm'


class CAM4IE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.cam4'
    IE_NAME = 'CAM4'
    _VALID_URL = 'https?://(?:[^/]+\\.)?cam4\\.com/(?P<id>[a-z0-9_]+)'
    age_limit = 18


class CamdemyIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.camdemy'
    IE_NAME = 'Camdemy'
    _VALID_URL = 'https?://(?:www\\.)?camdemy\\.com/media/(?P<id>\\d+)'


class CamdemyFolderIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.camdemy'
    IE_NAME = 'CamdemyFolder'
    _VALID_URL = 'https?://(?:www\\.)?camdemy\\.com/folder/(?P<id>\\d+)'


class CamModelsIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.cammodels'
    IE_NAME = 'CamModels'
    _VALID_URL = 'https?://(?:www\\.)?cammodels\\.com/cam/(?P<id>[^/?#&]+)'


class CamsodaIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.camsoda'
    IE_NAME = 'Camsoda'
    _VALID_URL = 'https?://www\\.camsoda\\.com/(?P<id>[\\w-]+)'
    age_limit = 18


class CamtasiaEmbedIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.camtasia'
    IE_NAME = 'CamtasiaEmbed'
    _VALID_URL = False


class CamWithHerIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.camwithher'
    IE_NAME = 'CamWithHer'
    _VALID_URL = 'https?://(?:www\\.)?camwithher\\.tv/view_video\\.php\\?.*\\bviewkey=(?P<id>\\w+)'
    age_limit = 18


class CanalAlphaIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.canalalpha'
    IE_NAME = 'CanalAlpha'
    _VALID_URL = 'https?://(?:www\\.)?canalalpha\\.ch/play/[^/]+/[^/]+/(?P<id>\\d+)/?.*'


class CanalplusIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.canalplus'
    IE_NAME = 'Canalplus'
    IE_DESC = 'mycanal.fr and piwiplus.fr'
    _VALID_URL = 'https?://(?:www\\.)?(?P<site>mycanal|piwiplus)\\.fr/(?:[^/]+/)*(?P<display_id>[^?/]+)(?:\\.html\\?.*\\bvid=|/p/)(?P<id>\\d+)'


class Canalc2IE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.canalc2'
    IE_NAME = 'canalc2.tv'
    _VALID_URL = 'https?://(?:(?:www\\.)?canalc2\\.tv/video/|archives-canalc2\\.u-strasbg\\.fr/video\\.asp\\?.*\\bidVideo=)(?P<id>\\d+)'


class CanvasIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.canvas'
    IE_NAME = 'Canvas'
    _VALID_URL = 'https?://mediazone\\.vrt\\.be/api/v1/(?P<site_id>canvas|een|ketnet|vrt(?:video|nieuws)|sporza|dako)/assets/(?P<id>[^/?#&]+)'


class CanvasEenIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.canvas'
    IE_NAME = 'CanvasEen'
    IE_DESC = 'canvas.be and een.be'
    _VALID_URL = 'https?://(?:www\\.)?(?P<site_id>canvas|een)\\.be/(?:[^/]+/)*(?P<id>[^/?#&]+)'


class GigyaBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.gigya'
    IE_NAME = 'GigyaBase'


class VrtNUIE(GigyaBaseIE):
    _module = 'yt_dlp.extractor.canvas'
    IE_NAME = 'VrtNU'
    IE_DESC = 'VrtNU.be'
    _VALID_URL = 'https?://(?:www\\.)?vrt\\.be/vrtnu/a-z/(?:[^/]+/){2}(?P<id>[^/?#&]+)'
    _NETRC_MACHINE = 'vrtnu'


class DagelijkseKostIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.canvas'
    IE_NAME = 'DagelijkseKost'
    IE_DESC = 'dagelijksekost.een.be'
    _VALID_URL = 'https?://dagelijksekost\\.een\\.be/gerechten/(?P<id>[^/?#&]+)'


class CarambaTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.carambatv'
    IE_NAME = 'CarambaTV'
    _VALID_URL = '(?:carambatv:|https?://video1\\.carambatv\\.ru/v/)(?P<id>\\d+)'


class CarambaTVPageIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.carambatv'
    IE_NAME = 'CarambaTVPage'
    _VALID_URL = 'https?://carambatv\\.ru/(?:[^/]+/)+(?P<id>[^/?#&]+)'


class CartoonNetworkIE(TurnerBaseIE):
    _module = 'yt_dlp.extractor.cartoonnetwork'
    IE_NAME = 'CartoonNetwork'
    _VALID_URL = 'https?://(?:www\\.)?cartoonnetwork\\.com/video/(?:[^/]+/)+(?P<id>[^/?#]+)-(?:clip|episode)\\.html'


class CBCIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.cbc'
    IE_NAME = 'cbc.ca'
    _VALID_URL = 'https?://(?:www\\.)?cbc\\.ca/(?!player/)(?:[^/]+/)+(?P<id>[^/?#]+)'

    @classmethod
    def suitable(cls, url):
        return False if CBCPlayerIE.suitable(url) else super(CBCIE, cls).suitable(url)


class CBCPlayerIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.cbc'
    IE_NAME = 'cbc.ca:player'
    _VALID_URL = '(?:cbcplayer:|https?://(?:www\\.)?cbc\\.ca/(?:player/play/|i/caffeine/syndicate/\\?mediaId=))(?P<id>\\d+)'


class CBCGemIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.cbc'
    IE_NAME = 'gem.cbc.ca'
    _VALID_URL = 'https?://gem\\.cbc\\.ca/media/(?P<id>[0-9a-z-]+/s[0-9]+[a-z][0-9]+)'
    _NETRC_MACHINE = 'cbcgem'


class CBCGemPlaylistIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.cbc'
    IE_NAME = 'gem.cbc.ca:playlist'
    _VALID_URL = 'https?://gem\\.cbc\\.ca/media/(?P<id>(?P<show>[0-9a-z-]+)/s(?P<season>[0-9]+))/?(?:[?#]|$)'


class CBCGemLiveIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.cbc'
    IE_NAME = 'gem.cbc.ca:live'
    _VALID_URL = 'https?://gem\\.cbc\\.ca/live/(?P<id>\\d+)'


class CBSLocalIE(AnvatoIE):
    _module = 'yt_dlp.extractor.cbslocal'
    IE_NAME = 'CBSLocal'
    _VALID_URL = 'https?://[a-z]+\\.cbslocal\\.com/video/(?P<id>\\d+)'


class CBSLocalArticleIE(AnvatoIE):
    _module = 'yt_dlp.extractor.cbslocal'
    IE_NAME = 'CBSLocalArticle'
    _VALID_URL = 'https?://[a-z]+\\.cbslocal\\.com/\\d+/\\d+/\\d+/(?P<id>[0-9a-z-]+)'


class CBSNewsLiveVideoIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.cbsnews'
    IE_NAME = 'cbsnews:livevideo'
    IE_DESC = 'CBS News Live Videos'
    _VALID_URL = 'https?://(?:www\\.)?cbsnews\\.com/live/video/(?P<id>[^/?#]+)'


class CBSSportsEmbedIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.cbssports'
    IE_NAME = 'cbssports:embed'
    _VALID_URL = '(?ix)https?://(?:(?:www\\.)?cbs|embed\\.247)sports\\.com/player/embed.+?\n        (?:\n            ids%3D(?P<id>[\\da-f]{8}-(?:[\\da-f]{4}-){3}[\\da-f]{12})|\n            pcid%3D(?P<pcid>\\d+)\n        )'


class CBSSportsBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.cbssports'
    IE_NAME = 'CBSSportsBase'


class CBSSportsIE(CBSSportsBaseIE):
    _module = 'yt_dlp.extractor.cbssports'
    IE_NAME = 'cbssports'
    _VALID_URL = 'https?://(?:www\\.)?cbssports\\.com/[^/]+/video/(?P<id>[^/?#&]+)'


class TwentyFourSevenSportsIE(CBSSportsBaseIE):
    _module = 'yt_dlp.extractor.cbssports'
    IE_NAME = '247sports'
    _VALID_URL = 'https?://(?:www\\.)?247sports\\.com/Video/(?:[^/?#&]+-)?(?P<id>\\d+)'


class CCCIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ccc'
    IE_NAME = 'media.ccc.de'
    _VALID_URL = 'https?://(?:www\\.)?media\\.ccc\\.de/v/(?P<id>[^/?#&]+)'


class CCCPlaylistIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ccc'
    IE_NAME = 'media.ccc.de:lists'
    _VALID_URL = 'https?://(?:www\\.)?media\\.ccc\\.de/c/(?P<id>[^/?#&]+)'


class CCMAIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ccma'
    IE_NAME = 'CCMA'
    _VALID_URL = 'https?://(?:www\\.)?ccma\\.cat/(?:[^/]+/)*?(?P<type>video|audio)/(?P<id>\\d+)'
    age_limit = 16


class CCTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.cctv'
    IE_NAME = 'CCTV'
    IE_DESC = '央视网'
    _VALID_URL = 'https?://(?:(?:[^/]+)\\.(?:cntv|cctv)\\.(?:com|cn)|(?:www\\.)?ncpa-classic\\.com)/(?:[^/]+/)*?(?P<id>[^/?#&]+?)(?:/index)?(?:\\.s?html|[?#&]|$)'


class CDAIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.cda'
    IE_NAME = 'CDA'
    _VALID_URL = 'https?://(?:(?:www\\.)?cda\\.pl/video|ebd\\.cda\\.pl/[0-9]+x[0-9]+)/(?P<id>[0-9a-z]+)'
    _NETRC_MACHINE = 'cdapl'
    age_limit = 18


class CellebriteIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.cellebrite'
    IE_NAME = 'Cellebrite'
    _VALID_URL = 'https?://cellebrite\\.com/(?:\\w+)?/(?P<id>[\\w-]+)'


class CeskaTelevizeIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ceskatelevize'
    IE_NAME = 'CeskaTelevize'
    _VALID_URL = 'https?://(?:www\\.)?ceskatelevize\\.cz/(?:ivysilani|porady|zive)/(?:[^/?#&]+/)*(?P<id>[^/#?]+)'


class CGTNIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.cgtn'
    IE_NAME = 'CGTN'
    _VALID_URL = 'https?://news\\.cgtn\\.com/news/[0-9]{4}-[0-9]{2}-[0-9]{2}/[a-zA-Z0-9-]+-(?P<id>[a-zA-Z0-9-]+)/index\\.html'


class Channel9IE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.channel9'
    IE_NAME = 'channel9'
    IE_DESC = 'Channel 9'
    _VALID_URL = 'https?://(?:www\\.)?(?:channel9\\.msdn\\.com|s\\.ch9\\.ms)/(?P<contentpath>.+?)(?P<rss>/RSS)?/?(?:[?#&]|$)'


class CharlieRoseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.charlierose'
    IE_NAME = 'CharlieRose'
    _VALID_URL = 'https?://(?:www\\.)?charlierose\\.com/(?:video|episode)(?:s|/player)/(?P<id>\\d+)'


class ChaturbateIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.chaturbate'
    IE_NAME = 'Chaturbate'
    _VALID_URL = 'https?://(?:[^/]+\\.)?chaturbate\\.com/(?:fullvideo/?\\?.*?\\bb=)?(?P<id>[^/?&#]+)'
    age_limit = 18


class ChilloutzoneIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.chilloutzone'
    IE_NAME = 'Chilloutzone'
    _VALID_URL = 'https?://(?:www\\.)?chilloutzone\\.net/video/(?P<id>[\\w|-]+)\\.html'


class ChingariBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.chingari'
    IE_NAME = 'ChingariBase'


class ChingariIE(ChingariBaseIE):
    _module = 'yt_dlp.extractor.chingari'
    IE_NAME = 'Chingari'
    _VALID_URL = 'https?://(?:www\\.)?chingari\\.io/share/post\\?id=(?P<id>[^&/#?]+)'


class ChingariUserIE(ChingariBaseIE):
    _module = 'yt_dlp.extractor.chingari'
    IE_NAME = 'ChingariUser'
    _VALID_URL = 'https?://(?:www\\.)?chingari\\.io/(?!share/post)(?P<id>[^/?]+)'


class ChirbitIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.chirbit'
    IE_NAME = 'chirbit'
    _VALID_URL = 'https?://(?:www\\.)?chirb\\.it/(?:(?:wp|pl)/|fb_chirbit_player\\.swf\\?key=)?(?P<id>[\\da-zA-Z]+)'


class ChirbitProfileIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.chirbit'
    IE_NAME = 'chirbit:profile'
    _VALID_URL = 'https?://(?:www\\.)?chirbit\\.com/(?:rss/)?(?P<id>[^/]+)'


class CinchcastIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.cinchcast'
    IE_NAME = 'Cinchcast'
    _VALID_URL = 'https?://player\\.cinchcast\\.com/.*?(?:assetId|show_id)=(?P<id>[0-9]+)'


class HBOBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.hbo'
    IE_NAME = 'HBOBase'


class CinemaxIE(HBOBaseIE):
    _module = 'yt_dlp.extractor.cinemax'
    IE_NAME = 'Cinemax'
    _VALID_URL = 'https?://(?:www\\.)?cinemax\\.com/(?P<path>[^/]+/video/[0-9a-z-]+-(?P<id>\\d+))'


class CinetecaMilanoIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.cinetecamilano'
    IE_NAME = 'CinetecaMilano'
    _VALID_URL = 'https?://(?:www\\.)?cinetecamilano\\.it/film/(?P<id>\\d+)'


class CiscoLiveBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ciscolive'
    IE_NAME = 'CiscoLiveBase'


class CiscoLiveSessionIE(CiscoLiveBaseIE):
    _module = 'yt_dlp.extractor.ciscolive'
    IE_NAME = 'CiscoLiveSession'
    _VALID_URL = 'https?://(?:www\\.)?ciscolive(?:\\.cisco)?\\.com/[^#]*#/session/(?P<id>[^/?&]+)'


class CiscoLiveSearchIE(CiscoLiveBaseIE):
    _module = 'yt_dlp.extractor.ciscolive'
    IE_NAME = 'CiscoLiveSearch'
    _VALID_URL = 'https?://(?:www\\.)?ciscolive(?:\\.cisco)?\\.com/(?:global/)?on-demand-library(?:\\.html|/)'

    @classmethod
    def suitable(cls, url):
        return False if CiscoLiveSessionIE.suitable(url) else super(CiscoLiveSearchIE, cls).suitable(url)


class CiscoWebexIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ciscowebex'
    IE_NAME = 'ciscowebex'
    IE_DESC = 'Cisco Webex'
    _VALID_URL = '(?x)\n                    (?P<url>https?://(?P<subdomain>[^/#?]*)\\.webex\\.com/(?:\n                        (?P<siteurl_1>[^/#?]*)/(?:ldr|lsr).php\\?(?:[^#]*&)*RCID=(?P<rcid>[0-9a-f]{32})|\n                        (?:recordingservice|webappng)/sites/(?P<siteurl_2>[^/#?]*)/recording/(?:playback/|play/)?(?P<id>[0-9a-f]{32})\n                    ))'


class CJSWIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.cjsw'
    IE_NAME = 'CJSW'
    _VALID_URL = 'https?://(?:www\\.)?cjsw\\.com/program/(?P<program>[^/]+)/episode/(?P<id>\\d+)'


class CliphunterIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.cliphunter'
    IE_NAME = 'cliphunter'
    _VALID_URL = '(?x)https?://(?:www\\.)?cliphunter\\.com/w/\n        (?P<id>[0-9]+)/\n        (?P<seo>.+?)(?:$|[#\\?])\n    '
    age_limit = 18


class ClippitIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.clippit'
    IE_NAME = 'Clippit'
    _VALID_URL = 'https?://(?:www\\.)?clippituser\\.tv/c/(?P<id>[a-z]+)'


class OnetBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.onet'
    IE_NAME = 'OnetBase'


class ClipRsIE(OnetBaseIE):
    _module = 'yt_dlp.extractor.cliprs'
    IE_NAME = 'ClipRs'
    _VALID_URL = 'https?://(?:www\\.)?clip\\.rs/(?P<id>[^/]+)/\\d+'


class ClipsyndicateIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.clipsyndicate'
    IE_NAME = 'Clipsyndicate'
    _VALID_URL = 'https?://(?:chic|www)\\.clipsyndicate\\.com/video/play(list/\\d+)?/(?P<id>\\d+)'


class CloserToTruthIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.closertotruth'
    IE_NAME = 'CloserToTruth'
    _VALID_URL = 'https?://(?:www\\.)?closertotruth\\.com/(?:[^/]+/)*(?P<id>[^/?#&]+)'


class CloudflareStreamIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.cloudflarestream'
    IE_NAME = 'CloudflareStream'
    _VALID_URL = '(?x)\n                    https?://\n                        (?:\n                            (?:watch\\.)?(?:cloudflarestream\\.com|(?:videodelivery|bytehighway)\\.net)/|\n                            embed\\.(?:cloudflarestream\\.com|(?:videodelivery|bytehighway)\\.net)/embed/[^/]+\\.js\\?.*?\\bvideo=\n                        )\n                        (?P<id>[\\da-f]{32}|[\\w-]+\\.[\\w-]+\\.[\\w-]+)\n                    '


class CloudyIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.cloudy'
    IE_NAME = 'Cloudy'
    _VALID_URL = 'https?://(?:www\\.)?cloudy\\.ec/(?:v/|embed\\.php\\?.*?\\bid=)(?P<id>[A-Za-z0-9]+)'


class ClubicIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.clubic'
    IE_NAME = 'Clubic'
    _VALID_URL = 'https?://(?:www\\.)?clubic\\.com/video/(?:[^/]+/)*video.*-(?P<id>[0-9]+)\\.html'


class ClypIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.clyp'
    IE_NAME = 'Clyp'
    _VALID_URL = 'https?://(?:www\\.)?clyp\\.it/(?P<id>[a-z0-9]+)'


class CNBCIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.cnbc'
    IE_NAME = 'CNBC'
    _VALID_URL = 'https?://video\\.cnbc\\.com/gallery/\\?video=(?P<id>[0-9]+)'


class CNBCVideoIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.cnbc'
    IE_NAME = 'CNBCVideo'
    _VALID_URL = 'https?://(?:www\\.)?cnbc\\.com(?P<path>/video/(?:[^/]+/)+(?P<id>[^./?#&]+)\\.html)'


class CNNIE(TurnerBaseIE):
    _module = 'yt_dlp.extractor.cnn'
    IE_NAME = 'CNN'
    _VALID_URL = '(?x)https?://(?:(?P<sub_domain>edition|www|money)\\.)?cnn\\.com/(?:video/(?:data/.+?|\\?)/)?videos?/\n        (?P<path>.+?/(?P<title>[^/]+?)(?:\\.(?:[a-z\\-]+)|(?=&)))'


class CNNBlogsIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.cnn'
    IE_NAME = 'CNNBlogs'
    _VALID_URL = 'https?://[^\\.]+\\.blogs\\.cnn\\.com/.+'


class CNNArticleIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.cnn'
    IE_NAME = 'CNNArticle'
    _VALID_URL = 'https?://(?:(?:edition|www)\\.)?cnn\\.com/(?!videos?/)'


class CNNIndonesiaIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.cnn'
    IE_NAME = 'CNNIndonesia'
    _VALID_URL = 'https?://www\\.cnnindonesia\\.com/[\\w-]+/(?P<upload_date>\\d{8})\\d+-\\d+-(?P<id>\\d+)/(?P<display_id>[\\w-]+)'


class CoubIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.coub'
    IE_NAME = 'Coub'
    _VALID_URL = '(?:coub:|https?://(?:coub\\.com/(?:view|embed|coubs)/|c-cdn\\.coub\\.com/fb-player\\.swf\\?.*\\bcoub(?:ID|id)=))(?P<id>[\\da-z]+)'


class ComedyCentralIE(MTVServicesInfoExtractor):
    _module = 'yt_dlp.extractor.comedycentral'
    IE_NAME = 'ComedyCentral'
    _VALID_URL = 'https?://(?:www\\.)?cc\\.com/(?:episodes|video(?:-clips)?|collection-playlist)/(?P<id>[0-9a-z]{6})'


class ComedyCentralTVIE(MTVServicesInfoExtractor):
    _module = 'yt_dlp.extractor.comedycentral'
    IE_NAME = 'ComedyCentralTV'
    _VALID_URL = 'https?://(?:www\\.)?comedycentral\\.tv/folgen/(?P<id>[0-9a-z]{6})'


class CommonMistakesIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.commonmistakes'
    IE_NAME = 'CommonMistakes'
    IE_DESC = False
    _VALID_URL = '(?:url|URL|yt-dlp)$'


class UnicodeBOMIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.commonmistakes'
    IE_NAME = 'UnicodeBOM'
    IE_DESC = False
    _VALID_URL = '(?P<bom>\\ufeff)(?P<id>.*)$'


class MmsIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.commonprotocols'
    IE_NAME = 'Mms'
    IE_DESC = False
    _VALID_URL = '(?i)mms://.+'


class RtmpIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.commonprotocols'
    IE_NAME = 'Rtmp'
    IE_DESC = False
    _VALID_URL = '(?i)rtmp[est]?://.+'


class ViewSourceIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.commonprotocols'
    IE_NAME = 'ViewSource'
    IE_DESC = False
    _VALID_URL = 'view-source:(?P<url>.+)'


class CondeNastIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.condenast'
    IE_NAME = 'CondeNast'
    IE_DESC = 'Condé Nast media group: Allure, Architectural Digest, Ars Technica, Bon Appétit, Brides, Condé Nast, Condé Nast Traveler, Details, Epicurious, GQ, Glamour, Golf Digest, SELF, Teen Vogue, The New Yorker, Vanity Fair, Vogue, W Magazine, WIRED'
    _VALID_URL = '(?x)https?://(?:video|www|player(?:-backend)?)\\.(?:allure|architecturaldigest|arstechnica|bonappetit|brides|cnevids|cntraveler|details|epicurious|glamour|golfdigest|gq|newyorker|self|teenvogue|vanityfair|vogue|wired|wmagazine)\\.com/\n        (?:\n            (?:\n                embed(?:js)?|\n                (?:script|inline)/video\n            )/(?P<id>[0-9a-f]{24})(?:/(?P<player_id>[0-9a-f]{24}))?(?:.+?\\btarget=(?P<target>[^&]+))?|\n            (?P<type>watch|series|video)/(?P<display_id>[^/?#]+)\n        )'


class CONtvIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.contv'
    IE_NAME = 'CONtv'
    _VALID_URL = 'https?://(?:www\\.)?contv\\.com/details-movie/(?P<id>[^/]+)'


class CPACIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.cpac'
    IE_NAME = 'cpac'
    _VALID_URL = 'https?://(?:www\\.)?cpac\\.ca/(?P<fr>l-)?episode\\?id=(?P<id>[\\da-f]{8}(?:-[\\da-f]{4}){3}-[\\da-f]{12})'


class CPACPlaylistIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.cpac'
    IE_NAME = 'cpac:playlist'
    _VALID_URL = '(?i)https?://(?:www\\.)?cpac\\.ca/(?:program|search|(?P<fr>emission|rechercher))\\?(?:[^&]+&)*?(?P<id>(?:id=\\d+|programId=\\d+|key=[^&]+))'


class CozyTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.cozytv'
    IE_NAME = 'CozyTV'
    _VALID_URL = 'https?://(?:www\\.)?cozy\\.tv/(?P<uploader>[^/]+)/replays/(?P<id>[^/$#&?]+)'


class CrackedIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.cracked'
    IE_NAME = 'Cracked'
    _VALID_URL = 'https?://(?:www\\.)?cracked\\.com/video_(?P<id>\\d+)_[\\da-z-]+\\.html'


class CrackleIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.crackle'
    IE_NAME = 'Crackle'
    _VALID_URL = '(?:crackle:|https?://(?:(?:www|m)\\.)?(?:sony)?crackle\\.com/(?:playlist/\\d+/|(?:[^/]+/)+))(?P<id>\\d+)'
    age_limit = 17


class CraftsyIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.craftsy'
    IE_NAME = 'Craftsy'
    _VALID_URL = 'https?://www.craftsy.com/class/(?P<id>[a-z0-9_-]+)/'


class CrooksAndLiarsIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.crooksandliars'
    IE_NAME = 'CrooksAndLiars'
    _VALID_URL = 'https?://embed\\.crooksandliars\\.com/(?:embed|v)/(?P<id>[A-Za-z0-9]+)'


class CrowdBunkerIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.crowdbunker'
    IE_NAME = 'CrowdBunker'
    _VALID_URL = 'https?://(?:www\\.)?crowdbunker\\.com/v/(?P<id>[^/?#$&]+)'


class CrowdBunkerChannelIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.crowdbunker'
    IE_NAME = 'CrowdBunkerChannel'
    _VALID_URL = 'https?://(?:www\\.)?crowdbunker\\.com/@(?P<id>[^/?#$&]+)'


class CrunchyrollBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.crunchyroll'
    IE_NAME = 'CrunchyrollBase'
    _NETRC_MACHINE = 'crunchyroll'


class CrunchyrollBetaIE(CrunchyrollBaseIE):
    _module = 'yt_dlp.extractor.crunchyroll'
    IE_NAME = 'crunchyroll'
    _VALID_URL = '(?x)\n        https?://(?:beta|www)\\.crunchyroll\\.com/\n        (?P<lang>(?:\\w{2}(?:-\\w{2})?/)?)\n        watch/(?P<id>\\w+)\n        (?:/(?P<display_id>[\\w-]+))?/?(?:[?#]|$)'
    _NETRC_MACHINE = 'crunchyroll'


class CrunchyrollBetaShowIE(CrunchyrollBaseIE):
    _module = 'yt_dlp.extractor.crunchyroll'
    IE_NAME = 'crunchyroll:playlist'
    _VALID_URL = '(?x)\n        https?://(?:beta|www)\\.crunchyroll\\.com/\n        (?P<lang>(?:\\w{2}(?:-\\w{2})?/)?)\n        series/(?P<id>\\w+)\n        (?:/(?P<display_id>[\\w-]+))?/?(?:[?#]|$)'
    _NETRC_MACHINE = 'crunchyroll'


class CSpanIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.cspan'
    IE_NAME = 'CSpan'
    IE_DESC = 'C-SPAN'
    _VALID_URL = 'https?://(?:www\\.)?c-span\\.org/video/\\?(?P<id>[0-9a-f]+)'


class CSpanCongressIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.cspan'
    IE_NAME = 'CSpanCongress'
    _VALID_URL = 'https?://(?:www\\.)?c-span\\.org/congress/'


class CtsNewsIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ctsnews'
    IE_NAME = 'CtsNews'
    IE_DESC = '華視新聞'
    _VALID_URL = 'https?://news\\.cts\\.com\\.tw/[a-z]+/[a-z]+/\\d+/(?P<id>\\d+)\\.html'


class CTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ctv'
    IE_NAME = 'CTV'
    _VALID_URL = 'https?://(?:www\\.)?ctv\\.ca/(?P<id>(?:show|movie)s/[^/]+/[^/?#&]+)'


class CTVNewsIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ctvnews'
    IE_NAME = 'CTVNews'
    _VALID_URL = 'https?://(?:.+?\\.)?ctvnews\\.ca/(?:video\\?(?:clip|playlist|bin)Id=|.*?)(?P<id>[0-9.]+)'


class CultureUnpluggedIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.cultureunplugged'
    IE_NAME = 'CultureUnplugged'
    _VALID_URL = 'https?://(?:www\\.)?cultureunplugged\\.com/documentary/watch-online/play/(?P<id>\\d+)(?:/(?P<display_id>[^/]+))?'


class CuriosityStreamBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.curiositystream'
    IE_NAME = 'CuriosityStreamBase'
    _NETRC_MACHINE = 'curiositystream'


class CuriosityStreamIE(CuriosityStreamBaseIE):
    _module = 'yt_dlp.extractor.curiositystream'
    IE_NAME = 'curiositystream'
    _VALID_URL = 'https?://(?:app\\.)?curiositystream\\.com/video/(?P<id>\\d+)'
    _NETRC_MACHINE = 'curiositystream'


class CuriosityStreamCollectionBaseIE(CuriosityStreamBaseIE):
    _module = 'yt_dlp.extractor.curiositystream'
    IE_NAME = 'CuriosityStreamCollectionBase'
    _NETRC_MACHINE = 'curiositystream'


class CuriosityStreamCollectionsIE(CuriosityStreamCollectionBaseIE):
    _module = 'yt_dlp.extractor.curiositystream'
    IE_NAME = 'curiositystream:collections'
    _VALID_URL = 'https?://(?:app\\.)?curiositystream\\.com/collections/(?P<id>\\d+)'
    _NETRC_MACHINE = 'curiositystream'


class CuriosityStreamSeriesIE(CuriosityStreamCollectionBaseIE):
    _module = 'yt_dlp.extractor.curiositystream'
    IE_NAME = 'curiositystream:series'
    _VALID_URL = 'https?://(?:app\\.)?curiositystream\\.com/(?:series|collection)/(?P<id>\\d+)'
    _NETRC_MACHINE = 'curiositystream'


class CWTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.cwtv'
    IE_NAME = 'CWTV'
    _VALID_URL = 'https?://(?:www\\.)?cw(?:tv(?:pr)?|seed)\\.com/(?:shows/)?(?:[^/]+/)+[^?]*\\?.*\\b(?:play|watch)=(?P<id>[a-z0-9]{8}-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{12})'
    age_limit = 14


class CybraryBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.cybrary'
    IE_NAME = 'CybraryBase'
    _NETRC_MACHINE = 'cybrary'


class CybraryIE(CybraryBaseIE):
    _module = 'yt_dlp.extractor.cybrary'
    IE_NAME = 'Cybrary'
    _VALID_URL = 'https?://app.cybrary.it/immersive/(?P<enrollment>[0-9]+)/activity/(?P<id>[0-9]+)'
    _NETRC_MACHINE = 'cybrary'


class CybraryCourseIE(CybraryBaseIE):
    _module = 'yt_dlp.extractor.cybrary'
    IE_NAME = 'CybraryCourse'
    _VALID_URL = 'https://app.cybrary.it/browse/course/(?P<id>[\\w-]+)/?(?:$|[#?])'
    _NETRC_MACHINE = 'cybrary'


class DaftsexIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.daftsex'
    IE_NAME = 'Daftsex'
    _VALID_URL = 'https?://(?:www\\.)?daftsex\\.com/watch/(?P<id>-?\\d+_\\d+)'


class DailyMailIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.dailymail'
    IE_NAME = 'DailyMail'
    _VALID_URL = 'https?://(?:www\\.)?dailymail\\.co\\.uk/(?:video/[^/]+/video-|embed/video/)(?P<id>[0-9]+)'


class DailymotionBaseInfoExtractor(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.dailymotion'
    IE_NAME = 'DailymotionBaseInfoExtract'
    _NETRC_MACHINE = 'dailymotion'


class DailymotionIE(DailymotionBaseInfoExtractor):
    _module = 'yt_dlp.extractor.dailymotion'
    IE_NAME = 'dailymotion'
    _VALID_URL = '(?ix)\n                    https?://\n                        (?:\n                            (?:(?:www|touch|geo)\\.)?dailymotion\\.[a-z]{2,3}/(?:(?:(?:(?:embed|swf|\\#)/)|player\\.html\\?)?video|swf)|\n                            (?:www\\.)?lequipe\\.fr/video\n                        )\n                        [/=](?P<id>[^/?_&]+)(?:.+?\\bplaylist=(?P<playlist_id>x[0-9a-z]+))?\n                    '
    _NETRC_MACHINE = 'dailymotion'
    age_limit = 18


class DailymotionPlaylistBaseIE(DailymotionBaseInfoExtractor):
    _module = 'yt_dlp.extractor.dailymotion'
    IE_NAME = 'DailymotionPlaylistBase'
    _NETRC_MACHINE = 'dailymotion'


class DailymotionPlaylistIE(DailymotionPlaylistBaseIE):
    _module = 'yt_dlp.extractor.dailymotion'
    IE_NAME = 'dailymotion:playlist'
    _VALID_URL = '(?:https?://)?(?:www\\.)?dailymotion\\.[a-z]{2,3}/playlist/(?P<id>x[0-9a-z]+)'
    _NETRC_MACHINE = 'dailymotion'


class DailymotionUserIE(DailymotionPlaylistBaseIE):
    _module = 'yt_dlp.extractor.dailymotion'
    IE_NAME = 'dailymotion:user'
    _VALID_URL = 'https?://(?:www\\.)?dailymotion\\.[a-z]{2,3}/(?!(?:embed|swf|#|video|playlist)/)(?:(?:old/)?user/)?(?P<id>[^/]+)'
    _NETRC_MACHINE = 'dailymotion'


class DailyWireBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.dailywire'
    IE_NAME = 'DailyWireBase'


class DailyWireIE(DailyWireBaseIE):
    _module = 'yt_dlp.extractor.dailywire'
    IE_NAME = 'DailyWire'
    _VALID_URL = 'https?://(?:www\\.)dailywire(?:\\.com)/(?P<sites_type>episode|videos)/(?P<id>[\\w-]+)'


class DailyWirePodcastIE(DailyWireBaseIE):
    _module = 'yt_dlp.extractor.dailywire'
    IE_NAME = 'DailyWirePodcast'
    _VALID_URL = 'https?://(?:www\\.)dailywire(?:\\.com)/(?P<sites_type>podcasts)/(?P<podcaster>[\\w-]+/(?P<id>[\\w-]+))'


class DamtomoBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.damtomo'
    IE_NAME = 'DamtomoBase'


class DamtomoRecordIE(DamtomoBaseIE):
    _module = 'yt_dlp.extractor.damtomo'
    IE_NAME = 'damtomo:record'
    _VALID_URL = 'https?://(?:www\\.)?clubdam\\.com/app/damtomo/(?:SP/)?karaokePost/StreamingKrk\\.do\\?karaokeContributeId=(?P<id>\\d+)'


class DamtomoVideoIE(DamtomoBaseIE):
    _module = 'yt_dlp.extractor.damtomo'
    IE_NAME = 'damtomo:video'
    _VALID_URL = 'https?://(?:www\\.)?clubdam\\.com/app/damtomo/(?:SP/)?karaokeMovie/StreamingDkm\\.do\\?karaokeMovieId=(?P<id>\\d+)'


class DaumBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.daum'
    IE_NAME = 'DaumBase'


class DaumIE(DaumBaseIE):
    _module = 'yt_dlp.extractor.daum'
    IE_NAME = 'daum.net'
    _VALID_URL = 'https?://(?:(?:m\\.)?tvpot\\.daum\\.net/v/|videofarm\\.daum\\.net/controller/player/VodPlayer\\.swf\\?vid=)(?P<id>[^?#&]+)'


class DaumClipIE(DaumBaseIE):
    _module = 'yt_dlp.extractor.daum'
    IE_NAME = 'daum.net:clip'
    _VALID_URL = 'https?://(?:m\\.)?tvpot\\.daum\\.net/(?:clip/ClipView.(?:do|tv)|mypot/View.do)\\?.*?clipid=(?P<id>\\d+)'

    @classmethod
    def suitable(cls, url):
        return False if DaumPlaylistIE.suitable(url) or DaumUserIE.suitable(url) else super(DaumClipIE, cls).suitable(url)


class DaumListIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.daum'
    IE_NAME = 'DaumList'


class DaumPlaylistIE(DaumListIE):
    _module = 'yt_dlp.extractor.daum'
    IE_NAME = 'daum.net:playlist'
    _VALID_URL = 'https?://(?:m\\.)?tvpot\\.daum\\.net/mypot/(?:View\\.do|Top\\.tv)\\?.*?playlistid=(?P<id>[0-9]+)'

    @classmethod
    def suitable(cls, url):
        return False if DaumUserIE.suitable(url) else super(DaumPlaylistIE, cls).suitable(url)


class DaumUserIE(DaumListIE):
    _module = 'yt_dlp.extractor.daum'
    IE_NAME = 'daum.net:user'
    _VALID_URL = 'https?://(?:m\\.)?tvpot\\.daum\\.net/mypot/(?:View|Top)\\.(?:do|tv)\\?.*?ownerid=(?P<id>[0-9a-zA-Z]+)'


class DaystarClipIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.daystar'
    IE_NAME = 'daystar:clip'
    _VALID_URL = 'https?://player\\.daystar\\.tv/(?P<id>\\w+)'


class DBTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.dbtv'
    IE_NAME = 'DBTV'
    _VALID_URL = 'https?://(?:www\\.)?dagbladet\\.no/video/(?:(?:embed|(?P<display_id>[^/]+))/)?(?P<id>[0-9A-Za-z_-]{11}|[a-zA-Z0-9]{8})'


class DctpTvIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.dctp'
    IE_NAME = 'DctpTv'
    _VALID_URL = 'https?://(?:www\\.)?dctp\\.tv/(?:#/)?filme/(?P<id>[^/?#&]+)'


class DeezerBaseInfoExtractor(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.deezer'
    IE_NAME = 'DeezerBaseInfoExtract'


class DeezerPlaylistIE(DeezerBaseInfoExtractor):
    _module = 'yt_dlp.extractor.deezer'
    IE_NAME = 'DeezerPlaylist'
    _VALID_URL = 'https?://(?:www\\.)?deezer\\.com/(../)?playlist/(?P<id>[0-9]+)'


class DeezerAlbumIE(DeezerBaseInfoExtractor):
    _module = 'yt_dlp.extractor.deezer'
    IE_NAME = 'DeezerAlbum'
    _VALID_URL = 'https?://(?:www\\.)?deezer\\.com/(../)?album/(?P<id>[0-9]+)'


class DemocracynowIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.democracynow'
    IE_NAME = 'democracynow'
    _VALID_URL = 'https?://(?:www\\.)?democracynow\\.org/(?P<id>[^\\?]*)'


class DetikEmbedIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.detik'
    IE_NAME = 'DetikEmbed'
    _VALID_URL = False


class DFBIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.dfb'
    IE_NAME = 'tv.dfb.de'
    _VALID_URL = 'https?://tv\\.dfb\\.de/video/(?P<display_id>[^/]+)/(?P<id>\\d+)'


class DHMIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.dhm'
    IE_NAME = 'DHM'
    IE_DESC = 'Filmarchiv - Deutsches Historisches Museum'
    _VALID_URL = 'https?://(?:www\\.)?dhm\\.de/filmarchiv/(?:[^/]+/)+(?P<id>[^/]+)'


class DiggIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.digg'
    IE_NAME = 'Digg'
    _VALID_URL = 'https?://(?:www\\.)?digg\\.com/video/(?P<id>[^/?#&]+)'


class DotsubIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.dotsub'
    IE_NAME = 'Dotsub'
    _VALID_URL = 'https?://(?:www\\.)?dotsub\\.com/view/(?P<id>[^/]+)'


class DouyuShowIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.douyutv'
    IE_NAME = 'DouyuShow'
    _VALID_URL = 'https?://v(?:mobile)?\\.douyu\\.com/show/(?P<id>[0-9a-zA-Z]+)'


class DouyuTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.douyutv'
    IE_NAME = 'DouyuTV'
    IE_DESC = '斗鱼'
    _VALID_URL = 'https?://(?:www\\.)?douyu(?:tv)?\\.com/(?:[^/]+/)*(?P<id>[A-Za-z0-9]+)'


class DPlayBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.dplay'
    IE_NAME = 'DPlayBase'


class DPlayIE(DPlayBaseIE):
    _module = 'yt_dlp.extractor.dplay'
    IE_NAME = 'DPlay'
    _VALID_URL = '(?x)https?://\n        (?P<domain>\n            (?:www\\.)?(?P<host>d\n                (?:\n                    play\\.(?P<country>dk|fi|jp|se|no)|\n                    iscoveryplus\\.(?P<plus_country>dk|es|fi|it|se|no)\n                )\n            )|\n            (?P<subdomain_country>es|it)\\.dplay\\.com\n        )/[^/]+/(?P<id>[^/]+/[^/?#]+)'


class DiscoveryPlusBaseIE(DPlayBaseIE):
    _module = 'yt_dlp.extractor.dplay'
    IE_NAME = 'DiscoveryPlusBase'


class DiscoveryPlusIE(DiscoveryPlusBaseIE):
    _module = 'yt_dlp.extractor.dplay'
    IE_NAME = 'DiscoveryPlus'
    _VALID_URL = 'https?://(?:www\\.)?discoveryplus\\.com/(?!it/)(?:\\w{2}/)?video/(?P<id>[^/]+/[^/?#]+)'


class HGTVDeIE(DPlayBaseIE):
    _module = 'yt_dlp.extractor.dplay'
    IE_NAME = 'HGTVDe'
    _VALID_URL = 'https?://de\\.hgtv\\.com/sendungen/(?P<id>[^/]+/[^/?#]+)'


class GoDiscoveryIE(DiscoveryPlusBaseIE):
    _module = 'yt_dlp.extractor.dplay'
    IE_NAME = 'GoDiscovery'
    _VALID_URL = 'https?://(?:go\\.)?discovery\\.com/video/(?P<id>[^/]+/[^/?#]+)'


class TravelChannelIE(DiscoveryPlusBaseIE):
    _module = 'yt_dlp.extractor.dplay'
    IE_NAME = 'TravelChannel'
    _VALID_URL = 'https?://(?:watch\\.)?travelchannel\\.com/video/(?P<id>[^/]+/[^/?#]+)'


class CookingChannelIE(DiscoveryPlusBaseIE):
    _module = 'yt_dlp.extractor.dplay'
    IE_NAME = 'CookingChannel'
    _VALID_URL = 'https?://(?:watch\\.)?cookingchanneltv\\.com/video/(?P<id>[^/]+/[^/?#]+)'


class HGTVUsaIE(DiscoveryPlusBaseIE):
    _module = 'yt_dlp.extractor.dplay'
    IE_NAME = 'HGTVUsa'
    _VALID_URL = 'https?://(?:watch\\.)?hgtv\\.com/video/(?P<id>[^/]+/[^/?#]+)'


class FoodNetworkIE(DiscoveryPlusBaseIE):
    _module = 'yt_dlp.extractor.dplay'
    IE_NAME = 'FoodNetwork'
    _VALID_URL = 'https?://(?:watch\\.)?foodnetwork\\.com/video/(?P<id>[^/]+/[^/?#]+)'


class InvestigationDiscoveryIE(DiscoveryPlusBaseIE):
    _module = 'yt_dlp.extractor.dplay'
    IE_NAME = 'InvestigationDiscovery'
    _VALID_URL = 'https?://(?:www\\.)?investigationdiscovery\\.com/video/(?P<id>[^/]+/[^/?#]+)'


class DestinationAmericaIE(DiscoveryPlusBaseIE):
    _module = 'yt_dlp.extractor.dplay'
    IE_NAME = 'DestinationAmerica'
    _VALID_URL = 'https?://(?:www\\.)?destinationamerica\\.com/video/(?P<id>[^/]+/[^/?#]+)'


class AmHistoryChannelIE(DiscoveryPlusBaseIE):
    _module = 'yt_dlp.extractor.dplay'
    IE_NAME = 'AmHistoryChannel'
    _VALID_URL = 'https?://(?:www\\.)?ahctv\\.com/video/(?P<id>[^/]+/[^/?#]+)'


class ScienceChannelIE(DiscoveryPlusBaseIE):
    _module = 'yt_dlp.extractor.dplay'
    IE_NAME = 'ScienceChannel'
    _VALID_URL = 'https?://(?:www\\.)?sciencechannel\\.com/video/(?P<id>[^/]+/[^/?#]+)'


class DIYNetworkIE(DiscoveryPlusBaseIE):
    _module = 'yt_dlp.extractor.dplay'
    IE_NAME = 'DIYNetwork'
    _VALID_URL = 'https?://(?:watch\\.)?diynetwork\\.com/video/(?P<id>[^/]+/[^/?#]+)'


class DiscoveryLifeIE(DiscoveryPlusBaseIE):
    _module = 'yt_dlp.extractor.dplay'
    IE_NAME = 'DiscoveryLife'
    _VALID_URL = 'https?://(?:www\\.)?discoverylife\\.com/video/(?P<id>[^/]+/[^/?#]+)'


class AnimalPlanetIE(DiscoveryPlusBaseIE):
    _module = 'yt_dlp.extractor.dplay'
    IE_NAME = 'AnimalPlanet'
    _VALID_URL = 'https?://(?:www\\.)?animalplanet\\.com/video/(?P<id>[^/]+/[^/?#]+)'


class TLCIE(DiscoveryPlusBaseIE):
    _module = 'yt_dlp.extractor.dplay'
    IE_NAME = 'TLC'
    _VALID_URL = 'https?://(?:go\\.)?tlc\\.com/video/(?P<id>[^/]+/[^/?#]+)'


class MotorTrendIE(DiscoveryPlusBaseIE):
    _module = 'yt_dlp.extractor.dplay'
    IE_NAME = 'MotorTrend'
    _VALID_URL = 'https?://(?:watch\\.)?motortrend\\.com/video/(?P<id>[^/]+/[^/?#]+)'


class MotorTrendOnDemandIE(DiscoveryPlusBaseIE):
    _module = 'yt_dlp.extractor.dplay'
    IE_NAME = 'MotorTrendOnDemand'
    _VALID_URL = 'https?://(?:www\\.)?motortrendondemand\\.com/detail/(?P<id>[^/]+/[^/?#]+)'


class DiscoveryPlusIndiaIE(DiscoveryPlusBaseIE):
    _module = 'yt_dlp.extractor.dplay'
    IE_NAME = 'DiscoveryPlusIndia'
    _VALID_URL = 'https?://(?:www\\.)?discoveryplus\\.in/videos?/(?P<id>[^/]+/[^/?#]+)'


class DiscoveryNetworksDeIE(DPlayBaseIE):
    _module = 'yt_dlp.extractor.dplay'
    IE_NAME = 'DiscoveryNetworksDe'
    _VALID_URL = 'https?://(?:www\\.)?(?P<domain>(?:tlc|dmax)\\.de|dplay\\.co\\.uk)/(?:programme|show|sendungen)/(?P<programme>[^/]+)/(?:video/)?(?P<alternate_id>[^/]+)'


class DiscoveryPlusItalyIE(DiscoveryPlusBaseIE):
    _module = 'yt_dlp.extractor.dplay'
    IE_NAME = 'DiscoveryPlusItaly'
    _VALID_URL = 'https?://(?:www\\.)?discoveryplus\\.com/it/video/(?P<id>[^/]+/[^/?#]+)'


class DiscoveryPlusShowBaseIE(DPlayBaseIE):
    _module = 'yt_dlp.extractor.dplay'
    IE_NAME = 'DiscoveryPlusShowBase'


class DiscoveryPlusItalyShowIE(DiscoveryPlusShowBaseIE):
    _module = 'yt_dlp.extractor.dplay'
    IE_NAME = 'DiscoveryPlusItalyShow'
    _VALID_URL = 'https?://(?:www\\.)?discoveryplus\\.it/programmi/(?P<show_name>[^/]+)/?(?:[?#]|$)'


class DiscoveryPlusIndiaShowIE(DiscoveryPlusShowBaseIE):
    _module = 'yt_dlp.extractor.dplay'
    IE_NAME = 'DiscoveryPlusIndiaShow'
    _VALID_URL = 'https?://(?:www\\.)?discoveryplus\\.in/show/(?P<show_name>[^/]+)/?(?:[?#]|$)'


class DRBonanzaIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.drbonanza'
    IE_NAME = 'DRBonanza'
    _VALID_URL = 'https?://(?:www\\.)?dr\\.dk/bonanza/[^/]+/\\d+/[^/]+/(?P<id>\\d+)/(?P<display_id>[^/?#&]+)'


class DrTuberIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.drtuber'
    IE_NAME = 'DrTuber'
    _VALID_URL = 'https?://(?:(?:www|m)\\.)?drtuber\\.com/(?:video|embed)/(?P<id>\\d+)(?:/(?P<display_id>[\\w-]+))?'
    age_limit = 18


class DRTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.drtv'
    IE_NAME = 'drtv'
    _VALID_URL = '(?x)\n                    https?://\n                        (?:\n                            (?:www\\.)?dr\\.dk/(?:tv/se|nyheder|(?:radio|lyd)(?:/ondemand)?)/(?:[^/]+/)*|\n                            (?:www\\.)?(?:dr\\.dk|dr-massive\\.com)/drtv/(?:se|episode|program)/\n                        )\n                        (?P<id>[\\da-z_-]+)\n                    '


class DRTVLiveIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.drtv'
    IE_NAME = 'drtv:live'
    _VALID_URL = 'https?://(?:www\\.)?dr\\.dk/(?:tv|TV)/live/(?P<id>[\\da-z-]+)'


class DTubeIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.dtube'
    IE_NAME = 'DTube'
    _VALID_URL = 'https?://(?:www\\.)?d\\.tube/(?:#!/)?v/(?P<uploader_id>[0-9a-z.-]+)/(?P<id>[0-9a-z]{8})'


class DVTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.dvtv'
    IE_NAME = 'dvtv'
    IE_DESC = 'http://video.aktualne.cz/'
    _VALID_URL = 'https?://video\\.aktualne\\.cz/(?:[^/]+/)+r~(?P<id>[0-9a-f]{32})'


class DubokuIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.duboku'
    IE_NAME = 'duboku'
    IE_DESC = 'www.duboku.io'
    _VALID_URL = '(?:https?://[^/]+\\.duboku\\.io/vodplay/)(?P<id>[0-9]+-[0-9-]+)\\.html.*'


class DubokuPlaylistIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.duboku'
    IE_NAME = 'duboku:list'
    IE_DESC = 'www.duboku.io entire series'
    _VALID_URL = '(?:https?://[^/]+\\.duboku\\.io/voddetail/)(?P<id>[0-9]+)\\.html.*'


class DumpertIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.dumpert'
    IE_NAME = 'Dumpert'
    _VALID_URL = '(?P<protocol>https?)://(?:(?:www|legacy)\\.)?dumpert\\.nl/(?:mediabase|embed|item)/(?P<id>[0-9]+[/_][0-9a-zA-Z]+)'


class DefenseGouvFrIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.defense'
    IE_NAME = 'defense.gouv.fr'
    _VALID_URL = 'https?://.*?\\.defense\\.gouv\\.fr/layout/set/ligthboxvideo/base-de-medias/webtv/(?P<id>[^/?#]*)'


class DeuxMIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.deuxm'
    IE_NAME = 'DeuxM'
    _VALID_URL = 'https?://(?:www\\.)?2m\\.ma/[^/]+/replay/single/(?P<id>([\\w.]{1,24})+)'


class DeuxMNewsIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.deuxm'
    IE_NAME = 'DeuxMNews'
    _VALID_URL = 'https?://(?:www\\.)?2m\\.ma/(?P<lang>\\w+)/news/(?P<id>[^/#?]+)'


class DigitalConcertHallIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.digitalconcerthall'
    IE_NAME = 'DigitalConcertHall'
    IE_DESC = 'DigitalConcertHall extractor'
    _VALID_URL = 'https?://(?:www\\.)?digitalconcerthall\\.com/(?P<language>[a-z]+)/concert/(?P<id>[0-9]+)'
    _NETRC_MACHINE = 'digitalconcerthall'


class DiscoveryGoBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.discoverygo'
    IE_NAME = 'DiscoveryGoBase'


class DiscoveryIE(DiscoveryGoBaseIE):
    _module = 'yt_dlp.extractor.discovery'
    IE_NAME = 'Discovery'
    _VALID_URL = '(?x)https?://\n        (?P<site>\n            go\\.discovery|\n            www\\.\n                (?:\n                    investigationdiscovery|\n                    discoverylife|\n                    animalplanet|\n                    ahctv|\n                    destinationamerica|\n                    sciencechannel|\n                    tlc\n                )|\n            watch\\.\n                (?:\n                    hgtv|\n                    foodnetwork|\n                    travelchannel|\n                    diynetwork|\n                    cookingchanneltv|\n                    motortrend\n                )\n        )\\.com/tv-shows/(?P<show_slug>[^/]+)/(?:video|full-episode)s/(?P<id>[^./?#]+)'


class DisneyIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.disney'
    IE_NAME = 'Disney'
    _VALID_URL = '(?x)\n        https?://(?P<domain>(?:[^/]+\\.)?(?:disney\\.[a-z]{2,3}(?:\\.[a-z]{2})?|disney(?:(?:me|latino)\\.com|turkiye\\.com\\.tr|channel\\.de)|(?:starwars|marvelkids)\\.com))/(?:(?:embed/|(?:[^/]+/)+[\\w-]+-)(?P<id>[a-z0-9]{24})|(?:[^/]+/)?(?P<display_id>[^/?#]+))'


class DigitallySpeakingIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.dispeak'
    IE_NAME = 'DigitallySpeaking'
    _VALID_URL = 'https?://(?:s?evt\\.dispeak|events\\.digitallyspeaking)\\.com/(?:[^/]+/)+xml/(?P<id>[^.]+)\\.xml'


class DropboxIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.dropbox'
    IE_NAME = 'Dropbox'
    _VALID_URL = 'https?://(?:www\\.)?dropbox[.]com/sh?/(?P<id>[a-zA-Z0-9]{15})/.*'


class DropoutSeasonIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.dropout'
    IE_NAME = 'DropoutSeason'
    _VALID_URL = 'https?://(?:www\\.)?dropout\\.tv/(?P<id>[^\\/$&?#]+)(?:/?$|/season:[0-9]+/?$)'


class DropoutIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.dropout'
    IE_NAME = 'Dropout'
    _VALID_URL = 'https?://(?:www\\.)?dropout\\.tv/(?:[^/]+/)*videos/(?P<id>[^/]+)/?$'
    _NETRC_MACHINE = 'dropout'


class DWIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.dw'
    IE_NAME = 'dw'
    _VALID_URL = 'https?://(?:www\\.)?dw\\.com/(?:[^/]+/)+(?:av|e)-(?P<id>\\d+)'


class DWArticleIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.dw'
    IE_NAME = 'dw:article'
    _VALID_URL = 'https?://(?:www\\.)?dw\\.com/(?:[^/]+/)+a-(?P<id>\\d+)'


class EaglePlatformIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.eagleplatform'
    IE_NAME = 'EaglePlatform'
    _VALID_URL = '(?x)\n                    (?:\n                        eagleplatform:(?P<custom_host>[^/]+):|\n                        https?://(?P<host>.+?\\.media\\.eagleplatform\\.com)/index/player\\?.*\\brecord_id=\n                    )\n                    (?P<id>\\d+)\n                '


class ClipYouEmbedIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.eagleplatform'
    IE_NAME = 'ClipYouEmbed'
    _VALID_URL = False


class EbaumsWorldIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ebaumsworld'
    IE_NAME = 'EbaumsWorld'
    _VALID_URL = 'https?://(?:www\\.)?ebaumsworld\\.com/videos/[^/]+/(?P<id>\\d+)'


class EchoMskIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.echomsk'
    IE_NAME = 'EchoMsk'
    _VALID_URL = 'https?://(?:www\\.)?echo\\.msk\\.ru/sounds/(?P<id>\\d+)'


class EggheadBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.egghead'
    IE_NAME = 'EggheadBase'


class EggheadCourseIE(EggheadBaseIE):
    _module = 'yt_dlp.extractor.egghead'
    IE_NAME = 'egghead:course'
    IE_DESC = 'egghead.io course'
    _VALID_URL = 'https://(?:app\\.)?egghead\\.io/(?:course|playlist)s/(?P<id>[^/?#&]+)'


class EggheadLessonIE(EggheadBaseIE):
    _module = 'yt_dlp.extractor.egghead'
    IE_NAME = 'egghead:lesson'
    IE_DESC = 'egghead.io lesson'
    _VALID_URL = 'https://(?:app\\.)?egghead\\.io/(?:api/v1/)?lessons/(?P<id>[^/?#&]+)'


class EHowIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ehow'
    IE_NAME = 'eHow'
    _VALID_URL = 'https?://(?:www\\.)?ehow\\.com/[^/_?]*_(?P<id>[0-9]+)'


class EightTracksIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.eighttracks'
    IE_NAME = '8tracks'
    _VALID_URL = 'https?://8tracks\\.com/(?P<user>[^/]+)/(?P<id>[^/#]+)(?:#.*)?$'


class EinthusanIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.einthusan'
    IE_NAME = 'Einthusan'
    _VALID_URL = 'https?://(?P<host>einthusan\\.(?:tv|com|ca))/movie/watch/(?P<id>[^/?#&]+)'


class EitbIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.eitb'
    IE_NAME = 'eitb.tv'
    _VALID_URL = 'https?://(?:www\\.)?eitb\\.tv/(?:eu/bideoa|es/video)/[^/]+/\\d+/(?P<id>\\d+)'


class EllenTubeBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ellentube'
    IE_NAME = 'EllenTubeBase'


class EllenTubeIE(EllenTubeBaseIE):
    _module = 'yt_dlp.extractor.ellentube'
    IE_NAME = 'EllenTube'
    _VALID_URL = '(?x)\n                        (?:\n                            ellentube:|\n                            https://api-prod\\.ellentube\\.com/ellenapi/api/item/\n                        )\n                        (?P<id>[\\da-f]{8}-[\\da-f]{4}-[\\da-f]{4}-[\\da-f]{4}-[\\da-f]{12})\n                    '


class EllenTubeVideoIE(EllenTubeBaseIE):
    _module = 'yt_dlp.extractor.ellentube'
    IE_NAME = 'EllenTubeVideo'
    _VALID_URL = 'https?://(?:www\\.)?ellentube\\.com/video/(?P<id>.+?)\\.html'


class EllenTubePlaylistIE(EllenTubeBaseIE):
    _module = 'yt_dlp.extractor.ellentube'
    IE_NAME = 'EllenTubePlaylist'
    _VALID_URL = 'https?://(?:www\\.)?ellentube\\.com/(?:episode|studios)/(?P<id>.+?)\\.html'


class ElonetIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.elonet'
    IE_NAME = 'Elonet'
    _VALID_URL = 'https?://elonet\\.finna\\.fi/Record/kavi\\.elonet_elokuva_(?P<id>[0-9]+)'


class ElPaisIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.elpais'
    IE_NAME = 'ElPais'
    IE_DESC = 'El País'
    _VALID_URL = 'https?://(?:[^.]+\\.)?elpais\\.com/.*/(?P<id>[^/#?]+)\\.html(?:$|[?#])'


class EmbedlyIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.embedly'
    IE_NAME = 'Embedly'
    _VALID_URL = 'https?://(?:www|cdn\\.)?embedly\\.com/widgets/media\\.html\\?(?:[^#]*?&)?url=(?P<id>[^#&]+)'


class EngadgetIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.engadget'
    IE_NAME = 'Engadget'
    _VALID_URL = 'https?://(?:www\\.)?engadget\\.com/video/(?P<id>[^/?#]+)'


class EpiconIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.epicon'
    IE_NAME = 'Epicon'
    _VALID_URL = 'https?://(?:www\\.)?epicon\\.in/(?:documentaries|movies|tv-shows/[^/?#]+/[^/?#]+)/(?P<id>[^/?#]+)'


class EpiconSeriesIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.epicon'
    IE_NAME = 'EpiconSeries'
    _VALID_URL = '(?!.*season)https?://(?:www\\.)?epicon\\.in/tv-shows/(?P<id>[^/?#]+)'


class EpochIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.epoch'
    IE_NAME = 'Epoch'
    _VALID_URL = 'https?://www.theepochtimes\\.com/[\\w-]+_(?P<id>\\d+).html'


class EpornerIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.eporner'
    IE_NAME = 'Eporner'
    _VALID_URL = 'https?://(?:www\\.)?eporner\\.com/(?:(?:hd-porn|embed)/|video-)(?P<id>\\w+)(?:/(?P<display_id>[\\w-]+))?'
    age_limit = 18


class EroProfileIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.eroprofile'
    IE_NAME = 'EroProfile'
    _VALID_URL = 'https?://(?:www\\.)?eroprofile\\.com/m/videos/view/(?P<id>[^/]+)'
    _NETRC_MACHINE = 'eroprofile'
    age_limit = 18


class EroProfileAlbumIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.eroprofile'
    IE_NAME = 'EroProfile:album'
    _VALID_URL = 'https?://(?:www\\.)?eroprofile\\.com/m/videos/album/(?P<id>[^/]+)'


class ERTFlixBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ertgr'
    IE_NAME = 'ERTFlixBase'


class ERTFlixCodenameIE(ERTFlixBaseIE):
    _module = 'yt_dlp.extractor.ertgr'
    IE_NAME = 'ertflix:codename'
    IE_DESC = 'ERTFLIX videos by codename'
    _VALID_URL = 'ertflix:(?P<id>[\\w-]+)'


class ERTFlixIE(ERTFlixBaseIE):
    _module = 'yt_dlp.extractor.ertgr'
    IE_NAME = 'ertflix'
    IE_DESC = 'ERTFLIX videos'
    _VALID_URL = 'https?://www\\.ertflix\\.gr/(?:[^/]+/)?(?:series|vod)/(?P<id>[a-z]{3}\\.\\d+)'
    age_limit = 8


class ERTWebtvEmbedIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ertgr'
    IE_NAME = 'ertwebtv:embed'
    IE_DESC = 'ert.gr webtv embedded videos'
    _VALID_URL = 'https?://www\\.ert\\.gr/webtv/live\\-uni/vod/dt\\-uni\\-vod\\.php\\?([^#]+&)?f=(?P<id>[^#&]+)'


class EscapistIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.escapist'
    IE_NAME = 'Escapist'
    _VALID_URL = 'https?://?(?:(?:www|v1)\\.)?escapistmagazine\\.com/videos/view/[^/]+/(?P<id>[0-9]+)'


class OnceIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.once'
    IE_NAME = 'Once'
    _VALID_URL = 'https?://.+?\\.unicornmedia\\.com/now/(?:ads/vmap/)?[^/]+/[^/]+/(?P<domain_id>[^/]+)/(?P<application_id>[^/]+)/(?:[^/]+/)?(?P<media_item_id>[^/]+)/content\\.(?:once|m3u8|mp4)'


class ESPNIE(OnceIE):
    _module = 'yt_dlp.extractor.espn'
    IE_NAME = 'ESPN'
    _VALID_URL = '(?x)\n                    https?://\n                        (?:\n                            (?:\n                                (?:\n                                    (?:(?:\\w+\\.)+)?espn\\.go|\n                                    (?:www\\.)?espn\n                                )\\.com/\n                                (?:\n                                    (?:\n                                        video/(?:clip|iframe/twitter)|\n                                    )\n                                    (?:\n                                        .*?\\?.*?\\bid=|\n                                        /_/id/\n                                    )|\n                                    [^/]+/video/\n                                )\n                            )|\n                            (?:www\\.)espnfc\\.(?:com|us)/(?:video/)?[^/]+/\\d+/video/\n                        )\n                        (?P<id>\\d+)\n                    '


class WatchESPNIE(AdobePassIE):
    _module = 'yt_dlp.extractor.espn'
    IE_NAME = 'WatchESPN'
    _VALID_URL = 'https?://(?:www\\.)?espn\\.com/(?:watch|espnplus)/player/_/id/(?P<id>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})'


class ESPNArticleIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.espn'
    IE_NAME = 'ESPNArticle'
    _VALID_URL = 'https?://(?:espn\\.go|(?:www\\.)?espn)\\.com/(?:[^/]+/)*(?P<id>[^/]+)'

    @classmethod
    def suitable(cls, url):
        return False if (ESPNIE.suitable(url) or WatchESPNIE.suitable(url)) else super().suitable(url)


class FiveThirtyEightIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.espn'
    IE_NAME = 'FiveThirtyEight'
    _VALID_URL = 'https?://(?:www\\.)?fivethirtyeight\\.com/features/(?P<id>[^/?#]+)'


class ESPNCricInfoIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.espn'
    IE_NAME = 'ESPNCricInfo'
    _VALID_URL = 'https?://(?:www\\.)?espncricinfo\\.com/video/[^#$&?/]+-(?P<id>\\d+)'


class EsriVideoIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.esri'
    IE_NAME = 'EsriVideo'
    _VALID_URL = 'https?://video\\.esri\\.com/watch/(?P<id>[0-9]+)'


class EuropaIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.europa'
    IE_NAME = 'Europa'
    _VALID_URL = 'https?://ec\\.europa\\.eu/avservices/(?:video/player|audio/audioDetails)\\.cfm\\?.*?\\bref=(?P<id>[A-Za-z0-9-]+)'


class EuropeanTourIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.europeantour'
    IE_NAME = 'EuropeanTour'
    _VALID_URL = 'https?://(?:www\\.)?europeantour\\.com/dpworld-tour/news/video/(?P<id>[^/&?#$]+)'


class EurosportIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.eurosport'
    IE_NAME = 'Eurosport'
    _VALID_URL = 'https?://www\\.eurosport\\.com/\\w+/[\\w-]+/\\d+/[\\w-]+_(?P<id>vid\\d+)'


class EUScreenIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.euscreen'
    IE_NAME = 'EUScreen'
    _VALID_URL = 'https?://(?:www\\.)?euscreen\\.eu/item.html\\?id=(?P<id>[^&?$/]+)'


class ExpoTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.expotv'
    IE_NAME = 'ExpoTV'
    _VALID_URL = 'https?://(?:www\\.)?expotv\\.com/videos/[^?#]*/(?P<id>[0-9]+)($|[?#])'


class ExpressenIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.expressen'
    IE_NAME = 'Expressen'
    _VALID_URL = '(?x)\n                    https?://\n                        (?:www\\.)?(?:expressen|di)\\.se/\n                        (?:(?:tvspelare/video|videoplayer/embed)/)?\n                        tv/(?:[^/]+/)*\n                        (?P<id>[^/?#&]+)\n                    '


class EyedoTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.eyedotv'
    IE_NAME = 'EyedoTV'
    _VALID_URL = 'https?://(?:www\\.)?eyedo\\.tv/[^/]+/(?:#!/)?Live/Detail/(?P<id>[0-9]+)'


class FacebookIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.facebook'
    IE_NAME = 'facebook'
    _VALID_URL = '(?x)\n                (?:\n                    https?://\n                        (?:[\\w-]+\\.)?(?:facebook\\.com|facebookwkhpilnemxj7asaniu7vnjjbiltxjqhye3mhbshg7kx5tfyd\\.onion)/\n                        (?:[^#]*?\\#!/)?\n                        (?:\n                            (?:\n                                video/video\\.php|\n                                photo\\.php|\n                                video\\.php|\n                                video/embed|\n                                story\\.php|\n                                watch(?:/live)?/?\n                            )\\?(?:.*?)(?:v|video_id|story_fbid)=|\n                            [^/]+/videos/(?:[^/]+/)?|\n                            [^/]+/posts/|\n                            groups/[^/]+/permalink/|\n                            watchparty/\n                        )|\n                    facebook:\n                )\n                (?P<id>[0-9]+)\n                '
    _NETRC_MACHINE = 'facebook'


class FacebookPluginsVideoIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.facebook'
    IE_NAME = 'FacebookPluginsVideo'
    _VALID_URL = 'https?://(?:[\\w-]+\\.)?facebook\\.com/plugins/video\\.php\\?.*?\\bhref=(?P<id>https.+)'


class FacebookRedirectURLIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.facebook'
    IE_NAME = 'FacebookRedirectURL'
    IE_DESC = False
    _VALID_URL = 'https?://(?:[\\w-]+\\.)?facebook\\.com/flx/warn[/?]'


class FacebookReelIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.facebook'
    IE_NAME = 'facebook:reel'
    _VALID_URL = 'https?://(?:[\\w-]+\\.)?facebook\\.com/reel/(?P<id>\\d+)'


class FancodeVodIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.fancode'
    IE_NAME = 'fancode:vod'
    _VALID_URL = 'https?://(?:www\\.)?fancode\\.com/video/(?P<id>[0-9]+)\\b'
    _NETRC_MACHINE = 'fancode'


class FancodeLiveIE(FancodeVodIE):
    _module = 'yt_dlp.extractor.fancode'
    IE_NAME = 'fancode:live'
    _VALID_URL = 'https?://(www\\.)?fancode\\.com/match/(?P<id>[0-9]+).+'
    _NETRC_MACHINE = 'fancode'


class FazIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.faz'
    IE_NAME = 'faz.net'
    _VALID_URL = 'https?://(?:www\\.)?faz\\.net/(?:[^/]+/)*.*?-(?P<id>\\d+)\\.html'


class FC2IE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.fc2'
    IE_NAME = 'fc2'
    _VALID_URL = '^(?:https?://video\\.fc2\\.com/(?:[^/]+/)*content/|fc2:)(?P<id>[^/]+)'
    _NETRC_MACHINE = 'fc2'


class FC2EmbedIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.fc2'
    IE_NAME = 'fc2:embed'
    _VALID_URL = 'https?://video\\.fc2\\.com/flv2\\.swf\\?(?P<query>.+)'


class FC2LiveIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.fc2'
    IE_NAME = 'fc2:live'
    _VALID_URL = 'https?://live\\.fc2\\.com/(?P<id>\\d+)'


class FczenitIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.fczenit'
    IE_NAME = 'Fczenit'
    _VALID_URL = 'https?://(?:www\\.)?fc-zenit\\.ru/video/(?P<id>[0-9]+)'


class FifaIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.fifa'
    IE_NAME = 'Fifa'
    _VALID_URL = 'https?://www.fifa.com/fifaplus/(?P<locale>\\w{2})/watch/([^#?]+/)?(?P<id>\\w+)'


class FilmmoduIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.filmmodu'
    IE_NAME = 'Filmmodu'
    _VALID_URL = 'https?://(?:www.)?filmmodu.org/(?P<id>[^/]+-(?:turkce-dublaj-izle|altyazili-izle))'


class FilmOnIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.filmon'
    IE_NAME = 'filmon'
    _VALID_URL = '(?:https?://(?:www\\.)?filmon\\.com/vod/view/|filmon:)(?P<id>\\d+)'


class FilmOnChannelIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.filmon'
    IE_NAME = 'filmon:channel'
    _VALID_URL = 'https?://(?:www\\.)?filmon\\.com/(?:tv|channel)/(?P<id>[a-z0-9-]+)'


class FilmwebIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.filmweb'
    IE_NAME = 'Filmweb'
    _VALID_URL = 'https?://(?:www\\.)?filmweb\\.no/(?P<type>trailere|filmnytt)/article(?P<id>\\d+)\\.ece'


class FirstTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.firsttv'
    IE_NAME = '1tv'
    IE_DESC = 'Первый канал'
    _VALID_URL = 'https?://(?:www\\.)?1tv\\.ru/(?:[^/]+/)+(?P<id>[^/?#]+)'


class FiveTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.fivetv'
    IE_NAME = 'FiveTV'
    _VALID_URL = '(?x)\n                    https?://\n                        (?:www\\.)?5-tv\\.ru/\n                        (?:\n                            (?:[^/]+/)+(?P<id>\\d+)|\n                            (?P<path>[^/?#]+)(?:[/?#])?\n                        )\n                    '


class FlickrIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.flickr'
    IE_NAME = 'Flickr'
    _VALID_URL = 'https?://(?:www\\.|secure\\.)?flickr\\.com/photos/[\\w\\-_@]+/(?P<id>\\d+)'


class FolketingetIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.folketinget'
    IE_NAME = 'Folketinget'
    IE_DESC = 'Folketinget (ft.dk; Danish parliament)'
    _VALID_URL = 'https?://(?:www\\.)?ft\\.dk/webtv/video/[^?#]*?\\.(?P<id>[0-9]+)\\.aspx'


class FootyRoomIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.footyroom'
    IE_NAME = 'FootyRoom'
    _VALID_URL = 'https?://footyroom\\.com/matches/(?P<id>\\d+)'


class Formula1IE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.formula1'
    IE_NAME = 'Formula1'
    _VALID_URL = 'https?://(?:www\\.)?formula1\\.com/en/latest/video\\.[^.]+\\.(?P<id>\\d+)\\.html'


class FourTubeBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.fourtube'
    IE_NAME = 'FourTubeBase'


class FourTubeIE(FourTubeBaseIE):
    _module = 'yt_dlp.extractor.fourtube'
    IE_NAME = '4tube'
    _VALID_URL = 'https?://(?:(?P<kind>www|m)\\.)?4tube\\.com/(?:videos|embed)/(?P<id>\\d+)(?:/(?P<display_id>[^/?#&]+))?'
    age_limit = 18


class PornTubeIE(FourTubeBaseIE):
    _module = 'yt_dlp.extractor.fourtube'
    IE_NAME = 'PornTube'
    _VALID_URL = 'https?://(?:(?P<kind>www|m)\\.)?porntube\\.com/(?:videos/(?P<display_id>[^/]+)_|embed/)(?P<id>\\d+)'
    age_limit = 18


class PornerBrosIE(FourTubeBaseIE):
    _module = 'yt_dlp.extractor.fourtube'
    IE_NAME = 'PornerBros'
    _VALID_URL = 'https?://(?:(?P<kind>www|m)\\.)?pornerbros\\.com/(?:videos/(?P<display_id>[^/]+)_|embed/)(?P<id>\\d+)'
    age_limit = 18


class FuxIE(FourTubeBaseIE):
    _module = 'yt_dlp.extractor.fourtube'
    IE_NAME = 'Fux'
    _VALID_URL = 'https?://(?:(?P<kind>www|m)\\.)?fux\\.com/(?:video|embed)/(?P<id>\\d+)(?:/(?P<display_id>[^/?#&]+))?'
    age_limit = 18


class FourZeroStudioArchiveIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.fourzerostudio'
    IE_NAME = '0000studio:archive'
    _VALID_URL = 'https?://0000\\.studio/(?P<uploader_id>[^/]+)/broadcasts/(?P<id>[^/]+)/archive'


class FourZeroStudioClipIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.fourzerostudio'
    IE_NAME = '0000studio:clip'
    _VALID_URL = 'https?://0000\\.studio/(?P<uploader_id>[^/]+)/archive-clip/(?P<id>[^/]+)'


class FOXIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.fox'
    IE_NAME = 'FOX'
    _VALID_URL = 'https?://(?:www\\.)?fox\\.com/watch/(?P<id>[\\da-fA-F]+)'
    age_limit = 14


class FOX9IE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.fox9'
    IE_NAME = 'FOX9'
    _VALID_URL = 'https?://(?:www\\.)?fox9\\.com/video/(?P<id>\\d+)'


class FOX9NewsIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.fox9'
    IE_NAME = 'FOX9News'
    _VALID_URL = 'https?://(?:www\\.)?fox9\\.com/news/(?P<id>[^/?&#]+)'


class FoxgayIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.foxgay'
    IE_NAME = 'Foxgay'
    _VALID_URL = 'https?://(?:www\\.)?foxgay\\.com/videos/(?:\\S+-)?(?P<id>\\d+)\\.shtml'
    age_limit = 18


class FoxNewsIE(AMPIE):
    _module = 'yt_dlp.extractor.foxnews'
    IE_NAME = 'foxnews'
    IE_DESC = 'Fox News and Fox Business Video'
    _VALID_URL = 'https?://(?P<host>video\\.(?:insider\\.)?fox(?:news|business)\\.com)/v/(?:video-embed\\.html\\?video_id=)?(?P<id>\\d+)'


class FoxNewsArticleIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.foxnews'
    IE_NAME = 'foxnews:article'
    _VALID_URL = 'https?://(?:www\\.)?(?:insider\\.)?foxnews\\.com/(?!v)([^/]+/)+(?P<id>[a-z-]+)'


class FoxNewsVideoIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.foxnews'
    IE_NAME = 'FoxNewsVideo'
    _VALID_URL = 'https?://(?:www\\.)?foxnews\\.com/video/(?P<id>\\d+)'


class FoxSportsIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.foxsports'
    IE_NAME = 'FoxSports'
    _VALID_URL = 'https?://(?:www\\.)?foxsports\\.com/(?:[^/]+/)*video/(?P<id>\\d+)'


class FptplayIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.fptplay'
    IE_NAME = 'fptplay'
    IE_DESC = 'fptplay.vn'
    _VALID_URL = 'https?://fptplay\\.vn/xem-video/[^/]+\\-(?P<id>\\w+)(?:/tap-(?P<episode>\\d+)?/?(?:[?#]|$)|)'


class FranceInterIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.franceinter'
    IE_NAME = 'FranceInter'
    _VALID_URL = 'https?://(?:www\\.)?franceinter\\.fr/emissions/(?P<id>[^?#]+)'


class FranceTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.francetv'
    IE_NAME = 'FranceTV'
    _VALID_URL = '(?x)\n                    (?:\n                        https?://\n                            sivideo\\.webservices\\.francetelevisions\\.fr/tools/getInfosOeuvre/v2/\\?\n                            .*?\\bidDiffusion=[^&]+|\n                        (?:\n                            https?://videos\\.francetv\\.fr/video/|\n                            francetv:\n                        )\n                        (?P<id>[^@]+)(?:@(?P<catalog>.+))?\n                    )\n                    '


class FranceTVBaseInfoExtractor(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.francetv'
    IE_NAME = 'FranceTVBaseInfoExtract'


class FranceTVSiteIE(FranceTVBaseInfoExtractor):
    _module = 'yt_dlp.extractor.francetv'
    IE_NAME = 'FranceTVSite'
    _VALID_URL = 'https?://(?:(?:www\\.)?france\\.tv|mobile\\.france\\.tv)/(?:[^/]+/)*(?P<id>[^/]+)\\.html'


class FranceTVInfoIE(FranceTVBaseInfoExtractor):
    _module = 'yt_dlp.extractor.francetv'
    IE_NAME = 'francetvinfo.fr'
    _VALID_URL = 'https?://(?:www|mobile|france3-regions)\\.francetvinfo\\.fr/(?:[^/]+/)*(?P<id>[^/?#&.]+)'


class FreesoundIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.freesound'
    IE_NAME = 'Freesound'
    _VALID_URL = 'https?://(?:www\\.)?freesound\\.org/people/[^/]+/sounds/(?P<id>[^/]+)'


class FreespeechIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.freespeech'
    IE_NAME = 'freespeech.org'
    _VALID_URL = 'https?://(?:www\\.)?freespeech\\.org/stories/(?P<id>.+)'


class FrontendMastersBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.frontendmasters'
    IE_NAME = 'FrontendMastersBase'
    _NETRC_MACHINE = 'frontendmasters'


class FrontendMastersIE(FrontendMastersBaseIE):
    _module = 'yt_dlp.extractor.frontendmasters'
    IE_NAME = 'FrontendMasters'
    _VALID_URL = '(?:frontendmasters:|https?://api\\.frontendmasters\\.com/v\\d+/kabuki/video/)(?P<id>[^/]+)'
    _NETRC_MACHINE = 'frontendmasters'


class FrontendMastersPageBaseIE(FrontendMastersBaseIE):
    _module = 'yt_dlp.extractor.frontendmasters'
    IE_NAME = 'FrontendMastersPageBase'
    _NETRC_MACHINE = 'frontendmasters'


class FrontendMastersLessonIE(FrontendMastersPageBaseIE):
    _module = 'yt_dlp.extractor.frontendmasters'
    IE_NAME = 'FrontendMastersLesson'
    _VALID_URL = 'https?://(?:www\\.)?frontendmasters\\.com/courses/(?P<course_name>[^/]+)/(?P<lesson_name>[^/]+)'
    _NETRC_MACHINE = 'frontendmasters'


class FrontendMastersCourseIE(FrontendMastersPageBaseIE):
    _module = 'yt_dlp.extractor.frontendmasters'
    IE_NAME = 'FrontendMastersCourse'
    _VALID_URL = 'https?://(?:www\\.)?frontendmasters\\.com/courses/(?P<id>[^/]+)'
    _NETRC_MACHINE = 'frontendmasters'

    @classmethod
    def suitable(cls, url):
        return False if FrontendMastersLessonIE.suitable(url) else super(
            FrontendMastersBaseIE, cls).suitable(url)


class FreeTvBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.freetv'
    IE_NAME = 'FreeTvBase'


class FreeTvIE(FreeTvBaseIE):
    _module = 'yt_dlp.extractor.freetv'
    IE_NAME = 'freetv:series'
    _VALID_URL = 'https?://(?:www\\.)?freetv\\.com/series/(?P<id>[^/]+)'


class FreeTvMoviesIE(FreeTvBaseIE):
    _module = 'yt_dlp.extractor.freetv'
    IE_NAME = 'FreeTvMovies'
    _VALID_URL = 'https?://(?:www\\.)?freetv\\.com/peliculas/(?P<id>[^/]+)'


class FujiTVFODPlus7IE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.fujitv'
    IE_NAME = 'FujiTVFODPlus7'
    _VALID_URL = 'https?://fod\\.fujitv\\.co\\.jp/title/(?P<sid>[0-9a-z]{4})/(?P<id>[0-9a-z]+)'


class FunimationBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.funimation'
    IE_NAME = 'FunimationBase'
    _NETRC_MACHINE = 'funimation'


class FunimationIE(FunimationBaseIE):
    _module = 'yt_dlp.extractor.funimation'
    IE_NAME = 'Funimation'
    _VALID_URL = 'https?://(?:www\\.)?funimation\\.com/player/(?P<id>\\d+)'
    _NETRC_MACHINE = 'funimation'


class FunimationPageIE(FunimationBaseIE):
    _module = 'yt_dlp.extractor.funimation'
    IE_NAME = 'funimation:page'
    _VALID_URL = 'https?://(?:www\\.)?funimation(?:\\.com|now\\.uk)/(?:(?P<lang>[^/]+)/)?(?:shows|v)/(?P<show>[^/]+)/(?P<episode>[^/?#&]+)'
    _NETRC_MACHINE = 'funimation'


class FunimationShowIE(FunimationBaseIE):
    _module = 'yt_dlp.extractor.funimation'
    IE_NAME = 'funimation:show'
    _VALID_URL = '(?P<url>https?://(?:www\\.)?funimation(?:\\.com|now\\.uk)/(?P<locale>[^/]+)?/?shows/(?P<id>[^/?#&]+))/?(?:[?#]|$)'
    _NETRC_MACHINE = 'funimation'


class FunkIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.funk'
    IE_NAME = 'Funk'
    _VALID_URL = 'https?://(?:www\\.|origin\\.)?funk\\.net/(?:channel|playlist)/[^/]+/(?P<display_id>[0-9a-z-]+)-(?P<id>\\d+)'


class FusionIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.fusion'
    IE_NAME = 'Fusion'
    _VALID_URL = 'https?://(?:www\\.)?fusion\\.(?:net|tv)/(?:video/|show/.+?\\bvideo=)(?P<id>\\d+)'


class FuyinTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.fuyintv'
    IE_NAME = 'FuyinTV'
    _VALID_URL = 'https?://(?:www\\.)?fuyin\\.tv/html/(?:\\d+)/(?P<id>\\d+)\\.html'


class GabTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.gab'
    IE_NAME = 'GabTV'
    _VALID_URL = 'https?://tv\\.gab\\.com/channel/[^/]+/view/(?P<id>[a-z0-9-]+)'


class GabIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.gab'
    IE_NAME = 'Gab'
    _VALID_URL = 'https?://(?:www\\.)?gab\\.com/[^/]+/posts/(?P<id>\\d+)'


class GaiaIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.gaia'
    IE_NAME = 'Gaia'
    _VALID_URL = 'https?://(?:www\\.)?gaia\\.com/video/(?P<id>[^/?]+).*?\\bfullplayer=(?P<type>feature|preview)'
    _NETRC_MACHINE = 'gaia'


class GameInformerIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.gameinformer'
    IE_NAME = 'GameInformer'
    _VALID_URL = 'https?://(?:www\\.)?gameinformer\\.com/(?:[^/]+/)*(?P<id>[^.?&#]+)'


class GameJoltBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.gamejolt'
    IE_NAME = 'GameJoltBase'


class GameJoltIE(GameJoltBaseIE):
    _module = 'yt_dlp.extractor.gamejolt'
    IE_NAME = 'GameJolt'
    _VALID_URL = 'https?://(?:www\\.)?gamejolt\\.com/p/(?:[\\w-]*-)?(?P<id>\\w{8})'


class GameJoltPostListBaseIE(GameJoltBaseIE):
    _module = 'yt_dlp.extractor.gamejolt'
    IE_NAME = 'GameJoltPostListBase'


class GameJoltUserIE(GameJoltPostListBaseIE):
    _module = 'yt_dlp.extractor.gamejolt'
    IE_NAME = 'GameJoltUser'
    _VALID_URL = 'https?://(?:www\\.)?gamejolt\\.com/@(?P<id>[\\w-]+)'


class GameJoltGameIE(GameJoltPostListBaseIE):
    _module = 'yt_dlp.extractor.gamejolt'
    IE_NAME = 'GameJoltGame'
    _VALID_URL = 'https?://(?:www\\.)?gamejolt\\.com/games/[\\w-]+/(?P<id>\\d+)'


class GameJoltGameSoundtrackIE(GameJoltBaseIE):
    _module = 'yt_dlp.extractor.gamejolt'
    IE_NAME = 'GameJoltGameSoundtrack'
    _VALID_URL = 'https?://(?:www\\.)?gamejolt\\.com/get/soundtrack(?:\\?|\\#!?)(?:.*?[&;])??game=(?P<id>(?:\\d+)+)'


class GameJoltCommunityIE(GameJoltPostListBaseIE):
    _module = 'yt_dlp.extractor.gamejolt'
    IE_NAME = 'GameJoltCommunity'
    _VALID_URL = 'https?://(?:www\\.)?gamejolt\\.com/c/(?P<id>(?P<community>[\\w-]+)(?:/(?P<channel>[\\w-]+))?)(?:(?:\\?|\\#!?)(?:.*?[&;])??sort=(?P<sort>\\w+))?'


class GameJoltSearchIE(GameJoltPostListBaseIE):
    _module = 'yt_dlp.extractor.gamejolt'
    IE_NAME = 'GameJoltSearch'
    _VALID_URL = 'https?://(?:www\\.)?gamejolt\\.com/search(?:/(?P<filter>communities|users|games))?(?:\\?|\\#!?)(?:.*?[&;])??q=(?P<id>(?:[^&#]+)+)'


class GameSpotIE(OnceIE):
    _module = 'yt_dlp.extractor.gamespot'
    IE_NAME = 'GameSpot'
    _VALID_URL = 'https?://(?:www\\.)?gamespot\\.com/(?:video|article|review)s/(?:[^/]+/\\d+-|embed/)(?P<id>\\d+)'


class GameStarIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.gamestar'
    IE_NAME = 'GameStar'
    _VALID_URL = 'https?://(?:www\\.)?game(?P<site>pro|star)\\.de/videos/.*,(?P<id>[0-9]+)\\.html'


class GaskrankIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.gaskrank'
    IE_NAME = 'Gaskrank'
    _VALID_URL = 'https?://(?:www\\.)?gaskrank\\.tv/tv/(?P<categories>[^/]+)/(?P<id>[^/]+)\\.htm'


class GazetaIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.gazeta'
    IE_NAME = 'Gazeta'
    _VALID_URL = '(?P<url>https?://(?:www\\.)?gazeta\\.ru/(?:[^/]+/)?video/(?:main/)*(?:\\d{4}/\\d{2}/\\d{2}/)?(?P<id>[A-Za-z0-9-_.]+)\\.s?html)'


class GDCVaultIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.gdcvault'
    IE_NAME = 'GDCVault'
    _VALID_URL = 'https?://(?:www\\.)?gdcvault\\.com/play/(?P<id>\\d+)(?:/(?P<name>[\\w-]+))?'
    _NETRC_MACHINE = 'gdcvault'


class GediDigitalIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.gedidigital'
    IE_NAME = 'GediDigital'
    _VALID_URL = '(?x:(?P<base_url>(?:https?:)//video\\.\n        (?:\n            (?:\n                (?:espresso\\.)?repubblica\n                |lastampa\n                |ilsecoloxix\n                |huffingtonpost\n            )|\n            (?:\n                iltirreno\n                |messaggeroveneto\n                |ilpiccolo\n                |gazzettadimantova\n                |mattinopadova\n                |laprovinciapavese\n                |tribunatreviso\n                |nuovavenezia\n                |gazzettadimodena\n                |lanuovaferrara\n                |corrierealpi\n                |lasentinella\n            )\\.gelocal\n        )\\.it(?:/[^/]+){2,4}/(?P<id>\\d+))(?:$|[?&].*))'


class GeniusIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.genius'
    IE_NAME = 'Genius'
    _VALID_URL = 'https?://(?:www\\.)?genius\\.com/videos/(?P<id>[^?/#]+)'


class GeniusLyricsIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.genius'
    IE_NAME = 'GeniusLyrics'
    _VALID_URL = 'https?://(?:www\\.)?genius\\.com/(?P<id>[^?/#]+)-lyrics[?/#]?'


class GettrBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.gettr'
    IE_NAME = 'GettrBase'


class GettrIE(GettrBaseIE):
    _module = 'yt_dlp.extractor.gettr'
    IE_NAME = 'Gettr'
    _VALID_URL = 'https?://(www\\.)?gettr\\.com/post/(?P<id>[a-z0-9]+)'


class GettrStreamingIE(GettrBaseIE):
    _module = 'yt_dlp.extractor.gettr'
    IE_NAME = 'GettrStreaming'
    _VALID_URL = 'https?://(www\\.)?gettr\\.com/streaming/(?P<id>[a-z0-9]+)'


class GfycatIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.gfycat'
    IE_NAME = 'Gfycat'
    _VALID_URL = 'https?://(?:(?:www|giant|thumbs)\\.)?gfycat\\.com/(?i:ru/|ifr/|gifs/detail/)?(?P<id>[^-/?#\\."\\\']+)'


class GiantBombIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.giantbomb'
    IE_NAME = 'GiantBomb'
    _VALID_URL = 'https?://(?:www\\.)?giantbomb\\.com/(?:videos|shows)/(?P<display_id>[^/]+)/(?P<id>\\d+-\\d+)'


class GigaIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.giga'
    IE_NAME = 'Giga'
    _VALID_URL = 'https?://(?:www\\.)?giga\\.de/(?:[^/]+/)*(?P<id>[^/]+)'


class GlideIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.glide'
    IE_NAME = 'Glide'
    IE_DESC = 'Glide mobile video messages (glide.me)'
    _VALID_URL = 'https?://share\\.glide\\.me/(?P<id>[A-Za-z0-9\\-=_+]+)'


class GloboIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.globo'
    IE_NAME = 'Globo'
    _VALID_URL = '(?:globo:|https?://.+?\\.globo\\.com/(?:[^/]+/)*(?:v/(?:[^/]+/)?|videos/))(?P<id>\\d{7,})'
    _NETRC_MACHINE = 'globo'


class GloboArticleIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.globo'
    IE_NAME = 'GloboArticle'
    _VALID_URL = 'https?://.+?\\.globo\\.com/(?:[^/]+/)*(?P<id>[^/.]+)(?:\\.html)?'

    @classmethod
    def suitable(cls, url):
        return False if GloboIE.suitable(url) else super(GloboArticleIE, cls).suitable(url)


class GoIE(AdobePassIE):
    _module = 'yt_dlp.extractor.go'
    IE_NAME = 'Go'
    _VALID_URL = '(?x)\n                    https?://\n                        (?P<sub_domain>\n                            (?:abc\\.|freeform\\.|watchdisneychannel\\.|watchdisneyjunior\\.|watchdisneyxd\\.|disneynow\\.|fxnow.fxnetworks\\.)?go|fxnow\\.fxnetworks|\n                            (?:www\\.)?(?:abc|freeform|disneynow)\n                        )\\.com/\n                        (?:\n                            (?:[^/]+/)*(?P<id>[Vv][Dd][Kk][Aa]\\w+)|\n                            (?:[^/]+/)*(?P<display_id>[^/?\\#]+)\n                        )\n                    '
    age_limit = 14


class GodTubeIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.godtube'
    IE_NAME = 'GodTube'
    _VALID_URL = 'https?://(?:www\\.)?godtube\\.com/watch/\\?v=(?P<id>[\\da-zA-Z]+)'


class GofileIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.gofile'
    IE_NAME = 'Gofile'
    _VALID_URL = 'https?://(?:www\\.)?gofile\\.io/d/(?P<id>[^/]+)'


class GolemIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.golem'
    IE_NAME = 'Golem'
    _VALID_URL = '^https?://video\\.golem\\.de/.+?/(?P<id>.+?)/'


class GoodGameIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.goodgame'
    IE_NAME = 'goodgame:stream'
    _VALID_URL = 'https?://goodgame\\.ru/channel/(?P<id>\\w+)'


class GoogleDriveIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.googledrive'
    IE_NAME = 'GoogleDrive'
    _VALID_URL = '(?x)\n                        https?://\n                            (?:\n                                (?:docs|drive)\\.google\\.com/\n                                (?:\n                                    (?:uc|open)\\?.*?id=|\n                                    file/d/\n                                )|\n                                video\\.google\\.com/get_player\\?.*?docid=\n                            )\n                            (?P<id>[a-zA-Z0-9_-]{28,})\n                    '


class GoogleDriveFolderIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.googledrive'
    IE_NAME = 'GoogleDrive:Folder'
    _VALID_URL = 'https?://(?:docs|drive)\\.google\\.com/drive/folders/(?P<id>[\\w-]{28,})'


class GooglePodcastsBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.googlepodcasts'
    IE_NAME = 'GooglePodcastsBase'


class GooglePodcastsIE(GooglePodcastsBaseIE):
    _module = 'yt_dlp.extractor.googlepodcasts'
    IE_NAME = 'google:podcasts'
    _VALID_URL = 'https?://podcasts\\.google\\.com/feed/(?P<feed_url>[^/]+)/episode/(?P<id>[^/?&#]+)'


class GooglePodcastsFeedIE(GooglePodcastsBaseIE):
    _module = 'yt_dlp.extractor.googlepodcasts'
    IE_NAME = 'google:podcasts:feed'
    _VALID_URL = 'https?://podcasts\\.google\\.com/feed/(?P<id>[^/?&#]+)/?(?:[?#&]|$)'


class GoogleSearchIE(LazyLoadSearchExtractor):
    _module = 'yt_dlp.extractor.googlesearch'
    IE_NAME = 'video.google:search'
    IE_DESC = 'Google Video search'
    SEARCH_KEY = 'gvsearch'
    _VALID_URL = 'gvsearch(?P<prefix>|[1-9][0-9]*|all):(?P<query>[\\s\\S]+)'


class GoProIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.gopro'
    IE_NAME = 'GoPro'
    _VALID_URL = 'https?://(www\\.)?gopro\\.com/v/(?P<id>[A-Za-z0-9]+)'


class GoPlayIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.goplay'
    IE_NAME = 'GoPlay'
    _VALID_URL = 'https?://(www\\.)?goplay\\.be/video/([^/]+/[^/]+/|)(?P<display_id>[^/#]+)'
    _NETRC_MACHINE = 'goplay'


class GoshgayIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.goshgay'
    IE_NAME = 'Goshgay'
    _VALID_URL = 'https?://(?:www\\.)?goshgay\\.com/video(?P<id>\\d+?)($|/)'
    age_limit = 18


class GoToStageIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.gotostage'
    IE_NAME = 'GoToStage'
    _VALID_URL = 'https?://(?:www\\.)?gotostage\\.com/channel/[a-z0-9]+/recording/(?P<id>[a-z0-9]+)/watch'


class GPUTechConfIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.gputechconf'
    IE_NAME = 'GPUTechConf'
    _VALID_URL = 'https?://on-demand\\.gputechconf\\.com/gtc/2015/video/S(?P<id>\\d+)\\.html'


class GronkhIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.gronkh'
    IE_NAME = 'Gronkh'
    _VALID_URL = 'https?://(?:www\\.)?gronkh\\.tv/(?:watch/)?stream/(?P<id>\\d+)'


class GronkhFeedIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.gronkh'
    IE_NAME = 'gronkh:feed'
    _VALID_URL = 'https?://(?:www\\.)?gronkh\\.tv(?:/feed)?/?(?:#|$)'


class GronkhVodsIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.gronkh'
    IE_NAME = 'gronkh:vods'
    _VALID_URL = 'https?://(?:www\\.)?gronkh\\.tv/vods/streams/?(?:#|$)'


class GrouponIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.groupon'
    IE_NAME = 'Groupon'
    _VALID_URL = 'https?://(?:www\\.)?groupon\\.com/deals/(?P<id>[^/?#&]+)'


class HarpodeonIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.harpodeon'
    IE_NAME = 'Harpodeon'
    _VALID_URL = 'https?://(?:www\\.)?harpodeon\\.com/(?:video|preview)/\\w+/(?P<id>\\d+)'


class HBOIE(HBOBaseIE):
    _module = 'yt_dlp.extractor.hbo'
    IE_NAME = 'hbo'
    _VALID_URL = 'https?://(?:www\\.)?hbo\\.com/(?:video|embed)(?:/[^/]+)*/(?P<id>[^/?#]+)'


class HearThisAtIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.hearthisat'
    IE_NAME = 'HearThisAt'
    _VALID_URL = 'https?://(?:www\\.)?hearthis\\.at/(?P<artist>[^/]+)/(?P<title>[A-Za-z0-9\\-]+)/?$'


class HeiseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.heise'
    IE_NAME = 'Heise'
    _VALID_URL = 'https?://(?:www\\.)?heise\\.de/(?:[^/]+/)+[^/]+-(?P<id>[0-9]+)\\.html'


class HellPornoIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.hellporno'
    IE_NAME = 'HellPorno'
    _VALID_URL = 'https?://(?:www\\.)?hellporno\\.(?:com/videos|net/v)/(?P<id>[^/]+)'
    age_limit = 18


class HelsinkiIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.helsinki'
    IE_NAME = 'Helsinki'
    IE_DESC = 'helsinki.fi'
    _VALID_URL = 'https?://video\\.helsinki\\.fi/Arkisto/flash\\.php\\?id=(?P<id>\\d+)'


class HentaiStigmaIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.hentaistigma'
    IE_NAME = 'HentaiStigma'
    _VALID_URL = '^https?://hentai\\.animestigma\\.com/(?P<id>[^/]+)'
    age_limit = 18


class HGTVComShowIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.hgtv'
    IE_NAME = 'hgtv.com:show'
    _VALID_URL = 'https?://(?:www\\.)?hgtv\\.com/shows/[^/]+/(?P<id>[^/?#&]+)'


class HKETVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.hketv'
    IE_NAME = 'hketv'
    IE_DESC = '香港教育局教育電視 (HKETV) Educational Television, Hong Kong Educational Bureau'
    _VALID_URL = 'https?://(?:www\\.)?hkedcity\\.net/etv/resource/(?P<id>[0-9]+)'


class HiDiveIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.hidive'
    IE_NAME = 'HiDive'
    _VALID_URL = 'https?://(?:www\\.)?hidive\\.com/stream/(?P<id>(?P<title>[^/]+)/(?P<key>[^/?#&]+))'
    _NETRC_MACHINE = 'hidive'


class HistoricFilmsIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.historicfilms'
    IE_NAME = 'HistoricFilms'
    _VALID_URL = 'https?://(?:www\\.)?historicfilms\\.com/(?:tapes/|play)(?P<id>\\d+)'


class HitboxIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.hitbox'
    IE_NAME = 'hitbox'
    _VALID_URL = 'https?://(?:www\\.)?(?:hitbox|smashcast)\\.tv/(?:[^/]+/)*videos?/(?P<id>[0-9]+)'


class HitboxLiveIE(HitboxIE):
    _module = 'yt_dlp.extractor.hitbox'
    IE_NAME = 'hitbox:live'
    _VALID_URL = 'https?://(?:www\\.)?(?:hitbox|smashcast)\\.tv/(?P<id>[^/?#&]+)'

    @classmethod
    def suitable(cls, url):
        return False if HitboxIE.suitable(url) else super(HitboxLiveIE, cls).suitable(url)


class HitRecordIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.hitrecord'
    IE_NAME = 'HitRecord'
    _VALID_URL = 'https?://(?:www\\.)?hitrecord\\.org/records/(?P<id>\\d+)'


class HolodexIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.holodex'
    IE_NAME = 'Holodex'
    _VALID_URL = '(?x)https?://(?:www\\.|staging\\.)?holodex\\.net/(?:\n            api/v2/playlist/(?P<playlist>\\d+)|\n            watch/(?P<id>[\\w-]{11})(?:\\?(?:[^#]+&)?playlist=(?P<playlist2>\\d+))?\n        )'


class HotNewHipHopIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.hotnewhiphop'
    IE_NAME = 'HotNewHipHop'
    _VALID_URL = 'https?://(?:www\\.)?hotnewhiphop\\.com/.*\\.(?P<id>.*)\\.html'


class HotStarBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.hotstar'
    IE_NAME = 'HotStarBase'


class HotStarIE(HotStarBaseIE):
    _module = 'yt_dlp.extractor.hotstar'
    IE_NAME = 'hotstar'
    _VALID_URL = '(?x)\n        https?://(?:www\\.)?hotstar\\.com(?:/in)?/(?!in/)\n        (?:\n            (?P<type>movies|sports|episode|(?P<tv>tv))/\n            (?(tv)(?:[^/?#]+/){2}|[^?#]*)\n        )?\n        [^/?#]+/\n        (?P<id>\\d{10})\n    '


class HotStarPrefixIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.hotstar'
    IE_NAME = 'HotStarPrefix'
    IE_DESC = False
    _VALID_URL = 'hotstar:(?:(?P<type>\\w+):)?(?P<id>\\d+)$'


class HotStarPlaylistIE(HotStarBaseIE):
    _module = 'yt_dlp.extractor.hotstar'
    IE_NAME = 'hotstar:playlist'
    _VALID_URL = 'https?://(?:www\\.)?hotstar\\.com(?:/in)?/tv(?:/[^/]+){2}/list/[^/]+/t-(?P<id>\\w+)'


class HotStarSeasonIE(HotStarBaseIE):
    _module = 'yt_dlp.extractor.hotstar'
    IE_NAME = 'hotstar:season'
    _VALID_URL = '(?P<url>https?://(?:www\\.)?hotstar\\.com(?:/in)?/tv/[^/]+/\\w+)/seasons/[^/]+/ss-(?P<id>\\w+)'


class HotStarSeriesIE(HotStarBaseIE):
    _module = 'yt_dlp.extractor.hotstar'
    IE_NAME = 'hotstar:series'
    _VALID_URL = '(?P<url>https?://(?:www\\.)?hotstar\\.com(?:/in)?/tv/[^/]+/(?P<id>\\d+))/?(?:[#?]|$)'


class HowcastIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.howcast'
    IE_NAME = 'Howcast'
    _VALID_URL = 'https?://(?:www\\.)?howcast\\.com/videos/(?P<id>\\d+)'


class HowStuffWorksIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.howstuffworks'
    IE_NAME = 'HowStuffWorks'
    _VALID_URL = 'https?://[\\da-z-]+\\.(?:howstuffworks|stuff(?:(?:youshould|theydontwantyouto)know|toblowyourmind|momnevertoldyou)|(?:brain|car)stuffshow|fwthinking|geniusstuff)\\.com/(?:[^/]+/)*(?:\\d+-)?(?P<id>.+?)-video\\.htm'


class HRFernsehenIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.hrfensehen'
    IE_NAME = 'hrfernsehen'
    _VALID_URL = '^https?://www\\.(?:hr-fernsehen|hessenschau)\\.de/.*,video-(?P<id>[0-9]{6})\\.html'


class HRTiBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.hrti'
    IE_NAME = 'HRTiBase'
    _NETRC_MACHINE = 'hrti'


class HRTiIE(HRTiBaseIE):
    _module = 'yt_dlp.extractor.hrti'
    IE_NAME = 'HRTi'
    _VALID_URL = '(?x)\n                        (?:\n                            hrti:(?P<short_id>[0-9]+)|\n                            https?://\n                                hrti\\.hrt\\.hr/(?:\\#/)?video/show/(?P<id>[0-9]+)/(?P<display_id>[^/]+)?\n                        )\n                    '
    _NETRC_MACHINE = 'hrti'
    age_limit = 12


class HRTiPlaylistIE(HRTiBaseIE):
    _module = 'yt_dlp.extractor.hrti'
    IE_NAME = 'HRTiPlaylist'
    _VALID_URL = 'https?://hrti\\.hrt\\.hr/(?:#/)?video/list/category/(?P<id>[0-9]+)/(?P<display_id>[^/]+)?'
    _NETRC_MACHINE = 'hrti'


class HSEShowBaseInfoExtractor(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.hse'
    IE_NAME = 'HSEShowBaseInfoExtract'


class HSEShowIE(HSEShowBaseInfoExtractor):
    _module = 'yt_dlp.extractor.hse'
    IE_NAME = 'HSEShow'
    _VALID_URL = 'https?://(?:www\\.)?hse\\.de/dpl/c/tv-shows/(?P<id>[0-9]+)'


class HSEProductIE(HSEShowBaseInfoExtractor):
    _module = 'yt_dlp.extractor.hse'
    IE_NAME = 'HSEProduct'
    _VALID_URL = 'https?://(?:www\\.)?hse\\.de/dpl/p/product/(?P<id>[0-9]+)'


class HTML5MediaEmbedIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.genericembeds'
    IE_NAME = 'html5'
    _VALID_URL = False


class QuotedHTMLIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.genericembeds'
    IE_NAME = 'generic:quoted-html'
    IE_DESC = False
    _VALID_URL = False


class HuajiaoIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.huajiao'
    IE_NAME = 'Huajiao'
    IE_DESC = '花椒直播'
    _VALID_URL = 'https?://(?:www\\.)?huajiao\\.com/l/(?P<id>[0-9]+)'


class HuyaLiveIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.huya'
    IE_NAME = 'huya:live'
    IE_DESC = 'huya.com'
    _VALID_URL = 'https?://(?:www\\.|m\\.)?huya\\.com/(?P<id>[^/#?&]+)(?:\\D|$)'


class HuffPostIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.huffpost'
    IE_NAME = 'HuffPost'
    IE_DESC = 'Huffington Post'
    _VALID_URL = '(?x)\n        https?://(embed\\.)?live\\.huffingtonpost\\.com/\n        (?:\n            r/segment/[^/]+/|\n            HPLEmbedPlayer/\\?segmentId=\n        )\n        (?P<id>[0-9a-f]+)'


class HungamaIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.hungama'
    IE_NAME = 'Hungama'
    _VALID_URL = '(?x)\n                    https?://\n                        (?:www\\.)?hungama\\.com/\n                        (?:\n                            (?:video|movie)/[^/]+/|\n                            tv-show/(?:[^/]+/){2}\\d+/episode/[^/]+/\n                        )\n                        (?P<id>\\d+)\n                    '


class HungamaSongIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.hungama'
    IE_NAME = 'HungamaSong'
    _VALID_URL = 'https?://(?:www\\.)?hungama\\.com/song/[^/]+/(?P<id>\\d+)'


class HungamaAlbumPlaylistIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.hungama'
    IE_NAME = 'HungamaAlbumPlaylist'
    _VALID_URL = 'https?://(?:www\\.)?hungama\\.com/(?:playlists|album)/[^/]+/(?P<id>\\d+)'


class HypemIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.hypem'
    IE_NAME = 'Hypem'
    _VALID_URL = 'https?://(?:www\\.)?hypem\\.com/track/(?P<id>[0-9a-z]{5})'


class HytaleIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.hytale'
    IE_NAME = 'Hytale'
    _VALID_URL = 'https?://(?:www\\.)?hytale\\.com/news/\\d+/\\d+/(?P<id>[a-z0-9-]+)'


class IcareusIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.icareus'
    IE_NAME = 'Icareus'
    _VALID_URL = '(?P<base_url>https?://(?:www\\.)?(?:asahitv\\.fi|helsinkikanava\\.fi|hyvinvointitv\\.fi|inez\\.fi|permanto\\.fi|suite\\.icareus\\.com|videos\\.minifiddlers\\.org))/[^?#]+/player/[^?#]+\\?(?:[^#]+&)?(?:assetId|eventId)=(?P<id>\\d+)'


class IchinanaLiveIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ichinanalive'
    IE_NAME = '17live'
    _VALID_URL = 'https?://(?:www\\.)?17\\.live/(?:[^/]+/)*(?:live|profile/r)/(?P<id>\\d+)'

    @classmethod
    def suitable(cls, url):
        return not IchinanaLiveClipIE.suitable(url) and super(IchinanaLiveIE, cls).suitable(url)


class IchinanaLiveClipIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ichinanalive'
    IE_NAME = '17live:clip'
    _VALID_URL = 'https?://(?:www\\.)?17\\.live/(?:[^/]+/)*profile/r/(?P<uploader_id>\\d+)/clip/(?P<id>[^/]+)'


class IGNBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ign'
    IE_NAME = 'IGNBase'


class IGNIE(IGNBaseIE):
    _module = 'yt_dlp.extractor.ign'
    IE_NAME = 'ign.com'
    _VALID_URL = 'https?://(?:.+?\\.ign|www\\.pcmag)\\.com/videos/(?:\\d{4}/\\d{2}/\\d{2}/)?(?P<id>[^/?&#]+)'


class IGNVideoIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ign'
    IE_NAME = 'IGNVideo'
    _VALID_URL = 'https?://.+?\\.ign\\.com/(?:[a-z]{2}/)?[^/]+/(?P<id>\\d+)/(?:video|trailer)/'


class IGNArticleIE(IGNBaseIE):
    _module = 'yt_dlp.extractor.ign'
    IE_NAME = 'IGNArticle'
    _VALID_URL = 'https?://.+?\\.ign\\.com/(?:articles(?:/\\d{4}/\\d{2}/\\d{2})?|(?:[a-z]{2}/)?feature/\\d+)/(?P<id>[^/?&#]+)'


class IHeartRadioBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.iheart'
    IE_NAME = 'IHeartRadioBase'


class IHeartRadioIE(IHeartRadioBaseIE):
    _module = 'yt_dlp.extractor.iheart'
    IE_NAME = 'IHeartRadio'
    _VALID_URL = '(?:https?://(?:www\\.)?iheart\\.com/podcast/[^/]+/episode/(?P<display_id>[^/?&#]+)-|iheartradio:)(?P<id>\\d+)'


class IHeartRadioPodcastIE(IHeartRadioBaseIE):
    _module = 'yt_dlp.extractor.iheart'
    IE_NAME = 'iheartradio:podcast'
    _VALID_URL = 'https?://(?:www\\.)?iheart(?:podcastnetwork)?\\.com/podcast/[^/?&#]+-(?P<id>\\d+)/?(?:[?#&]|$)'


class IltalehtiIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.iltalehti'
    IE_NAME = 'Iltalehti'
    _VALID_URL = 'https?://(?:www\\.)?iltalehti\\.fi/[^/?#]+/a/(?P<id>[^/?#])'


class ImdbIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.imdb'
    IE_NAME = 'imdb'
    IE_DESC = 'Internet Movie Database trailers'
    _VALID_URL = 'https?://(?:www|m)\\.imdb\\.com/(?:video|title|list).*?[/-]vi(?P<id>\\d+)'


class ImdbListIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.imdb'
    IE_NAME = 'imdb:list'
    IE_DESC = 'Internet Movie Database lists'
    _VALID_URL = 'https?://(?:www\\.)?imdb\\.com/list/ls(?P<id>\\d{9})(?!/videoplayer/vi\\d+)'


class ImgurIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.imgur'
    IE_NAME = 'Imgur'
    _VALID_URL = 'https?://(?:i\\.)?imgur\\.com/(?!(?:a|gallery|(?:t(?:opic)?|r)/[^/]+)/)(?P<id>[a-zA-Z0-9]+)'


class ImgurGalleryIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.imgur'
    IE_NAME = 'imgur:gallery'
    _VALID_URL = 'https?://(?:i\\.)?imgur\\.com/(?:gallery|(?:t(?:opic)?|r)/[^/]+)/(?P<id>[a-zA-Z0-9]+)'


class ImgurAlbumIE(ImgurGalleryIE):
    _module = 'yt_dlp.extractor.imgur'
    IE_NAME = 'imgur:album'
    _VALID_URL = 'https?://(?:i\\.)?imgur\\.com/a/(?P<id>[a-zA-Z0-9]+)'


class InaIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ina'
    IE_NAME = 'Ina'
    _VALID_URL = 'https?://(?:(?:www|m)\\.)?ina\\.fr/(?:[^?#]+/)(?P<id>[\\w-]+)'


class IncIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.inc'
    IE_NAME = 'Inc'
    _VALID_URL = 'https?://(?:www\\.)?inc\\.com/(?:[^/]+/)+(?P<id>[^.]+).html'


class IndavideoEmbedIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.indavideo'
    IE_NAME = 'IndavideoEmbed'
    _VALID_URL = 'https?://(?:(?:embed\\.)?indavideo\\.hu/player/video/|assets\\.indavideo\\.hu/swf/player\\.swf\\?.*\\b(?:v(?:ID|id))=)(?P<id>[\\da-f]+)'


class InfoQIE(BokeCCBaseIE):
    _module = 'yt_dlp.extractor.infoq'
    IE_NAME = 'InfoQ'
    _VALID_URL = 'https?://(?:www\\.)?infoq\\.com/(?:[^/]+/)+(?P<id>[^/]+)'


class InstagramBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.instagram'
    IE_NAME = 'InstagramBase'
    _NETRC_MACHINE = 'instagram'


class InstagramIE(InstagramBaseIE):
    _module = 'yt_dlp.extractor.instagram'
    IE_NAME = 'Instagram'
    _VALID_URL = '(?P<url>https?://(?:www\\.)?instagram\\.com(?:/[^/]+)?/(?:p|tv|reel)/(?P<id>[^/?#&]+))'
    _NETRC_MACHINE = 'instagram'


class InstagramIOSIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.instagram'
    IE_NAME = 'InstagramIOS'
    IE_DESC = 'IOS instagram:// URL'
    _VALID_URL = 'instagram://media\\?id=(?P<id>[\\d_]+)'


class InstagramPlaylistBaseIE(InstagramBaseIE):
    _module = 'yt_dlp.extractor.instagram'
    IE_NAME = 'InstagramPlaylistBase'
    _NETRC_MACHINE = 'instagram'


class InstagramUserIE(InstagramPlaylistBaseIE):
    _module = 'yt_dlp.extractor.instagram'
    IE_NAME = 'instagram:user'
    IE_DESC = 'Instagram user profile'
    _VALID_URL = 'https?://(?:www\\.)?instagram\\.com/(?P<id>[^/]{2,})/?(?:$|[?#])'
    _NETRC_MACHINE = 'instagram'


class InstagramTagIE(InstagramPlaylistBaseIE):
    _module = 'yt_dlp.extractor.instagram'
    IE_NAME = 'instagram:tag'
    IE_DESC = 'Instagram hashtag search URLs'
    _VALID_URL = 'https?://(?:www\\.)?instagram\\.com/explore/tags/(?P<id>[^/]+)'
    _NETRC_MACHINE = 'instagram'


class InstagramStoryIE(InstagramBaseIE):
    _module = 'yt_dlp.extractor.instagram'
    IE_NAME = 'instagram:story'
    _VALID_URL = 'https?://(?:www\\.)?instagram\\.com/stories/(?P<user>[^/]+)/(?P<id>\\d+)'
    _NETRC_MACHINE = 'instagram'


class InternazionaleIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.internazionale'
    IE_NAME = 'Internazionale'
    _VALID_URL = 'https?://(?:www\\.)?internazionale\\.it/video/(?:[^/]+/)*(?P<id>[^/?#&]+)'


class InternetVideoArchiveIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.internetvideoarchive'
    IE_NAME = 'InternetVideoArchive'
    _VALID_URL = 'https?://video\\.internetvideoarchive\\.net/(?:player|flash/players)/.*?\\?.*?publishedid.*?'


class IPrimaIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.iprima'
    IE_NAME = 'IPrima'
    _VALID_URL = 'https?://(?!cnn)(?:[^/]+)\\.iprima\\.cz/(?:[^/]+/)*(?P<id>[^/?#&]+)'
    _NETRC_MACHINE = 'iprima'


class IPrimaCNNIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.iprima'
    IE_NAME = 'IPrimaCNN'
    _VALID_URL = 'https?://cnn\\.iprima\\.cz/(?:[^/]+/)*(?P<id>[^/?#&]+)'


class IqiyiIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.iqiyi'
    IE_NAME = 'iqiyi'
    IE_DESC = '爱奇艺'
    _VALID_URL = 'https?://(?:(?:[^.]+\\.)?iqiyi\\.com|www\\.pps\\.tv)/.+\\.html'
    _NETRC_MACHINE = 'iqiyi'


class IqIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.iqiyi'
    IE_NAME = 'iq.com'
    IE_DESC = 'International version of iQiyi'
    _VALID_URL = 'https?://(?:www\\.)?iq\\.com/play/(?:[\\w%-]*-)?(?P<id>\\w+)'
    age_limit = 13


class IqAlbumIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.iqiyi'
    IE_NAME = 'iq.com:album'
    _VALID_URL = 'https?://(?:www\\.)?iq\\.com/album/(?:[\\w%-]*-)?(?P<id>\\w+)'
    age_limit = 13


class IslamChannelIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.islamchannel'
    IE_NAME = 'IslamChannel'
    _VALID_URL = 'https?://watch\\.islamchannel\\.tv/watch/(?P<id>\\d+)'


class IslamChannelSeriesIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.islamchannel'
    IE_NAME = 'IslamChannelSeries'
    _VALID_URL = 'https?://watch\\.islamchannel\\.tv/series/(?P<id>[a-f\\d-]+)'


class IsraelNationalNewsIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.israelnationalnews'
    IE_NAME = 'IsraelNationalNews'
    _VALID_URL = 'https?://(?:www\\.)?israelnationalnews\\.com/news/(?P<id>\\d+)'


class ITProTVBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.itprotv'
    IE_NAME = 'ITProTVBase'


class ITProTVIE(ITProTVBaseIE):
    _module = 'yt_dlp.extractor.itprotv'
    IE_NAME = 'ITProTV'
    _VALID_URL = 'https://app.itpro.tv/course/(?P<course>[\\w-]+)/(?P<id>[\\w-]+)'


class ITProTVCourseIE(ITProTVBaseIE):
    _module = 'yt_dlp.extractor.itprotv'
    IE_NAME = 'ITProTVCourse'
    _VALID_URL = 'https?://app.itpro.tv/course/(?P<id>[\\w-]+)/?(?:$|[#?])'


class ITVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.itv'
    IE_NAME = 'ITV'
    _VALID_URL = 'https?://(?:www\\.)?itv\\.com/hub/[^/]+/(?P<id>[0-9a-zA-Z]+)'


class ITVBTCCIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.itv'
    IE_NAME = 'ITVBTCC'
    _VALID_URL = 'https?://(?:www\\.)?itv\\.com/(?:news|btcc)/(?:[^/]+/)*(?P<id>[^/?#&]+)'


class IviIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ivi'
    IE_NAME = 'ivi'
    IE_DESC = 'ivi.ru'
    _VALID_URL = 'https?://(?:www\\.)?ivi\\.(?:ru|tv)/(?:watch/(?:[^/]+/)?|video/player\\?.*?videoId=)(?P<id>\\d+)'


class IviCompilationIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ivi'
    IE_NAME = 'ivi:compilation'
    IE_DESC = 'ivi.ru compilations'
    _VALID_URL = 'https?://(?:www\\.)?ivi\\.ru/watch/(?!\\d+)(?P<compilationid>[a-z\\d_-]+)(?:/season(?P<seasonid>\\d+))?$'


class IvideonIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ivideon'
    IE_NAME = 'ivideon'
    IE_DESC = 'Ivideon TV'
    _VALID_URL = 'https?://(?:www\\.)?ivideon\\.com/tv/(?:[^/]+/)*camera/(?P<id>\\d+-[\\da-f]+)/(?P<camera_id>\\d+)'


class IwaraBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.iwara'
    IE_NAME = 'IwaraBase'


class IwaraIE(IwaraBaseIE):
    _module = 'yt_dlp.extractor.iwara'
    IE_NAME = 'Iwara'
    _VALID_URL = '(?P<base_url>https?://(?:www\\.|ecchi\\.)?iwara\\.tv)/videos/(?P<id>[a-zA-Z0-9]+)'
    age_limit = 18


class IwaraPlaylistIE(IwaraBaseIE):
    _module = 'yt_dlp.extractor.iwara'
    IE_NAME = 'iwara:playlist'
    _VALID_URL = '(?P<base_url>https?://(?:www\\.|ecchi\\.)?iwara\\.tv)/playlist/(?P<id>[^/?#&]+)'


class IwaraUserIE(IwaraBaseIE):
    _module = 'yt_dlp.extractor.iwara'
    IE_NAME = 'iwara:user'
    _VALID_URL = '(?P<base_url>https?://(?:www\\.|ecchi\\.)?iwara\\.tv)/users/(?P<id>[^/?#&]+)'


class IxiguaIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ixigua'
    IE_NAME = 'Ixigua'
    _VALID_URL = 'https?://(?:\\w+\\.)?ixigua\\.com/(?:video/)?(?P<id>\\d+).+'


class IzleseneIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.izlesene'
    IE_NAME = 'Izlesene'
    _VALID_URL = '(?x)\n        https?://(?:(?:www|m)\\.)?izlesene\\.com/\n        (?:video|embedplayer)/(?:[^/]+/)?(?P<id>[0-9]+)\n        '


class JableIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.jable'
    IE_NAME = 'Jable'
    _VALID_URL = 'https?://(?:www\\.)?jable.tv/videos/(?P<id>[\\w-]+)'
    age_limit = 18


class JablePlaylistIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.jable'
    IE_NAME = 'JablePlaylist'
    _VALID_URL = 'https?://(?:www\\.)?jable.tv/(?:categories|models|tags)/(?P<id>[\\w-]+)'


class JamendoIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.jamendo'
    IE_NAME = 'Jamendo'
    _VALID_URL = '(?x)\n                    https?://\n                        (?:\n                            licensing\\.jamendo\\.com/[^/]+|\n                            (?:www\\.)?jamendo\\.com\n                        )\n                        /track/(?P<id>[0-9]+)(?:/(?P<display_id>[^/?#&]+))?\n                    '


class JamendoAlbumIE(JamendoIE):
    _module = 'yt_dlp.extractor.jamendo'
    IE_NAME = 'JamendoAlbum'
    _VALID_URL = 'https?://(?:www\\.)?jamendo\\.com/album/(?P<id>[0-9]+)'


class ShugiinItvBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.japandiet'
    IE_NAME = 'ShugiinItvBase'


class ShugiinItvLiveIE(ShugiinItvBaseIE):
    _module = 'yt_dlp.extractor.japandiet'
    IE_NAME = 'ShugiinItvLive'
    IE_DESC = '衆議院インターネット審議中継'
    _VALID_URL = 'https?://(?:www\\.)?shugiintv\\.go\\.jp/(?:jp|en)(?:/index\\.php)?$'

    @classmethod
    def suitable(cls, url):
        return super().suitable(url) and not any(x.suitable(url) for x in (ShugiinItvLiveRoomIE, ShugiinItvVodIE))


class ShugiinItvLiveRoomIE(ShugiinItvBaseIE):
    _module = 'yt_dlp.extractor.japandiet'
    IE_NAME = 'ShugiinItvLiveRoom'
    IE_DESC = '衆議院インターネット審議中継 (中継)'
    _VALID_URL = 'https?://(?:www\\.)?shugiintv\\.go\\.jp/(?:jp|en)/index\\.php\\?room_id=(?P<id>room\\d+)'


class ShugiinItvVodIE(ShugiinItvBaseIE):
    _module = 'yt_dlp.extractor.japandiet'
    IE_NAME = 'ShugiinItvVod'
    IE_DESC = '衆議院インターネット審議中継 (ビデオライブラリ)'
    _VALID_URL = 'https?://(?:www\\.)?shugiintv\\.go\\.jp/(?:jp|en)/index\\.php\\?ex=VL(?:\\&[^=]+=[^&]*)*\\&deli_id=(?P<id>\\d+)'


class SangiinInstructionIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.japandiet'
    IE_NAME = 'SangiinInstruction'
    IE_DESC = False
    _VALID_URL = '^https?://www\\.webtv\\.sangiin\\.go\\.jp/webtv/index\\.php'


class SangiinIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.japandiet'
    IE_NAME = 'Sangiin'
    IE_DESC = '参議院インターネット審議中継 (archive)'
    _VALID_URL = 'https?://www\\.webtv\\.sangiin\\.go\\.jp/webtv/detail\\.php\\?sid=(?P<id>\\d+)'


class JeuxVideoIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.jeuxvideo'
    IE_NAME = 'JeuxVideo'
    _VALID_URL = 'https?://.*?\\.jeuxvideo\\.com/.*/(.*?)\\.htm'


class JoveIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.jove'
    IE_NAME = 'Jove'
    _VALID_URL = 'https?://(?:www\\.)?jove\\.com/video/(?P<id>[0-9]+)'


class JojIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.joj'
    IE_NAME = 'Joj'
    _VALID_URL = '(?x)\n                    (?:\n                        joj:|\n                        https?://media\\.joj\\.sk/embed/\n                    )\n                    (?P<id>[^/?#^]+)\n                '


class JWPlatformIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.jwplatform'
    IE_NAME = 'JWPlatform'
    _VALID_URL = '(?:https?://(?:content\\.jwplatform|cdn\\.jwplayer)\\.com/(?:(?:feed|player|thumb|preview|manifest)s|jw6|v2/media)/|jwplatform:)(?P<id>[a-zA-Z0-9]{8})'


class KakaoIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.kakao'
    IE_NAME = 'Kakao'
    _VALID_URL = 'https?://(?:play-)?tv\\.kakao\\.com/(?:channel/\\d+|embed/player)/cliplink/(?P<id>\\d+|[^?#&]+@my)'


class KalturaIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.kaltura'
    IE_NAME = 'Kaltura'
    _VALID_URL = '(?x)\n                (?:\n                    kaltura:(?P<partner_id>\\w+):(?P<id>\\w+)(?::(?P<player_type>\\w+))?|\n                    https?://\n                        (:?(?:www|cdnapi(?:sec)?)\\.)?kaltura\\.com(?::\\d+)?/\n                        (?:\n                            (?:\n                                # flash player\n                                index\\.php/(?:kwidget|extwidget/preview)|\n                                # html5 player\n                                html5/html5lib/[^/]+/mwEmbedFrame\\.php\n                            )\n                        )(?:/(?P<path>[^?]+))?(?:\\?(?P<query>.*))?\n                )\n                '


class KaraoketvIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.karaoketv'
    IE_NAME = 'Karaoketv'
    _VALID_URL = 'https?://(?:www\\.)?karaoketv\\.co\\.il/[^/]+/(?P<id>\\d+)'


class KarriereVideosIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.karrierevideos'
    IE_NAME = 'KarriereVideos'
    _VALID_URL = 'https?://(?:www\\.)?karrierevideos\\.at(?:/[^/]+)+/(?P<id>[^/]+)'


class KeezMoviesIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.keezmovies'
    IE_NAME = 'KeezMovies'
    _VALID_URL = 'https?://(?:www\\.)?keezmovies\\.com/video/(?:(?P<display_id>[^/]+)-)?(?P<id>\\d+)'
    age_limit = 18


class ExtremeTubeIE(KeezMoviesIE):
    _module = 'yt_dlp.extractor.extremetube'
    IE_NAME = 'ExtremeTube'
    _VALID_URL = 'https?://(?:www\\.)?extremetube\\.com/(?:[^/]+/)?video/(?P<id>[^/#?&]+)'
    age_limit = 18


class KelbyOneIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.kelbyone'
    IE_NAME = 'KelbyOne'
    _VALID_URL = 'https?://members\\.kelbyone\\.com/course/(?P<id>[^$&?#/]+)'


class KetnetIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ketnet'
    IE_NAME = 'Ketnet'
    _VALID_URL = 'https?://(?:www\\.)?ketnet\\.be/(?P<id>(?:[^/]+/)*[^/?#&]+)'


class KhanAcademyBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.khanacademy'
    IE_NAME = 'KhanAcademyBase'


class KhanAcademyIE(KhanAcademyBaseIE):
    _module = 'yt_dlp.extractor.khanacademy'
    IE_NAME = 'khanacademy'
    _VALID_URL = 'https?://(?:www\\.)?khanacademy\\.org/(?P<id>(?:[^/]+/){4}v/[^?#/&]+)'


class KhanAcademyUnitIE(KhanAcademyBaseIE):
    _module = 'yt_dlp.extractor.khanacademy'
    IE_NAME = 'khanacademy:unit'
    _VALID_URL = 'https?://(?:www\\.)?khanacademy\\.org/(?P<id>(?:[^/]+/){2}[^?#/&]+)/?(?:[?#&]|$)'


class KickerIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.kicker'
    IE_NAME = 'Kicker'
    _VALID_URL = 'https?://(?:www\\.)kicker\\.(?:de)/(?P<id>[\\w-]+)/video'


class KickStarterIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.kickstarter'
    IE_NAME = 'KickStarter'
    _VALID_URL = 'https?://(?:www\\.)?kickstarter\\.com/projects/(?P<id>[^/]*)/.*'


class KinjaEmbedIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.kinja'
    IE_NAME = 'KinjaEmbed'
    _VALID_URL = '(?x)https?://(?:[^.]+\\.)?\n        (?:\n            avclub|\n            clickhole|\n            deadspin|\n            gizmodo|\n            jalopnik|\n            jezebel|\n            kinja|\n            kotaku|\n            lifehacker|\n            splinternews|\n            the(?:inventory|onion|root|takeout)\n        )\\.com/\n        (?:\n            ajax/inset|\n            embed/video\n        )/iframe\\?.*?\\bid=\n        (?P<type>\n            fb|\n            imgur|\n            instagram|\n            jwp(?:layer)?-video|\n            kinjavideo|\n            mcp|\n            megaphone|\n            ooyala|\n            soundcloud(?:-playlist)?|\n            tumblr-post|\n            twitch-stream|\n            twitter|\n            ustream-channel|\n            vimeo|\n            vine|\n            youtube-(?:list|video)\n        )-(?P<id>[^&]+)'


class KinoPoiskIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.kinopoisk'
    IE_NAME = 'KinoPoisk'
    _VALID_URL = 'https?://(?:www\\.)?kinopoisk\\.ru/film/(?P<id>\\d+)'
    age_limit = 12


class JixieBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.jixie'
    IE_NAME = 'JixieBase'


class KompasVideoIE(JixieBaseIE):
    _module = 'yt_dlp.extractor.kompas'
    IE_NAME = 'KompasVideo'
    _VALID_URL = 'https?://video\\.kompas\\.com/\\w+/(?P<id>\\d+)/(?P<slug>[\\w-]+)'


class KonserthusetPlayIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.konserthusetplay'
    IE_NAME = 'KonserthusetPlay'
    _VALID_URL = 'https?://(?:www\\.)?(?:konserthusetplay|rspoplay)\\.se/\\?.*\\bm=(?P<id>[^&]+)'


class KooIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.koo'
    IE_NAME = 'Koo'
    _VALID_URL = 'https?://(?:www\\.)?kooapp\\.com/koo/[^/]+/(?P<id>[^/&#$?]+)'


class KTHIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.kth'
    IE_NAME = 'KTH'
    _VALID_URL = 'https?://play\\.kth\\.se/(?:[^/]+/)+(?P<id>[a-z0-9_]+)'


class KrasViewIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.krasview'
    IE_NAME = 'KrasView'
    IE_DESC = 'Красвью'
    _VALID_URL = 'https?://krasview\\.ru/(?:video|embed)/(?P<id>\\d+)'


class Ku6IE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ku6'
    IE_NAME = 'Ku6'
    _VALID_URL = 'https?://v\\.ku6\\.com/show/(?P<id>[a-zA-Z0-9\\-\\_]+)(?:\\.)*html'


class KUSIIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.kusi'
    IE_NAME = 'KUSI'
    _VALID_URL = 'https?://(?:www\\.)?kusi\\.com/(?P<path>story/.+|video\\?clipId=(?P<clipId>\\d+))'


class KuwoBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.kuwo'
    IE_NAME = 'KuwoBase'


class KuwoIE(KuwoBaseIE):
    _module = 'yt_dlp.extractor.kuwo'
    IE_NAME = 'kuwo:song'
    IE_DESC = '酷我音乐'
    _VALID_URL = 'https?://(?:www\\.)?kuwo\\.cn/yinyue/(?P<id>\\d+)'


class KuwoAlbumIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.kuwo'
    IE_NAME = 'kuwo:album'
    IE_DESC = '酷我音乐 - 专辑'
    _VALID_URL = 'https?://(?:www\\.)?kuwo\\.cn/album/(?P<id>\\d+?)/'


class KuwoChartIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.kuwo'
    IE_NAME = 'kuwo:chart'
    IE_DESC = '酷我音乐 - 排行榜'
    _VALID_URL = 'https?://yinyue\\.kuwo\\.cn/billboard_(?P<id>[^.]+).htm'


class KuwoSingerIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.kuwo'
    IE_NAME = 'kuwo:singer'
    IE_DESC = '酷我音乐 - 歌手'
    _VALID_URL = 'https?://(?:www\\.)?kuwo\\.cn/mingxing/(?P<id>[^/]+)'


class KuwoCategoryIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.kuwo'
    IE_NAME = 'kuwo:category'
    IE_DESC = '酷我音乐 - 分类'
    _VALID_URL = 'https?://yinyue\\.kuwo\\.cn/yy/cinfo_(?P<id>\\d+?).htm'


class KuwoMvIE(KuwoBaseIE):
    _module = 'yt_dlp.extractor.kuwo'
    IE_NAME = 'kuwo:mv'
    IE_DESC = '酷我音乐 - MV'
    _VALID_URL = 'https?://(?:www\\.)?kuwo\\.cn/mv/(?P<id>\\d+?)/'


class LA7IE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.la7'
    IE_NAME = 'la7.it'
    _VALID_URL = '(?x)(https?://)?(?:\n        (?:www\\.)?la7\\.it/([^/]+)/(?:rivedila7|video)/|\n        tg\\.la7\\.it/repliche-tgla7\\?id=\n    )(?P<id>.+)'


class LA7PodcastEpisodeIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.la7'
    IE_NAME = 'la7.it:pod:episode'
    _VALID_URL = '(?x)(https?://)?\n        (?:www\\.)?la7\\.it/[^/]+/podcast/([^/]+-)?(?P<id>\\d+)'


class LA7PodcastIE(LA7PodcastEpisodeIE):
    _module = 'yt_dlp.extractor.la7'
    IE_NAME = 'la7.it:podcast'
    _VALID_URL = '(https?://)?(www\\.)?la7\\.it/(?P<id>[^/]+)/podcast/?(?:$|[#?])'


class Laola1TvEmbedIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.laola1tv'
    IE_NAME = 'laola1tv:embed'
    _VALID_URL = 'https?://(?:www\\.)?laola1\\.tv/titanplayer\\.php\\?.*?\\bvideoid=(?P<id>\\d+)'


class Laola1TvBaseIE(Laola1TvEmbedIE):
    _module = 'yt_dlp.extractor.laola1tv'
    IE_NAME = 'laola1tv:embed'
    _VALID_URL = 'https?://(?:www\\.)?laola1\\.tv/titanplayer\\.php\\?.*?\\bvideoid=(?P<id>\\d+)'


class Laola1TvIE(Laola1TvBaseIE):
    _module = 'yt_dlp.extractor.laola1tv'
    IE_NAME = 'laola1tv'
    _VALID_URL = 'https?://(?:www\\.)?laola1\\.tv/[a-z]+-[a-z]+/[^/]+/(?P<id>[^/?#&]+)'


class EHFTVIE(Laola1TvBaseIE):
    _module = 'yt_dlp.extractor.laola1tv'
    IE_NAME = 'ehftv'
    _VALID_URL = 'https?://(?:www\\.)?ehftv\\.com/[a-z]+(?:-[a-z]+)?/[^/]+/(?P<id>[^/?#&]+)'


class ITTFIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.laola1tv'
    IE_NAME = 'ITTF'
    _VALID_URL = 'https?://tv\\.ittf\\.com/video/[^/]+/(?P<id>\\d+)'


class LastFMIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.lastfm'
    IE_NAME = 'LastFM'
    _VALID_URL = 'https?://(?:www\\.)?last\\.fm/music(?:/[^/]+){2}/(?P<id>[^/#?]+)'


class LastFMPlaylistBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.lastfm'
    IE_NAME = 'LastFMPlaylistBase'


class LastFMPlaylistIE(LastFMPlaylistBaseIE):
    _module = 'yt_dlp.extractor.lastfm'
    IE_NAME = 'LastFMPlaylist'
    _VALID_URL = 'https?://(?:www\\.)?last\\.fm/(music|tag)/(?P<id>[^/]+)(?:/[^/]+)?/?(?:[?#]|$)'


class LastFMUserIE(LastFMPlaylistBaseIE):
    _module = 'yt_dlp.extractor.lastfm'
    IE_NAME = 'LastFMUser'
    _VALID_URL = 'https?://(?:www\\.)?last\\.fm/user/[^/]+/playlists/(?P<id>[^/#?]+)'


class LBRYBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.lbry'
    IE_NAME = 'LBRYBase'


class LBRYIE(LBRYBaseIE):
    _module = 'yt_dlp.extractor.lbry'
    IE_NAME = 'lbry'
    _VALID_URL = '(?:https?://(?:www\\.)?(?:lbry\\.tv|odysee\\.com)/|lbry://)(?P<id>\\$/[^/]+/[^/]+/[0-9a-f]{1,40}|@[^:/?#&]+(?:[:#][0-9a-f]{1,40})?/[^:/?#&]+(?:[:#][0-9a-f]{1,40})?|(?!@)[^:/?#&]+(?:[:#][0-9a-f]{1,40})?)'


class LBRYChannelIE(LBRYBaseIE):
    _module = 'yt_dlp.extractor.lbry'
    IE_NAME = 'lbry:channel'
    _VALID_URL = '(?:https?://(?:www\\.)?(?:lbry\\.tv|odysee\\.com)/|lbry://)(?P<id>@[^:/?#&]+(?:[:#][0-9a-f]{1,40})?)/?(?:[?&]|$)'


class LCIIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.lci'
    IE_NAME = 'LCI'
    _VALID_URL = 'https?://(?:www\\.)?(?:lci|tf1info)\\.fr/[^/]+/[\\w-]+-(?P<id>\\d+)\\.html'


class LcpPlayIE(ArkenaIE):
    _module = 'yt_dlp.extractor.lcp'
    IE_NAME = 'LcpPlay'
    _VALID_URL = 'https?://play\\.lcp\\.fr/embed/(?P<id>[^/]+)/(?P<account_id>[^/]+)/[^/]+/[^/]+'


class LcpIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.lcp'
    IE_NAME = 'Lcp'
    _VALID_URL = 'https?://(?:www\\.)?lcp\\.fr/(?:[^/]+/)*(?P<id>[^/]+)'


class Lecture2GoIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.lecture2go'
    IE_NAME = 'Lecture2Go'
    _VALID_URL = 'https?://lecture2go\\.uni-hamburg\\.de/veranstaltungen/-/v/(?P<id>\\d+)'


class LecturioBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.lecturio'
    IE_NAME = 'LecturioBase'
    _NETRC_MACHINE = 'lecturio'


class LecturioIE(LecturioBaseIE):
    _module = 'yt_dlp.extractor.lecturio'
    IE_NAME = 'Lecturio'
    _VALID_URL = '(?x)\n                    https://\n                        (?:\n                            app\\.lecturio\\.com/([^/]+/(?P<nt>[^/?#&]+)\\.lecture|(?:\\#/)?lecture/c/\\d+/(?P<id>\\d+))|\n                            (?:www\\.)?lecturio\\.de/[^/]+/(?P<nt_de>[^/?#&]+)\\.vortrag\n                        )\n                    '
    _NETRC_MACHINE = 'lecturio'


class LecturioCourseIE(LecturioBaseIE):
    _module = 'yt_dlp.extractor.lecturio'
    IE_NAME = 'LecturioCourse'
    _VALID_URL = 'https://app\\.lecturio\\.com/(?:[^/]+/(?P<nt>[^/?#&]+)\\.course|(?:#/)?course/c/(?P<id>\\d+))'
    _NETRC_MACHINE = 'lecturio'


class LecturioDeCourseIE(LecturioBaseIE):
    _module = 'yt_dlp.extractor.lecturio'
    IE_NAME = 'LecturioDeCourse'
    _VALID_URL = 'https://(?:www\\.)?lecturio\\.de/[^/]+/(?P<id>[^/?#&]+)\\.kurs'
    _NETRC_MACHINE = 'lecturio'


class LeIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.leeco'
    IE_NAME = 'Le'
    IE_DESC = '乐视网'
    _VALID_URL = 'https?://(?:www\\.le\\.com/ptv/vplay|(?:sports\\.le|(?:www\\.)?lesports)\\.com/(?:match|video))/(?P<id>\\d+)\\.html'


class LePlaylistIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.leeco'
    IE_NAME = 'LePlaylist'
    _VALID_URL = 'https?://[a-z]+\\.le\\.com/(?!video)[a-z]+/(?P<id>[a-z0-9_]+)'

    @classmethod
    def suitable(cls, url):
        return False if LeIE.suitable(url) else super(LePlaylistIE, cls).suitable(url)


class LetvCloudIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.leeco'
    IE_NAME = 'LetvCloud'
    IE_DESC = '乐视云'
    _VALID_URL = 'https?://yuntv\\.letv\\.com/bcloud.html\\?.+'


class LEGOIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.lego'
    IE_NAME = 'LEGO'
    _VALID_URL = 'https?://(?:www\\.)?lego\\.com/(?P<locale>[a-z]{2}-[a-z]{2})/(?:[^/]+/)*videos/(?:[^/]+/)*[^/?#]+-(?P<id>[0-9a-f]{32})'
    age_limit = 5


class LemondeIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.lemonde'
    IE_NAME = 'Lemonde'
    _VALID_URL = 'https?://(?:.+?\\.)?lemonde\\.fr/(?:[^/]+/)*(?P<id>[^/]+)\\.html'


class LentaIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.lenta'
    IE_NAME = 'Lenta'
    _VALID_URL = 'https?://(?:www\\.)?lenta\\.ru/[^/]+/\\d+/\\d+/\\d+/(?P<id>[^/?#&]+)'


class LibraryOfCongressIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.libraryofcongress'
    IE_NAME = 'loc'
    IE_DESC = 'Library of Congress'
    _VALID_URL = 'https?://(?:www\\.)?loc\\.gov/(?:item/|today/cyberlc/feature_wdesc\\.php\\?.*\\brec=)(?P<id>[0-9a-z_.]+)'


class LibsynIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.libsyn'
    IE_NAME = 'Libsyn'
    _VALID_URL = '(?P<mainurl>https?://html5-player\\.libsyn\\.com/embed/episode/id/(?P<id>[0-9]+))'


class LifeNewsIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.lifenews'
    IE_NAME = 'life'
    IE_DESC = 'Life.ru'
    _VALID_URL = 'https?://life\\.ru/t/[^/]+/(?P<id>\\d+)'


class LifeEmbedIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.lifenews'
    IE_NAME = 'life:embed'
    _VALID_URL = 'https?://embed\\.life\\.ru/(?:embed|video)/(?P<id>[\\da-f]{32})'


class LikeeIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.likee'
    IE_NAME = 'likee'
    _VALID_URL = '(?x)https?://(www\\.)?likee\\.video/(?:(?P<channel_name>[^/]+)/video/|v/)(?P<id>\\w+)'


class LikeeUserIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.likee'
    IE_NAME = 'likee:user'
    _VALID_URL = 'https?://(www\\.)?likee\\.video/(?P<id>[^/]+)/?$'


class LimelightBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.limelight'
    IE_NAME = 'LimelightBase'


class LimelightMediaIE(LimelightBaseIE):
    _module = 'yt_dlp.extractor.limelight'
    IE_NAME = 'limelight'
    _VALID_URL = '(?x)\n                        (?:\n                            limelight:media:|\n                            https?://\n                                (?:\n                                    link\\.videoplatform\\.limelight\\.com/media/|\n                                    assets\\.delvenetworks\\.com/player/loader\\.swf\n                                )\n                                \\?.*?\\bmediaId=\n                        )\n                        (?P<id>[a-z0-9]{32})\n                    '


class LimelightChannelIE(LimelightBaseIE):
    _module = 'yt_dlp.extractor.limelight'
    IE_NAME = 'limelight:channel'
    _VALID_URL = '(?x)\n                        (?:\n                            limelight:channel:|\n                            https?://\n                                (?:\n                                    link\\.videoplatform\\.limelight\\.com/media/|\n                                    assets\\.delvenetworks\\.com/player/loader\\.swf\n                                )\n                                \\?.*?\\bchannelId=\n                        )\n                        (?P<id>[a-z0-9]{32})\n                    '


class LimelightChannelListIE(LimelightBaseIE):
    _module = 'yt_dlp.extractor.limelight'
    IE_NAME = 'limelight:channel_list'
    _VALID_URL = '(?x)\n                        (?:\n                            limelight:channel_list:|\n                            https?://\n                                (?:\n                                    link\\.videoplatform\\.limelight\\.com/media/|\n                                    assets\\.delvenetworks\\.com/player/loader\\.swf\n                                )\n                                \\?.*?\\bchannelListId=\n                        )\n                        (?P<id>[a-z0-9]{32})\n                    '


class LineLiveBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.line'
    IE_NAME = 'LineLiveBase'


class LineLiveIE(LineLiveBaseIE):
    _module = 'yt_dlp.extractor.line'
    IE_NAME = 'LineLive'
    _VALID_URL = 'https?://live\\.line\\.me/channels/(?P<channel_id>\\d+)/broadcast/(?P<id>\\d+)'


class LineLiveChannelIE(LineLiveBaseIE):
    _module = 'yt_dlp.extractor.line'
    IE_NAME = 'LineLiveChannel'
    _VALID_URL = 'https?://live\\.line\\.me/channels/(?P<id>\\d+)(?!/broadcast/\\d+)(?:[/?&#]|$)'


class LinkedInBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.linkedin'
    IE_NAME = 'LinkedInBase'
    _NETRC_MACHINE = 'linkedin'


class LinkedInIE(LinkedInBaseIE):
    _module = 'yt_dlp.extractor.linkedin'
    IE_NAME = 'LinkedIn'
    _VALID_URL = 'https?://(?:www\\.)?linkedin\\.com/posts/.+?(?P<id>\\d+)'
    _NETRC_MACHINE = 'linkedin'


class LinkedInLearningBaseIE(LinkedInBaseIE):
    _module = 'yt_dlp.extractor.linkedin'
    IE_NAME = 'LinkedInLearningBase'
    _NETRC_MACHINE = 'linkedin'


class LinkedInLearningIE(LinkedInLearningBaseIE):
    _module = 'yt_dlp.extractor.linkedin'
    IE_NAME = 'linkedin:learning'
    _VALID_URL = 'https?://(?:www\\.)?linkedin\\.com/learning/(?P<course_slug>[^/]+)/(?P<id>[^/?#]+)'
    _NETRC_MACHINE = 'linkedin'


class LinkedInLearningCourseIE(LinkedInLearningBaseIE):
    _module = 'yt_dlp.extractor.linkedin'
    IE_NAME = 'linkedin:learning:course'
    _VALID_URL = 'https?://(?:www\\.)?linkedin\\.com/learning/(?P<id>[^/?#]+)'
    _NETRC_MACHINE = 'linkedin'

    @classmethod
    def suitable(cls, url):
        return False if LinkedInLearningIE.suitable(url) else super(LinkedInLearningCourseIE, cls).suitable(url)


class LinuxAcademyIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.linuxacademy'
    IE_NAME = 'LinuxAcademy'
    _VALID_URL = '(?x)\n                    https?://\n                        (?:www\\.)?linuxacademy\\.com/cp/\n                        (?:\n                            courses/lesson/course/(?P<chapter_id>\\d+)/lesson/(?P<lesson_id>\\d+)|\n                            modules/view/id/(?P<course_id>\\d+)\n                        )\n                    '
    _NETRC_MACHINE = 'linuxacademy'


class Liputan6IE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.liputan6'
    IE_NAME = 'Liputan6'
    _VALID_URL = 'https?://www\\.liputan6\\.com/\\w+/read/\\d+/(?P<id>[\\w-]+)'


class ListenNotesIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.listennotes'
    IE_NAME = 'ListenNotes'
    _VALID_URL = 'https?://(?:www\\.)?listennotes\\.com/podcasts/[^/]+/[^/]+-(?P<id>.+)/'


class LiTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.litv'
    IE_NAME = 'LiTV'
    _VALID_URL = 'https?://(?:www\\.)?litv\\.tv/(?:vod|promo)/[^/]+/(?:content\\.do)?\\?.*?\\b(?:content_)?id=(?P<id>[^&]+)'


class LiveJournalIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.livejournal'
    IE_NAME = 'LiveJournal'
    _VALID_URL = 'https?://(?:[^.]+\\.)?livejournal\\.com/video/album/\\d+.+?\\bid=(?P<id>\\d+)'


class LivestreamIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.livestream'
    IE_NAME = 'livestream'
    _VALID_URL = 'https?://(?:new\\.)?livestream\\.com/(?:accounts/(?P<account_id>\\d+)|(?P<account_name>[^/]+))/(?:events/(?P<event_id>\\d+)|(?P<event_name>[^/]+))(?:/videos/(?P<id>\\d+))?'


class LivestreamOriginalIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.livestream'
    IE_NAME = 'livestream:original'
    _VALID_URL = '(?x)https?://original\\.livestream\\.com/\n        (?P<user>[^/\\?#]+)(?:/(?P<type>video|folder)\n        (?:(?:\\?.*?Id=|/)(?P<id>.*?)(&|$))?)?\n        '


class LivestreamShortenerIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.livestream'
    IE_NAME = 'livestream:shortener'
    IE_DESC = False
    _VALID_URL = 'https?://livestre\\.am/(?P<id>.+)'


class LivestreamfailsIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.livestreamfails'
    IE_NAME = 'Livestreamfails'
    _VALID_URL = 'https?://(?:www\\.)?livestreamfails\\.com/(?:clip|post)/(?P<id>[0-9]+)'


class LnkGoIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.lnkgo'
    IE_NAME = 'LnkGo'
    _VALID_URL = 'https?://(?:www\\.)?lnk(?:go)?\\.(?:alfa\\.)?lt/(?:visi-video/[^/]+|video)/(?P<id>[A-Za-z0-9-]+)(?:/(?P<episode_id>\\d+))?'
    age_limit = 18


class LnkIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.lnkgo'
    IE_NAME = 'Lnk'
    _VALID_URL = 'https?://(?:www\\.)?lnk\\.lt/[^/]+/(?P<id>\\d+)'


class LocalNews8IE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.localnews8'
    IE_NAME = 'LocalNews8'
    _VALID_URL = 'https?://(?:www\\.)?localnews8\\.com/(?:[^/]+/)*(?P<display_id>[^/]+)/(?P<id>[0-9]+)'


class NuevoBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.nuevo'
    IE_NAME = 'NuevoBase'


class LoveHomePornIE(NuevoBaseIE):
    _module = 'yt_dlp.extractor.lovehomeporn'
    IE_NAME = 'LoveHomePorn'
    _VALID_URL = 'https?://(?:www\\.)?lovehomeporn\\.com/video/(?P<id>\\d+)(?:/(?P<display_id>[^/?#&]+))?'
    age_limit = 18


class LRTBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.lrt'
    IE_NAME = 'LRTBase'


class LRTVODIE(LRTBaseIE):
    _module = 'yt_dlp.extractor.lrt'
    IE_NAME = 'LRTVOD'
    _VALID_URL = 'https?://(?:www\\.)?lrt\\.lt(?P<path>/mediateka/irasas/(?P<id>[0-9]+))'


class LRTStreamIE(LRTBaseIE):
    _module = 'yt_dlp.extractor.lrt'
    IE_NAME = 'LRTStream'
    _VALID_URL = 'https?://(?:www\\.)?lrt\\.lt/mediateka/tiesiogiai/(?P<id>[\\w-]+)'


class LyndaBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.lynda'
    IE_NAME = 'LyndaBase'
    _NETRC_MACHINE = 'lynda'


class LyndaIE(LyndaBaseIE):
    _module = 'yt_dlp.extractor.lynda'
    IE_NAME = 'lynda'
    IE_DESC = 'lynda.com videos'
    _VALID_URL = '(?x)\n                    https?://\n                        (?:www\\.)?(?:lynda\\.com|educourse\\.ga)/\n                        (?:\n                            (?:[^/]+/){2,3}(?P<course_id>\\d+)|\n                            player/embed\n                        )/\n                        (?P<id>\\d+)\n                    '
    _NETRC_MACHINE = 'lynda'


class LyndaCourseIE(LyndaBaseIE):
    _module = 'yt_dlp.extractor.lynda'
    IE_NAME = 'lynda:course'
    IE_DESC = 'lynda.com online courses'
    _VALID_URL = 'https?://(?:www|m)\\.(?:lynda\\.com|educourse\\.ga)/(?P<coursepath>(?:[^/]+/){2,3}(?P<courseid>\\d+))-2\\.html'
    _NETRC_MACHINE = 'lynda'


class M6IE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.m6'
    IE_NAME = 'm6'
    _VALID_URL = 'https?://(?:www\\.)?m6\\.fr/[^/]+/videos/(?P<id>\\d+)-[^\\.]+\\.html'


class MagentaMusik360IE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.magentamusik360'
    IE_NAME = 'MagentaMusik360'
    _VALID_URL = 'https?://(?:www\\.)?magenta-musik-360\\.de/([a-z0-9-]+-(?P<id>[0-9]+)|festivals/.+)'


class MailRuIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.mailru'
    IE_NAME = 'mailru'
    IE_DESC = 'Видео@Mail.Ru'
    _VALID_URL = '(?x)\n                    https?://\n                        (?:(?:www|m|videoapi)\\.)?my\\.mail\\.ru/+\n                        (?:\n                            video/.*\\#video=/?(?P<idv1>(?:[^/]+/){3}\\d+)|\n                            (?:videos/embed/)?(?:(?P<idv2prefix>(?:[^/]+/+){2})(?:video/(?:embed/)?)?(?P<idv2suffix>[^/]+/\\d+))(?:\\.html)?|\n                            (?:video/embed|\\+/video/meta)/(?P<metaid>\\d+)\n                        )\n                    '


class MailRuMusicSearchBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.mailru'
    IE_NAME = 'MailRuMusicSearchBase'


class MailRuMusicIE(MailRuMusicSearchBaseIE):
    _module = 'yt_dlp.extractor.mailru'
    IE_NAME = 'mailru:music'
    IE_DESC = 'Музыка@Mail.Ru'
    _VALID_URL = 'https?://my\\.mail\\.ru/+music/+songs/+[^/?#&]+-(?P<id>[\\da-f]+)'


class MailRuMusicSearchIE(MailRuMusicSearchBaseIE):
    _module = 'yt_dlp.extractor.mailru'
    IE_NAME = 'mailru:music:search'
    IE_DESC = 'Музыка@Mail.Ru'
    _VALID_URL = 'https?://my\\.mail\\.ru/+music/+search/+(?P<id>[^/?#&]+)'


class MainStreamingIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.mainstreaming'
    IE_NAME = 'MainStreaming'
    IE_DESC = 'MainStreaming Player'
    _VALID_URL = 'https?://(?:webtools-?)?(?P<host>[A-Za-z0-9-]*\\.msvdn.net)/(?:embed|amp_embed|content)/(?P<id>\\w+)'


class MallTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.malltv'
    IE_NAME = 'MallTV'
    _VALID_URL = 'https?://(?:(?:www|sk)\\.)?mall\\.tv/(?:[^/]+/)*(?P<id>[^/?#&]+)'


class MangomoloBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.mangomolo'
    IE_NAME = 'MangomoloBase'
    _VALID_URL = '(?:https?:)?//(?:admin\\.mangomolo\\.com/analytics/index\\.php/customers/embed/|player\\.mangomolo\\.com/v1/)None'


class MangomoloVideoIE(MangomoloBaseIE):
    _module = 'yt_dlp.extractor.mangomolo'
    IE_NAME = 'mangomolo:video'
    _VALID_URL = '(?:https?:)?//(?:admin\\.mangomolo\\.com/analytics/index\\.php/customers/embed/|player\\.mangomolo\\.com/v1/)video\\?.*?\\bid=(?P<id>\\d+)'


class MangomoloLiveIE(MangomoloBaseIE):
    _module = 'yt_dlp.extractor.mangomolo'
    IE_NAME = 'mangomolo:live'
    _VALID_URL = '(?:https?:)?//(?:admin\\.mangomolo\\.com/analytics/index\\.php/customers/embed/|player\\.mangomolo\\.com/v1/)(?:live|index)\\?.*?\\bchannelid=(?P<id>(?:[A-Za-z0-9+/=]|%2B|%2F|%3D)+)'


class ManotoTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.manoto'
    IE_NAME = 'ManotoTV'
    IE_DESC = 'Manoto TV (Episode)'
    _VALID_URL = 'https?://(?:www\\.)?manototv\\.com/episode/(?P<id>[0-9]+)'


class ManotoTVShowIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.manoto'
    IE_NAME = 'ManotoTVShow'
    IE_DESC = 'Manoto TV (Show)'
    _VALID_URL = 'https?://(?:www\\.)?manototv\\.com/show/(?P<id>[0-9]+)'


class ManotoTVLiveIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.manoto'
    IE_NAME = 'ManotoTVLive'
    IE_DESC = 'Manoto TV (Live)'
    _VALID_URL = 'https?://(?:www\\.)?manototv\\.com/live/'


class ManyVidsIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.manyvids'
    IE_NAME = 'ManyVids'
    _VALID_URL = '(?i)https?://(?:www\\.)?manyvids\\.com/video/(?P<id>\\d+)'


class MaoriTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.maoritv'
    IE_NAME = 'MaoriTV'
    _VALID_URL = 'https?://(?:www\\.)?maoritelevision\\.com/shows/(?:[^/]+/)+(?P<id>[^/?&#]+)'


class MarkizaIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.markiza'
    IE_NAME = 'Markiza'
    _VALID_URL = 'https?://(?:www\\.)?videoarchiv\\.markiza\\.sk/(?:video/(?:[^/]+/)*|embed/)(?P<id>\\d+)(?:[_/]|$)'


class MarkizaPageIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.markiza'
    IE_NAME = 'MarkizaPage'
    _VALID_URL = 'https?://(?:www\\.)?(?:(?:[^/]+\\.)?markiza|tvnoviny)\\.sk/(?:[^/]+/)*(?P<id>\\d+)_'

    @classmethod
    def suitable(cls, url):
        return False if MarkizaIE.suitable(url) else super(MarkizaPageIE, cls).suitable(url)


class MassengeschmackTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.massengeschmacktv'
    IE_NAME = 'massengeschmack.tv'
    _VALID_URL = 'https?://(?:www\\.)?massengeschmack\\.tv/play/(?P<id>[^?&#]+)'


class MastersIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.masters'
    IE_NAME = 'Masters'
    _VALID_URL = 'https?://(?:www\\.)?masters\\.com/en_US/watch/(?P<date>\\d{4}-\\d{2}-\\d{2})/(?P<id>\\d+)'


class MatchTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.matchtv'
    IE_NAME = 'MatchTV'
    _VALID_URL = 'https?://matchtv\\.ru(?:/on-air|/?#live-player)'


class MDRIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.mdr'
    IE_NAME = 'MDR'
    IE_DESC = 'MDR.DE and KiKA'
    _VALID_URL = 'https?://(?:www\\.)?(?:mdr|kika)\\.de/(?:.*)/[a-z-]+-?(?P<id>\\d+)(?:_.+?)?\\.html'


class MedalTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.medaltv'
    IE_NAME = 'MedalTV'
    _VALID_URL = 'https?://(?:www\\.)?medal\\.tv/(?P<path>games/[^/?#&]+/clips)/(?P<id>[^/?#&]+)'


class MediaiteIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.mediaite'
    IE_NAME = 'Mediaite'
    _VALID_URL = 'https?://(?:www\\.)?mediaite.com(?!/category)(?:/[\\w-]+){2}'


class MediaKlikkIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.mediaklikk'
    IE_NAME = 'MediaKlikk'
    _VALID_URL = '(?x)https?://(?:www\\.)?\n                        (?:mediaklikk|m4sport|hirado|petofilive)\\.hu/.*?(?:videok?|cikk)/\n                        (?:(?P<year>[0-9]{4})/(?P<month>[0-9]{1,2})/(?P<day>[0-9]{1,2})/)?\n                        (?P<id>[^/#?_]+)'


class ThePlatformBaseIE(OnceIE):
    _module = 'yt_dlp.extractor.theplatform'
    IE_NAME = 'ThePlatformBase'
    _VALID_URL = 'https?://.+?\\.unicornmedia\\.com/now/(?:ads/vmap/)?[^/]+/[^/]+/(?P<domain_id>[^/]+)/(?P<application_id>[^/]+)/(?:[^/]+/)?(?P<media_item_id>[^/]+)/content\\.(?:once|m3u8|mp4)'


class MediasetIE(ThePlatformBaseIE):
    _module = 'yt_dlp.extractor.mediaset'
    IE_NAME = 'Mediaset'
    _VALID_URL = '(?x)\n                    (?:\n                        mediaset:|\n                        https?://\n                            (?:\\w+\\.)+mediaset\\.it/\n                            (?:\n                                (?:video|on-demand|movie)/(?:[^/]+/)+[^/]+_|\n                                player/(?:v\\d+/)?index\\.html\\?.*?\\bprogramGuid=\n                            )\n                    )(?P<id>[0-9A-Z]{16,})\n                    '


class MediasetShowIE(MediasetIE):
    _module = 'yt_dlp.extractor.mediaset'
    IE_NAME = 'MediasetShow'
    _VALID_URL = '(?x)\n                    (?:\n                        https?://\n                            (\\w+\\.)+mediaset\\.it/\n                            (?:\n                                (?:fiction|programmi-tv|serie-tv|kids)/(?:.+?/)?\n                                    (?:[a-z-]+)_SE(?P<id>\\d{12})\n                                    (?:,ST(?P<st>\\d{12}))?\n                                    (?:,sb(?P<sb>\\d{9}))?$\n                            )\n                    )\n                    '


class MediasiteIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.mediasite'
    IE_NAME = 'Mediasite'
    _VALID_URL = '(?xi)https?://[^/]+/Mediasite/(?:Play|Showcase/[^/#?]+/Presentation)/(?P<id>(?:[0-9a-f]{32,34}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12,14}))(?P<query>\\?[^#]+|)'


class MediasiteCatalogIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.mediasite'
    IE_NAME = 'MediasiteCatalog'
    _VALID_URL = '(?xi)\n                        (?P<url>https?://[^/]+/Mediasite)\n                        /Catalog/Full/\n                        (?P<catalog_id>(?:[0-9a-f]{32,34}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12,14}))\n                        (?:\n                            /(?P<current_folder_id>(?:[0-9a-f]{32,34}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12,14}))\n                            /(?P<root_dynamic_folder_id>(?:[0-9a-f]{32,34}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12,14}))\n                        )?\n                    '


class MediasiteNamedCatalogIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.mediasite'
    IE_NAME = 'MediasiteNamedCatalog'
    _VALID_URL = '(?xi)(?P<url>https?://[^/]+/Mediasite)/Catalog/catalogs/(?P<catalog_name>[^/?#&]+)'


class MediaWorksNZVODIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.mediaworksnz'
    IE_NAME = 'MediaWorksNZVOD'
    _VALID_URL = 'https?://vodupload-api\\.mediaworks\\.nz/library/asset/published/(?P<id>[A-Za-z0-9-]+)'


class MediciIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.medici'
    IE_NAME = 'Medici'
    _VALID_URL = 'https?://(?:www\\.)?medici\\.tv/#!/(?P<id>[^?#&]+)'


class MegaphoneIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.megaphone'
    IE_NAME = 'megaphone.fm'
    IE_DESC = 'megaphone.fm embedded players'
    _VALID_URL = 'https://player\\.megaphone\\.fm/(?P<id>[A-Z0-9]+)'


class MeipaiIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.meipai'
    IE_NAME = 'Meipai'
    IE_DESC = '美拍'
    _VALID_URL = 'https?://(?:www\\.)?meipai\\.com/media/(?P<id>[0-9]+)'


class MelonVODIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.melonvod'
    IE_NAME = 'MelonVOD'
    _VALID_URL = 'https?://vod\\.melon\\.com/video/detail2\\.html?\\?.*?mvId=(?P<id>[0-9]+)'


class METAIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.meta'
    IE_NAME = 'META'
    _VALID_URL = 'https?://video\\.meta\\.ua/(?:iframe/)?(?P<id>[0-9]+)'


class MetacafeIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.metacafe'
    IE_NAME = 'metacafe'
    _VALID_URL = 'https?://(?:www\\.)?metacafe\\.com/watch/(?P<id>[^/]+)/(?P<display_id>[^/?#]+)'
    age_limit = 18


class MetacriticIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.metacritic'
    IE_NAME = 'Metacritic'
    _VALID_URL = 'https?://(?:www\\.)?metacritic\\.com/.+?/trailers/(?P<id>\\d+)'


class MgoonIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.mgoon'
    IE_NAME = 'Mgoon'
    _VALID_URL = '(?x)https?://(?:www\\.)?\n    (?:(:?m\\.)?mgoon\\.com/(?:ch/(?:.+)/v|play/view)|\n        video\\.mgoon\\.com)/(?P<id>[0-9]+)'


class MGTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.mgtv'
    IE_NAME = 'MangoTV'
    IE_DESC = '芒果TV'
    _VALID_URL = 'https?://(?:w(?:ww)?\\.)?mgtv\\.com/(v|b)/(?:[^/]+/)*(?P<id>\\d+)\\.html'


class MiaoPaiIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.miaopai'
    IE_NAME = 'MiaoPai'
    _VALID_URL = 'https?://(?:www\\.)?miaopai\\.com/show/(?P<id>[-A-Za-z0-9~_]+)'


class MicrosoftStreamIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.microsoftstream'
    IE_NAME = 'microsoftstream'
    IE_DESC = 'Microsoft Stream'
    _VALID_URL = 'https?://(?:web|www|msit)\\.microsoftstream\\.com/video/(?P<id>[\\da-f]{8}-[\\da-f]{4}-[\\da-f]{4}-[\\da-f]{4}-[\\da-f]{12})'


class MicrosoftVirtualAcademyBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.microsoftvirtualacademy'
    IE_NAME = 'MicrosoftVirtualAcademyBase'


class MicrosoftVirtualAcademyIE(MicrosoftVirtualAcademyBaseIE):
    _module = 'yt_dlp.extractor.microsoftvirtualacademy'
    IE_NAME = 'mva'
    IE_DESC = 'Microsoft Virtual Academy videos'
    _VALID_URL = '(?:mva:|https?://(?:mva\\.microsoft|(?:www\\.)?microsoftvirtualacademy)\\.com/[^/]+/training-courses/[^/?#&]+-)(?P<course_id>\\d+)(?::|\\?l=)(?P<id>[\\da-zA-Z]+_\\d+)'


class MicrosoftVirtualAcademyCourseIE(MicrosoftVirtualAcademyBaseIE):
    _module = 'yt_dlp.extractor.microsoftvirtualacademy'
    IE_NAME = 'mva:course'
    IE_DESC = 'Microsoft Virtual Academy courses'
    _VALID_URL = '(?:mva:course:|https?://(?:mva\\.microsoft|(?:www\\.)?microsoftvirtualacademy)\\.com/[^/]+/training-courses/(?P<display_id>[^/?#&]+)-)(?P<id>\\d+)'

    @classmethod
    def suitable(cls, url):
        return False if MicrosoftVirtualAcademyIE.suitable(url) else super(
            MicrosoftVirtualAcademyCourseIE, cls).suitable(url)


class MicrosoftEmbedIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.microsoftembed'
    IE_NAME = 'MicrosoftEmbed'
    _VALID_URL = 'https?://(?:www\\.)?microsoft\\.com/(?:[^/]+/)?videoplayer/embed/(?P<id>[a-z0-9A-Z]+)'


class MildomBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.mildom'
    IE_NAME = 'MildomBase'


class MildomIE(MildomBaseIE):
    _module = 'yt_dlp.extractor.mildom'
    IE_NAME = 'mildom'
    IE_DESC = 'Record ongoing live by specific user in Mildom'
    _VALID_URL = 'https?://(?:(?:www|m)\\.)mildom\\.com/(?P<id>\\d+)'


class MildomVodIE(MildomBaseIE):
    _module = 'yt_dlp.extractor.mildom'
    IE_NAME = 'mildom:vod'
    IE_DESC = 'VOD in Mildom'
    _VALID_URL = 'https?://(?:(?:www|m)\\.)mildom\\.com/playback/(?P<user_id>\\d+)/(?P<id>(?P=user_id)-[a-zA-Z0-9]+-?[0-9]*)'


class MildomClipIE(MildomBaseIE):
    _module = 'yt_dlp.extractor.mildom'
    IE_NAME = 'mildom:clip'
    IE_DESC = 'Clip in Mildom'
    _VALID_URL = 'https?://(?:(?:www|m)\\.)mildom\\.com/clip/(?P<id>(?P<user_id>\\d+)-[a-zA-Z0-9]+)'


class MildomUserVodIE(MildomBaseIE):
    _module = 'yt_dlp.extractor.mildom'
    IE_NAME = 'mildom:user:vod'
    IE_DESC = 'Download all VODs from specific user in Mildom'
    _VALID_URL = 'https?://(?:(?:www|m)\\.)mildom\\.com/profile/(?P<id>\\d+)'


class MindsBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.minds'
    IE_NAME = 'MindsBase'


class MindsIE(MindsBaseIE):
    _module = 'yt_dlp.extractor.minds'
    IE_NAME = 'minds'
    _VALID_URL = 'https?://(?:www\\.)?minds\\.com/(?:media|newsfeed|archive/view)/(?P<id>[0-9]+)'


class MindsFeedBaseIE(MindsBaseIE):
    _module = 'yt_dlp.extractor.minds'
    IE_NAME = 'MindsFeedBase'


class MindsChannelIE(MindsFeedBaseIE):
    _module = 'yt_dlp.extractor.minds'
    IE_NAME = 'minds:channel'
    _VALID_URL = 'https?://(?:www\\.)?minds\\.com/(?!(?:newsfeed|media|api|archive|groups)/)(?P<id>[^/?&#]+)'


class MindsGroupIE(MindsFeedBaseIE):
    _module = 'yt_dlp.extractor.minds'
    IE_NAME = 'minds:group'
    _VALID_URL = 'https?://(?:www\\.)?minds\\.com/groups/profile/(?P<id>[0-9]+)'


class MinistryGridIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ministrygrid'
    IE_NAME = 'MinistryGrid'
    _VALID_URL = 'https?://(?:www\\.)?ministrygrid\\.com/([^/?#]*/)*(?P<id>[^/#?]+)/?(?:$|[?#])'


class MinotoIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.minoto'
    IE_NAME = 'Minoto'
    _VALID_URL = '(?:minoto:|https?://(?:play|iframe|embed)\\.minoto-video\\.com/(?P<player_id>[0-9]+)/)(?P<id>[a-zA-Z0-9]+)'


class MioMioIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.miomio'
    IE_NAME = 'miomio.tv'
    _VALID_URL = 'https?://(?:www\\.)?miomio\\.tv/watch/cc(?P<id>[0-9]+)'


class MirrativBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.mirrativ'
    IE_NAME = 'MirrativBase'


class MirrativIE(MirrativBaseIE):
    _module = 'yt_dlp.extractor.mirrativ'
    IE_NAME = 'mirrativ'
    _VALID_URL = 'https?://(?:www\\.)?mirrativ\\.com/live/(?P<id>[^/?#&]+)'


class MirrativUserIE(MirrativBaseIE):
    _module = 'yt_dlp.extractor.mirrativ'
    IE_NAME = 'mirrativ:user'
    _VALID_URL = 'https?://(?:www\\.)?mirrativ\\.com/user/(?P<id>\\d+)'


class MirrorCoUKIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.mirrorcouk'
    IE_NAME = 'MirrorCoUK'
    _VALID_URL = 'https?://(?:www\\.)?mirror\\.co\\.uk/[/+[\\w-]+-(?P<id>\\d+)'


class TechTVMITIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.mit'
    IE_NAME = 'techtv.mit.edu'
    _VALID_URL = 'https?://techtv\\.mit\\.edu/(?:videos|embeds)/(?P<id>\\d+)'


class OCWMITIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.mit'
    IE_NAME = 'ocw.mit.edu'
    _VALID_URL = '^https?://ocw\\.mit\\.edu/courses/(?P<topic>[a-z0-9\\-]+)'


class MixchIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.mixch'
    IE_NAME = 'mixch'
    _VALID_URL = 'https?://(?:www\\.)?mixch\\.tv/u/(?P<id>\\d+)'


class MixchArchiveIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.mixch'
    IE_NAME = 'mixch:archive'
    _VALID_URL = 'https?://(?:www\\.)?mixch\\.tv/archive/(?P<id>\\d+)'


class MixcloudBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.mixcloud'
    IE_NAME = 'MixcloudBase'


class MixcloudIE(MixcloudBaseIE):
    _module = 'yt_dlp.extractor.mixcloud'
    IE_NAME = 'mixcloud'
    _VALID_URL = 'https?://(?:(?:www|beta|m)\\.)?mixcloud\\.com/([^/]+)/(?!stream|uploads|favorites|listens|playlists)([^/]+)'


class MixcloudPlaylistBaseIE(MixcloudBaseIE):
    _module = 'yt_dlp.extractor.mixcloud'
    IE_NAME = 'MixcloudPlaylistBase'


class MixcloudUserIE(MixcloudPlaylistBaseIE):
    _module = 'yt_dlp.extractor.mixcloud'
    IE_NAME = 'mixcloud:user'
    _VALID_URL = 'https?://(?:www\\.)?mixcloud\\.com/(?P<id>[^/]+)/(?P<type>uploads|favorites|listens|stream)?/?$'


class MixcloudPlaylistIE(MixcloudPlaylistBaseIE):
    _module = 'yt_dlp.extractor.mixcloud'
    IE_NAME = 'mixcloud:playlist'
    _VALID_URL = 'https?://(?:www\\.)?mixcloud\\.com/(?P<user>[^/]+)/playlists/(?P<playlist>[^/]+)/?$'


class MLBBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.mlb'
    IE_NAME = 'MLBBase'


class MLBIE(MLBBaseIE):
    _module = 'yt_dlp.extractor.mlb'
    IE_NAME = 'MLB'
    _VALID_URL = '(?x)\n                    https?://\n                        (?:[\\da-z_-]+\\.)*mlb\\.com/\n                        (?:\n                            (?:\n                                (?:[^/]+/)*video/[^/]+/c-|\n                                (?:\n                                    shared/video/embed/(?:embed|m-internal-embed)\\.html|\n                                    (?:[^/]+/)+(?:play|index)\\.jsp|\n                                )\\?.*?\\bcontent_id=\n                            )\n                            (?P<id>\\d+)\n                        )\n                    '


class MLBVideoIE(MLBBaseIE):
    _module = 'yt_dlp.extractor.mlb'
    IE_NAME = 'MLBVideo'
    _VALID_URL = 'https?://(?:www\\.)?mlb\\.com/(?:[^/]+/)*video/(?P<id>[^/?&#]+)'

    @classmethod
    def suitable(cls, url):
        return False if MLBIE.suitable(url) else super(MLBVideoIE, cls).suitable(url)


class MLBTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.mlb'
    IE_NAME = 'MLBTV'
    _VALID_URL = 'https?://(?:www\\.)?mlb\\.com/tv/g(?P<id>\\d{6})'
    _NETRC_MACHINE = 'mlb'


class MLBArticleIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.mlb'
    IE_NAME = 'MLBArticle'
    _VALID_URL = 'https?://www\\.mlb\\.com/news/(?P<id>[\\w-]+)'


class MLSSoccerIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.mlssoccer'
    IE_NAME = 'MLSSoccer'
    _VALID_URL = 'https?://(?:www\\.)?(?:(?:cfmontreal|intermiamicf|lagalaxy|lafc|houstondynamofc|dcunited|atlutd|mlssoccer|fcdallas|columbuscrew|coloradorapids|fccincinnati|chicagofirefc|austinfc|nashvillesc|whitecapsfc|sportingkc|soundersfc|sjearthquakes|rsl|timbers|philadelphiaunion|orlandocitysc|newyorkredbulls|nycfc)\\.com|(?:torontofc)\\.ca|(?:revolutionsoccer)\\.net)/video/#?(?P<id>[^/&$#?]+)'


class MnetIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.mnet'
    IE_NAME = 'Mnet'
    _VALID_URL = 'https?://(?:www\\.)?mnet\\.(?:com|interest\\.me)/tv/vod/(?:.*?\\bclip_id=)?(?P<id>[0-9]+)'


class MochaVideoIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.mocha'
    IE_NAME = 'MochaVideo'
    _VALID_URL = 'https?://video.mocha.com.vn/(?P<video_slug>[\\w-]+)'


class MoeVideoIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.moevideo'
    IE_NAME = 'MoeVideo'
    IE_DESC = 'LetitBit video services: moevideo.net, playreplay.net and videochart.net'
    _VALID_URL = '(?x)\n        https?://(?P<host>(?:www\\.)?\n        (?:(?:moevideo|playreplay|videochart)\\.net|thesame\\.tv))/\n        (?:video|framevideo|embed)/(?P<id>[0-9a-z]+\\.[0-9A-Za-z]+)'


class MofosexIE(KeezMoviesIE):
    _module = 'yt_dlp.extractor.mofosex'
    IE_NAME = 'Mofosex'
    _VALID_URL = 'https?://(?:www\\.)?mofosex\\.com/videos/(?P<id>\\d+)/(?P<display_id>[^/?#&.]+)\\.html'
    age_limit = 18


class MofosexEmbedIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.mofosex'
    IE_NAME = 'MofosexEmbed'
    _VALID_URL = 'https?://(?:www\\.)?mofosex\\.com/embed/?\\?.*?\\bvideoid=(?P<id>\\d+)'


class MojvideoIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.mojvideo'
    IE_NAME = 'Mojvideo'
    _VALID_URL = 'https?://(?:www\\.)?mojvideo\\.com/video-(?P<display_id>[^/]+)/(?P<id>[a-f0-9]+)'


class MorningstarIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.morningstar'
    IE_NAME = 'Morningstar'
    IE_DESC = 'morningstar.com'
    _VALID_URL = 'https?://(?:(?:www|news)\\.)morningstar\\.com/[cC]over/video[cC]enter\\.aspx\\?id=(?P<id>[0-9]+)'


class MotherlessIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.motherless'
    IE_NAME = 'Motherless'
    _VALID_URL = 'https?://(?:www\\.)?motherless\\.com/(?:g/[a-z0-9_]+/)?(?P<id>[A-Z0-9]+)'
    age_limit = 18


class MotherlessGroupIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.motherless'
    IE_NAME = 'MotherlessGroup'
    _VALID_URL = 'https?://(?:www\\.)?motherless\\.com/gv?/(?P<id>[a-z0-9_]+)'

    @classmethod
    def suitable(cls, url):
        return (False if MotherlessIE.suitable(url)
                else super(MotherlessGroupIE, cls).suitable(url))


class MotorsportIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.motorsport'
    IE_NAME = 'Motorsport'
    IE_DESC = 'motorsport.com'
    _VALID_URL = 'https?://(?:www\\.)?motorsport\\.com/[^/?#]+/video/(?:[^/?#]+/)(?P<id>[^/]+)/?(?:$|[?#])'


class MovieClipsIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.movieclips'
    IE_NAME = 'MovieClips'
    _VALID_URL = 'https?://(?:www\\.)?movieclips\\.com/videos/.+-(?P<id>\\d+)(?:\\?|$)'


class MoviepilotIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.moviepilot'
    IE_NAME = 'Moviepilot'
    _VALID_URL = 'https?://(?:www\\.)?moviepilot\\.de/movies/(?P<id>[^/]+)'


class MoviewPlayIE(JixieBaseIE):
    _module = 'yt_dlp.extractor.moview'
    IE_NAME = 'MoviewPlay'
    _VALID_URL = 'https?://www\\.moview\\.id/play/\\d+/(?P<id>[\\w-]+)'


class MoviezineIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.moviezine'
    IE_NAME = 'Moviezine'
    _VALID_URL = 'https?://(?:www\\.)?moviezine\\.se/video/(?P<id>[^?#]+)'


class MovingImageIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.movingimage'
    IE_NAME = 'MovingImage'
    _VALID_URL = 'https?://movingimage\\.nls\\.uk/film/(?P<id>\\d+)'


class MSNIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.msn'
    IE_NAME = 'MSN'
    _VALID_URL = 'https?://(?:(?:www|preview)\\.)?msn\\.com/(?:[^/]+/)+(?P<display_id>[^/]+)/[a-z]{2}-(?P<id>[\\da-zA-Z]+)'


class MTVIE(MTVServicesInfoExtractor):
    _module = 'yt_dlp.extractor.mtv'
    IE_NAME = 'mtv'
    _VALID_URL = 'https?://(?:www\\.)?mtv\\.com/(?:video-clips|(?:full-)?episodes)/(?P<id>[^/?#.]+)'


class CMTIE(MTVIE):
    _module = 'yt_dlp.extractor.cmt'
    IE_NAME = 'cmt.com'
    _VALID_URL = 'https?://(?:www\\.)?cmt\\.com/(?:videos|shows|(?:full-)?episodes|video-clips)/(?P<id>[^/]+)'


class MTVVideoIE(MTVServicesInfoExtractor):
    _module = 'yt_dlp.extractor.mtv'
    IE_NAME = 'mtv:video'
    _VALID_URL = '(?x)^https?://\n        (?:(?:www\\.)?mtv\\.com/videos/.+?/(?P<videoid>[0-9]+)/[^/]+$|\n           m\\.mtv\\.com/videos/video\\.rbml\\?.*?id=(?P<mgid>[^&]+))'


class MTVServicesEmbeddedIE(MTVServicesInfoExtractor):
    _module = 'yt_dlp.extractor.mtv'
    IE_NAME = 'mtvservices:embedded'
    _VALID_URL = 'https?://media\\.mtvnservices\\.com/embed/(?P<mgid>.+?)(\\?|/|$)'


class MTVDEIE(MTVServicesInfoExtractor):
    _module = 'yt_dlp.extractor.mtv'
    IE_NAME = 'mtv.de'
    _VALID_URL = 'https?://(?:www\\.)?mtv\\.de/(?:musik/videoclips|folgen|news)/(?P<id>[0-9a-z]+)'


class MTVJapanIE(MTVServicesInfoExtractor):
    _module = 'yt_dlp.extractor.mtv'
    IE_NAME = 'mtvjapan'
    _VALID_URL = 'https?://(?:www\\.)?mtvjapan\\.com/videos/(?P<id>[0-9a-z]+)'


class MTVItaliaIE(MTVServicesInfoExtractor):
    _module = 'yt_dlp.extractor.mtv'
    IE_NAME = 'mtv.it'
    _VALID_URL = 'https?://(?:www\\.)?mtv\\.it/(?:episodi|video|musica)/(?P<id>[0-9a-z]+)'


class MTVItaliaProgrammaIE(MTVItaliaIE):
    _module = 'yt_dlp.extractor.mtv'
    IE_NAME = 'mtv.it:programma'
    _VALID_URL = 'https?://(?:www\\.)?mtv\\.it/(?:programmi|playlist)/(?P<id>[0-9a-z]+)'


class MuenchenTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.muenchentv'
    IE_NAME = 'MuenchenTV'
    IE_DESC = 'münchen.tv'
    _VALID_URL = 'https?://(?:www\\.)?muenchen\\.tv/livestream'


class MurrtubeIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.murrtube'
    IE_NAME = 'Murrtube'
    _VALID_URL = '(?x)\n                        (?:\n                            murrtube:|\n                            https?://murrtube\\.net/videos/(?P<slug>[a-z0-9\\-]+)\\-\n                        )\n                        (?P<id>[a-f0-9]{8}\\-[a-f0-9]{4}\\-[a-f0-9]{4}\\-[a-f0-9]{4}\\-[a-f0-9]{12})\n                    '
    age_limit = 18


class MurrtubeUserIE(MurrtubeIE):
    _module = 'yt_dlp.extractor.murrtube'
    IE_NAME = 'MurrtubeUser'
    IE_DESC = 'Murrtube user profile'
    _VALID_URL = 'https?://murrtube\\.net/(?P<id>[^/]+)$'


class MuseScoreIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.musescore'
    IE_NAME = 'MuseScore'
    _VALID_URL = 'https?://(?:www\\.)?musescore\\.com/(?:user/\\d+|[^/]+)(?:/scores)?/(?P<id>[^#&?]+)'


class MusicdexBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.musicdex'
    IE_NAME = 'MusicdexBase'


class MusicdexSongIE(MusicdexBaseIE):
    _module = 'yt_dlp.extractor.musicdex'
    IE_NAME = 'MusicdexSong'
    _VALID_URL = 'https?://(?:www\\.)?musicdex\\.org/track/(?P<id>\\d+)'


class MusicdexAlbumIE(MusicdexBaseIE):
    _module = 'yt_dlp.extractor.musicdex'
    IE_NAME = 'MusicdexAlbum'
    _VALID_URL = 'https?://(?:www\\.)?musicdex\\.org/album/(?P<id>\\d+)'


class MusicdexPageIE(MusicdexBaseIE):
    _module = 'yt_dlp.extractor.musicdex'
    IE_NAME = 'MusicdexPage'


class MusicdexArtistIE(MusicdexPageIE):
    _module = 'yt_dlp.extractor.musicdex'
    IE_NAME = 'MusicdexArtist'
    _VALID_URL = 'https?://(?:www\\.)?musicdex\\.org/artist/(?P<id>\\d+)'


class MusicdexPlaylistIE(MusicdexPageIE):
    _module = 'yt_dlp.extractor.musicdex'
    IE_NAME = 'MusicdexPlaylist'
    _VALID_URL = 'https?://(?:www\\.)?musicdex\\.org/playlist/(?P<id>\\d+)'


class MwaveIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.mwave'
    IE_NAME = 'Mwave'
    _VALID_URL = 'https?://mwave\\.interest\\.me/(?:[^/]+/)?mnettv/videodetail\\.m\\?searchVideoDetailVO\\.clip_id=(?P<id>[0-9]+)'


class MwaveMeetGreetIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.mwave'
    IE_NAME = 'MwaveMeetGreet'
    _VALID_URL = 'https?://mwave\\.interest\\.me/(?:[^/]+/)?meetgreet/view/(?P<id>\\d+)'


class MxplayerIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.mxplayer'
    IE_NAME = 'Mxplayer'
    _VALID_URL = 'https?://(?:www\\.)?mxplayer\\.in/(?P<type>movie|show/[-\\w]+/[-\\w]+)/(?P<display_id>[-\\w]+)-(?P<id>\\w+)'


class MxplayerShowIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.mxplayer'
    IE_NAME = 'MxplayerShow'
    _VALID_URL = 'https?://(?:www\\.)?mxplayer\\.in/show/(?P<display_id>[-\\w]+)-(?P<id>\\w+)/?(?:$|[#?])'


class MyChannelsIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.mychannels'
    IE_NAME = 'MyChannels'
    _VALID_URL = 'https?://(?:www\\.)?mychannels\\.com/.*(?P<id_type>video|production)_id=(?P<id>[0-9]+)'


class MySpaceIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.myspace'
    IE_NAME = 'MySpace'
    _VALID_URL = '(?x)\n                    https?://\n                        myspace\\.com/[^/]+/\n                        (?P<mediatype>\n                            video/[^/]+/(?P<video_id>\\d+)|\n                            music/song/[^/?#&]+-(?P<song_id>\\d+)-\\d+(?:[/?#&]|$)\n                        )\n                    '


class MySpaceAlbumIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.myspace'
    IE_NAME = 'MySpace:album'
    _VALID_URL = 'https?://myspace\\.com/([^/]+)/music/album/(?P<title>.*-)(?P<id>\\d+)'


class MySpassIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.myspass'
    IE_NAME = 'MySpass'
    _VALID_URL = 'https?://(?:www\\.)?myspass\\.de/(?:[^/]+/)*(?P<id>\\d+)/?[^/]*$'


class SprutoBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.vimple'
    IE_NAME = 'SprutoBase'


class MyviIE(SprutoBaseIE):
    _module = 'yt_dlp.extractor.myvi'
    IE_NAME = 'Myvi'
    _VALID_URL = '(?x)\n                        (?:\n                            https?://\n                                (?:www\\.)?\n                                myvi\\.\n                                (?:\n                                    (?:ru/player|tv)/\n                                    (?:\n                                        (?:\n                                            embed/html|\n                                            flash|\n                                            api/Video/Get\n                                        )/|\n                                        content/preloader\\.swf\\?.*\\bid=\n                                    )|\n                                    ru/watch/\n                                )|\n                            myvi:\n                        )\n                        (?P<id>[\\da-zA-Z_-]+)\n                    '


class MyviEmbedIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.myvi'
    IE_NAME = 'MyviEmbed'
    _VALID_URL = 'https?://(?:www\\.)?myvi\\.tv/(?:[^?]+\\?.*?\\bv=|embed/)(?P<id>[\\da-z]+)'

    @classmethod
    def suitable(cls, url):
        return False if MyviIE.suitable(url) else super(MyviEmbedIE, cls).suitable(url)


class MyVideoGeIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.myvideoge'
    IE_NAME = 'MyVideoGe'
    _VALID_URL = 'https?://(?:www\\.)?myvideo\\.ge/v/(?P<id>[0-9]+)'


class MyVidsterIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.myvidster'
    IE_NAME = 'MyVidster'
    _VALID_URL = 'https?://(?:www\\.)?myvidster\\.com/video/(?P<id>\\d+)/'
    age_limit = 18


class N1InfoAssetIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.n1'
    IE_NAME = 'N1InfoAsset'
    _VALID_URL = 'https?://best-vod\\.umn\\.cdn\\.united\\.cloud/stream\\?asset=(?P<id>[^&]+)'


class N1InfoIIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.n1'
    IE_NAME = 'N1Info:article'
    _VALID_URL = 'https?://(?:(?:(?:ba|rs|hr)\\.)?n1info\\.(?:com|si)|nova\\.rs)/(?:[^/]+/){1,2}(?P<id>[^/]+)'


class NateIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.nate'
    IE_NAME = 'Nate'
    _VALID_URL = 'https?://tv\\.nate\\.com/clip/(?P<id>[0-9]+)'
    age_limit = 15


class NateProgramIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.nate'
    IE_NAME = 'NateProgram'
    _VALID_URL = 'https?://tv\\.nate\\.com/program/clips/(?P<id>[0-9]+)'


class NationalGeographicVideoIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.nationalgeographic'
    IE_NAME = 'natgeo:video'
    _VALID_URL = 'https?://video\\.nationalgeographic\\.com/.*?'


class NationalGeographicTVIE(FOXIE):
    _module = 'yt_dlp.extractor.nationalgeographic'
    IE_NAME = 'NationalGeographicTV'
    _VALID_URL = 'https?://(?:www\\.)?nationalgeographic\\.com/tv/watch/(?P<id>[\\da-fA-F]+)'
    age_limit = 14


class NaverBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.naver'
    IE_NAME = 'NaverBase'


class NaverIE(NaverBaseIE):
    _module = 'yt_dlp.extractor.naver'
    IE_NAME = 'Naver'
    _VALID_URL = 'https?://(?:m\\.)?tv(?:cast)?\\.naver\\.com/(?:v|embed)/(?P<id>\\d+)'


class NaverLiveIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.naver'
    IE_NAME = 'Naver:live'
    _VALID_URL = 'https?://(?:m\\.)?tv(?:cast)?\\.naver\\.com/l/(?P<id>\\d+)'


class NaverNowIE(NaverBaseIE):
    _module = 'yt_dlp.extractor.naver'
    IE_NAME = 'navernow'
    _VALID_URL = 'https?://now\\.naver\\.com/s/now\\.(?P<id>[0-9]+)'


class NBACVPBaseIE(TurnerBaseIE):
    _module = 'yt_dlp.extractor.nba'
    IE_NAME = 'NBACVPBase'


class NBAWatchBaseIE(NBACVPBaseIE):
    _module = 'yt_dlp.extractor.nba'
    IE_NAME = 'NBAWatchBase'


class NBAWatchEmbedIE(NBAWatchBaseIE):
    _module = 'yt_dlp.extractor.nba'
    IE_NAME = 'NBAWatchEmbed'
    _VALID_URL = 'https?://(?:(?:www\\.)?nba\\.com(?:/watch)?|watch\\.nba\\.com)/embed\\?.*?\\bid=(?P<id>\\d+)'


class NBAWatchIE(NBAWatchBaseIE):
    _module = 'yt_dlp.extractor.nba'
    IE_NAME = 'nba:watch'
    _VALID_URL = 'https?://(?:(?:www\\.)?nba\\.com(?:/watch)?|watch\\.nba\\.com)/(?:nba/)?video/(?P<id>.+?(?=/index\\.html)|(?:[^/]+/)*[^/?#&]+)'


class NBAWatchCollectionIE(NBAWatchBaseIE):
    _module = 'yt_dlp.extractor.nba'
    IE_NAME = 'nba:watch:collection'
    _VALID_URL = 'https?://(?:(?:www\\.)?nba\\.com(?:/watch)?|watch\\.nba\\.com)/list/collection/(?P<id>[^/?#&]+)'


class NBABaseIE(NBACVPBaseIE):
    _module = 'yt_dlp.extractor.nba'
    IE_NAME = 'NBABase'


class NBAEmbedIE(NBABaseIE):
    _module = 'yt_dlp.extractor.nba'
    IE_NAME = 'NBAEmbed'
    _VALID_URL = 'https?://secure\\.nba\\.com/assets/amp/include/video/(?:topI|i)frame\\.html\\?.*?\\bcontentId=(?P<id>[^?#&]+)'


class NBAIE(NBABaseIE):
    _module = 'yt_dlp.extractor.nba'
    IE_NAME = 'NBA'
    _VALID_URL = '(?x)\n        https?://(?:www\\.)?nba\\.com/\n            (?P<team>\n                blazers|\n                bucks|\n                bulls|\n                cavaliers|\n                celtics|\n                clippers|\n                grizzlies|\n                hawks|\n                heat|\n                hornets|\n                jazz|\n                kings|\n                knicks|\n                lakers|\n                magic|\n                mavericks|\n                nets|\n                nuggets|\n                pacers|\n                pelicans|\n                pistons|\n                raptors|\n                rockets|\n                sixers|\n                spurs|\n                suns|\n                thunder|\n                timberwolves|\n                warriors|\n                wizards\n            )\n        (?:/play\\#)?/(?!video/channel|series)video/(?P<id>(?:[^/]+/)*[^/?#&]+)'


class NBAChannelIE(NBABaseIE):
    _module = 'yt_dlp.extractor.nba'
    IE_NAME = 'NBAChannel'
    _VALID_URL = '(?x)\n        https?://(?:www\\.)?nba\\.com/\n            (?P<team>\n                blazers|\n                bucks|\n                bulls|\n                cavaliers|\n                celtics|\n                clippers|\n                grizzlies|\n                hawks|\n                heat|\n                hornets|\n                jazz|\n                kings|\n                knicks|\n                lakers|\n                magic|\n                mavericks|\n                nets|\n                nuggets|\n                pacers|\n                pelicans|\n                pistons|\n                raptors|\n                rockets|\n                sixers|\n                spurs|\n                suns|\n                thunder|\n                timberwolves|\n                warriors|\n                wizards\n            )\n        (?:/play\\#)?/(?:video/channel|series)/(?P<id>[^/?#&]+)'


class NBCOlympicsIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.nbc'
    IE_NAME = 'nbcolympics'
    _VALID_URL = 'https?://www\\.nbcolympics\\.com/videos?/(?P<id>[0-9a-z-]+)'


class NBCOlympicsStreamIE(AdobePassIE):
    _module = 'yt_dlp.extractor.nbc'
    IE_NAME = 'nbcolympics:stream'
    _VALID_URL = 'https?://stream\\.nbcolympics\\.com/(?P<id>[0-9a-z-]+)'


class NBCSportsIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.nbc'
    IE_NAME = 'NBCSports'
    _VALID_URL = 'https?://(?:www\\.)?nbcsports\\.com//?(?!vplayer/)(?:[^/]+/)+(?P<id>[0-9a-z-]+)'


class NBCSportsStreamIE(AdobePassIE):
    _module = 'yt_dlp.extractor.nbc'
    IE_NAME = 'NBCSportsStream'
    _VALID_URL = 'https?://stream\\.nbcsports\\.com/.+?\\bpid=(?P<id>\\d+)'


class NBCSportsVPlayerIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.nbc'
    IE_NAME = 'NBCSportsVPlayer'
    _VALID_URL = 'https?://(?:vplayer\\.nbcsports\\.com|(?:www\\.)?nbcsports\\.com/vplayer)/(?:[^/]+/)+(?P<id>[0-9a-zA-Z_]+)'


class NBCStationsIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.nbc'
    IE_NAME = 'NBCStations'
    _VALID_URL = 'https?://(?:www\\.)?(?P<site>nbcbayarea|nbcboston|nbcchicago|nbcconnecticut|nbcdfw|nbclosangeles|nbcmiami|nbcnewyork|nbcphiladelphia|nbcsandiego|nbcwashington|necn|telemundo52|telemundoarizona|telemundochicago|telemundonuevainglaterra)\\.com/(?:[^/?#]+/)*(?P<id>[^/?#]+)/?(?:$|[#?])'


class NDRBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ndr'
    IE_NAME = 'NDRBase'


class NDRIE(NDRBaseIE):
    _module = 'yt_dlp.extractor.ndr'
    IE_NAME = 'ndr'
    IE_DESC = 'NDR.de - Norddeutscher Rundfunk'
    _VALID_URL = 'https?://(?:\\w+\\.)*ndr\\.de/(?:[^/]+/)*(?P<id>[^/?#]+),[\\da-z]+\\.html'


class NJoyIE(NDRBaseIE):
    _module = 'yt_dlp.extractor.ndr'
    IE_NAME = 'njoy'
    IE_DESC = 'N-JOY'
    _VALID_URL = 'https?://(?:www\\.)?n-joy\\.de/(?:[^/]+/)*(?:(?P<display_id>[^/?#]+),)?(?P<id>[\\da-z]+)\\.html'


class NDREmbedBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ndr'
    IE_NAME = 'ndr:embed:base'
    _VALID_URL = '(?:ndr:(?P<id_s>[\\da-z]+)|https?://www\\.ndr\\.de/(?P<id>[\\da-z]+)-ppjson\\.json)'


class NDREmbedIE(NDREmbedBaseIE):
    _module = 'yt_dlp.extractor.ndr'
    IE_NAME = 'ndr:embed'
    _VALID_URL = 'https?://(?:\\w+\\.)*ndr\\.de/(?:[^/]+/)*(?P<id>[\\da-z]+)-(?:(?:ard)?player|externalPlayer)\\.html'


class NJoyEmbedIE(NDREmbedBaseIE):
    _module = 'yt_dlp.extractor.ndr'
    IE_NAME = 'njoy:embed'
    _VALID_URL = 'https?://(?:www\\.)?n-joy\\.de/(?:[^/]+/)*(?P<id>[\\da-z]+)-(?:player|externalPlayer)_[^/]+\\.html'


class NDTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ndtv'
    IE_NAME = 'NDTV'
    _VALID_URL = 'https?://(?:[^/]+\\.)?ndtv\\.com/(?:[^/]+/)*videos?/?(?:[^/]+/)*[^/?^&]+-(?P<id>\\d+)'


class NebulaBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.nebula'
    IE_NAME = 'NebulaBase'
    _NETRC_MACHINE = 'watchnebula'


class NebulaIE(NebulaBaseIE):
    _module = 'yt_dlp.extractor.nebula'
    IE_NAME = 'Nebula'
    _VALID_URL = 'https?://(?:www\\.)?(?:watchnebula\\.com|nebula\\.app|nebula\\.tv)/videos/(?P<id>[-\\w]+)'
    _NETRC_MACHINE = 'watchnebula'


class NebulaSubscriptionsIE(NebulaBaseIE):
    _module = 'yt_dlp.extractor.nebula'
    IE_NAME = 'nebula:subscriptions'
    _VALID_URL = 'https?://(?:www\\.)?(?:watchnebula\\.com|nebula\\.app|nebula\\.tv)/myshows'
    _NETRC_MACHINE = 'watchnebula'


class NebulaChannelIE(NebulaBaseIE):
    _module = 'yt_dlp.extractor.nebula'
    IE_NAME = 'nebula:channel'
    _VALID_URL = 'https?://(?:www\\.)?(?:watchnebula\\.com|nebula\\.app|nebula\\.tv)/(?!myshows|videos/)(?P<id>[-\\w]+)'
    _NETRC_MACHINE = 'watchnebula'


class NerdCubedFeedIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.nerdcubed'
    IE_NAME = 'NerdCubedFeed'
    _VALID_URL = 'https?://(?:www\\.)?nerdcubed\\.co\\.uk/feed\\.json'


class NetzkinoIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.netzkino'
    IE_NAME = 'Netzkino'
    _VALID_URL = 'https?://(?:www\\.)?netzkino\\.de/\\#!/[^/]+/(?P<id>[^/]+)'
    age_limit = 18


class NetEaseMusicBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.neteasemusic'
    IE_NAME = 'NetEaseMusicBase'


class NetEaseMusicIE(NetEaseMusicBaseIE):
    _module = 'yt_dlp.extractor.neteasemusic'
    IE_NAME = 'netease:song'
    IE_DESC = '网易云音乐'
    _VALID_URL = 'https?://(y\\.)?music\\.163\\.com/(?:[#m]/)?song\\?.*?\\bid=(?P<id>[0-9]+)'


class NetEaseMusicAlbumIE(NetEaseMusicBaseIE):
    _module = 'yt_dlp.extractor.neteasemusic'
    IE_NAME = 'netease:album'
    IE_DESC = '网易云音乐 - 专辑'
    _VALID_URL = 'https?://music\\.163\\.com/(#/)?album\\?id=(?P<id>[0-9]+)'


class NetEaseMusicSingerIE(NetEaseMusicBaseIE):
    _module = 'yt_dlp.extractor.neteasemusic'
    IE_NAME = 'netease:singer'
    IE_DESC = '网易云音乐 - 歌手'
    _VALID_URL = 'https?://music\\.163\\.com/(#/)?artist\\?id=(?P<id>[0-9]+)'


class NetEaseMusicListIE(NetEaseMusicBaseIE):
    _module = 'yt_dlp.extractor.neteasemusic'
    IE_NAME = 'netease:playlist'
    IE_DESC = '网易云音乐 - 歌单'
    _VALID_URL = 'https?://music\\.163\\.com/(#/)?(playlist|discover/toplist)\\?id=(?P<id>[0-9]+)'


class NetEaseMusicMvIE(NetEaseMusicBaseIE):
    _module = 'yt_dlp.extractor.neteasemusic'
    IE_NAME = 'netease:mv'
    IE_DESC = '网易云音乐 - MV'
    _VALID_URL = 'https?://music\\.163\\.com/(#/)?mv\\?id=(?P<id>[0-9]+)'


class NetEaseMusicProgramIE(NetEaseMusicBaseIE):
    _module = 'yt_dlp.extractor.neteasemusic'
    IE_NAME = 'netease:program'
    IE_DESC = '网易云音乐 - 电台节目'
    _VALID_URL = 'https?://music\\.163\\.com/(#/?)program\\?id=(?P<id>[0-9]+)'


class NetEaseMusicDjRadioIE(NetEaseMusicBaseIE):
    _module = 'yt_dlp.extractor.neteasemusic'
    IE_NAME = 'netease:djradio'
    IE_DESC = '网易云音乐 - 电台'
    _VALID_URL = 'https?://music\\.163\\.com/(#/)?djradio\\?id=(?P<id>[0-9]+)'


class NetverseBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.netverse'
    IE_NAME = 'NetverseBase'


class NetverseIE(NetverseBaseIE):
    _module = 'yt_dlp.extractor.netverse'
    IE_NAME = 'Netverse'
    _VALID_URL = 'https?://(?:\\w+\\.)?netverse\\.id/(?P<type>watch|video)/(?P<display_id>[^/?#&]+)'


class NetversePlaylistIE(NetverseBaseIE):
    _module = 'yt_dlp.extractor.netverse'
    IE_NAME = 'NetversePlaylist'
    _VALID_URL = 'https?://(?:\\w+\\.)?netverse\\.id/(?P<type>webseries)/(?P<display_id>[^/?#&]+)'


class NewgroundsIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.newgrounds'
    IE_NAME = 'Newgrounds'
    _VALID_URL = 'https?://(?:www\\.)?newgrounds\\.com/(?:audio/listen|portal/view)/(?P<id>\\d+)(?:/format/flash)?'
    age_limit = 17


class NewgroundsPlaylistIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.newgrounds'
    IE_NAME = 'Newgrounds:playlist'
    _VALID_URL = 'https?://(?:www\\.)?newgrounds\\.com/(?:collection|[^/]+/search/[^/]+)/(?P<id>[^/?#&]+)'


class NewgroundsUserIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.newgrounds'
    IE_NAME = 'Newgrounds:user'
    _VALID_URL = 'https?://(?P<id>[^\\.]+)\\.newgrounds\\.com/(?:movies|audio)/?(?:[#?]|$)'


class NewsPicksIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.newspicks'
    IE_NAME = 'NewsPicks'
    _VALID_URL = 'https://newspicks\\.com/movie-series/(?P<channel_id>\\d+)\\?movieId=(?P<id>\\d+)'


class NewstubeIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.newstube'
    IE_NAME = 'Newstube'
    _VALID_URL = 'https?://(?:www\\.)?newstube\\.ru/media/(?P<id>.+)'


class NewsyIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.newsy'
    IE_NAME = 'Newsy'
    _VALID_URL = 'https?://(?:www\\.)?newsy\\.com/stories/(?P<id>[^/?#$&]+)'


class NextMediaIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.nextmedia'
    IE_NAME = 'NextMedia'
    IE_DESC = '蘋果日報'
    _VALID_URL = 'https?://hk\\.apple\\.nextmedia\\.com/[^/]+/[^/]+/(?P<date>\\d+)/(?P<id>\\d+)'


class NextMediaActionNewsIE(NextMediaIE):
    _module = 'yt_dlp.extractor.nextmedia'
    IE_NAME = 'NextMediaActionNews'
    IE_DESC = '蘋果日報 - 動新聞'
    _VALID_URL = 'https?://hk\\.dv\\.nextmedia\\.com/actionnews/[^/]+/(?P<date>\\d+)/(?P<id>\\d+)/\\d+'


class AppleDailyIE(NextMediaIE):
    _module = 'yt_dlp.extractor.nextmedia'
    IE_NAME = 'AppleDaily'
    IE_DESC = '臺灣蘋果日報'
    _VALID_URL = 'https?://(www|ent)\\.appledaily\\.com\\.tw/[^/]+/[^/]+/[^/]+/(?P<date>\\d+)/(?P<id>\\d+)(/.*)?'


class NextTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.nextmedia'
    IE_NAME = 'NextTV'
    IE_DESC = '壹電視'
    _VALID_URL = 'https?://(?:www\\.)?nexttv\\.com\\.tw/(?:[^/]+/)+(?P<id>\\d+)'


class NexxIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.nexx'
    IE_NAME = 'Nexx'
    _VALID_URL = '(?x)\n                        (?:\n                            https?://api\\.nexx(?:\\.cloud|cdn\\.com)/v3(?:\\.\\d)?/(?P<domain_id>\\d+)/videos/byid/|\n                            nexx:(?:(?P<domain_id_s>\\d+):)?|\n                            https?://arc\\.nexx\\.cloud/api/video/\n                        )\n                        (?P<id>\\d+)\n                    '


class NexxEmbedIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.nexx'
    IE_NAME = 'NexxEmbed'
    _VALID_URL = 'https?://embed\\.nexx(?:\\.cloud|cdn\\.com)/\\d+/(?:video/)?(?P<id>[^/?#&]+)'


class NFBIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.nfb'
    IE_NAME = 'NFB'
    _VALID_URL = 'https?://(?:www\\.)?nfb\\.ca/film/(?P<id>[^/?#&]+)'


class NFHSNetworkIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.nfhsnetwork'
    IE_NAME = 'NFHSNetwork'
    _VALID_URL = 'https?://(?:www\\.)?nfhsnetwork\\.com/events/[\\w-]+/(?P<id>(?:gam|evt|dd|)?[\\w\\d]{0,10})'


class NFLBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.nfl'
    IE_NAME = 'NFLBase'


class NFLIE(NFLBaseIE):
    _module = 'yt_dlp.extractor.nfl'
    IE_NAME = 'nfl.com'
    _VALID_URL = '(?x)\n                    https?://\n                        (?P<host>\n                            (?:www\\.)?\n                            (?:\n                                (?:\n                                    nfl|\n                                    buffalobills|\n                                    miamidolphins|\n                                    patriots|\n                                    newyorkjets|\n                                    baltimoreravens|\n                                    bengals|\n                                    clevelandbrowns|\n                                    steelers|\n                                    houstontexans|\n                                    colts|\n                                    jaguars|\n                                    (?:titansonline|tennesseetitans)|\n                                    denverbroncos|\n                                    (?:kc)?chiefs|\n                                    raiders|\n                                    chargers|\n                                    dallascowboys|\n                                    giants|\n                                    philadelphiaeagles|\n                                    (?:redskins|washingtonfootball)|\n                                    chicagobears|\n                                    detroitlions|\n                                    packers|\n                                    vikings|\n                                    atlantafalcons|\n                                    panthers|\n                                    neworleanssaints|\n                                    buccaneers|\n                                    azcardinals|\n                                    (?:stlouis|the)rams|\n                                    49ers|\n                                    seahawks\n                                )\\.com|\n                                .+?\\.clubs\\.nfl\\.com\n                            )\n                        )/\n                    (?:videos?|listen|audio)/(?P<id>[^/#?&]+)'


class NFLArticleIE(NFLBaseIE):
    _module = 'yt_dlp.extractor.nfl'
    IE_NAME = 'nfl.com:article'
    _VALID_URL = '(?x)\n                    https?://\n                        (?P<host>\n                            (?:www\\.)?\n                            (?:\n                                (?:\n                                    nfl|\n                                    buffalobills|\n                                    miamidolphins|\n                                    patriots|\n                                    newyorkjets|\n                                    baltimoreravens|\n                                    bengals|\n                                    clevelandbrowns|\n                                    steelers|\n                                    houstontexans|\n                                    colts|\n                                    jaguars|\n                                    (?:titansonline|tennesseetitans)|\n                                    denverbroncos|\n                                    (?:kc)?chiefs|\n                                    raiders|\n                                    chargers|\n                                    dallascowboys|\n                                    giants|\n                                    philadelphiaeagles|\n                                    (?:redskins|washingtonfootball)|\n                                    chicagobears|\n                                    detroitlions|\n                                    packers|\n                                    vikings|\n                                    atlantafalcons|\n                                    panthers|\n                                    neworleanssaints|\n                                    buccaneers|\n                                    azcardinals|\n                                    (?:stlouis|the)rams|\n                                    49ers|\n                                    seahawks\n                                )\\.com|\n                                .+?\\.clubs\\.nfl\\.com\n                            )\n                        )/\n                    news/(?P<id>[^/#?&]+)'


class NhkBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.nhk'
    IE_NAME = 'NhkBase'


class NhkVodIE(NhkBaseIE):
    _module = 'yt_dlp.extractor.nhk'
    IE_NAME = 'NhkVod'
    _VALID_URL = 'https?://www3\\.nhk\\.or\\.jp/nhkworld/(?P<lang>[a-z]{2})/ondemand/(?P<type>video|audio)/(?P<id>[0-9a-z]{7}|[^/]+?-\\d{8}-[0-9a-z]+)'


class NhkVodProgramIE(NhkBaseIE):
    _module = 'yt_dlp.extractor.nhk'
    IE_NAME = 'NhkVodProgram'
    _VALID_URL = 'https?://www3\\.nhk\\.or\\.jp/nhkworld/(?P<lang>[a-z]{2})/ondemand/program/(?P<type>video|audio)/(?P<id>[0-9a-z]+)(?:.+?\\btype=(?P<episode_type>clip|(?:radio|tv)Episode))?'


class NhkForSchoolBangumiIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.nhk'
    IE_NAME = 'NhkForSchoolBangumi'
    _VALID_URL = 'https?://www2\\.nhk\\.or\\.jp/school/movie/(?P<type>bangumi|clip)\\.cgi\\?das_id=(?P<id>[a-zA-Z0-9_-]+)'


class NhkForSchoolSubjectIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.nhk'
    IE_NAME = 'NhkForSchoolSubject'
    IE_DESC = 'Portal page for each school subjects, like Japanese (kokugo, 国語) or math (sansuu/suugaku or 算数・数学)'
    _VALID_URL = 'https?://www\\.nhk\\.or\\.jp/school/(?P<id>rika|syakai|kokugo|sansuu|seikatsu|doutoku|ongaku|taiiku|zukou|gijutsu|katei|sougou|eigo|tokkatsu|tokushi|sonota)/?(?:[\\?#].*)?$'


class NhkForSchoolProgramListIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.nhk'
    IE_NAME = 'NhkForSchoolProgramList'
    _VALID_URL = 'https?://www\\.nhk\\.or\\.jp/school/(?P<id>(?:rika|syakai|kokugo|sansuu|seikatsu|doutoku|ongaku|taiiku|zukou|gijutsu|katei|sougou|eigo|tokkatsu|tokushi|sonota)/[a-zA-Z0-9_-]+)'


class NHLBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.nhl'
    IE_NAME = 'NHLBase'


class NHLIE(NHLBaseIE):
    _module = 'yt_dlp.extractor.nhl'
    IE_NAME = 'nhl.com'
    _VALID_URL = 'https?://(?:www\\.)?(?P<site>nhl|wch2016)\\.com/(?:[^/]+/)*c-(?P<id>\\d+)'


class NickIE(MTVServicesInfoExtractor):
    _module = 'yt_dlp.extractor.nick'
    IE_NAME = 'nick.com'
    _VALID_URL = 'https?://(?P<domain>(?:www\\.)?nick(?:jr)?\\.com)/(?:[^/]+/)?(?P<type>videos/clip|[^/]+/videos|episodes/[^/]+)/(?P<id>[^/?#.]+)'


class NickBrIE(MTVServicesInfoExtractor):
    _module = 'yt_dlp.extractor.nick'
    IE_NAME = 'nickelodeon:br'
    _VALID_URL = '(?x)\n                    https?://\n                        (?:\n                            (?P<domain>(?:www\\.)?nickjr|mundonick\\.uol)\\.com\\.br|\n                            (?:www\\.)?nickjr\\.[a-z]{2}|\n                            (?:www\\.)?nickelodeonjunior\\.fr\n                        )\n                        /(?:programas/)?[^/]+/videos/(?:episodios/)?(?P<id>[^/?\\#.]+)\n                    '


class NickDeIE(MTVServicesInfoExtractor):
    _module = 'yt_dlp.extractor.nick'
    IE_NAME = 'nick.de'
    _VALID_URL = 'https?://(?:www\\.)?(?P<host>nick\\.(?:de|com\\.pl|ch)|nickelodeon\\.(?:nl|be|at|dk|no|se))/[^/]+/(?:[^/]+/)*(?P<id>[^/?#&]+)'


class NickNightIE(NickDeIE):
    _module = 'yt_dlp.extractor.nick'
    IE_NAME = 'nicknight'
    _VALID_URL = 'https?://(?:www\\.)(?P<host>nicknight\\.(?:de|at|tv))/(?:playlist|shows)/(?:[^/]+/)*(?P<id>[^/?#&]+)'


class NickRuIE(MTVServicesInfoExtractor):
    _module = 'yt_dlp.extractor.nick'
    IE_NAME = 'nickelodeonru'
    _VALID_URL = 'https?://(?:www\\.)nickelodeon\\.(?:ru|fr|es|pt|ro|hu|com\\.tr)/[^/]+/(?:[^/]+/)*(?P<id>[^/?#&]+)'


class NiconicoIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.niconico'
    IE_NAME = 'niconico'
    IE_DESC = 'ニコニコ動画'
    _VALID_URL = 'https?://(?:(?:www\\.|secure\\.|sp\\.)?nicovideo\\.jp/watch|nico\\.ms)/(?P<id>(?:[a-z]{2})?[0-9]+)'
    _NETRC_MACHINE = 'niconico'


class NiconicoPlaylistBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.niconico'
    IE_NAME = 'NiconicoPlaylistBase'


class NiconicoPlaylistIE(NiconicoPlaylistBaseIE):
    _module = 'yt_dlp.extractor.niconico'
    IE_NAME = 'niconico:playlist'
    _VALID_URL = 'https?://(?:(?:www\\.|sp\\.)?nicovideo\\.jp|nico\\.ms)/(?:user/\\d+/)?(?:my/)?mylist/(?:#/)?(?P<id>\\d+)'


class NiconicoUserIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.niconico'
    IE_NAME = 'NiconicoUser'
    _VALID_URL = 'https?://(?:www\\.)?nicovideo\\.jp/user/(?P<id>\\d+)/?(?:$|[#?])'


class NiconicoSeriesIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.niconico'
    IE_NAME = 'niconico:series'
    _VALID_URL = 'https?://(?:(?:www\\.|sp\\.)?nicovideo\\.jp|nico\\.ms)/series/(?P<id>\\d+)'


class NiconicoHistoryIE(NiconicoPlaylistBaseIE):
    _module = 'yt_dlp.extractor.niconico'
    IE_NAME = 'niconico:history'
    IE_DESC = 'NicoNico user history. Requires cookies.'
    _VALID_URL = 'https?://(?:www\\.|sp\\.)?nicovideo\\.jp/my/history'


class NicovideoSearchBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.niconico'
    IE_NAME = 'NicovideoSearchBase'


class NicovideoSearchDateIE(NicovideoSearchBaseIE, LazyLoadSearchExtractor):
    _module = 'yt_dlp.extractor.niconico'
    IE_NAME = 'nicovideo:search:date'
    IE_DESC = 'Nico video search, newest first'
    SEARCH_KEY = 'nicosearchdate'
    _VALID_URL = 'nicosearchdate(?P<prefix>|[1-9][0-9]*|all):(?P<query>[\\s\\S]+)'


class NicovideoSearchIE(NicovideoSearchBaseIE, LazyLoadSearchExtractor):
    _module = 'yt_dlp.extractor.niconico'
    IE_NAME = 'nicovideo:search'
    IE_DESC = 'Nico video search'
    SEARCH_KEY = 'nicosearch'
    _VALID_URL = 'nicosearch(?P<prefix>|[1-9][0-9]*|all):(?P<query>[\\s\\S]+)'


class NicovideoSearchURLIE(NicovideoSearchBaseIE):
    _module = 'yt_dlp.extractor.niconico'
    IE_NAME = 'nicovideo:search_url'
    IE_DESC = 'Nico video search URLs'
    _VALID_URL = 'https?://(?:www\\.)?nicovideo\\.jp/search/(?P<id>[^?#&]+)?'


class NicovideoTagURLIE(NicovideoSearchBaseIE):
    _module = 'yt_dlp.extractor.niconico'
    IE_NAME = 'niconico:tag'
    IE_DESC = 'NicoNico video tag URLs'
    _VALID_URL = 'https?://(?:www\\.)?nicovideo\\.jp/tag/(?P<id>[^?#&]+)?'


class NineCNineMediaIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ninecninemedia'
    IE_NAME = '9c9media'
    _VALID_URL = '9c9media:(?P<destination_code>[^:]+):(?P<id>\\d+)'


class CPTwentyFourIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ninecninemedia'
    IE_NAME = 'cp24'
    _VALID_URL = 'https?://(?:www\\.)?cp24\\.com/news/(?P<id>[^?#]+)'


class NineGagIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ninegag'
    IE_NAME = '9gag'
    IE_DESC = '9GAG'
    _VALID_URL = 'https?://(?:www\\.)?9gag\\.com/gag/(?P<id>[^/?&#]+)'


class NineNowIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ninenow'
    IE_NAME = '9now.com.au'
    _VALID_URL = 'https?://(?:www\\.)?9now\\.com\\.au/(?:[^/]+/){2}(?P<id>[^/?#]+)'


class NintendoIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.nintendo'
    IE_NAME = 'Nintendo'
    _VALID_URL = 'https?://(?:www\\.)?nintendo\\.com/(?:games/detail|nintendo-direct)/(?P<id>[^/?#&]+)'


class NitterIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.nitter'
    IE_NAME = 'Nitter'
    _VALID_URL = 'https?://(?:3nzoldnxplag42gqjs23xvghtzf6t6yzssrtytnntc6ppc7xxuoneoad\\.onion|nitter\\.l4qlywnpwqsluw65ts7md3khrivpirse744un3x7mlskqauz5pyuzgqd\\.onion|nitter7bryz3jv7e3uekphigvmoyoem4al3fynerxkj22dmoxoq553qd\\.onion|npf37k3mtzwxreiw52ccs5ay4e6qt2fkcs2ndieurdyn2cuzzsfyfvid\\.onion|nitter\\.v6vgyqpa7yefkorazmg5d5fimstmvm2vtbirt6676mt7qmllrcnwycqd\\.onion|i23nv6w3juvzlw32xzoxcqzktegd4i4fu3nmnc2ewv4ggiu4ledwklad\\.onion|26oq3gioiwcmfojub37nz5gzbkdiqp7fue5kvye7d4txv4ny6fb4wwid\\.onion|vfaomgh4jxphpbdfizkm5gbtjahmei234giqj4facbwhrfjtcldauqad\\.onion|iwgu3cv7ywf3gssed5iqtavmrlszgsxazkmwwnt4h2kdait75thdyrqd\\.onion|erpnncl5nhyji3c32dcfmztujtl3xaddqb457jsbkulq24zqq7ifdgad\\.onion|ckzuw5misyahmg7j5t5xwwuj3bwy62jfolxyux4brfflramzsvvd3syd\\.onion|jebqj47jgxleaiosfcxfibx2xdahjettuydlxbg64azd4khsxv6kawid\\.onion|nttr2iupbb6fazdpr2rgbooon2tzbbsvvkagkgkwohhodjzj43stxhad\\.onion|nitraeju2mipeziu2wtcrqsxg7h62v5y4eqgwi75uprynkj74gevvuqd\\.onion|nitter\\.lqs5fjmajyp7rvp4qvyubwofzi6d4imua7vs237rkc4m5qogitqwrgyd\\.onion|ibsboeui2im5o7dxnik3s5yghufumgy5abevtij5nbizequfpu4qi4ad\\.onion|ec5nvbycpfa5k6ro77blxgkyrzbkv7uy6r5cngcbkadtjj2733nm3uyd\\.onion|nitter\\.i2p|u6ikd6zndl3c4dsdq4mmujpntgeevdk5qzkfb57r4tnfeccrn2qa\\.b32\\.i2p|nitterlgj3n5fgwesu3vxc5h67ruku33nqaoeoocae2mvlzhsu6k7fqd\\.onion|nitter\\.42l\\.fr|nitter\\.pussthecat\\.org|nitter\\.nixnet\\.services|nitter\\.fdn\\.fr|nitter\\.1d4\\.us|nitter\\.kavin\\.rocks|nitter\\.unixfox\\.eu|nitter\\.domain\\.glass|nitter\\.eu|nitter\\.namazso\\.eu|nitter\\.actionsack\\.com|birdsite\\.xanny\\.family|nitter\\.hu|twitr\\.gq|nitter\\.moomoo\\.me|nittereu\\.moomoo\\.me|bird\\.from\\.tf|nitter\\.it|twitter\\.censors\\.us|twitter\\.grimneko\\.de|nitter\\.alefvanoon\\.xyz|n\\.hyperborea\\.cloud|nitter\\.ca|twitter\\.076\\.ne\\.jp|twitter\\.mstdn\\.social|nitter\\.fly\\.dev|notabird\\.site|nitter\\.weiler\\.rocks|nitter\\.silkky\\.cloud|nitter\\.sethforprivacy\\.com|nttr\\.stream|nitter\\.cutelab\\.space|nitter\\.nl|nitter\\.mint\\.lgbt|nitter\\.bus\\-hit\\.me|fuckthesacklers\\.network|nitter\\.govt\\.land|nitter\\.datatunnel\\.xyz|nitter\\.esmailelbob\\.xyz|tw\\.artemislena\\.eu|de\\.nttr\\.stream|nitter\\.winscloud\\.net|nitter\\.tiekoetter\\.com|nitter\\.spaceint\\.fr|twtr\\.bch\\.bar|nitter\\.exonip\\.de|nitter\\.mastodon\\.pro|nitter\\.notraxx\\.ch|nitter\\.skrep\\.in|nitter\\.snopyta\\.org|nitter\\.ethibox\\.fr|nitter\\.net|is\\-nitter\\.resolv\\.ee|lu\\-nitter\\.resolv\\.ee|nitter\\.13ad\\.de|nitter\\.40two\\.app|nitter\\.cattube\\.org|nitter\\.cc|nitter\\.dark\\.fail|nitter\\.himiko\\.cloud|nitter\\.koyu\\.space|nitter\\.mailstation\\.de|nitter\\.mastodont\\.cat|nitter\\.tedomum\\.net|nitter\\.tokhmi\\.xyz|nitter\\.weaponizedhumiliation\\.com|nitter\\.vxempire\\.xyz|tweet\\.lambda\\.dance)/(?P<uploader_id>.+)/status/(?P<id>[0-9]+)(#.)?'


class NJPWWorldIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.njpwworld'
    IE_NAME = 'NJPWWorld'
    IE_DESC = '新日本プロレスワールド'
    _VALID_URL = 'https?://(front\\.)?njpwworld\\.com/p/(?P<id>[a-z0-9_]+)'
    _NETRC_MACHINE = 'njpwworld'


class NobelPrizeIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.nobelprize'
    IE_NAME = 'NobelPrize'
    _VALID_URL = 'https?://(?:www\\.)?nobelprize\\.org/mediaplayer.*?\\bid=(?P<id>\\d+)'


class NonkTubeIE(NuevoBaseIE):
    _module = 'yt_dlp.extractor.nonktube'
    IE_NAME = 'NonkTube'
    _VALID_URL = 'https?://(?:www\\.)?nonktube\\.com/(?:(?:video|embed)/|media/nuevo/embed\\.php\\?.*?\\bid=)(?P<id>\\d+)'
    age_limit = 18


class NoodleMagazineIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.noodlemagazine'
    IE_NAME = 'NoodleMagazine'
    _VALID_URL = 'https?://(?:www|adult\\.)?noodlemagazine\\.com/watch/(?P<id>[0-9-_]+)'
    age_limit = 18


class NoovoIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.noovo'
    IE_NAME = 'Noovo'
    _VALID_URL = 'https?://(?:[^/]+\\.)?noovo\\.ca/videos/(?P<id>[^/]+/[^/?#&]+)'


class NormalbootsIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.normalboots'
    IE_NAME = 'Normalboots'
    _VALID_URL = 'https?://(?:www\\.)?normalboots\\.com/video/(?P<id>[0-9a-z-]*)/?$'


class NosVideoIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.nosvideo'
    IE_NAME = 'NosVideo'
    _VALID_URL = 'https?://(?:www\\.)?nosvideo\\.com/(?:embed/|\\?v=)(?P<id>[A-Za-z0-9]{12})/?'


class NOSNLArticleIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.nosnl'
    IE_NAME = 'NOSNLArticle'
    _VALID_URL = 'https?://nos\\.nl/((?!video)(\\w+/)?\\w+/)\\d+-(?P<display_id>[\\w-]+)'


class NovaEmbedIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.nova'
    IE_NAME = 'NovaEmbed'
    _VALID_URL = 'https?://media\\.cms\\.nova\\.cz/embed/(?P<id>[^/?#&]+)'


class NovaIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.nova'
    IE_NAME = 'Nova'
    IE_DESC = 'TN.cz, Prásk.tv, Nova.cz, Novaplus.cz, FANDA.tv, Krásná.cz and Doma.cz'
    _VALID_URL = 'https?://(?:[^.]+\\.)?(?P<site>tv(?:noviny)?|tn|novaplus|vymena|fanda|krasna|doma|prask)\\.nova\\.cz/(?:[^/]+/)+(?P<id>[^/]+?)(?:\\.html|/|$)'


class NovaPlayIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.novaplay'
    IE_NAME = 'NovaPlay'
    _VALID_URL = 'https://play.nova\\.bg/video/.*/(?P<id>\\d+)'


class NownessBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.nowness'
    IE_NAME = 'NownessBase'


class NownessIE(NownessBaseIE):
    _module = 'yt_dlp.extractor.nowness'
    IE_NAME = 'nowness'
    _VALID_URL = 'https?://(?:(?:www|cn)\\.)?nowness\\.com/(?:story|(?:series|category)/[^/]+)/(?P<id>[^/]+?)(?:$|[?#])'


class NownessPlaylistIE(NownessBaseIE):
    _module = 'yt_dlp.extractor.nowness'
    IE_NAME = 'nowness:playlist'
    _VALID_URL = 'https?://(?:(?:www|cn)\\.)?nowness\\.com/playlist/(?P<id>\\d+)'


class NownessSeriesIE(NownessBaseIE):
    _module = 'yt_dlp.extractor.nowness'
    IE_NAME = 'nowness:series'
    _VALID_URL = 'https?://(?:(?:www|cn)\\.)?nowness\\.com/series/(?P<id>[^/]+?)(?:$|[?#])'


class NozIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.noz'
    IE_NAME = 'Noz'
    _VALID_URL = 'https?://(?:www\\.)?noz\\.de/video/(?P<id>[0-9]+)/'


class NPOBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.npo'
    IE_NAME = 'NPOBase'


class NPOIE(NPOBaseIE):
    _module = 'yt_dlp.extractor.npo'
    IE_NAME = 'npo'
    IE_DESC = 'npo.nl, ntr.nl, omroepwnl.nl, zapp.nl and npo3.nl'
    _VALID_URL = '(?x)\n                    (?:\n                        npo:|\n                        https?://\n                            (?:www\\.)?\n                            (?:\n                                npo\\.nl/(?:[^/]+/)*|\n                                (?:ntr|npostart)\\.nl/(?:[^/]+/){2,}|\n                                omroepwnl\\.nl/video/fragment/[^/]+__|\n                                (?:zapp|npo3)\\.nl/(?:[^/]+/){2,}\n                            )\n                        )\n                        (?P<id>[^/?#]+)\n                '

    @classmethod
    def suitable(cls, url):
        return (False if any(ie.suitable(url)
                for ie in (NPOLiveIE, NPORadioIE, NPORadioFragmentIE))
                else super(NPOIE, cls).suitable(url))


class NPOPlaylistBaseIE(NPOIE):
    _module = 'yt_dlp.extractor.npo'
    IE_NAME = 'npo'
    IE_DESC = 'npo.nl, ntr.nl, omroepwnl.nl, zapp.nl and npo3.nl'
    _VALID_URL = '(?x)\n                    (?:\n                        npo:|\n                        https?://\n                            (?:www\\.)?\n                            (?:\n                                npo\\.nl/(?:[^/]+/)*|\n                                (?:ntr|npostart)\\.nl/(?:[^/]+/){2,}|\n                                omroepwnl\\.nl/video/fragment/[^/]+__|\n                                (?:zapp|npo3)\\.nl/(?:[^/]+/){2,}\n                            )\n                        )\n                        (?P<id>[^/?#]+)\n                '

    @classmethod
    def suitable(cls, url):
        return (False if any(ie.suitable(url)
                for ie in (NPOLiveIE, NPORadioIE, NPORadioFragmentIE))
                else super(NPOIE, cls).suitable(url))


class AndereTijdenIE(NPOPlaylistBaseIE):
    _module = 'yt_dlp.extractor.npo'
    IE_NAME = 'anderetijden'
    IE_DESC = 'npo.nl, ntr.nl, omroepwnl.nl, zapp.nl and npo3.nl'
    _VALID_URL = 'https?://(?:www\\.)?anderetijden\\.nl/programma/(?:[^/]+/)+(?P<id>[^/?#&]+)'

    @classmethod
    def suitable(cls, url):
        return (False if any(ie.suitable(url)
                for ie in (NPOLiveIE, NPORadioIE, NPORadioFragmentIE))
                else super(NPOIE, cls).suitable(url))


class NPOLiveIE(NPOBaseIE):
    _module = 'yt_dlp.extractor.npo'
    IE_NAME = 'npo.nl:live'
    _VALID_URL = 'https?://(?:www\\.)?npo(?:start)?\\.nl/live(?:/(?P<id>[^/?#&]+))?'


class NPORadioIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.npo'
    IE_NAME = 'npo.nl:radio'
    _VALID_URL = 'https?://(?:www\\.)?npo\\.nl/radio/(?P<id>[^/]+)'

    @classmethod
    def suitable(cls, url):
        return False if NPORadioFragmentIE.suitable(url) else super(NPORadioIE, cls).suitable(url)


class NPORadioFragmentIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.npo'
    IE_NAME = 'npo.nl:radio:fragment'
    _VALID_URL = 'https?://(?:www\\.)?npo\\.nl/radio/[^/]+/fragment/(?P<id>\\d+)'


class NPODataMidEmbedIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.npo'
    IE_NAME = 'NPODataMidEmbed'


class SchoolTVIE(NPODataMidEmbedIE):
    _module = 'yt_dlp.extractor.npo'
    IE_NAME = 'schooltv'
    _VALID_URL = 'https?://(?:www\\.)?schooltv\\.nl/video/(?P<id>[^/?#&]+)'


class HetKlokhuisIE(NPODataMidEmbedIE):
    _module = 'yt_dlp.extractor.npo'
    IE_NAME = 'hetklokhuis'
    _VALID_URL = 'https?://(?:www\\.)?hetklokhuis\\.nl/[^/]+/\\d+/(?P<id>[^/?#&]+)'


class VPROIE(NPOPlaylistBaseIE):
    _module = 'yt_dlp.extractor.npo'
    IE_NAME = 'vpro'
    IE_DESC = 'npo.nl, ntr.nl, omroepwnl.nl, zapp.nl and npo3.nl'
    _VALID_URL = 'https?://(?:www\\.)?(?:(?:tegenlicht\\.)?vpro|2doc)\\.nl/(?:[^/]+/)*(?P<id>[^/]+)\\.html'

    @classmethod
    def suitable(cls, url):
        return (False if any(ie.suitable(url)
                for ie in (NPOLiveIE, NPORadioIE, NPORadioFragmentIE))
                else super(NPOIE, cls).suitable(url))


class WNLIE(NPOPlaylistBaseIE):
    _module = 'yt_dlp.extractor.npo'
    IE_NAME = 'wnl'
    IE_DESC = 'npo.nl, ntr.nl, omroepwnl.nl, zapp.nl and npo3.nl'
    _VALID_URL = 'https?://(?:www\\.)?omroepwnl\\.nl/video/detail/(?P<id>[^/]+)__\\d+'

    @classmethod
    def suitable(cls, url):
        return (False if any(ie.suitable(url)
                for ie in (NPOLiveIE, NPORadioIE, NPORadioFragmentIE))
                else super(NPOIE, cls).suitable(url))


class NprIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.npr'
    IE_NAME = 'Npr'
    _VALID_URL = 'https?://(?:www\\.)?npr\\.org/(?:sections/[^/]+/)?\\d{4}/\\d{2}/\\d{2}/(?P<id>\\d+)'


class NRKBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.nrk'
    IE_NAME = 'NRKBase'


class NRKIE(NRKBaseIE):
    _module = 'yt_dlp.extractor.nrk'
    IE_NAME = 'NRK'
    _VALID_URL = '(?x)\n                        (?:\n                            nrk:|\n                            https?://\n                                (?:\n                                    (?:www\\.)?nrk\\.no/video/(?:PS\\*|[^_]+_)|\n                                    v8[-.]psapi\\.nrk\\.no/mediaelement/\n                                )\n                            )\n                            (?P<id>[^?\\#&]+)\n                        '


class NRKPlaylistBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.nrk'
    IE_NAME = 'NRKPlaylistBase'


class NRKPlaylistIE(NRKPlaylistBaseIE):
    _module = 'yt_dlp.extractor.nrk'
    IE_NAME = 'NRKPlaylist'
    _VALID_URL = 'https?://(?:www\\.)?nrk\\.no/(?!video|skole)(?:[^/]+/)+(?P<id>[^/]+)'


class NRKSkoleIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.nrk'
    IE_NAME = 'NRKSkole'
    IE_DESC = 'NRK Skole'
    _VALID_URL = 'https?://(?:www\\.)?nrk\\.no/skole/?\\?.*\\bmediaId=(?P<id>\\d+)'


class NRKTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.nrk'
    IE_NAME = 'NRKTV'
    IE_DESC = 'NRK TV and NRK Radio'
    _VALID_URL = 'https?://(?:tv|radio)\\.nrk(?:super)?\\.no/(?:[^/]+/)*(?P<id>[a-zA-Z]{4}\\d{8})'
    age_limit = 6


class NRKTVDirekteIE(NRKTVIE):
    _module = 'yt_dlp.extractor.nrk'
    IE_NAME = 'NRKTVDirekte'
    IE_DESC = 'NRK TV Direkte and NRK Radio Direkte'
    _VALID_URL = 'https?://(?:tv|radio)\\.nrk\\.no/direkte/(?P<id>[^/?#&]+)'


class NRKRadioPodkastIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.nrk'
    IE_NAME = 'NRKRadioPodkast'
    _VALID_URL = 'https?://radio\\.nrk\\.no/pod[ck]ast/(?:[^/]+/)+(?P<id>l_[\\da-f]{8}-[\\da-f]{4}-[\\da-f]{4}-[\\da-f]{4}-[\\da-f]{12})'


class NRKTVEpisodeIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.nrk'
    IE_NAME = 'NRKTVEpisode'
    _VALID_URL = 'https?://tv\\.nrk\\.no/serie/(?P<id>[^/]+/sesong/(?P<season_number>\\d+)/episode/(?P<episode_number>\\d+))'
    age_limit = 6


class NRKTVEpisodesIE(NRKPlaylistBaseIE):
    _module = 'yt_dlp.extractor.nrk'
    IE_NAME = 'NRKTVEpisodes'
    _VALID_URL = 'https?://tv\\.nrk\\.no/program/[Ee]pisodes/[^/]+/(?P<id>\\d+)'


class NRKTVSerieBaseIE(NRKBaseIE):
    _module = 'yt_dlp.extractor.nrk'
    IE_NAME = 'NRKTVSerieBase'


class NRKTVSeasonIE(NRKTVSerieBaseIE):
    _module = 'yt_dlp.extractor.nrk'
    IE_NAME = 'NRKTVSeason'
    _VALID_URL = '(?x)\n                    https?://\n                        (?P<domain>tv|radio)\\.nrk\\.no/\n                        (?P<serie_kind>serie|pod[ck]ast)/\n                        (?P<serie>[^/]+)/\n                        (?:\n                            (?:sesong/)?(?P<id>\\d+)|\n                            sesong/(?P<id_2>[^/?#&]+)\n                        )\n                    '

    @classmethod
    def suitable(cls, url):
        return (False if NRKTVIE.suitable(url) or NRKTVEpisodeIE.suitable(url) or NRKRadioPodkastIE.suitable(url)
                else super(NRKTVSeasonIE, cls).suitable(url))


class NRKTVSeriesIE(NRKTVSerieBaseIE):
    _module = 'yt_dlp.extractor.nrk'
    IE_NAME = 'NRKTVSeries'
    _VALID_URL = 'https?://(?P<domain>(?:tv|radio)\\.nrk|(?:tv\\.)?nrksuper)\\.no/(?P<serie_kind>serie|pod[ck]ast)/(?P<id>[^/]+)'

    @classmethod
    def suitable(cls, url):
        return (
            False if any(ie.suitable(url)
                         for ie in (NRKTVIE, NRKTVEpisodeIE, NRKRadioPodkastIE, NRKTVSeasonIE))
            else super(NRKTVSeriesIE, cls).suitable(url))


class NRLTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.nrl'
    IE_NAME = 'NRLTV'
    _VALID_URL = 'https?://(?:www\\.)?nrl\\.com/tv(/[^/]+)*/(?P<id>[^/?&#]+)'


class NTVCoJpCUIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ntvcojp'
    IE_NAME = 'cu.ntv.co.jp'
    IE_DESC = 'Nippon Television Network'
    _VALID_URL = 'https?://cu\\.ntv\\.co\\.jp/(?!program)(?P<id>[^/?&#]+)'


class NTVDeIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ntvde'
    IE_NAME = 'n-tv.de'
    _VALID_URL = 'https?://(?:www\\.)?n-tv\\.de/mediathek/videos/[^/?#]+/[^/?#]+-article(?P<id>.+)\\.html'


class NTVRuIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ntvru'
    IE_NAME = 'ntv.ru'
    _VALID_URL = 'https?://(?:www\\.)?ntv\\.ru/(?:[^/]+/)*(?P<id>[^/?#&]+)'


class NYTimesBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.nytimes'
    IE_NAME = 'NYTimesBase'


class NYTimesIE(NYTimesBaseIE):
    _module = 'yt_dlp.extractor.nytimes'
    IE_NAME = 'NYTimes'
    _VALID_URL = 'https?://(?:(?:www\\.)?nytimes\\.com/video/(?:[^/]+/)+?|graphics8\\.nytimes\\.com/bcvideo/\\d+(?:\\.\\d+)?/iframe/embed\\.html\\?videoId=)(?P<id>\\d+)'


class NYTimesArticleIE(NYTimesBaseIE):
    _module = 'yt_dlp.extractor.nytimes'
    IE_NAME = 'NYTimesArticle'
    _VALID_URL = 'https?://(?:www\\.)?nytimes\\.com/(.(?<!video))*?/(?:[^/]+/)*(?P<id>[^.]+)(?:\\.html)?'


class NYTimesCookingIE(NYTimesBaseIE):
    _module = 'yt_dlp.extractor.nytimes'
    IE_NAME = 'NYTimesCooking'
    _VALID_URL = 'https?://cooking\\.nytimes\\.com/(?:guid|recip)es/(?P<id>\\d+)'


class NuvidIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.nuvid'
    IE_NAME = 'Nuvid'
    _VALID_URL = 'https?://(?:www|m)\\.nuvid\\.com/video/(?P<id>[0-9]+)'
    age_limit = 18


class NZHeraldIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.nzherald'
    IE_NAME = 'nzherald'
    _VALID_URL = 'https?://(?:www\\.)?nzherald\\.co\\.nz/[\\w\\/-]+\\/(?P<id>[A-Z0-9]+)'


class NZZIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.nzz'
    IE_NAME = 'NZZ'
    _VALID_URL = 'https?://(?:www\\.)?nzz\\.ch/(?:[^/]+/)*[^/?#]+-ld\\.(?P<id>\\d+)'


class OdaTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.odatv'
    IE_NAME = 'OdaTV'
    _VALID_URL = 'https?://(?:www\\.)?odatv\\.com/(?:mob|vid)_video\\.php\\?.*\\bid=(?P<id>[^&]+)'


class OdnoklassnikiIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.odnoklassniki'
    IE_NAME = 'Odnoklassniki'
    _VALID_URL = '(?x)\n                https?://\n                    (?:(?:www|m|mobile)\\.)?\n                    (?:odnoklassniki|ok)\\.ru/\n                    (?:\n                        video(?P<embed>embed)?/|\n                        web-api/video/moviePlayer/|\n                        live/|\n                        dk\\?.*?st\\.mvId=\n                    )\n                    (?P<id>[\\d-]+)\n                '


class OfTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.oftv'
    IE_NAME = 'OfTV'
    _VALID_URL = 'https?://(?:www\\.)?of.tv/video/(?P<id>\\w+)'


class OfTVPlaylistIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.oftv'
    IE_NAME = 'OfTVPlaylist'
    _VALID_URL = 'https?://(?:www\\.)?of.tv/creators/(?P<id>[a-zA-Z0-9-]+)/.?'


class OktoberfestTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.oktoberfesttv'
    IE_NAME = 'OktoberfestTV'
    _VALID_URL = 'https?://(?:www\\.)?oktoberfest-tv\\.de/[^/]+/[^/]+/video/(?P<id>[^/?#]+)'


class OlympicsReplayIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.olympics'
    IE_NAME = 'OlympicsReplay'
    _VALID_URL = 'https?://(?:www\\.)?olympics\\.com(?:/tokyo-2020)?/[a-z]{2}/(?:replay|video)/(?P<id>[^/#&?]+)'


class On24IE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.on24'
    IE_NAME = 'on24'
    IE_DESC = 'ON24'
    _VALID_URL = '(?x)\n                    https?://event\\.on24\\.com/(?:\n                        wcc/r/(?P<id_1>\\d{7})/(?P<key_1>[0-9A-F]{32})|\n                        eventRegistration/(?:console/EventConsoleApollo|EventLobbyServlet\\?target=lobby30)\n                            \\.jsp\\?(?:[^/#?]*&)?eventid=(?P<id_2>\\d{7})[^/#?]*&key=(?P<key_2>[0-9A-F]{32})\n                    )'


class OnDemandKoreaIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ondemandkorea'
    IE_NAME = 'OnDemandKorea'
    _VALID_URL = 'https?://(?:www\\.)?ondemandkorea\\.com/(?P<id>[^/]+)\\.html'


class OneFootballIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.onefootball'
    IE_NAME = 'OneFootball'
    _VALID_URL = 'https?://(?:www\\.)?onefootball\\.com/[a-z]{2}/video/[^/&?#]+-(?P<id>\\d+)'


class OneNewsNZIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.onenewsnz'
    IE_NAME = '1News'
    IE_DESC = '1news.co.nz article videos'
    _VALID_URL = 'https?://(?:www\\.)?(?:1|one)news\\.co\\.nz/\\d+/\\d+/\\d+/(?P<id>[^/?#&]+)'


class OnetIE(OnetBaseIE):
    _module = 'yt_dlp.extractor.onet'
    IE_NAME = 'onet.tv'
    _VALID_URL = 'https?://(?:(?:www\\.)?onet\\.tv|onet100\\.vod\\.pl)/[a-z]/[a-z]+/(?P<display_id>[0-9a-z-]+)/(?P<id>[0-9a-z]+)'


class OnetChannelIE(OnetBaseIE):
    _module = 'yt_dlp.extractor.onet'
    IE_NAME = 'onet.tv:channel'
    _VALID_URL = 'https?://(?:(?:www\\.)?onet\\.tv|onet100\\.vod\\.pl)/[a-z]/(?P<id>[a-z]+)(?:[?#]|$)'


class OnetMVPIE(OnetBaseIE):
    _module = 'yt_dlp.extractor.onet'
    IE_NAME = 'OnetMVP'
    _VALID_URL = 'onetmvp:(?P<id>\\d+\\.\\d+)'


class OnetPlIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.onet'
    IE_NAME = 'onet.pl'
    _VALID_URL = 'https?://(?:[^/]+\\.)?(?:onet|businessinsider\\.com|plejada)\\.pl/(?:[^/]+/)+(?P<id>[0-9a-z]+)'


class OnionStudiosIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.onionstudios'
    IE_NAME = 'OnionStudios'
    _VALID_URL = 'https?://(?:www\\.)?onionstudios\\.com/(?:video(?:s/[^/]+-|/)|embed\\?.*\\bid=)(?P<id>\\d+)(?!-)'


class OoyalaBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ooyala'
    IE_NAME = 'OoyalaBase'


class OoyalaIE(OoyalaBaseIE):
    _module = 'yt_dlp.extractor.ooyala'
    IE_NAME = 'Ooyala'
    _VALID_URL = '(?:ooyala:|https?://.+?\\.ooyala\\.com/.*?(?:embedCode|ec)=)(?P<id>.+?)(&|$)'


class OoyalaExternalIE(OoyalaBaseIE):
    _module = 'yt_dlp.extractor.ooyala'
    IE_NAME = 'OoyalaExternal'
    _VALID_URL = '(?x)\n                    (?:\n                        ooyalaexternal:|\n                        https?://.+?\\.ooyala\\.com/.*?\\bexternalId=\n                    )\n                    (?P<partner_id>[^:]+)\n                    :\n                    (?P<id>.+)\n                    (?:\n                        :|\n                        .*?&pcode=\n                    )\n                    (?P<pcode>.+?)\n                    (?:&|$)\n                    '


class OpencastBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.opencast'
    IE_NAME = 'OpencastBase'


class OpencastIE(OpencastBaseIE):
    _module = 'yt_dlp.extractor.opencast'
    IE_NAME = 'Opencast'
    _VALID_URL = '(?x)\n                    https?://(?P<host>(?:\n                            opencast\\.informatik\\.kit\\.edu|\n                            electures\\.uni-muenster\\.de|\n                            oc-presentation\\.ltcc\\.tuwien\\.ac\\.at|\n                            medien\\.ph-noe\\.ac\\.at|\n                            oc-video\\.ruhr-uni-bochum\\.de|\n                            oc-video1\\.ruhr-uni-bochum\\.de|\n                            opencast\\.informatik\\.uni-goettingen\\.de|\n                            heicast\\.uni-heidelberg\\.de|\n                            opencast\\.hawk\\.de:8080|\n                            opencast\\.hs-osnabrueck\\.de|\n                            video[0-9]+\\.virtuos\\.uni-osnabrueck\\.de|\n                            opencast\\.uni-koeln\\.de|\n                            media\\.opencast\\.hochschule-rhein-waal\\.de|\n                            matterhorn\\.dce\\.harvard\\.edu|\n                            hs-harz\\.opencast\\.uni-halle\\.de|\n                            videocampus\\.urz\\.uni-leipzig\\.de|\n                            media\\.uct\\.ac\\.za|\n                            vid\\.igb\\.illinois\\.edu|\n                            cursosabertos\\.c3sl\\.ufpr\\.br|\n                            mcmedia\\.missioncollege\\.org|\n                            clases\\.odon\\.edu\\.uy\n                        ))/paella/ui/watch.html\\?.*?\n                    id=(?P<id>[\\da-fA-F]{8}-[\\da-fA-F]{4}-[\\da-fA-F]{4}-[\\da-fA-F]{4}-[\\da-fA-F]{12})\n                    '


class OpencastPlaylistIE(OpencastBaseIE):
    _module = 'yt_dlp.extractor.opencast'
    IE_NAME = 'OpencastPlaylist'
    _VALID_URL = '(?x)\n                            https?://(?P<host>(?:\n                            opencast\\.informatik\\.kit\\.edu|\n                            electures\\.uni-muenster\\.de|\n                            oc-presentation\\.ltcc\\.tuwien\\.ac\\.at|\n                            medien\\.ph-noe\\.ac\\.at|\n                            oc-video\\.ruhr-uni-bochum\\.de|\n                            oc-video1\\.ruhr-uni-bochum\\.de|\n                            opencast\\.informatik\\.uni-goettingen\\.de|\n                            heicast\\.uni-heidelberg\\.de|\n                            opencast\\.hawk\\.de:8080|\n                            opencast\\.hs-osnabrueck\\.de|\n                            video[0-9]+\\.virtuos\\.uni-osnabrueck\\.de|\n                            opencast\\.uni-koeln\\.de|\n                            media\\.opencast\\.hochschule-rhein-waal\\.de|\n                            matterhorn\\.dce\\.harvard\\.edu|\n                            hs-harz\\.opencast\\.uni-halle\\.de|\n                            videocampus\\.urz\\.uni-leipzig\\.de|\n                            media\\.uct\\.ac\\.za|\n                            vid\\.igb\\.illinois\\.edu|\n                            cursosabertos\\.c3sl\\.ufpr\\.br|\n                            mcmedia\\.missioncollege\\.org|\n                            clases\\.odon\\.edu\\.uy\n                        ))/engage/ui/index.html\\?.*?\n                            epFrom=(?P<id>[\\da-fA-F]{8}-[\\da-fA-F]{4}-[\\da-fA-F]{4}-[\\da-fA-F]{4}-[\\da-fA-F]{12})\n                    '


class OpenRecBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.openrec'
    IE_NAME = 'OpenRecBase'


class OpenRecIE(OpenRecBaseIE):
    _module = 'yt_dlp.extractor.openrec'
    IE_NAME = 'openrec'
    _VALID_URL = 'https?://(?:www\\.)?openrec\\.tv/live/(?P<id>[^/]+)'


class OpenRecCaptureIE(OpenRecBaseIE):
    _module = 'yt_dlp.extractor.openrec'
    IE_NAME = 'openrec:capture'
    _VALID_URL = 'https?://(?:www\\.)?openrec\\.tv/capture/(?P<id>[^/]+)'


class OpenRecMovieIE(OpenRecBaseIE):
    _module = 'yt_dlp.extractor.openrec'
    IE_NAME = 'openrec:movie'
    _VALID_URL = 'https?://(?:www\\.)?openrec\\.tv/movie/(?P<id>[^/]+)'


class OraTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ora'
    IE_NAME = 'OraTV'
    _VALID_URL = 'https?://(?:www\\.)?(?:ora\\.tv|unsafespeech\\.com)/([^/]+/)*(?P<id>[^/\\?#]+)'


class ORFTVthekIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.orf'
    IE_NAME = 'orf:tvthek'
    IE_DESC = 'ORF TVthek'
    _VALID_URL = '(?P<url>https?://tvthek\\.orf\\.at/(?:(?:[^/]+/){2}){1,2}(?P<id>\\d+))(/[^/]+/(?P<vid>\\d+))?(?:$|[?#])'


class ORFFM4StoryIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.orf'
    IE_NAME = 'orf:fm4:story'
    IE_DESC = 'fm4.orf.at stories'
    _VALID_URL = 'https?://fm4\\.orf\\.at/stories/(?P<id>\\d+)'


class ORFRadioIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.orf'
    IE_NAME = 'orf:radio'
    _VALID_URL = '(?x)\n        https?://(?:\n            (?P<station>fm4|noe|wien|burgenland|ooe|steiermark|kaernten|salzburg|tirol|vorarlberg|oe3|oe1)\\.orf\\.at/player|\n            radiothek\\.orf\\.at/(?P<station2>fm4|noe|wien|burgenland|ooe|steiermark|kaernten|salzburg|tirol|vorarlberg|oe3|oe1)\n        )/(?P<date>[0-9]+)/(?P<show>\\w+)'


class ORFIPTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.orf'
    IE_NAME = 'orf:iptv'
    IE_DESC = 'iptv.ORF.at'
    _VALID_URL = 'https?://iptv\\.orf\\.at/(?:#/)?stories/(?P<id>\\d+)'


class OutsideTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.outsidetv'
    IE_NAME = 'OutsideTV'
    _VALID_URL = 'https?://(?:www\\.)?outsidetv\\.com/(?:[^/]+/)*?play/[a-zA-Z0-9]{8}/\\d+/\\d+/(?P<id>[a-zA-Z0-9]{8})'


class PacktPubBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.packtpub'
    IE_NAME = 'PacktPubBase'


class PacktPubIE(PacktPubBaseIE):
    _module = 'yt_dlp.extractor.packtpub'
    IE_NAME = 'PacktPub'
    _VALID_URL = 'https?://(?:(?:www\\.)?packtpub\\.com/mapt|subscription\\.packtpub\\.com)/video/[^/]+/(?P<course_id>\\d+)/(?P<chapter_id>[^/]+)/(?P<id>[^/]+)(?:/(?P<display_id>[^/?&#]+))?'
    _NETRC_MACHINE = 'packtpub'


class PacktPubCourseIE(PacktPubBaseIE):
    _module = 'yt_dlp.extractor.packtpub'
    IE_NAME = 'PacktPubCourse'
    _VALID_URL = '(?P<url>https?://(?:(?:www\\.)?packtpub\\.com/mapt|subscription\\.packtpub\\.com)/video/[^/]+/(?P<id>\\d+))'

    @classmethod
    def suitable(cls, url):
        return False if PacktPubIE.suitable(url) else super(
            PacktPubCourseIE, cls).suitable(url)


class PalcoMP3BaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.palcomp3'
    IE_NAME = 'PalcoMP3Base'


class PalcoMP3IE(PalcoMP3BaseIE):
    _module = 'yt_dlp.extractor.palcomp3'
    IE_NAME = 'PalcoMP3:song'
    _VALID_URL = 'https?://(?:www\\.)?palcomp3\\.com(?:\\.br)?/(?P<artist>[^/]+)/(?P<id>[^/?&#]+)'

    @classmethod
    def suitable(cls, url):
        return False if PalcoMP3VideoIE.suitable(url) else super(PalcoMP3IE, cls).suitable(url)


class PalcoMP3ArtistIE(PalcoMP3BaseIE):
    _module = 'yt_dlp.extractor.palcomp3'
    IE_NAME = 'PalcoMP3:artist'
    _VALID_URL = 'https?://(?:www\\.)?palcomp3\\.com(?:\\.br)?/(?P<id>[^/?&#]+)'

    @classmethod
    def suitable(cls, url):
        return False if PalcoMP3IE._match_valid_url(url) else super(PalcoMP3ArtistIE, cls).suitable(url)


class PalcoMP3VideoIE(PalcoMP3BaseIE):
    _module = 'yt_dlp.extractor.palcomp3'
    IE_NAME = 'PalcoMP3:video'
    _VALID_URL = 'https?://(?:www\\.)?palcomp3\\.com(?:\\.br)?/(?P<artist>[^/]+)/(?P<id>[^/?&#]+)/?#clipe'


class PandoraTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.pandoratv'
    IE_NAME = 'pandora.tv'
    IE_DESC = '판도라TV'
    _VALID_URL = '(?x)\n                        https?://\n                            (?:\n                                (?:www\\.)?pandora\\.tv/view/(?P<user_id>[^/]+)/(?P<id>\\d+)|  # new format\n                                (?:.+?\\.)?channel\\.pandora\\.tv/channel/video\\.ptv\\?|        # old format\n                                m\\.pandora\\.tv/?\\?                                          # mobile\n                            )\n                    '


class PanoptoBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.panopto'
    IE_NAME = 'PanoptoBase'


class PanoptoIE(PanoptoBaseIE):
    _module = 'yt_dlp.extractor.panopto'
    IE_NAME = 'Panopto'
    _VALID_URL = '(?P<base_url>https?://[\\w.-]+\\.panopto.(?:com|eu)/Panopto)/Pages/(Viewer|Embed)\\.aspx.*(?:\\?|&)id=(?P<id>[a-f0-9-]+)'

    @classmethod
    def suitable(cls, url):
        return False if PanoptoPlaylistIE.suitable(url) else super().suitable(url)


class PanoptoListIE(PanoptoBaseIE):
    _module = 'yt_dlp.extractor.panopto'
    IE_NAME = 'PanoptoList'
    _VALID_URL = '(?P<base_url>https?://[\\w.-]+\\.panopto.(?:com|eu)/Panopto)/Pages/Sessions/List\\.aspx'


class PanoptoPlaylistIE(PanoptoBaseIE):
    _module = 'yt_dlp.extractor.panopto'
    IE_NAME = 'PanoptoPlaylist'
    _VALID_URL = '(?P<base_url>https?://[\\w.-]+\\.panopto.(?:com|eu)/Panopto)/Pages/(Viewer|Embed)\\.aspx.*(?:\\?|&)pid=(?P<id>[a-f0-9-]+)'


class ParamountPlusSeriesIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.paramountplus'
    IE_NAME = 'ParamountPlusSeries'
    _VALID_URL = 'https?://(?:www\\.)?paramountplus\\.com/shows/(?P<id>[a-zA-Z0-9-_]+)/?(?:[#?]|$)'


class ParlerIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.parler'
    IE_NAME = 'Parler'
    IE_DESC = 'Posts on parler.com'
    _VALID_URL = 'https://parler\\.com/feed/(?P<id>[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12})'


class ParlviewIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.parlview'
    IE_NAME = 'Parlview'
    _VALID_URL = 'https?://(?:www\\.)?parlview\\.aph\\.gov\\.au/(?:[^/]+)?\\bvideoID=(?P<id>\\d{6})'


class PatreonBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.patreon'
    IE_NAME = 'PatreonBase'


class PatreonIE(PatreonBaseIE):
    _module = 'yt_dlp.extractor.patreon'
    IE_NAME = 'Patreon'
    _VALID_URL = 'https?://(?:www\\.)?patreon\\.com/(?:creation\\?hid=|posts/(?:[\\w-]+-)?)(?P<id>\\d+)'


class PatreonCampaignIE(PatreonBaseIE):
    _module = 'yt_dlp.extractor.patreon'
    IE_NAME = 'PatreonCampaign'
    _VALID_URL = 'https?://(?:www\\.)?patreon\\.com/(?!rss)(?:(?:m/(?P<campaign_id>\\d+))|(?P<vanity>[-\\w]+))'

    @classmethod
    def suitable(cls, url):
        return False if PatreonIE.suitable(url) else super(PatreonCampaignIE, cls).suitable(url)


class PBSIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.pbs'
    IE_NAME = 'pbs'
    IE_DESC = 'Public Broadcasting Service (PBS) and member stations: PBS: Public Broadcasting Service, APT - Alabama Public Television (WBIQ), GPB/Georgia Public Broadcasting (WGTV), Mississippi Public Broadcasting (WMPN), Nashville Public Television (WNPT), WFSU-TV (WFSU), WSRE (WSRE), WTCI (WTCI), WPBA/Channel 30 (WPBA), Alaska Public Media (KAKM), Arizona PBS (KAET), KNME-TV/Channel 5 (KNME), Vegas PBS (KLVX), AETN/ARKANSAS ETV NETWORK (KETS), KET (WKLE), WKNO/Channel 10 (WKNO), LPB/LOUISIANA PUBLIC BROADCASTING (WLPB), OETA (KETA), Ozarks Public Television (KOZK), WSIU Public Broadcasting (WSIU), KEET TV (KEET), KIXE/Channel 9 (KIXE), KPBS San Diego (KPBS), KQED (KQED), KVIE Public Television (KVIE), PBS SoCal/KOCE (KOCE), ValleyPBS (KVPT), CONNECTICUT PUBLIC TELEVISION (WEDH), KNPB Channel 5 (KNPB), SOPTV (KSYS), Rocky Mountain PBS (KRMA), KENW-TV3 (KENW), KUED Channel 7 (KUED), Wyoming PBS (KCWC), Colorado Public Television / KBDI 12 (KBDI), KBYU-TV (KBYU), Thirteen/WNET New York (WNET), WGBH/Channel 2 (WGBH), WGBY (WGBY), NJTV Public Media NJ (WNJT), WLIW21 (WLIW), mpt/Maryland Public Television (WMPB), WETA Television and Radio (WETA), WHYY (WHYY), PBS 39 (WLVT), WVPT - Your Source for PBS and More! (WVPT), Howard University Television (WHUT), WEDU PBS (WEDU), WGCU Public Media (WGCU), WPBT2 (WPBT), WUCF TV (WUCF), WUFT/Channel 5 (WUFT), WXEL/Channel 42 (WXEL), WLRN/Channel 17 (WLRN), WUSF Public Broadcasting (WUSF), ETV (WRLK), UNC-TV (WUNC), PBS Hawaii - Oceanic Cable Channel 10 (KHET), Idaho Public Television (KAID), KSPS (KSPS), OPB (KOPB), KWSU/Channel 10 & KTNW/Channel 31 (KWSU), WILL-TV (WILL), Network Knowledge - WSEC/Springfield (WSEC), WTTW11 (WTTW), Iowa Public Television/IPTV (KDIN), Nine Network (KETC), PBS39 Fort Wayne (WFWA), WFYI Indianapolis (WFYI), Milwaukee Public Television (WMVS), WNIN (WNIN), WNIT Public Television (WNIT), WPT (WPNE), WVUT/Channel 22 (WVUT), WEIU/Channel 51 (WEIU), WQPT-TV (WQPT), WYCC PBS Chicago (WYCC), WIPB-TV (WIPB), WTIU (WTIU), CET  (WCET), ThinkTVNetwork (WPTD), WBGU-TV (WBGU), WGVU TV (WGVU), NET1 (KUON), Pioneer Public Television (KWCM), SDPB Television (KUSD), TPT (KTCA), KSMQ (KSMQ), KPTS/Channel 8 (KPTS), KTWU/Channel 11 (KTWU), East Tennessee PBS (WSJK), WCTE-TV (WCTE), WLJT, Channel 11 (WLJT), WOSU TV (WOSU), WOUB/WOUC (WOUB), WVPB (WVPB), WKYU-PBS (WKYU), KERA 13 (KERA), MPBN (WCBB), Mountain Lake PBS (WCFE), NHPTV (WENH), Vermont PBS (WETK), witf (WITF), WQED Multimedia (WQED), WMHT Educational Telecommunications (WMHT), Q-TV (WDCQ), WTVS Detroit Public TV (WTVS), CMU Public Television (WCMU), WKAR-TV (WKAR), WNMU-TV Public TV 13 (WNMU), WDSE - WRPT (WDSE), WGTE TV (WGTE), Lakeland Public Television (KAWE), KMOS-TV - Channels 6.1, 6.2 and 6.3 (KMOS), MontanaPBS (KUSM), KRWG/Channel 22 (KRWG), KACV (KACV), KCOS/Channel 13 (KCOS), WCNY/Channel 24 (WCNY), WNED (WNED), WPBS (WPBS), WSKG Public TV (WSKG), WXXI (WXXI), WPSU (WPSU), WVIA Public Media Studios (WVIA), WTVI (WTVI), Western Reserve PBS (WNEO), WVIZ/PBS ideastream (WVIZ), KCTS 9 (KCTS), Basin PBS (KPBT), KUHT / Channel 8 (KUHT), KLRN (KLRN), KLRU (KLRU), WTJX Channel 12 (WTJX), WCVE PBS (WCVE), KBTC Public Television (KBTC)'
    _VALID_URL = '(?x)https?://\n        (?:\n           # Direct video URL\n           (?:(?:video|www|player)\\.pbs\\.org|video\\.aptv\\.org|video\\.gpb\\.org|video\\.mpbonline\\.org|video\\.wnpt\\.org|video\\.wfsu\\.org|video\\.wsre\\.org|video\\.wtcitv\\.org|video\\.pba\\.org|video\\.alaskapublic\\.org|video\\.azpbs\\.org|portal\\.knme\\.org|video\\.vegaspbs\\.org|watch\\.aetn\\.org|video\\.ket\\.org|video\\.wkno\\.org|video\\.lpb\\.org|videos\\.oeta\\.tv|video\\.optv\\.org|watch\\.wsiu\\.org|video\\.keet\\.org|pbs\\.kixe\\.org|video\\.kpbs\\.org|video\\.kqed\\.org|vids\\.kvie\\.org|video\\.pbssocal\\.org|video\\.valleypbs\\.org|video\\.cptv\\.org|watch\\.knpb\\.org|video\\.soptv\\.org|video\\.rmpbs\\.org|video\\.kenw\\.org|video\\.kued\\.org|video\\.wyomingpbs\\.org|video\\.cpt12\\.org|video\\.kbyueleven\\.org|video\\.thirteen\\.org|video\\.wgbh\\.org|video\\.wgby\\.org|watch\\.njtvonline\\.org|watch\\.wliw\\.org|video\\.mpt\\.tv|watch\\.weta\\.org|video\\.whyy\\.org|video\\.wlvt\\.org|video\\.wvpt\\.net|video\\.whut\\.org|video\\.wedu\\.org|video\\.wgcu\\.org|video\\.wpbt2\\.org|video\\.wucftv\\.org|video\\.wuft\\.org|watch\\.wxel\\.org|video\\.wlrn\\.org|video\\.wusf\\.usf\\.edu|video\\.scetv\\.org|video\\.unctv\\.org|video\\.pbshawaii\\.org|video\\.idahoptv\\.org|video\\.ksps\\.org|watch\\.opb\\.org|watch\\.nwptv\\.org|video\\.will\\.illinois\\.edu|video\\.networkknowledge\\.tv|video\\.wttw\\.com|video\\.iptv\\.org|video\\.ninenet\\.org|video\\.wfwa\\.org|video\\.wfyi\\.org|video\\.mptv\\.org|video\\.wnin\\.org|video\\.wnit\\.org|video\\.wpt\\.org|video\\.wvut\\.org|video\\.weiu\\.net|video\\.wqpt\\.org|video\\.wycc\\.org|video\\.wipb\\.org|video\\.indianapublicmedia\\.org|watch\\.cetconnect\\.org|video\\.thinktv\\.org|video\\.wbgu\\.org|video\\.wgvu\\.org|video\\.netnebraska\\.org|video\\.pioneer\\.org|watch\\.sdpb\\.org|video\\.tpt\\.org|watch\\.ksmq\\.org|watch\\.kpts\\.org|watch\\.ktwu\\.org|watch\\.easttennesseepbs\\.org|video\\.wcte\\.tv|video\\.wljt\\.org|video\\.wosu\\.org|video\\.woub\\.org|video\\.wvpublic\\.org|video\\.wkyupbs\\.org|video\\.kera\\.org|video\\.mpbn\\.net|video\\.mountainlake\\.org|video\\.nhptv\\.org|video\\.vpt\\.org|video\\.witf\\.org|watch\\.wqed\\.org|video\\.wmht\\.org|video\\.deltabroadcasting\\.org|video\\.dptv\\.org|video\\.wcmu\\.org|video\\.wkar\\.org|wnmuvideo\\.nmu\\.edu|video\\.wdse\\.org|video\\.wgte\\.org|video\\.lptv\\.org|video\\.kmos\\.org|watch\\.montanapbs\\.org|video\\.krwg\\.org|video\\.kacvtv\\.org|video\\.kcostv\\.org|video\\.wcny\\.org|video\\.wned\\.org|watch\\.wpbstv\\.org|video\\.wskg\\.org|video\\.wxxi\\.org|video\\.wpsu\\.org|on-demand\\.wvia\\.org|video\\.wtvi\\.org|video\\.westernreservepublicmedia\\.org|video\\.ideastream\\.org|video\\.kcts9\\.org|video\\.basinpbs\\.org|video\\.houstonpbs\\.org|video\\.klrn\\.org|video\\.klru\\.tv|video\\.wtjx\\.org|video\\.ideastations\\.org|video\\.kbtc\\.org)/(?:(?:vir|port)alplayer|video)/(?P<id>[0-9]+)(?:[?/]|$) |\n           # Article with embedded player (or direct video)\n           (?:www\\.)?pbs\\.org/(?:[^/]+/){1,5}(?P<presumptive_id>[^/]+?)(?:\\.html)?/?(?:$|[?\\#]) |\n           # Player\n           (?:video|player)\\.pbs\\.org/(?:widget/)?partnerplayer/(?P<player_id>[^/]+)\n        )\n    '
    age_limit = 10


class PearVideoIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.pearvideo'
    IE_NAME = 'PearVideo'
    _VALID_URL = 'https?://(?:www\\.)?pearvideo\\.com/video_(?P<id>\\d+)'


class PeekVidsIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.peekvids'
    IE_NAME = 'PeekVids'
    _VALID_URL = '(?x)\n        https?://(?:www\\.)?peekvids\\.com/\n        (?:(?:[^/?#]+/){2}|embed/?\\?(?:[^#]*&)?v=)\n        (?P<id>[^/?&#]*)\n    '
    age_limit = 18


class PlayVidsIE(PeekVidsIE):
    _module = 'yt_dlp.extractor.peekvids'
    IE_NAME = 'PlayVids'
    _VALID_URL = 'https?://(?:www\\.)?playvids\\.com/(?:embed/|[^/]{2}/)?(?P<id>[^/?#]*)'
    age_limit = 18


class PeerTubeIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.peertube'
    IE_NAME = 'PeerTube'
    _VALID_URL = '(?x)\n                    (?:\n                        peertube:(?P<host>[^:]+):|\n                        https?://(?P<host_2>(?:\n                            # Taken from https://instances.joinpeertube.org/instances\n                            40two\\.tube|\n                            a\\.metube\\.ch|\n                            advtv\\.ml|\n                            algorithmic\\.tv|\n                            alimulama\\.com|\n                            arcana\\.fun|\n                            archive\\.vidicon\\.org|\n                            artefac-paris\\.tv|\n                            auf1\\.eu|\n                            battlepenguin\\.video|\n                            beertube\\.epgn\\.ch|\n                            befree\\.nohost\\.me|\n                            bideoak\\.argia\\.eus|\n                            birkeundnymphe\\.de|\n                            bitcointv\\.com|\n                            cattube\\.org|\n                            clap\\.nerv-project\\.eu|\n                            climatejustice\\.video|\n                            comf\\.tube|\n                            conspiracydistillery\\.com|\n                            darkvapor\\.nohost\\.me|\n                            daschauher\\.aksel\\.rocks|\n                            digitalcourage\\.video|\n                            dreiecksnebel\\.alex-detsch\\.de|\n                            eduvid\\.org|\n                            evangelisch\\.video|\n                            exo\\.tube|\n                            fair\\.tube|\n                            fediverse\\.tv|\n                            film\\.k-prod\\.fr|\n                            flim\\.txmn\\.tk|\n                            fotogramas\\.politicaconciencia\\.org|\n                            ftsi\\.ru|\n                            gary\\.vger\\.cloud|\n                            graeber\\.video|\n                            greatview\\.video|\n                            grypstube\\.uni-greifswald\\.de|\n                            highvoltage\\.tv|\n                            hpstube\\.fr|\n                            htp\\.live|\n                            hyperreal\\.tube|\n                            juggling\\.digital|\n                            kino\\.kompot\\.si|\n                            kino\\.schuerz\\.at|\n                            kinowolnosc\\.pl|\n                            kirche\\.peertube-host\\.de|\n                            kodcast\\.com|\n                            kolektiva\\.media|\n                            kraut\\.zone|\n                            kumi\\.tube|\n                            lastbreach\\.tv|\n                            lepetitmayennais\\.fr\\.nf|\n                            lexx\\.impa\\.me|\n                            libertynode\\.tv|\n                            libra\\.syntazia\\.org|\n                            libremedia\\.video|\n                            live\\.libratoi\\.org|\n                            live\\.nanao\\.moe|\n                            live\\.toobnix\\.org|\n                            livegram\\.net|\n                            lolitube\\.freedomchan\\.moe|\n                            lucarne\\.balsamine\\.be|\n                            maindreieck-tv\\.de|\n                            mani\\.tube|\n                            manicphase\\.me|\n                            media\\.fsfe\\.org|\n                            media\\.gzevd\\.de|\n                            media\\.inno3\\.cricket|\n                            media\\.kaitaia\\.life|\n                            media\\.krashboyz\\.org|\n                            media\\.over-world\\.org|\n                            media\\.skewed\\.de|\n                            media\\.undeadnetwork\\.de|\n                            medias\\.pingbase\\.net|\n                            melsungen\\.peertube-host\\.de|\n                            mirametube\\.fr|\n                            mojotube\\.net|\n                            monplaisirtube\\.ddns\\.net|\n                            mountaintown\\.video|\n                            my\\.bunny\\.cafe|\n                            myfreetube\\.de|\n                            mytube\\.kn-cloud\\.de|\n                            mytube\\.madzel\\.de|\n                            myworkoutarenapeertube\\.cf|\n                            nanawel-peertube\\.dyndns\\.org|\n                            nastub\\.cz|\n                            offenes\\.tv|\n                            orgdup\\.media|\n                            ovaltube\\.codinglab\\.ch|\n                            p2ptv\\.ru|\n                            p\\.eertu\\.be|\n                            p\\.lu|\n                            peer\\.azurs\\.fr|\n                            peertube1\\.zeteo\\.me|\n                            peertube\\.020\\.pl|\n                            peertube\\.0x5e\\.eu|\n                            peertube\\.alpharius\\.io|\n                            peertube\\.am-networks\\.fr|\n                            peertube\\.anduin\\.net|\n                            peertube\\.anzui\\.dev|\n                            peertube\\.arbleizez\\.bzh|\n                            peertube\\.art3mis\\.de|\n                            peertube\\.atilla\\.org|\n                            peertube\\.atsuchan\\.page|\n                            peertube\\.aukfood\\.net|\n                            peertube\\.aventer\\.biz|\n                            peertube\\.b38\\.rural-it\\.org|\n                            peertube\\.beeldengeluid\\.nl|\n                            peertube\\.be|\n                            peertube\\.bgzashtita\\.es|\n                            peertube\\.bitsandlinux\\.com|\n                            peertube\\.biz|\n                            peertube\\.boba\\.best|\n                            peertube\\.br0\\.fr|\n                            peertube\\.bridaahost\\.ynh\\.fr|\n                            peertube\\.bubbletea\\.dev|\n                            peertube\\.bubuit\\.net|\n                            peertube\\.cabaal\\.net|\n                            peertube\\.cats-home\\.net|\n                            peertube\\.chemnitz\\.freifunk\\.net|\n                            peertube\\.chevro\\.fr|\n                            peertube\\.chrisspiegl\\.com|\n                            peertube\\.chtisurel\\.net|\n                            peertube\\.cipherbliss\\.com|\n                            peertube\\.cloud\\.sans\\.pub|\n                            peertube\\.cpge-brizeux\\.fr|\n                            peertube\\.ctseuro\\.com|\n                            peertube\\.cuatrolibertades\\.org|\n                            peertube\\.cybercirujas\\.club|\n                            peertube\\.cythin\\.com|\n                            peertube\\.davigge\\.com|\n                            peertube\\.dc\\.pini\\.fr|\n                            peertube\\.debian\\.social|\n                            peertube\\.demonix\\.fr|\n                            peertube\\.designersethiques\\.org|\n                            peertube\\.desmu\\.fr|\n                            peertube\\.devloprog\\.org|\n                            peertube\\.devol\\.it|\n                            peertube\\.dtmf\\.ca|\n                            peertube\\.ecologie\\.bzh|\n                            peertube\\.eu\\.org|\n                            peertube\\.european-pirates\\.eu|\n                            peertube\\.euskarabildua\\.eus|\n                            peertube\\.fenarinarsa\\.com|\n                            peertube\\.fomin\\.site|\n                            peertube\\.forsud\\.be|\n                            peertube\\.francoispelletier\\.org|\n                            peertube\\.freenet\\.ru|\n                            peertube\\.freetalklive\\.com|\n                            peertube\\.functional\\.cafe|\n                            peertube\\.gardeludwig\\.fr|\n                            peertube\\.gargantia\\.fr|\n                            peertube\\.gcfamily\\.fr|\n                            peertube\\.genma\\.fr|\n                            peertube\\.get-racing\\.de|\n                            peertube\\.gidikroon\\.eu|\n                            peertube\\.gruezishop\\.ch|\n                            peertube\\.habets\\.house|\n                            peertube\\.hackerfraternity\\.org|\n                            peertube\\.ichigo\\.everydayimshuflin\\.com|\n                            peertube\\.ignifi\\.me|\n                            peertube\\.inapurna\\.org|\n                            peertube\\.informaction\\.info|\n                            peertube\\.interhop\\.org|\n                            peertube\\.iselfhost\\.com|\n                            peertube\\.it|\n                            peertube\\.jensdiemer\\.de|\n                            peertube\\.joffreyverd\\.fr|\n                            peertube\\.kalua\\.im|\n                            peertube\\.kathryl\\.fr|\n                            peertube\\.keazilla\\.net|\n                            peertube\\.klaewyss\\.fr|\n                            peertube\\.kodcast\\.com|\n                            peertube\\.kx\\.studio|\n                            peertube\\.lagvoid\\.com|\n                            peertube\\.lavallee\\.tech|\n                            peertube\\.le5emeaxe\\.fr|\n                            peertube\\.lestutosdeprocessus\\.fr|\n                            peertube\\.librenet\\.co\\.za|\n                            peertube\\.logilab\\.fr|\n                            peertube\\.louisematic\\.site|\n                            peertube\\.luckow\\.org|\n                            peertube\\.luga\\.at|\n                            peertube\\.lyceeconnecte\\.fr|\n                            peertube\\.manalejandro\\.com|\n                            peertube\\.marud\\.fr|\n                            peertube\\.mattone\\.net|\n                            peertube\\.maxweiss\\.io|\n                            peertube\\.monlycee\\.net|\n                            peertube\\.mxinfo\\.fr|\n                            peertube\\.myrasp\\.eu|\n                            peertube\\.nebelcloud\\.de|\n                            peertube\\.netzbegruenung\\.de|\n                            peertube\\.newsocial\\.tech|\n                            peertube\\.nicolastissot\\.fr|\n                            peertube\\.nz|\n                            peertube\\.offerman\\.com|\n                            peertube\\.opencloud\\.lu|\n                            peertube\\.orthus\\.link|\n                            peertube\\.patapouf\\.xyz|\n                            peertube\\.pi2\\.dev|\n                            peertube\\.plataformess\\.org|\n                            peertube\\.pl|\n                            peertube\\.portaesgnos\\.org|\n                            peertube\\.r2\\.enst\\.fr|\n                            peertube\\.r5c3\\.fr|\n                            peertube\\.radres\\.xyz|\n                            peertube\\.red|\n                            peertube\\.robonomics\\.network|\n                            peertube\\.rtnkv\\.cloud|\n                            peertube\\.runfox\\.tk|\n                            peertube\\.satoshishop\\.de|\n                            peertube\\.scic-tetris\\.org|\n                            peertube\\.securitymadein\\.lu|\n                            peertube\\.semweb\\.pro|\n                            peertube\\.social\\.my-wan\\.de|\n                            peertube\\.soykaf\\.org|\n                            peertube\\.stefofficiel\\.me|\n                            peertube\\.stream|\n                            peertube\\.su|\n                            peertube\\.swrs\\.net|\n                            peertube\\.takeko\\.cyou|\n                            peertube\\.tangentfox\\.com|\n                            peertube\\.taxinachtegel\\.de|\n                            peertube\\.thenewoil\\.xyz|\n                            peertube\\.ti-fr\\.com|\n                            peertube\\.tiennot\\.net|\n                            peertube\\.troback\\.com|\n                            peertube\\.tspu\\.edu\\.ru|\n                            peertube\\.tux\\.ovh|\n                            peertube\\.tv|\n                            peertube\\.tweb\\.tv|\n                            peertube\\.ucy\\.de|\n                            peertube\\.underworld\\.fr|\n                            peertube\\.us\\.to|\n                            peertube\\.ventresmous\\.fr|\n                            peertube\\.vlaki\\.cz|\n                            peertube\\.w\\.utnw\\.de|\n                            peertube\\.westring\\.digital|\n                            peertube\\.xwiki\\.com|\n                            peertube\\.zoz-serv\\.org|\n                            peervideo\\.ru|\n                            periscope\\.numenaute\\.org|\n                            perron-tube\\.de|\n                            petitlutinartube\\.fr|\n                            phijkchu\\.com|\n                            pierre\\.tube|\n                            piraten\\.space|\n                            play\\.rosano\\.ca|\n                            player\\.ojamajo\\.moe|\n                            plextube\\.nl|\n                            pocketnetpeertube1\\.nohost\\.me|\n                            pocketnetpeertube3\\.nohost\\.me|\n                            pocketnetpeertube4\\.nohost\\.me|\n                            pocketnetpeertube5\\.nohost\\.me|\n                            pocketnetpeertube6\\.nohost\\.me|\n                            pt\\.24-7\\.ro|\n                            pt\\.apathy\\.top|\n                            pt\\.diaspodon\\.fr|\n                            pt\\.fedi\\.tech|\n                            pt\\.maciej\\.website|\n                            ptb\\.lunarviews\\.net|\n                            ptmir1\\.inter21\\.net|\n                            ptmir2\\.inter21\\.net|\n                            ptmir3\\.inter21\\.net|\n                            ptmir4\\.inter21\\.net|\n                            ptmir5\\.inter21\\.net|\n                            ptube\\.horsentiers\\.fr|\n                            ptube\\.xmanifesto\\.club|\n                            queermotion\\.org|\n                            re-wizja\\.re-medium\\.com|\n                            regarder\\.sans\\.pub|\n                            ruraletv\\.ovh|\n                            s1\\.gegenstimme\\.tv|\n                            s2\\.veezee\\.tube|\n                            sdmtube\\.fr|\n                            sender-fm\\.veezee\\.tube|\n                            serv1\\.wiki-tube\\.de|\n                            serv3\\.wiki-tube\\.de|\n                            sickstream\\.net|\n                            sleepy\\.tube|\n                            sovran\\.video|\n                            spectra\\.video|\n                            stream\\.elven\\.pw|\n                            stream\\.k-prod\\.fr|\n                            stream\\.shahab\\.nohost\\.me|\n                            streamsource\\.video|\n                            studios\\.racer159\\.com|\n                            testtube\\.florimond\\.eu|\n                            tgi\\.hosted\\.spacebear\\.ee|\n                            thaitube\\.in\\.th|\n                            the\\.jokertv\\.eu|\n                            theater\\.ethernia\\.net|\n                            thecool\\.tube|\n                            tilvids\\.com|\n                            toob\\.bub\\.org|\n                            tpaw\\.video|\n                            truetube\\.media|\n                            tuba\\.lhub\\.pl|\n                            tube-aix-marseille\\.beta\\.education\\.fr|\n                            tube-amiens\\.beta\\.education\\.fr|\n                            tube-besancon\\.beta\\.education\\.fr|\n                            tube-bordeaux\\.beta\\.education\\.fr|\n                            tube-clermont-ferrand\\.beta\\.education\\.fr|\n                            tube-corse\\.beta\\.education\\.fr|\n                            tube-creteil\\.beta\\.education\\.fr|\n                            tube-dijon\\.beta\\.education\\.fr|\n                            tube-education\\.beta\\.education\\.fr|\n                            tube-grenoble\\.beta\\.education\\.fr|\n                            tube-lille\\.beta\\.education\\.fr|\n                            tube-limoges\\.beta\\.education\\.fr|\n                            tube-montpellier\\.beta\\.education\\.fr|\n                            tube-nancy\\.beta\\.education\\.fr|\n                            tube-nantes\\.beta\\.education\\.fr|\n                            tube-nice\\.beta\\.education\\.fr|\n                            tube-normandie\\.beta\\.education\\.fr|\n                            tube-orleans-tours\\.beta\\.education\\.fr|\n                            tube-outremer\\.beta\\.education\\.fr|\n                            tube-paris\\.beta\\.education\\.fr|\n                            tube-poitiers\\.beta\\.education\\.fr|\n                            tube-reims\\.beta\\.education\\.fr|\n                            tube-rennes\\.beta\\.education\\.fr|\n                            tube-strasbourg\\.beta\\.education\\.fr|\n                            tube-toulouse\\.beta\\.education\\.fr|\n                            tube-versailles\\.beta\\.education\\.fr|\n                            tube1\\.it\\.tuwien\\.ac\\.at|\n                            tube\\.abolivier\\.bzh|\n                            tube\\.ac-amiens\\.fr|\n                            tube\\.aerztefueraufklaerung\\.de|\n                            tube\\.alexx\\.ml|\n                            tube\\.amic37\\.fr|\n                            tube\\.anufrij\\.de|\n                            tube\\.apolut\\.net|\n                            tube\\.arkhalabs\\.io|\n                            tube\\.arthack\\.nz|\n                            tube\\.as211696\\.net|\n                            tube\\.avensio\\.de|\n                            tube\\.azbyka\\.ru|\n                            tube\\.azkware\\.net|\n                            tube\\.bachaner\\.fr|\n                            tube\\.bmesh\\.org|\n                            tube\\.borked\\.host|\n                            tube\\.bstly\\.de|\n                            tube\\.chaoszone\\.tv|\n                            tube\\.chatelet\\.ovh|\n                            tube\\.cloud-libre\\.eu|\n                            tube\\.cms\\.garden|\n                            tube\\.cowfee\\.moe|\n                            tube\\.cryptography\\.dog|\n                            tube\\.darknight-coffee\\.org|\n                            tube\\.dev\\.lhub\\.pl|\n                            tube\\.distrilab\\.fr|\n                            tube\\.dsocialize\\.net|\n                            tube\\.ebin\\.club|\n                            tube\\.fdn\\.fr|\n                            tube\\.florimond\\.eu|\n                            tube\\.foxarmy\\.ml|\n                            tube\\.foxden\\.party|\n                            tube\\.frischesicht\\.de|\n                            tube\\.futuretic\\.fr|\n                            tube\\.gnous\\.eu|\n                            tube\\.grap\\.coop|\n                            tube\\.graz\\.social|\n                            tube\\.grin\\.hu|\n                            tube\\.hackerscop\\.org|\n                            tube\\.hordearii\\.fr|\n                            tube\\.jeena\\.net|\n                            tube\\.kai-stuht\\.com|\n                            tube\\.kockatoo\\.org|\n                            tube\\.kotur\\.org|\n                            tube\\.lacaveatonton\\.ovh|\n                            tube\\.linkse\\.media|\n                            tube\\.lokad\\.com|\n                            tube\\.lucie-philou\\.com|\n                            tube\\.melonbread\\.xyz|\n                            tube\\.mfraters\\.net|\n                            tube\\.motuhake\\.xyz|\n                            tube\\.mrbesen\\.de|\n                            tube\\.nah\\.re|\n                            tube\\.nchoco\\.net|\n                            tube\\.novg\\.net|\n                            tube\\.nox-rhea\\.org|\n                            tube\\.nuagelibre\\.fr|\n                            tube\\.nx12\\.net|\n                            tube\\.octaplex\\.net|\n                            tube\\.odat\\.xyz|\n                            tube\\.oisux\\.org|\n                            tube\\.opportunis\\.me|\n                            tube\\.org\\.il|\n                            tube\\.ortion\\.xyz|\n                            tube\\.others\\.social|\n                            tube\\.picasoft\\.net|\n                            tube\\.plomlompom\\.com|\n                            tube\\.pmj\\.rocks|\n                            tube\\.portes-imaginaire\\.org|\n                            tube\\.pyngu\\.com|\n                            tube\\.rebellion\\.global|\n                            tube\\.rhythms-of-resistance\\.org|\n                            tube\\.rita\\.moe|\n                            tube\\.rsi\\.cnr\\.it|\n                            tube\\.s1gm4\\.eu|\n                            tube\\.saumon\\.io|\n                            tube\\.schleuss\\.online|\n                            tube\\.schule\\.social|\n                            tube\\.seditio\\.fr|\n                            tube\\.shanti\\.cafe|\n                            tube\\.shela\\.nu|\n                            tube\\.skrep\\.in|\n                            tube\\.sp-codes\\.de|\n                            tube\\.sp4ke\\.com|\n                            tube\\.superseriousbusiness\\.org|\n                            tube\\.systest\\.eu|\n                            tube\\.tappret\\.fr|\n                            tube\\.tardis\\.world|\n                            tube\\.toontoet\\.nl|\n                            tube\\.tpshd\\.de|\n                            tube\\.troopers\\.agency|\n                            tube\\.tylerdavis\\.xyz|\n                            tube\\.undernet\\.uy|\n                            tube\\.vigilian-consulting\\.nl|\n                            tube\\.vraphim\\.com|\n                            tube\\.wehost\\.lgbt|\n                            tube\\.wien\\.rocks|\n                            tube\\.wolfe\\.casa|\n                            tube\\.xd0\\.de|\n                            tube\\.xy-space\\.de|\n                            tube\\.yapbreak\\.fr|\n                            tubedu\\.org|\n                            tubes\\.jodh\\.us|\n                            tuktube\\.com|\n                            turkum\\.me|\n                            tututu\\.tube|\n                            tuvideo\\.encanarias\\.info|\n                            tv1\\.cocu\\.cc|\n                            tv1\\.gomntu\\.space|\n                            tv2\\.cocu\\.cc|\n                            tv\\.adn\\.life|\n                            tv\\.atmx\\.ca|\n                            tv\\.bitma\\.st|\n                            tv\\.generallyrubbish\\.net\\.au|\n                            tv\\.lumbung\\.space|\n                            tv\\.mattchristiansenmedia\\.com|\n                            tv\\.netwhood\\.online|\n                            tv\\.neue\\.city|\n                            tv\\.piejacker\\.net|\n                            tv\\.pirateradio\\.social|\n                            tv\\.undersco\\.re|\n                            tvox\\.ru|\n                            twctube\\.twc-zone\\.eu|\n                            unfilter\\.tube|\n                            v\\.basspistol\\.org|\n                            v\\.kisombrella\\.top|\n                            v\\.lastorder\\.xyz|\n                            v\\.lor\\.sh|\n                            v\\.phreedom\\.club|\n                            v\\.sil\\.sh|\n                            v\\.szy\\.io|\n                            v\\.xxxapex\\.com|\n                            veezee\\.tube|\n                            vid\\.dascoyote\\.xyz|\n                            vid\\.garwood\\.io|\n                            vid\\.ncrypt\\.at|\n                            vid\\.pravdastalina\\.info|\n                            vid\\.qorg11\\.net|\n                            vid\\.rajeshtaylor\\.com|\n                            vid\\.samtripoli\\.com|\n                            vid\\.werefox\\.dev|\n                            vid\\.wildeboer\\.net|\n                            video-cave-v2\\.de|\n                            video\\.076\\.ne\\.jp|\n                            video\\.1146\\.nohost\\.me|\n                            video\\.altertek\\.org|\n                            video\\.anartist\\.org|\n                            video\\.apps\\.thedoodleproject\\.net|\n                            video\\.artist\\.cx|\n                            video\\.asgardius\\.company|\n                            video\\.balsillie\\.net|\n                            video\\.bards\\.online|\n                            video\\.binarydad\\.com|\n                            video\\.blast-info\\.fr|\n                            video\\.catgirl\\.biz|\n                            video\\.cigliola\\.com|\n                            video\\.cm-en-transition\\.fr|\n                            video\\.cnt\\.social|\n                            video\\.coales\\.co|\n                            video\\.codingfield\\.com|\n                            video\\.comptoir\\.net|\n                            video\\.comune\\.trento\\.it|\n                            video\\.cpn\\.so|\n                            video\\.csc49\\.fr|\n                            video\\.cybre\\.town|\n                            video\\.demokratischer-sommer\\.de|\n                            video\\.discord-insoumis\\.fr|\n                            video\\.dolphincastle\\.com|\n                            video\\.dresden\\.network|\n                            video\\.ecole-89\\.com|\n                            video\\.elgrillolibertario\\.org|\n                            video\\.emergeheart\\.info|\n                            video\\.eradicatinglove\\.xyz|\n                            video\\.ethantheenigma\\.me|\n                            video\\.exodus-privacy\\.eu\\.org|\n                            video\\.fbxl\\.net|\n                            video\\.fhtagn\\.org|\n                            video\\.greenmycity\\.eu|\n                            video\\.guerredeclasse\\.fr|\n                            video\\.gyt\\.is|\n                            video\\.hackers\\.town|\n                            video\\.hardlimit\\.com|\n                            video\\.hooli\\.co|\n                            video\\.igem\\.org|\n                            video\\.internet-czas-dzialac\\.pl|\n                            video\\.islameye\\.com|\n                            video\\.kicik\\.fr|\n                            video\\.kuba-orlik\\.name|\n                            video\\.kyushojitsu\\.ca|\n                            video\\.lavolte\\.net|\n                            video\\.lespoesiesdheloise\\.fr|\n                            video\\.liberta\\.vip|\n                            video\\.liege\\.bike|\n                            video\\.linc\\.systems|\n                            video\\.linux\\.it|\n                            video\\.linuxtrent\\.it|\n                            video\\.lokal\\.social|\n                            video\\.lono\\.space|\n                            video\\.lunasqu\\.ee|\n                            video\\.lundi\\.am|\n                            video\\.marcorennmaus\\.de|\n                            video\\.mass-trespass\\.uk|\n                            video\\.mugoreve\\.fr|\n                            video\\.mundodesconocido\\.com|\n                            video\\.mycrowd\\.ca|\n                            video\\.nogafam\\.es|\n                            video\\.odayacres\\.farm|\n                            video\\.ozgurkon\\.org|\n                            video\\.p1ng0ut\\.social|\n                            video\\.p3x\\.de|\n                            video\\.pcf\\.fr|\n                            video\\.pony\\.gallery|\n                            video\\.potate\\.space|\n                            video\\.pourpenser\\.pro|\n                            video\\.progressiv\\.dev|\n                            video\\.resolutions\\.it|\n                            video\\.rw501\\.de|\n                            video\\.screamer\\.wiki|\n                            video\\.sdm-tools\\.net|\n                            video\\.sftblw\\.moe|\n                            video\\.shitposter\\.club|\n                            video\\.skyn3t\\.in|\n                            video\\.soi\\.ch|\n                            video\\.stuartbrand\\.co\\.uk|\n                            video\\.thinkof\\.name|\n                            video\\.toot\\.pt|\n                            video\\.triplea\\.fr|\n                            video\\.turbo\\.chat|\n                            video\\.vaku\\.org\\.ua|\n                            video\\.veloma\\.org|\n                            video\\.violoncello\\.ch|\n                            video\\.wilkie\\.how|\n                            video\\.wsf2021\\.info|\n                            videorelay\\.co|\n                            videos-passages\\.huma-num\\.fr|\n                            videos\\.3d-wolf\\.com|\n                            videos\\.ahp-numerique\\.fr|\n                            videos\\.alexandrebadalo\\.pt|\n                            videos\\.archigny\\.net|\n                            videos\\.benjaminbrady\\.ie|\n                            videos\\.buceoluegoexisto\\.com|\n                            videos\\.capas\\.se|\n                            videos\\.casually\\.cat|\n                            videos\\.cloudron\\.io|\n                            videos\\.coletivos\\.org|\n                            videos\\.danksquad\\.org|\n                            videos\\.denshi\\.live|\n                            videos\\.fromouter\\.space|\n                            videos\\.fsci\\.in|\n                            videos\\.globenet\\.org|\n                            videos\\.hauspie\\.fr|\n                            videos\\.hush\\.is|\n                            videos\\.john-livingston\\.fr|\n                            videos\\.jordanwarne\\.xyz|\n                            videos\\.lavoixdessansvoix\\.org|\n                            videos\\.leslionsfloorball\\.fr|\n                            videos\\.lucero\\.top|\n                            videos\\.martyn\\.berlin|\n                            videos\\.mastodont\\.cat|\n                            videos\\.monstro1\\.com|\n                            videos\\.npo\\.city|\n                            videos\\.optoutpod\\.com|\n                            videos\\.petch\\.rocks|\n                            videos\\.pzelawski\\.xyz|\n                            videos\\.rampin\\.org|\n                            videos\\.scanlines\\.xyz|\n                            videos\\.shmalls\\.pw|\n                            videos\\.sibear\\.fr|\n                            videos\\.stadtfabrikanten\\.org|\n                            videos\\.tankernn\\.eu|\n                            videos\\.testimonia\\.org|\n                            videos\\.thisishowidontdisappear\\.com|\n                            videos\\.traumaheilung\\.net|\n                            videos\\.trom\\.tf|\n                            videos\\.wakkerewereld\\.nu|\n                            videos\\.weblib\\.re|\n                            videos\\.yesil\\.club|\n                            vids\\.roshless\\.me|\n                            vids\\.tekdmn\\.me|\n                            vidz\\.dou\\.bet|\n                            vod\\.lumikko\\.dev|\n                            vs\\.uniter\\.network|\n                            vulgarisation-informatique\\.fr|\n                            watch\\.breadtube\\.tv|\n                            watch\\.deranalyst\\.ch|\n                            watch\\.ignorance\\.eu|\n                            watch\\.krazy\\.party|\n                            watch\\.libertaria\\.space|\n                            watch\\.rt4mn\\.org|\n                            watch\\.softinio\\.com|\n                            watch\\.tubelab\\.video|\n                            web-fellow\\.de|\n                            webtv\\.vandoeuvre\\.net|\n                            wechill\\.space|\n                            wikileaks\\.video|\n                            wiwi\\.video|\n                            worldofvids\\.com|\n                            wwtube\\.net|\n                            www4\\.mir\\.inter21\\.net|\n                            www\\.birkeundnymphe\\.de|\n                            www\\.captain-german\\.com|\n                            www\\.wiki-tube\\.de|\n                            xxivproduction\\.video|\n                            xxx\\.noho\\.st|\n\n                            # from youtube-dl\n                            peertube\\.rainbowswingers\\.net|\n                            tube\\.stanisic\\.nl|\n                            peer\\.suiri\\.us|\n                            medias\\.libox\\.fr|\n                            videomensoif\\.ynh\\.fr|\n                            peertube\\.travelpandas\\.eu|\n                            peertube\\.rachetjay\\.fr|\n                            peertube\\.montecsys\\.fr|\n                            tube\\.eskuero\\.me|\n                            peer\\.tube|\n                            peertube\\.umeahackerspace\\.se|\n                            tube\\.nx-pod\\.de|\n                            video\\.monsieurbidouille\\.fr|\n                            tube\\.openalgeria\\.org|\n                            vid\\.lelux\\.fi|\n                            video\\.anormallostpod\\.ovh|\n                            tube\\.crapaud-fou\\.org|\n                            peertube\\.stemy\\.me|\n                            lostpod\\.space|\n                            exode\\.me|\n                            peertube\\.snargol\\.com|\n                            vis\\.ion\\.ovh|\n                            videosdulib\\.re|\n                            v\\.mbius\\.io|\n                            videos\\.judrey\\.eu|\n                            peertube\\.osureplayviewer\\.xyz|\n                            peertube\\.mathieufamily\\.ovh|\n                            www\\.videos-libr\\.es|\n                            fightforinfo\\.com|\n                            peertube\\.fediverse\\.ru|\n                            peertube\\.oiseauroch\\.fr|\n                            video\\.nesven\\.eu|\n                            v\\.bearvideo\\.win|\n                            video\\.qoto\\.org|\n                            justporn\\.cc|\n                            video\\.vny\\.fr|\n                            peervideo\\.club|\n                            tube\\.taker\\.fr|\n                            peertube\\.chantierlibre\\.org|\n                            tube\\.ipfixe\\.info|\n                            tube\\.kicou\\.info|\n                            tube\\.dodsorf\\.as|\n                            videobit\\.cc|\n                            video\\.yukari\\.moe|\n                            videos\\.elbinario\\.net|\n                            hkvideo\\.live|\n                            pt\\.tux\\.tf|\n                            www\\.hkvideo\\.live|\n                            FIGHTFORINFO\\.com|\n                            pt\\.765racing\\.com|\n                            peertube\\.gnumeria\\.eu\\.org|\n                            nordenmedia\\.com|\n                            peertube\\.co\\.uk|\n                            tube\\.darfweb\\.eu|\n                            tube\\.kalah-france\\.org|\n                            0ch\\.in|\n                            vod\\.mochi\\.academy|\n                            film\\.node9\\.org|\n                            peertube\\.hatthieves\\.es|\n                            video\\.fitchfamily\\.org|\n                            peertube\\.ddns\\.net|\n                            video\\.ifuncle\\.kr|\n                            video\\.fdlibre\\.eu|\n                            tube\\.22decembre\\.eu|\n                            peertube\\.harmoniescreatives\\.com|\n                            tube\\.fabrigli\\.fr|\n                            video\\.thedwyers\\.co|\n                            video\\.bruitbruit\\.com|\n                            peertube\\.foxfam\\.club|\n                            peer\\.philoxweb\\.be|\n                            videos\\.bugs\\.social|\n                            peertube\\.malbert\\.xyz|\n                            peertube\\.bilange\\.ca|\n                            libretube\\.net|\n                            diytelevision\\.com|\n                            peertube\\.fedilab\\.app|\n                            libre\\.video|\n                            video\\.mstddntfdn\\.online|\n                            us\\.tv|\n                            peertube\\.sl-network\\.fr|\n                            peertube\\.dynlinux\\.io|\n                            peertube\\.david\\.durieux\\.family|\n                            peertube\\.linuxrocks\\.online|\n                            peerwatch\\.xyz|\n                            v\\.kretschmann\\.social|\n                            tube\\.otter\\.sh|\n                            yt\\.is\\.nota\\.live|\n                            tube\\.dragonpsi\\.xyz|\n                            peertube\\.boneheadmedia\\.com|\n                            videos\\.funkwhale\\.audio|\n                            watch\\.44con\\.com|\n                            peertube\\.gcaillaut\\.fr|\n                            peertube\\.icu|\n                            pony\\.tube|\n                            spacepub\\.space|\n                            tube\\.stbr\\.io|\n                            v\\.mom-gay\\.faith|\n                            tube\\.port0\\.xyz|\n                            peertube\\.simounet\\.net|\n                            play\\.jergefelt\\.se|\n                            peertube\\.zeteo\\.me|\n                            tube\\.danq\\.me|\n                            peertube\\.kerenon\\.com|\n                            tube\\.fab-l3\\.org|\n                            tube\\.calculate\\.social|\n                            peertube\\.mckillop\\.org|\n                            tube\\.netzspielplatz\\.de|\n                            vod\\.ksite\\.de|\n                            peertube\\.laas\\.fr|\n                            tube\\.govital\\.net|\n                            peertube\\.stephenson\\.cc|\n                            bistule\\.nohost\\.me|\n                            peertube\\.kajalinifi\\.de|\n                            video\\.ploud\\.jp|\n                            video\\.omniatv\\.com|\n                            peertube\\.ffs2play\\.fr|\n                            peertube\\.leboulaire\\.ovh|\n                            peertube\\.tronic-studio\\.com|\n                            peertube\\.public\\.cat|\n                            peertube\\.metalbanana\\.net|\n                            video\\.1000i100\\.fr|\n                            peertube\\.alter-nativ-voll\\.de|\n                            tube\\.pasa\\.tf|\n                            tube\\.worldofhauru\\.xyz|\n                            pt\\.kamp\\.site|\n                            peertube\\.teleassist\\.fr|\n                            videos\\.mleduc\\.xyz|\n                            conf\\.tube|\n                            media\\.privacyinternational\\.org|\n                            pt\\.forty-two\\.nl|\n                            video\\.halle-leaks\\.de|\n                            video\\.grosskopfgames\\.de|\n                            peertube\\.schaeferit\\.de|\n                            peertube\\.jackbot\\.fr|\n                            tube\\.extinctionrebellion\\.fr|\n                            peertube\\.f-si\\.org|\n                            video\\.subak\\.ovh|\n                            videos\\.koweb\\.fr|\n                            peertube\\.zergy\\.net|\n                            peertube\\.roflcopter\\.fr|\n                            peertube\\.floss-marketing-school\\.com|\n                            vloggers\\.social|\n                            peertube\\.iriseden\\.eu|\n                            videos\\.ubuntu-paris\\.org|\n                            peertube\\.mastodon\\.host|\n                            armstube\\.com|\n                            peertube\\.s2s\\.video|\n                            peertube\\.lol|\n                            tube\\.open-plug\\.eu|\n                            open\\.tube|\n                            peertube\\.ch|\n                            peertube\\.normandie-libre\\.fr|\n                            peertube\\.slat\\.org|\n                            video\\.lacaveatonton\\.ovh|\n                            peertube\\.uno|\n                            peertube\\.servebeer\\.com|\n                            peertube\\.fedi\\.quebec|\n                            tube\\.h3z\\.jp|\n                            tube\\.plus200\\.com|\n                            peertube\\.eric\\.ovh|\n                            tube\\.metadocs\\.cc|\n                            tube\\.unmondemeilleur\\.eu|\n                            gouttedeau\\.space|\n                            video\\.antirep\\.net|\n                            nrop\\.cant\\.at|\n                            tube\\.ksl-bmx\\.de|\n                            tube\\.plaf\\.fr|\n                            tube\\.tchncs\\.de|\n                            video\\.devinberg\\.com|\n                            hitchtube\\.fr|\n                            peertube\\.kosebamse\\.com|\n                            yunopeertube\\.myddns\\.me|\n                            peertube\\.varney\\.fr|\n                            peertube\\.anon-kenkai\\.com|\n                            tube\\.maiti\\.info|\n                            tubee\\.fr|\n                            videos\\.dinofly\\.com|\n                            toobnix\\.org|\n                            videotape\\.me|\n                            voca\\.tube|\n                            video\\.heromuster\\.com|\n                            video\\.lemediatv\\.fr|\n                            video\\.up\\.edu\\.ph|\n                            balafon\\.video|\n                            video\\.ivel\\.fr|\n                            thickrips\\.cloud|\n                            pt\\.laurentkruger\\.fr|\n                            video\\.monarch-pass\\.net|\n                            peertube\\.artica\\.center|\n                            video\\.alternanet\\.fr|\n                            indymotion\\.fr|\n                            fanvid\\.stopthatimp\\.net|\n                            video\\.farci\\.org|\n                            v\\.lesterpig\\.com|\n                            video\\.okaris\\.de|\n                            tube\\.pawelko\\.net|\n                            peertube\\.mablr\\.org|\n                            tube\\.fede\\.re|\n                            pytu\\.be|\n                            evertron\\.tv|\n                            devtube\\.dev-wiki\\.de|\n                            raptube\\.antipub\\.org|\n                            video\\.selea\\.se|\n                            peertube\\.mygaia\\.org|\n                            video\\.oh14\\.de|\n                            peertube\\.livingutopia\\.org|\n                            peertube\\.the-penguin\\.de|\n                            tube\\.thechangebook\\.org|\n                            tube\\.anjara\\.eu|\n                            pt\\.pube\\.tk|\n                            video\\.samedi\\.pm|\n                            mplayer\\.demouliere\\.eu|\n                            widemus\\.de|\n                            peertube\\.me|\n                            peertube\\.zapashcanon\\.fr|\n                            video\\.latavernedejohnjohn\\.fr|\n                            peertube\\.pcservice46\\.fr|\n                            peertube\\.mazzonetto\\.eu|\n                            video\\.irem\\.univ-paris-diderot\\.fr|\n                            video\\.livecchi\\.cloud|\n                            alttube\\.fr|\n                            video\\.coop\\.tools|\n                            video\\.cabane-libre\\.org|\n                            peertube\\.openstreetmap\\.fr|\n                            videos\\.alolise\\.org|\n                            irrsinn\\.video|\n                            video\\.antopie\\.org|\n                            scitech\\.video|\n                            tube2\\.nemsia\\.org|\n                            video\\.amic37\\.fr|\n                            peertube\\.freeforge\\.eu|\n                            video\\.arbitrarion\\.com|\n                            video\\.datsemultimedia\\.com|\n                            stoptrackingus\\.tv|\n                            peertube\\.ricostrongxxx\\.com|\n                            docker\\.videos\\.lecygnenoir\\.info|\n                            peertube\\.togart\\.de|\n                            tube\\.postblue\\.info|\n                            videos\\.domainepublic\\.net|\n                            peertube\\.cyber-tribal\\.com|\n                            video\\.gresille\\.org|\n                            peertube\\.dsmouse\\.net|\n                            cinema\\.yunohost\\.support|\n                            tube\\.theocevaer\\.fr|\n                            repro\\.video|\n                            tube\\.4aem\\.com|\n                            quaziinc\\.com|\n                            peertube\\.metawurst\\.space|\n                            videos\\.wakapo\\.com|\n                            video\\.ploud\\.fr|\n                            video\\.freeradical\\.zone|\n                            tube\\.valinor\\.fr|\n                            refuznik\\.video|\n                            pt\\.kircheneuenburg\\.de|\n                            peertube\\.asrun\\.eu|\n                            peertube\\.lagob\\.fr|\n                            videos\\.side-ways\\.net|\n                            91video\\.online|\n                            video\\.valme\\.io|\n                            video\\.taboulisme\\.com|\n                            videos-libr\\.es|\n                            tv\\.mooh\\.fr|\n                            nuage\\.acostey\\.fr|\n                            video\\.monsieur-a\\.fr|\n                            peertube\\.librelois\\.fr|\n                            videos\\.pair2jeux\\.tube|\n                            videos\\.pueseso\\.club|\n                            peer\\.mathdacloud\\.ovh|\n                            media\\.assassinate-you\\.net|\n                            vidcommons\\.org|\n                            ptube\\.rousset\\.nom\\.fr|\n                            tube\\.cyano\\.at|\n                            videos\\.squat\\.net|\n                            video\\.iphodase\\.fr|\n                            peertube\\.makotoworkshop\\.org|\n                            peertube\\.serveur\\.slv-valbonne\\.fr|\n                            vault\\.mle\\.party|\n                            hostyour\\.tv|\n                            videos\\.hack2g2\\.fr|\n                            libre\\.tube|\n                            pire\\.artisanlogiciel\\.net|\n                            videos\\.numerique-en-commun\\.fr|\n                            video\\.netsyms\\.com|\n                            video\\.die-partei\\.social|\n                            video\\.writeas\\.org|\n                            peertube\\.swarm\\.solvingmaz\\.es|\n                            tube\\.pericoloso\\.ovh|\n                            watching\\.cypherpunk\\.observer|\n                            videos\\.adhocmusic\\.com|\n                            tube\\.rfc1149\\.net|\n                            peertube\\.librelabucm\\.org|\n                            videos\\.numericoop\\.fr|\n                            peertube\\.koehn\\.com|\n                            peertube\\.anarchmusicall\\.net|\n                            tube\\.kampftoast\\.de|\n                            vid\\.y-y\\.li|\n                            peertube\\.xtenz\\.xyz|\n                            diode\\.zone|\n                            tube\\.egf\\.mn|\n                            peertube\\.nomagic\\.uk|\n                            visionon\\.tv|\n                            videos\\.koumoul\\.com|\n                            video\\.rastapuls\\.com|\n                            video\\.mantlepro\\.com|\n                            video\\.deadsuperhero\\.com|\n                            peertube\\.musicstudio\\.pro|\n                            peertube\\.we-keys\\.fr|\n                            artitube\\.artifaille\\.fr|\n                            peertube\\.ethernia\\.net|\n                            tube\\.midov\\.pl|\n                            peertube\\.fr|\n                            watch\\.snoot\\.tube|\n                            peertube\\.donnadieu\\.fr|\n                            argos\\.aquilenet\\.fr|\n                            tube\\.nemsia\\.org|\n                            tube\\.bruniau\\.net|\n                            videos\\.darckoune\\.moe|\n                            tube\\.traydent\\.info|\n                            dev\\.videos\\.lecygnenoir\\.info|\n                            peertube\\.nayya\\.org|\n                            peertube\\.live|\n                            peertube\\.mofgao\\.space|\n                            video\\.lequerrec\\.eu|\n                            peertube\\.amicale\\.net|\n                            aperi\\.tube|\n                            tube\\.ac-lyon\\.fr|\n                            video\\.lw1\\.at|\n                            www\\.yiny\\.org|\n                            videos\\.pofilo\\.fr|\n                            tube\\.lou\\.lt|\n                            choob\\.h\\.etbus\\.ch|\n                            tube\\.hoga\\.fr|\n                            peertube\\.heberge\\.fr|\n                            video\\.obermui\\.de|\n                            videos\\.cloudfrancois\\.fr|\n                            betamax\\.video|\n                            video\\.typica\\.us|\n                            tube\\.piweb\\.be|\n                            video\\.blender\\.org|\n                            peertube\\.cat|\n                            tube\\.kdy\\.ch|\n                            pe\\.ertu\\.be|\n                            peertube\\.social|\n                            videos\\.lescommuns\\.org|\n                            tv\\.datamol\\.org|\n                            videonaute\\.fr|\n                            dialup\\.express|\n                            peertube\\.nogafa\\.org|\n                            megatube\\.lilomoino\\.fr|\n                            peertube\\.tamanoir\\.foucry\\.net|\n                            peertube\\.devosi\\.org|\n                            peertube\\.1312\\.media|\n                            tube\\.bootlicker\\.party|\n                            skeptikon\\.fr|\n                            video\\.blueline\\.mg|\n                            tube\\.homecomputing\\.fr|\n                            tube\\.ouahpiti\\.info|\n                            video\\.tedomum\\.net|\n                            video\\.g3l\\.org|\n                            fontube\\.fr|\n                            peertube\\.gaialabs\\.ch|\n                            tube\\.kher\\.nl|\n                            peertube\\.qtg\\.fr|\n                            video\\.migennes\\.net|\n                            tube\\.p2p\\.legal|\n                            troll\\.tv|\n                            videos\\.iut-orsay\\.fr|\n                            peertube\\.solidev\\.net|\n                            videos\\.cemea\\.org|\n                            video\\.passageenseine\\.fr|\n                            videos\\.festivalparminous\\.org|\n                            peertube\\.touhoppai\\.moe|\n                            sikke\\.fi|\n                            peer\\.hostux\\.social|\n                            share\\.tube|\n                            peertube\\.walkingmountains\\.fr|\n                            videos\\.benpro\\.fr|\n                            peertube\\.parleur\\.net|\n                            peertube\\.heraut\\.eu|\n                            tube\\.aquilenet\\.fr|\n                            peertube\\.gegeweb\\.eu|\n                            framatube\\.org|\n                            thinkerview\\.video|\n                            tube\\.conferences-gesticulees\\.net|\n                            peertube\\.datagueule\\.tv|\n                            video\\.lqdn\\.fr|\n                            tube\\.mochi\\.academy|\n                            media\\.zat\\.im|\n                            video\\.colibris-outilslibres\\.org|\n                            tube\\.svnet\\.fr|\n                            peertube\\.video|\n                            peertube2\\.cpy\\.re|\n                            peertube3\\.cpy\\.re|\n                            videos\\.tcit\\.fr|\n                            peertube\\.cpy\\.re|\n                            canard\\.tube\n                        ))/(?:videos/(?:watch|embed)|api/v\\d/videos|w)/\n                    )\n                    (?P<id>[\\da-zA-Z]{22}|[\\da-fA-F]{8}-[\\da-fA-F]{4}-[\\da-fA-F]{4}-[\\da-fA-F]{4}-[\\da-fA-F]{12})\n                    '


class PeerTubePlaylistIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.peertube'
    IE_NAME = 'PeerTube:Playlist'
    _VALID_URL = '(?x)\n                        https?://(?P<host>(?:\n                            # Taken from https://instances.joinpeertube.org/instances\n                            40two\\.tube|\n                            a\\.metube\\.ch|\n                            advtv\\.ml|\n                            algorithmic\\.tv|\n                            alimulama\\.com|\n                            arcana\\.fun|\n                            archive\\.vidicon\\.org|\n                            artefac-paris\\.tv|\n                            auf1\\.eu|\n                            battlepenguin\\.video|\n                            beertube\\.epgn\\.ch|\n                            befree\\.nohost\\.me|\n                            bideoak\\.argia\\.eus|\n                            birkeundnymphe\\.de|\n                            bitcointv\\.com|\n                            cattube\\.org|\n                            clap\\.nerv-project\\.eu|\n                            climatejustice\\.video|\n                            comf\\.tube|\n                            conspiracydistillery\\.com|\n                            darkvapor\\.nohost\\.me|\n                            daschauher\\.aksel\\.rocks|\n                            digitalcourage\\.video|\n                            dreiecksnebel\\.alex-detsch\\.de|\n                            eduvid\\.org|\n                            evangelisch\\.video|\n                            exo\\.tube|\n                            fair\\.tube|\n                            fediverse\\.tv|\n                            film\\.k-prod\\.fr|\n                            flim\\.txmn\\.tk|\n                            fotogramas\\.politicaconciencia\\.org|\n                            ftsi\\.ru|\n                            gary\\.vger\\.cloud|\n                            graeber\\.video|\n                            greatview\\.video|\n                            grypstube\\.uni-greifswald\\.de|\n                            highvoltage\\.tv|\n                            hpstube\\.fr|\n                            htp\\.live|\n                            hyperreal\\.tube|\n                            juggling\\.digital|\n                            kino\\.kompot\\.si|\n                            kino\\.schuerz\\.at|\n                            kinowolnosc\\.pl|\n                            kirche\\.peertube-host\\.de|\n                            kodcast\\.com|\n                            kolektiva\\.media|\n                            kraut\\.zone|\n                            kumi\\.tube|\n                            lastbreach\\.tv|\n                            lepetitmayennais\\.fr\\.nf|\n                            lexx\\.impa\\.me|\n                            libertynode\\.tv|\n                            libra\\.syntazia\\.org|\n                            libremedia\\.video|\n                            live\\.libratoi\\.org|\n                            live\\.nanao\\.moe|\n                            live\\.toobnix\\.org|\n                            livegram\\.net|\n                            lolitube\\.freedomchan\\.moe|\n                            lucarne\\.balsamine\\.be|\n                            maindreieck-tv\\.de|\n                            mani\\.tube|\n                            manicphase\\.me|\n                            media\\.fsfe\\.org|\n                            media\\.gzevd\\.de|\n                            media\\.inno3\\.cricket|\n                            media\\.kaitaia\\.life|\n                            media\\.krashboyz\\.org|\n                            media\\.over-world\\.org|\n                            media\\.skewed\\.de|\n                            media\\.undeadnetwork\\.de|\n                            medias\\.pingbase\\.net|\n                            melsungen\\.peertube-host\\.de|\n                            mirametube\\.fr|\n                            mojotube\\.net|\n                            monplaisirtube\\.ddns\\.net|\n                            mountaintown\\.video|\n                            my\\.bunny\\.cafe|\n                            myfreetube\\.de|\n                            mytube\\.kn-cloud\\.de|\n                            mytube\\.madzel\\.de|\n                            myworkoutarenapeertube\\.cf|\n                            nanawel-peertube\\.dyndns\\.org|\n                            nastub\\.cz|\n                            offenes\\.tv|\n                            orgdup\\.media|\n                            ovaltube\\.codinglab\\.ch|\n                            p2ptv\\.ru|\n                            p\\.eertu\\.be|\n                            p\\.lu|\n                            peer\\.azurs\\.fr|\n                            peertube1\\.zeteo\\.me|\n                            peertube\\.020\\.pl|\n                            peertube\\.0x5e\\.eu|\n                            peertube\\.alpharius\\.io|\n                            peertube\\.am-networks\\.fr|\n                            peertube\\.anduin\\.net|\n                            peertube\\.anzui\\.dev|\n                            peertube\\.arbleizez\\.bzh|\n                            peertube\\.art3mis\\.de|\n                            peertube\\.atilla\\.org|\n                            peertube\\.atsuchan\\.page|\n                            peertube\\.aukfood\\.net|\n                            peertube\\.aventer\\.biz|\n                            peertube\\.b38\\.rural-it\\.org|\n                            peertube\\.beeldengeluid\\.nl|\n                            peertube\\.be|\n                            peertube\\.bgzashtita\\.es|\n                            peertube\\.bitsandlinux\\.com|\n                            peertube\\.biz|\n                            peertube\\.boba\\.best|\n                            peertube\\.br0\\.fr|\n                            peertube\\.bridaahost\\.ynh\\.fr|\n                            peertube\\.bubbletea\\.dev|\n                            peertube\\.bubuit\\.net|\n                            peertube\\.cabaal\\.net|\n                            peertube\\.cats-home\\.net|\n                            peertube\\.chemnitz\\.freifunk\\.net|\n                            peertube\\.chevro\\.fr|\n                            peertube\\.chrisspiegl\\.com|\n                            peertube\\.chtisurel\\.net|\n                            peertube\\.cipherbliss\\.com|\n                            peertube\\.cloud\\.sans\\.pub|\n                            peertube\\.cpge-brizeux\\.fr|\n                            peertube\\.ctseuro\\.com|\n                            peertube\\.cuatrolibertades\\.org|\n                            peertube\\.cybercirujas\\.club|\n                            peertube\\.cythin\\.com|\n                            peertube\\.davigge\\.com|\n                            peertube\\.dc\\.pini\\.fr|\n                            peertube\\.debian\\.social|\n                            peertube\\.demonix\\.fr|\n                            peertube\\.designersethiques\\.org|\n                            peertube\\.desmu\\.fr|\n                            peertube\\.devloprog\\.org|\n                            peertube\\.devol\\.it|\n                            peertube\\.dtmf\\.ca|\n                            peertube\\.ecologie\\.bzh|\n                            peertube\\.eu\\.org|\n                            peertube\\.european-pirates\\.eu|\n                            peertube\\.euskarabildua\\.eus|\n                            peertube\\.fenarinarsa\\.com|\n                            peertube\\.fomin\\.site|\n                            peertube\\.forsud\\.be|\n                            peertube\\.francoispelletier\\.org|\n                            peertube\\.freenet\\.ru|\n                            peertube\\.freetalklive\\.com|\n                            peertube\\.functional\\.cafe|\n                            peertube\\.gardeludwig\\.fr|\n                            peertube\\.gargantia\\.fr|\n                            peertube\\.gcfamily\\.fr|\n                            peertube\\.genma\\.fr|\n                            peertube\\.get-racing\\.de|\n                            peertube\\.gidikroon\\.eu|\n                            peertube\\.gruezishop\\.ch|\n                            peertube\\.habets\\.house|\n                            peertube\\.hackerfraternity\\.org|\n                            peertube\\.ichigo\\.everydayimshuflin\\.com|\n                            peertube\\.ignifi\\.me|\n                            peertube\\.inapurna\\.org|\n                            peertube\\.informaction\\.info|\n                            peertube\\.interhop\\.org|\n                            peertube\\.iselfhost\\.com|\n                            peertube\\.it|\n                            peertube\\.jensdiemer\\.de|\n                            peertube\\.joffreyverd\\.fr|\n                            peertube\\.kalua\\.im|\n                            peertube\\.kathryl\\.fr|\n                            peertube\\.keazilla\\.net|\n                            peertube\\.klaewyss\\.fr|\n                            peertube\\.kodcast\\.com|\n                            peertube\\.kx\\.studio|\n                            peertube\\.lagvoid\\.com|\n                            peertube\\.lavallee\\.tech|\n                            peertube\\.le5emeaxe\\.fr|\n                            peertube\\.lestutosdeprocessus\\.fr|\n                            peertube\\.librenet\\.co\\.za|\n                            peertube\\.logilab\\.fr|\n                            peertube\\.louisematic\\.site|\n                            peertube\\.luckow\\.org|\n                            peertube\\.luga\\.at|\n                            peertube\\.lyceeconnecte\\.fr|\n                            peertube\\.manalejandro\\.com|\n                            peertube\\.marud\\.fr|\n                            peertube\\.mattone\\.net|\n                            peertube\\.maxweiss\\.io|\n                            peertube\\.monlycee\\.net|\n                            peertube\\.mxinfo\\.fr|\n                            peertube\\.myrasp\\.eu|\n                            peertube\\.nebelcloud\\.de|\n                            peertube\\.netzbegruenung\\.de|\n                            peertube\\.newsocial\\.tech|\n                            peertube\\.nicolastissot\\.fr|\n                            peertube\\.nz|\n                            peertube\\.offerman\\.com|\n                            peertube\\.opencloud\\.lu|\n                            peertube\\.orthus\\.link|\n                            peertube\\.patapouf\\.xyz|\n                            peertube\\.pi2\\.dev|\n                            peertube\\.plataformess\\.org|\n                            peertube\\.pl|\n                            peertube\\.portaesgnos\\.org|\n                            peertube\\.r2\\.enst\\.fr|\n                            peertube\\.r5c3\\.fr|\n                            peertube\\.radres\\.xyz|\n                            peertube\\.red|\n                            peertube\\.robonomics\\.network|\n                            peertube\\.rtnkv\\.cloud|\n                            peertube\\.runfox\\.tk|\n                            peertube\\.satoshishop\\.de|\n                            peertube\\.scic-tetris\\.org|\n                            peertube\\.securitymadein\\.lu|\n                            peertube\\.semweb\\.pro|\n                            peertube\\.social\\.my-wan\\.de|\n                            peertube\\.soykaf\\.org|\n                            peertube\\.stefofficiel\\.me|\n                            peertube\\.stream|\n                            peertube\\.su|\n                            peertube\\.swrs\\.net|\n                            peertube\\.takeko\\.cyou|\n                            peertube\\.tangentfox\\.com|\n                            peertube\\.taxinachtegel\\.de|\n                            peertube\\.thenewoil\\.xyz|\n                            peertube\\.ti-fr\\.com|\n                            peertube\\.tiennot\\.net|\n                            peertube\\.troback\\.com|\n                            peertube\\.tspu\\.edu\\.ru|\n                            peertube\\.tux\\.ovh|\n                            peertube\\.tv|\n                            peertube\\.tweb\\.tv|\n                            peertube\\.ucy\\.de|\n                            peertube\\.underworld\\.fr|\n                            peertube\\.us\\.to|\n                            peertube\\.ventresmous\\.fr|\n                            peertube\\.vlaki\\.cz|\n                            peertube\\.w\\.utnw\\.de|\n                            peertube\\.westring\\.digital|\n                            peertube\\.xwiki\\.com|\n                            peertube\\.zoz-serv\\.org|\n                            peervideo\\.ru|\n                            periscope\\.numenaute\\.org|\n                            perron-tube\\.de|\n                            petitlutinartube\\.fr|\n                            phijkchu\\.com|\n                            pierre\\.tube|\n                            piraten\\.space|\n                            play\\.rosano\\.ca|\n                            player\\.ojamajo\\.moe|\n                            plextube\\.nl|\n                            pocketnetpeertube1\\.nohost\\.me|\n                            pocketnetpeertube3\\.nohost\\.me|\n                            pocketnetpeertube4\\.nohost\\.me|\n                            pocketnetpeertube5\\.nohost\\.me|\n                            pocketnetpeertube6\\.nohost\\.me|\n                            pt\\.24-7\\.ro|\n                            pt\\.apathy\\.top|\n                            pt\\.diaspodon\\.fr|\n                            pt\\.fedi\\.tech|\n                            pt\\.maciej\\.website|\n                            ptb\\.lunarviews\\.net|\n                            ptmir1\\.inter21\\.net|\n                            ptmir2\\.inter21\\.net|\n                            ptmir3\\.inter21\\.net|\n                            ptmir4\\.inter21\\.net|\n                            ptmir5\\.inter21\\.net|\n                            ptube\\.horsentiers\\.fr|\n                            ptube\\.xmanifesto\\.club|\n                            queermotion\\.org|\n                            re-wizja\\.re-medium\\.com|\n                            regarder\\.sans\\.pub|\n                            ruraletv\\.ovh|\n                            s1\\.gegenstimme\\.tv|\n                            s2\\.veezee\\.tube|\n                            sdmtube\\.fr|\n                            sender-fm\\.veezee\\.tube|\n                            serv1\\.wiki-tube\\.de|\n                            serv3\\.wiki-tube\\.de|\n                            sickstream\\.net|\n                            sleepy\\.tube|\n                            sovran\\.video|\n                            spectra\\.video|\n                            stream\\.elven\\.pw|\n                            stream\\.k-prod\\.fr|\n                            stream\\.shahab\\.nohost\\.me|\n                            streamsource\\.video|\n                            studios\\.racer159\\.com|\n                            testtube\\.florimond\\.eu|\n                            tgi\\.hosted\\.spacebear\\.ee|\n                            thaitube\\.in\\.th|\n                            the\\.jokertv\\.eu|\n                            theater\\.ethernia\\.net|\n                            thecool\\.tube|\n                            tilvids\\.com|\n                            toob\\.bub\\.org|\n                            tpaw\\.video|\n                            truetube\\.media|\n                            tuba\\.lhub\\.pl|\n                            tube-aix-marseille\\.beta\\.education\\.fr|\n                            tube-amiens\\.beta\\.education\\.fr|\n                            tube-besancon\\.beta\\.education\\.fr|\n                            tube-bordeaux\\.beta\\.education\\.fr|\n                            tube-clermont-ferrand\\.beta\\.education\\.fr|\n                            tube-corse\\.beta\\.education\\.fr|\n                            tube-creteil\\.beta\\.education\\.fr|\n                            tube-dijon\\.beta\\.education\\.fr|\n                            tube-education\\.beta\\.education\\.fr|\n                            tube-grenoble\\.beta\\.education\\.fr|\n                            tube-lille\\.beta\\.education\\.fr|\n                            tube-limoges\\.beta\\.education\\.fr|\n                            tube-montpellier\\.beta\\.education\\.fr|\n                            tube-nancy\\.beta\\.education\\.fr|\n                            tube-nantes\\.beta\\.education\\.fr|\n                            tube-nice\\.beta\\.education\\.fr|\n                            tube-normandie\\.beta\\.education\\.fr|\n                            tube-orleans-tours\\.beta\\.education\\.fr|\n                            tube-outremer\\.beta\\.education\\.fr|\n                            tube-paris\\.beta\\.education\\.fr|\n                            tube-poitiers\\.beta\\.education\\.fr|\n                            tube-reims\\.beta\\.education\\.fr|\n                            tube-rennes\\.beta\\.education\\.fr|\n                            tube-strasbourg\\.beta\\.education\\.fr|\n                            tube-toulouse\\.beta\\.education\\.fr|\n                            tube-versailles\\.beta\\.education\\.fr|\n                            tube1\\.it\\.tuwien\\.ac\\.at|\n                            tube\\.abolivier\\.bzh|\n                            tube\\.ac-amiens\\.fr|\n                            tube\\.aerztefueraufklaerung\\.de|\n                            tube\\.alexx\\.ml|\n                            tube\\.amic37\\.fr|\n                            tube\\.anufrij\\.de|\n                            tube\\.apolut\\.net|\n                            tube\\.arkhalabs\\.io|\n                            tube\\.arthack\\.nz|\n                            tube\\.as211696\\.net|\n                            tube\\.avensio\\.de|\n                            tube\\.azbyka\\.ru|\n                            tube\\.azkware\\.net|\n                            tube\\.bachaner\\.fr|\n                            tube\\.bmesh\\.org|\n                            tube\\.borked\\.host|\n                            tube\\.bstly\\.de|\n                            tube\\.chaoszone\\.tv|\n                            tube\\.chatelet\\.ovh|\n                            tube\\.cloud-libre\\.eu|\n                            tube\\.cms\\.garden|\n                            tube\\.cowfee\\.moe|\n                            tube\\.cryptography\\.dog|\n                            tube\\.darknight-coffee\\.org|\n                            tube\\.dev\\.lhub\\.pl|\n                            tube\\.distrilab\\.fr|\n                            tube\\.dsocialize\\.net|\n                            tube\\.ebin\\.club|\n                            tube\\.fdn\\.fr|\n                            tube\\.florimond\\.eu|\n                            tube\\.foxarmy\\.ml|\n                            tube\\.foxden\\.party|\n                            tube\\.frischesicht\\.de|\n                            tube\\.futuretic\\.fr|\n                            tube\\.gnous\\.eu|\n                            tube\\.grap\\.coop|\n                            tube\\.graz\\.social|\n                            tube\\.grin\\.hu|\n                            tube\\.hackerscop\\.org|\n                            tube\\.hordearii\\.fr|\n                            tube\\.jeena\\.net|\n                            tube\\.kai-stuht\\.com|\n                            tube\\.kockatoo\\.org|\n                            tube\\.kotur\\.org|\n                            tube\\.lacaveatonton\\.ovh|\n                            tube\\.linkse\\.media|\n                            tube\\.lokad\\.com|\n                            tube\\.lucie-philou\\.com|\n                            tube\\.melonbread\\.xyz|\n                            tube\\.mfraters\\.net|\n                            tube\\.motuhake\\.xyz|\n                            tube\\.mrbesen\\.de|\n                            tube\\.nah\\.re|\n                            tube\\.nchoco\\.net|\n                            tube\\.novg\\.net|\n                            tube\\.nox-rhea\\.org|\n                            tube\\.nuagelibre\\.fr|\n                            tube\\.nx12\\.net|\n                            tube\\.octaplex\\.net|\n                            tube\\.odat\\.xyz|\n                            tube\\.oisux\\.org|\n                            tube\\.opportunis\\.me|\n                            tube\\.org\\.il|\n                            tube\\.ortion\\.xyz|\n                            tube\\.others\\.social|\n                            tube\\.picasoft\\.net|\n                            tube\\.plomlompom\\.com|\n                            tube\\.pmj\\.rocks|\n                            tube\\.portes-imaginaire\\.org|\n                            tube\\.pyngu\\.com|\n                            tube\\.rebellion\\.global|\n                            tube\\.rhythms-of-resistance\\.org|\n                            tube\\.rita\\.moe|\n                            tube\\.rsi\\.cnr\\.it|\n                            tube\\.s1gm4\\.eu|\n                            tube\\.saumon\\.io|\n                            tube\\.schleuss\\.online|\n                            tube\\.schule\\.social|\n                            tube\\.seditio\\.fr|\n                            tube\\.shanti\\.cafe|\n                            tube\\.shela\\.nu|\n                            tube\\.skrep\\.in|\n                            tube\\.sp-codes\\.de|\n                            tube\\.sp4ke\\.com|\n                            tube\\.superseriousbusiness\\.org|\n                            tube\\.systest\\.eu|\n                            tube\\.tappret\\.fr|\n                            tube\\.tardis\\.world|\n                            tube\\.toontoet\\.nl|\n                            tube\\.tpshd\\.de|\n                            tube\\.troopers\\.agency|\n                            tube\\.tylerdavis\\.xyz|\n                            tube\\.undernet\\.uy|\n                            tube\\.vigilian-consulting\\.nl|\n                            tube\\.vraphim\\.com|\n                            tube\\.wehost\\.lgbt|\n                            tube\\.wien\\.rocks|\n                            tube\\.wolfe\\.casa|\n                            tube\\.xd0\\.de|\n                            tube\\.xy-space\\.de|\n                            tube\\.yapbreak\\.fr|\n                            tubedu\\.org|\n                            tubes\\.jodh\\.us|\n                            tuktube\\.com|\n                            turkum\\.me|\n                            tututu\\.tube|\n                            tuvideo\\.encanarias\\.info|\n                            tv1\\.cocu\\.cc|\n                            tv1\\.gomntu\\.space|\n                            tv2\\.cocu\\.cc|\n                            tv\\.adn\\.life|\n                            tv\\.atmx\\.ca|\n                            tv\\.bitma\\.st|\n                            tv\\.generallyrubbish\\.net\\.au|\n                            tv\\.lumbung\\.space|\n                            tv\\.mattchristiansenmedia\\.com|\n                            tv\\.netwhood\\.online|\n                            tv\\.neue\\.city|\n                            tv\\.piejacker\\.net|\n                            tv\\.pirateradio\\.social|\n                            tv\\.undersco\\.re|\n                            tvox\\.ru|\n                            twctube\\.twc-zone\\.eu|\n                            unfilter\\.tube|\n                            v\\.basspistol\\.org|\n                            v\\.kisombrella\\.top|\n                            v\\.lastorder\\.xyz|\n                            v\\.lor\\.sh|\n                            v\\.phreedom\\.club|\n                            v\\.sil\\.sh|\n                            v\\.szy\\.io|\n                            v\\.xxxapex\\.com|\n                            veezee\\.tube|\n                            vid\\.dascoyote\\.xyz|\n                            vid\\.garwood\\.io|\n                            vid\\.ncrypt\\.at|\n                            vid\\.pravdastalina\\.info|\n                            vid\\.qorg11\\.net|\n                            vid\\.rajeshtaylor\\.com|\n                            vid\\.samtripoli\\.com|\n                            vid\\.werefox\\.dev|\n                            vid\\.wildeboer\\.net|\n                            video-cave-v2\\.de|\n                            video\\.076\\.ne\\.jp|\n                            video\\.1146\\.nohost\\.me|\n                            video\\.altertek\\.org|\n                            video\\.anartist\\.org|\n                            video\\.apps\\.thedoodleproject\\.net|\n                            video\\.artist\\.cx|\n                            video\\.asgardius\\.company|\n                            video\\.balsillie\\.net|\n                            video\\.bards\\.online|\n                            video\\.binarydad\\.com|\n                            video\\.blast-info\\.fr|\n                            video\\.catgirl\\.biz|\n                            video\\.cigliola\\.com|\n                            video\\.cm-en-transition\\.fr|\n                            video\\.cnt\\.social|\n                            video\\.coales\\.co|\n                            video\\.codingfield\\.com|\n                            video\\.comptoir\\.net|\n                            video\\.comune\\.trento\\.it|\n                            video\\.cpn\\.so|\n                            video\\.csc49\\.fr|\n                            video\\.cybre\\.town|\n                            video\\.demokratischer-sommer\\.de|\n                            video\\.discord-insoumis\\.fr|\n                            video\\.dolphincastle\\.com|\n                            video\\.dresden\\.network|\n                            video\\.ecole-89\\.com|\n                            video\\.elgrillolibertario\\.org|\n                            video\\.emergeheart\\.info|\n                            video\\.eradicatinglove\\.xyz|\n                            video\\.ethantheenigma\\.me|\n                            video\\.exodus-privacy\\.eu\\.org|\n                            video\\.fbxl\\.net|\n                            video\\.fhtagn\\.org|\n                            video\\.greenmycity\\.eu|\n                            video\\.guerredeclasse\\.fr|\n                            video\\.gyt\\.is|\n                            video\\.hackers\\.town|\n                            video\\.hardlimit\\.com|\n                            video\\.hooli\\.co|\n                            video\\.igem\\.org|\n                            video\\.internet-czas-dzialac\\.pl|\n                            video\\.islameye\\.com|\n                            video\\.kicik\\.fr|\n                            video\\.kuba-orlik\\.name|\n                            video\\.kyushojitsu\\.ca|\n                            video\\.lavolte\\.net|\n                            video\\.lespoesiesdheloise\\.fr|\n                            video\\.liberta\\.vip|\n                            video\\.liege\\.bike|\n                            video\\.linc\\.systems|\n                            video\\.linux\\.it|\n                            video\\.linuxtrent\\.it|\n                            video\\.lokal\\.social|\n                            video\\.lono\\.space|\n                            video\\.lunasqu\\.ee|\n                            video\\.lundi\\.am|\n                            video\\.marcorennmaus\\.de|\n                            video\\.mass-trespass\\.uk|\n                            video\\.mugoreve\\.fr|\n                            video\\.mundodesconocido\\.com|\n                            video\\.mycrowd\\.ca|\n                            video\\.nogafam\\.es|\n                            video\\.odayacres\\.farm|\n                            video\\.ozgurkon\\.org|\n                            video\\.p1ng0ut\\.social|\n                            video\\.p3x\\.de|\n                            video\\.pcf\\.fr|\n                            video\\.pony\\.gallery|\n                            video\\.potate\\.space|\n                            video\\.pourpenser\\.pro|\n                            video\\.progressiv\\.dev|\n                            video\\.resolutions\\.it|\n                            video\\.rw501\\.de|\n                            video\\.screamer\\.wiki|\n                            video\\.sdm-tools\\.net|\n                            video\\.sftblw\\.moe|\n                            video\\.shitposter\\.club|\n                            video\\.skyn3t\\.in|\n                            video\\.soi\\.ch|\n                            video\\.stuartbrand\\.co\\.uk|\n                            video\\.thinkof\\.name|\n                            video\\.toot\\.pt|\n                            video\\.triplea\\.fr|\n                            video\\.turbo\\.chat|\n                            video\\.vaku\\.org\\.ua|\n                            video\\.veloma\\.org|\n                            video\\.violoncello\\.ch|\n                            video\\.wilkie\\.how|\n                            video\\.wsf2021\\.info|\n                            videorelay\\.co|\n                            videos-passages\\.huma-num\\.fr|\n                            videos\\.3d-wolf\\.com|\n                            videos\\.ahp-numerique\\.fr|\n                            videos\\.alexandrebadalo\\.pt|\n                            videos\\.archigny\\.net|\n                            videos\\.benjaminbrady\\.ie|\n                            videos\\.buceoluegoexisto\\.com|\n                            videos\\.capas\\.se|\n                            videos\\.casually\\.cat|\n                            videos\\.cloudron\\.io|\n                            videos\\.coletivos\\.org|\n                            videos\\.danksquad\\.org|\n                            videos\\.denshi\\.live|\n                            videos\\.fromouter\\.space|\n                            videos\\.fsci\\.in|\n                            videos\\.globenet\\.org|\n                            videos\\.hauspie\\.fr|\n                            videos\\.hush\\.is|\n                            videos\\.john-livingston\\.fr|\n                            videos\\.jordanwarne\\.xyz|\n                            videos\\.lavoixdessansvoix\\.org|\n                            videos\\.leslionsfloorball\\.fr|\n                            videos\\.lucero\\.top|\n                            videos\\.martyn\\.berlin|\n                            videos\\.mastodont\\.cat|\n                            videos\\.monstro1\\.com|\n                            videos\\.npo\\.city|\n                            videos\\.optoutpod\\.com|\n                            videos\\.petch\\.rocks|\n                            videos\\.pzelawski\\.xyz|\n                            videos\\.rampin\\.org|\n                            videos\\.scanlines\\.xyz|\n                            videos\\.shmalls\\.pw|\n                            videos\\.sibear\\.fr|\n                            videos\\.stadtfabrikanten\\.org|\n                            videos\\.tankernn\\.eu|\n                            videos\\.testimonia\\.org|\n                            videos\\.thisishowidontdisappear\\.com|\n                            videos\\.traumaheilung\\.net|\n                            videos\\.trom\\.tf|\n                            videos\\.wakkerewereld\\.nu|\n                            videos\\.weblib\\.re|\n                            videos\\.yesil\\.club|\n                            vids\\.roshless\\.me|\n                            vids\\.tekdmn\\.me|\n                            vidz\\.dou\\.bet|\n                            vod\\.lumikko\\.dev|\n                            vs\\.uniter\\.network|\n                            vulgarisation-informatique\\.fr|\n                            watch\\.breadtube\\.tv|\n                            watch\\.deranalyst\\.ch|\n                            watch\\.ignorance\\.eu|\n                            watch\\.krazy\\.party|\n                            watch\\.libertaria\\.space|\n                            watch\\.rt4mn\\.org|\n                            watch\\.softinio\\.com|\n                            watch\\.tubelab\\.video|\n                            web-fellow\\.de|\n                            webtv\\.vandoeuvre\\.net|\n                            wechill\\.space|\n                            wikileaks\\.video|\n                            wiwi\\.video|\n                            worldofvids\\.com|\n                            wwtube\\.net|\n                            www4\\.mir\\.inter21\\.net|\n                            www\\.birkeundnymphe\\.de|\n                            www\\.captain-german\\.com|\n                            www\\.wiki-tube\\.de|\n                            xxivproduction\\.video|\n                            xxx\\.noho\\.st|\n\n                            # from youtube-dl\n                            peertube\\.rainbowswingers\\.net|\n                            tube\\.stanisic\\.nl|\n                            peer\\.suiri\\.us|\n                            medias\\.libox\\.fr|\n                            videomensoif\\.ynh\\.fr|\n                            peertube\\.travelpandas\\.eu|\n                            peertube\\.rachetjay\\.fr|\n                            peertube\\.montecsys\\.fr|\n                            tube\\.eskuero\\.me|\n                            peer\\.tube|\n                            peertube\\.umeahackerspace\\.se|\n                            tube\\.nx-pod\\.de|\n                            video\\.monsieurbidouille\\.fr|\n                            tube\\.openalgeria\\.org|\n                            vid\\.lelux\\.fi|\n                            video\\.anormallostpod\\.ovh|\n                            tube\\.crapaud-fou\\.org|\n                            peertube\\.stemy\\.me|\n                            lostpod\\.space|\n                            exode\\.me|\n                            peertube\\.snargol\\.com|\n                            vis\\.ion\\.ovh|\n                            videosdulib\\.re|\n                            v\\.mbius\\.io|\n                            videos\\.judrey\\.eu|\n                            peertube\\.osureplayviewer\\.xyz|\n                            peertube\\.mathieufamily\\.ovh|\n                            www\\.videos-libr\\.es|\n                            fightforinfo\\.com|\n                            peertube\\.fediverse\\.ru|\n                            peertube\\.oiseauroch\\.fr|\n                            video\\.nesven\\.eu|\n                            v\\.bearvideo\\.win|\n                            video\\.qoto\\.org|\n                            justporn\\.cc|\n                            video\\.vny\\.fr|\n                            peervideo\\.club|\n                            tube\\.taker\\.fr|\n                            peertube\\.chantierlibre\\.org|\n                            tube\\.ipfixe\\.info|\n                            tube\\.kicou\\.info|\n                            tube\\.dodsorf\\.as|\n                            videobit\\.cc|\n                            video\\.yukari\\.moe|\n                            videos\\.elbinario\\.net|\n                            hkvideo\\.live|\n                            pt\\.tux\\.tf|\n                            www\\.hkvideo\\.live|\n                            FIGHTFORINFO\\.com|\n                            pt\\.765racing\\.com|\n                            peertube\\.gnumeria\\.eu\\.org|\n                            nordenmedia\\.com|\n                            peertube\\.co\\.uk|\n                            tube\\.darfweb\\.eu|\n                            tube\\.kalah-france\\.org|\n                            0ch\\.in|\n                            vod\\.mochi\\.academy|\n                            film\\.node9\\.org|\n                            peertube\\.hatthieves\\.es|\n                            video\\.fitchfamily\\.org|\n                            peertube\\.ddns\\.net|\n                            video\\.ifuncle\\.kr|\n                            video\\.fdlibre\\.eu|\n                            tube\\.22decembre\\.eu|\n                            peertube\\.harmoniescreatives\\.com|\n                            tube\\.fabrigli\\.fr|\n                            video\\.thedwyers\\.co|\n                            video\\.bruitbruit\\.com|\n                            peertube\\.foxfam\\.club|\n                            peer\\.philoxweb\\.be|\n                            videos\\.bugs\\.social|\n                            peertube\\.malbert\\.xyz|\n                            peertube\\.bilange\\.ca|\n                            libretube\\.net|\n                            diytelevision\\.com|\n                            peertube\\.fedilab\\.app|\n                            libre\\.video|\n                            video\\.mstddntfdn\\.online|\n                            us\\.tv|\n                            peertube\\.sl-network\\.fr|\n                            peertube\\.dynlinux\\.io|\n                            peertube\\.david\\.durieux\\.family|\n                            peertube\\.linuxrocks\\.online|\n                            peerwatch\\.xyz|\n                            v\\.kretschmann\\.social|\n                            tube\\.otter\\.sh|\n                            yt\\.is\\.nota\\.live|\n                            tube\\.dragonpsi\\.xyz|\n                            peertube\\.boneheadmedia\\.com|\n                            videos\\.funkwhale\\.audio|\n                            watch\\.44con\\.com|\n                            peertube\\.gcaillaut\\.fr|\n                            peertube\\.icu|\n                            pony\\.tube|\n                            spacepub\\.space|\n                            tube\\.stbr\\.io|\n                            v\\.mom-gay\\.faith|\n                            tube\\.port0\\.xyz|\n                            peertube\\.simounet\\.net|\n                            play\\.jergefelt\\.se|\n                            peertube\\.zeteo\\.me|\n                            tube\\.danq\\.me|\n                            peertube\\.kerenon\\.com|\n                            tube\\.fab-l3\\.org|\n                            tube\\.calculate\\.social|\n                            peertube\\.mckillop\\.org|\n                            tube\\.netzspielplatz\\.de|\n                            vod\\.ksite\\.de|\n                            peertube\\.laas\\.fr|\n                            tube\\.govital\\.net|\n                            peertube\\.stephenson\\.cc|\n                            bistule\\.nohost\\.me|\n                            peertube\\.kajalinifi\\.de|\n                            video\\.ploud\\.jp|\n                            video\\.omniatv\\.com|\n                            peertube\\.ffs2play\\.fr|\n                            peertube\\.leboulaire\\.ovh|\n                            peertube\\.tronic-studio\\.com|\n                            peertube\\.public\\.cat|\n                            peertube\\.metalbanana\\.net|\n                            video\\.1000i100\\.fr|\n                            peertube\\.alter-nativ-voll\\.de|\n                            tube\\.pasa\\.tf|\n                            tube\\.worldofhauru\\.xyz|\n                            pt\\.kamp\\.site|\n                            peertube\\.teleassist\\.fr|\n                            videos\\.mleduc\\.xyz|\n                            conf\\.tube|\n                            media\\.privacyinternational\\.org|\n                            pt\\.forty-two\\.nl|\n                            video\\.halle-leaks\\.de|\n                            video\\.grosskopfgames\\.de|\n                            peertube\\.schaeferit\\.de|\n                            peertube\\.jackbot\\.fr|\n                            tube\\.extinctionrebellion\\.fr|\n                            peertube\\.f-si\\.org|\n                            video\\.subak\\.ovh|\n                            videos\\.koweb\\.fr|\n                            peertube\\.zergy\\.net|\n                            peertube\\.roflcopter\\.fr|\n                            peertube\\.floss-marketing-school\\.com|\n                            vloggers\\.social|\n                            peertube\\.iriseden\\.eu|\n                            videos\\.ubuntu-paris\\.org|\n                            peertube\\.mastodon\\.host|\n                            armstube\\.com|\n                            peertube\\.s2s\\.video|\n                            peertube\\.lol|\n                            tube\\.open-plug\\.eu|\n                            open\\.tube|\n                            peertube\\.ch|\n                            peertube\\.normandie-libre\\.fr|\n                            peertube\\.slat\\.org|\n                            video\\.lacaveatonton\\.ovh|\n                            peertube\\.uno|\n                            peertube\\.servebeer\\.com|\n                            peertube\\.fedi\\.quebec|\n                            tube\\.h3z\\.jp|\n                            tube\\.plus200\\.com|\n                            peertube\\.eric\\.ovh|\n                            tube\\.metadocs\\.cc|\n                            tube\\.unmondemeilleur\\.eu|\n                            gouttedeau\\.space|\n                            video\\.antirep\\.net|\n                            nrop\\.cant\\.at|\n                            tube\\.ksl-bmx\\.de|\n                            tube\\.plaf\\.fr|\n                            tube\\.tchncs\\.de|\n                            video\\.devinberg\\.com|\n                            hitchtube\\.fr|\n                            peertube\\.kosebamse\\.com|\n                            yunopeertube\\.myddns\\.me|\n                            peertube\\.varney\\.fr|\n                            peertube\\.anon-kenkai\\.com|\n                            tube\\.maiti\\.info|\n                            tubee\\.fr|\n                            videos\\.dinofly\\.com|\n                            toobnix\\.org|\n                            videotape\\.me|\n                            voca\\.tube|\n                            video\\.heromuster\\.com|\n                            video\\.lemediatv\\.fr|\n                            video\\.up\\.edu\\.ph|\n                            balafon\\.video|\n                            video\\.ivel\\.fr|\n                            thickrips\\.cloud|\n                            pt\\.laurentkruger\\.fr|\n                            video\\.monarch-pass\\.net|\n                            peertube\\.artica\\.center|\n                            video\\.alternanet\\.fr|\n                            indymotion\\.fr|\n                            fanvid\\.stopthatimp\\.net|\n                            video\\.farci\\.org|\n                            v\\.lesterpig\\.com|\n                            video\\.okaris\\.de|\n                            tube\\.pawelko\\.net|\n                            peertube\\.mablr\\.org|\n                            tube\\.fede\\.re|\n                            pytu\\.be|\n                            evertron\\.tv|\n                            devtube\\.dev-wiki\\.de|\n                            raptube\\.antipub\\.org|\n                            video\\.selea\\.se|\n                            peertube\\.mygaia\\.org|\n                            video\\.oh14\\.de|\n                            peertube\\.livingutopia\\.org|\n                            peertube\\.the-penguin\\.de|\n                            tube\\.thechangebook\\.org|\n                            tube\\.anjara\\.eu|\n                            pt\\.pube\\.tk|\n                            video\\.samedi\\.pm|\n                            mplayer\\.demouliere\\.eu|\n                            widemus\\.de|\n                            peertube\\.me|\n                            peertube\\.zapashcanon\\.fr|\n                            video\\.latavernedejohnjohn\\.fr|\n                            peertube\\.pcservice46\\.fr|\n                            peertube\\.mazzonetto\\.eu|\n                            video\\.irem\\.univ-paris-diderot\\.fr|\n                            video\\.livecchi\\.cloud|\n                            alttube\\.fr|\n                            video\\.coop\\.tools|\n                            video\\.cabane-libre\\.org|\n                            peertube\\.openstreetmap\\.fr|\n                            videos\\.alolise\\.org|\n                            irrsinn\\.video|\n                            video\\.antopie\\.org|\n                            scitech\\.video|\n                            tube2\\.nemsia\\.org|\n                            video\\.amic37\\.fr|\n                            peertube\\.freeforge\\.eu|\n                            video\\.arbitrarion\\.com|\n                            video\\.datsemultimedia\\.com|\n                            stoptrackingus\\.tv|\n                            peertube\\.ricostrongxxx\\.com|\n                            docker\\.videos\\.lecygnenoir\\.info|\n                            peertube\\.togart\\.de|\n                            tube\\.postblue\\.info|\n                            videos\\.domainepublic\\.net|\n                            peertube\\.cyber-tribal\\.com|\n                            video\\.gresille\\.org|\n                            peertube\\.dsmouse\\.net|\n                            cinema\\.yunohost\\.support|\n                            tube\\.theocevaer\\.fr|\n                            repro\\.video|\n                            tube\\.4aem\\.com|\n                            quaziinc\\.com|\n                            peertube\\.metawurst\\.space|\n                            videos\\.wakapo\\.com|\n                            video\\.ploud\\.fr|\n                            video\\.freeradical\\.zone|\n                            tube\\.valinor\\.fr|\n                            refuznik\\.video|\n                            pt\\.kircheneuenburg\\.de|\n                            peertube\\.asrun\\.eu|\n                            peertube\\.lagob\\.fr|\n                            videos\\.side-ways\\.net|\n                            91video\\.online|\n                            video\\.valme\\.io|\n                            video\\.taboulisme\\.com|\n                            videos-libr\\.es|\n                            tv\\.mooh\\.fr|\n                            nuage\\.acostey\\.fr|\n                            video\\.monsieur-a\\.fr|\n                            peertube\\.librelois\\.fr|\n                            videos\\.pair2jeux\\.tube|\n                            videos\\.pueseso\\.club|\n                            peer\\.mathdacloud\\.ovh|\n                            media\\.assassinate-you\\.net|\n                            vidcommons\\.org|\n                            ptube\\.rousset\\.nom\\.fr|\n                            tube\\.cyano\\.at|\n                            videos\\.squat\\.net|\n                            video\\.iphodase\\.fr|\n                            peertube\\.makotoworkshop\\.org|\n                            peertube\\.serveur\\.slv-valbonne\\.fr|\n                            vault\\.mle\\.party|\n                            hostyour\\.tv|\n                            videos\\.hack2g2\\.fr|\n                            libre\\.tube|\n                            pire\\.artisanlogiciel\\.net|\n                            videos\\.numerique-en-commun\\.fr|\n                            video\\.netsyms\\.com|\n                            video\\.die-partei\\.social|\n                            video\\.writeas\\.org|\n                            peertube\\.swarm\\.solvingmaz\\.es|\n                            tube\\.pericoloso\\.ovh|\n                            watching\\.cypherpunk\\.observer|\n                            videos\\.adhocmusic\\.com|\n                            tube\\.rfc1149\\.net|\n                            peertube\\.librelabucm\\.org|\n                            videos\\.numericoop\\.fr|\n                            peertube\\.koehn\\.com|\n                            peertube\\.anarchmusicall\\.net|\n                            tube\\.kampftoast\\.de|\n                            vid\\.y-y\\.li|\n                            peertube\\.xtenz\\.xyz|\n                            diode\\.zone|\n                            tube\\.egf\\.mn|\n                            peertube\\.nomagic\\.uk|\n                            visionon\\.tv|\n                            videos\\.koumoul\\.com|\n                            video\\.rastapuls\\.com|\n                            video\\.mantlepro\\.com|\n                            video\\.deadsuperhero\\.com|\n                            peertube\\.musicstudio\\.pro|\n                            peertube\\.we-keys\\.fr|\n                            artitube\\.artifaille\\.fr|\n                            peertube\\.ethernia\\.net|\n                            tube\\.midov\\.pl|\n                            peertube\\.fr|\n                            watch\\.snoot\\.tube|\n                            peertube\\.donnadieu\\.fr|\n                            argos\\.aquilenet\\.fr|\n                            tube\\.nemsia\\.org|\n                            tube\\.bruniau\\.net|\n                            videos\\.darckoune\\.moe|\n                            tube\\.traydent\\.info|\n                            dev\\.videos\\.lecygnenoir\\.info|\n                            peertube\\.nayya\\.org|\n                            peertube\\.live|\n                            peertube\\.mofgao\\.space|\n                            video\\.lequerrec\\.eu|\n                            peertube\\.amicale\\.net|\n                            aperi\\.tube|\n                            tube\\.ac-lyon\\.fr|\n                            video\\.lw1\\.at|\n                            www\\.yiny\\.org|\n                            videos\\.pofilo\\.fr|\n                            tube\\.lou\\.lt|\n                            choob\\.h\\.etbus\\.ch|\n                            tube\\.hoga\\.fr|\n                            peertube\\.heberge\\.fr|\n                            video\\.obermui\\.de|\n                            videos\\.cloudfrancois\\.fr|\n                            betamax\\.video|\n                            video\\.typica\\.us|\n                            tube\\.piweb\\.be|\n                            video\\.blender\\.org|\n                            peertube\\.cat|\n                            tube\\.kdy\\.ch|\n                            pe\\.ertu\\.be|\n                            peertube\\.social|\n                            videos\\.lescommuns\\.org|\n                            tv\\.datamol\\.org|\n                            videonaute\\.fr|\n                            dialup\\.express|\n                            peertube\\.nogafa\\.org|\n                            megatube\\.lilomoino\\.fr|\n                            peertube\\.tamanoir\\.foucry\\.net|\n                            peertube\\.devosi\\.org|\n                            peertube\\.1312\\.media|\n                            tube\\.bootlicker\\.party|\n                            skeptikon\\.fr|\n                            video\\.blueline\\.mg|\n                            tube\\.homecomputing\\.fr|\n                            tube\\.ouahpiti\\.info|\n                            video\\.tedomum\\.net|\n                            video\\.g3l\\.org|\n                            fontube\\.fr|\n                            peertube\\.gaialabs\\.ch|\n                            tube\\.kher\\.nl|\n                            peertube\\.qtg\\.fr|\n                            video\\.migennes\\.net|\n                            tube\\.p2p\\.legal|\n                            troll\\.tv|\n                            videos\\.iut-orsay\\.fr|\n                            peertube\\.solidev\\.net|\n                            videos\\.cemea\\.org|\n                            video\\.passageenseine\\.fr|\n                            videos\\.festivalparminous\\.org|\n                            peertube\\.touhoppai\\.moe|\n                            sikke\\.fi|\n                            peer\\.hostux\\.social|\n                            share\\.tube|\n                            peertube\\.walkingmountains\\.fr|\n                            videos\\.benpro\\.fr|\n                            peertube\\.parleur\\.net|\n                            peertube\\.heraut\\.eu|\n                            tube\\.aquilenet\\.fr|\n                            peertube\\.gegeweb\\.eu|\n                            framatube\\.org|\n                            thinkerview\\.video|\n                            tube\\.conferences-gesticulees\\.net|\n                            peertube\\.datagueule\\.tv|\n                            video\\.lqdn\\.fr|\n                            tube\\.mochi\\.academy|\n                            media\\.zat\\.im|\n                            video\\.colibris-outilslibres\\.org|\n                            tube\\.svnet\\.fr|\n                            peertube\\.video|\n                            peertube2\\.cpy\\.re|\n                            peertube3\\.cpy\\.re|\n                            videos\\.tcit\\.fr|\n                            peertube\\.cpy\\.re|\n                            canard\\.tube\n                        ))/(?P<type>(?:a|c|w/p))/\n                    (?P<id>[^/]+)\n                    '


class PeerTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.peertv'
    IE_NAME = 'peer.tv'
    _VALID_URL = 'https?://(?:www\\.)?peer\\.tv/(?:de|it|en)/(?P<id>\\d+)'


class PelotonIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.peloton'
    IE_NAME = 'peloton'
    _VALID_URL = 'https?://members\\.onepeloton\\.com/classes/player/(?P<id>[a-f0-9]+)'
    _NETRC_MACHINE = 'peloton'


class PelotonLiveIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.peloton'
    IE_NAME = 'peloton:live'
    IE_DESC = 'Peloton Live'
    _VALID_URL = 'https?://members\\.onepeloton\\.com/player/live/(?P<id>[a-f0-9]+)'


class PeopleIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.people'
    IE_NAME = 'People'
    _VALID_URL = 'https?://(?:www\\.)?people\\.com/people/videos/0,,(?P<id>\\d+),00\\.html'


class PerformGroupIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.performgroup'
    IE_NAME = 'PerformGroup'
    _VALID_URL = 'https?://player\\.performgroup\\.com/eplayer(?:/eplayer\\.html|\\.js)#/?(?P<id>[0-9a-f]{26})\\.(?P<auth_token>[0-9a-z]{26})'


class PeriscopeBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.periscope'
    IE_NAME = 'PeriscopeBase'


class PeriscopeIE(PeriscopeBaseIE):
    _module = 'yt_dlp.extractor.periscope'
    IE_NAME = 'periscope'
    IE_DESC = 'Periscope'
    _VALID_URL = 'https?://(?:www\\.)?(?:periscope|pscp)\\.tv/[^/]+/(?P<id>[^/?#]+)'


class PeriscopeUserIE(PeriscopeBaseIE):
    _module = 'yt_dlp.extractor.periscope'
    IE_NAME = 'periscope:user'
    IE_DESC = 'Periscope user videos'
    _VALID_URL = 'https?://(?:www\\.)?(?:periscope|pscp)\\.tv/(?P<id>[^/]+)/?$'


class PhilharmonieDeParisIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.philharmoniedeparis'
    IE_NAME = 'PhilharmonieDeParis'
    IE_DESC = 'Philharmonie de Paris'
    _VALID_URL = '(?x)\n                    https?://\n                        (?:\n                            live\\.philharmoniedeparis\\.fr/(?:[Cc]oncert/|embed(?:app)?/|misc/Playlist\\.ashx\\?id=)|\n                            pad\\.philharmoniedeparis\\.fr/(?:doc/CIMU/|player\\.aspx\\?id=)|\n                            philharmoniedeparis\\.fr/fr/live/concert/|\n                            otoplayer\\.philharmoniedeparis\\.fr/fr/embed/\n                        )\n                        (?P<id>\\d+)\n                    '


class ZDFBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.zdf'
    IE_NAME = 'ZDFBase'


class PhoenixIE(ZDFBaseIE):
    _module = 'yt_dlp.extractor.phoenix'
    IE_NAME = 'phoenix.de'
    _VALID_URL = 'https?://(?:www\\.)?phoenix\\.de/(?:[^/]+/)*[^/?#&]*-a-(?P<id>\\d+)\\.html'


class PhotobucketIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.photobucket'
    IE_NAME = 'Photobucket'
    _VALID_URL = 'https?://(?:[a-z0-9]+\\.)?photobucket\\.com/.*(([\\?\\&]current=)|_)(?P<id>.*)\\.(?P<ext>(flv)|(mp4))'


class PiaproIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.piapro'
    IE_NAME = 'Piapro'
    _VALID_URL = 'https?://piapro\\.jp/t/(?P<id>\\w+)/?'
    _NETRC_MACHINE = 'piapro'


class PicartoIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.picarto'
    IE_NAME = 'Picarto'
    _VALID_URL = 'https?://(?:www.)?picarto\\.tv/(?P<id>[a-zA-Z0-9]+)'

    @classmethod
    def suitable(cls, url):
        return False if PicartoVodIE.suitable(url) else super(PicartoIE, cls).suitable(url)


class PicartoVodIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.picarto'
    IE_NAME = 'PicartoVod'
    _VALID_URL = 'https?://(?:www.)?picarto\\.tv/videopopout/(?P<id>[^/?#&]+)'


class PikselIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.piksel'
    IE_NAME = 'Piksel'
    _VALID_URL = '(?x)https?://\n        (?:\n            (?:\n                player\\.\n                    (?:\n                        olympusattelecom|\n                        vibebyvista\n                    )|\n                (?:api|player)\\.multicastmedia|\n                (?:api-ovp|player)\\.piksel\n            )\\.com|\n            (?:\n                mz-edge\\.stream\\.co|\n                movie-s\\.nhk\\.or\n            )\\.jp|\n            vidego\\.baltimorecity\\.gov\n        )/v/(?:refid/(?P<refid>[^/]+)/prefid/)?(?P<id>[\\w-]+)'


class PinkbikeIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.pinkbike'
    IE_NAME = 'Pinkbike'
    _VALID_URL = 'https?://(?:(?:www\\.)?pinkbike\\.com/video/|es\\.pinkbike\\.org/i/kvid/kvid-y5\\.swf\\?id=)(?P<id>[0-9]+)'


class PinterestBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.pinterest'
    IE_NAME = 'PinterestBase'


class PinterestIE(PinterestBaseIE):
    _module = 'yt_dlp.extractor.pinterest'
    IE_NAME = 'Pinterest'
    _VALID_URL = 'https?://(?:[^/]+\\.)?pinterest\\.(?:com|fr|de|ch|jp|cl|ca|it|co\\.uk|nz|ru|com\\.au|at|pt|co\\.kr|es|com\\.mx|dk|ph|th|com\\.uy|co|nl|info|kr|ie|vn|com\\.vn|ec|mx|in|pe|co\\.at|hu|co\\.in|co\\.nz|id|com\\.ec|com\\.py|tw|be|uk|com\\.bo|com\\.pe)/pin/(?P<id>\\d+)'


class PinterestCollectionIE(PinterestBaseIE):
    _module = 'yt_dlp.extractor.pinterest'
    IE_NAME = 'PinterestCollection'
    _VALID_URL = 'https?://(?:[^/]+\\.)?pinterest\\.(?:com|fr|de|ch|jp|cl|ca|it|co\\.uk|nz|ru|com\\.au|at|pt|co\\.kr|es|com\\.mx|dk|ph|th|com\\.uy|co|nl|info|kr|ie|vn|com\\.vn|ec|mx|in|pe|co\\.at|hu|co\\.in|co\\.nz|id|com\\.ec|com\\.py|tw|be|uk|com\\.bo|com\\.pe)/(?P<username>[^/]+)/(?P<id>[^/?#&]+)'

    @classmethod
    def suitable(cls, url):
        return False if PinterestIE.suitable(url) else super(
            PinterestCollectionIE, cls).suitable(url)


class PixivSketchBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.pixivsketch'
    IE_NAME = 'PixivSketchBase'


class PixivSketchIE(PixivSketchBaseIE):
    _module = 'yt_dlp.extractor.pixivsketch'
    IE_NAME = 'pixiv:sketch'
    _VALID_URL = 'https?://sketch\\.pixiv\\.net/@(?P<uploader_id>[a-zA-Z0-9_-]+)/lives/(?P<id>\\d+)/?'
    age_limit = 18


class PixivSketchUserIE(PixivSketchBaseIE):
    _module = 'yt_dlp.extractor.pixivsketch'
    IE_NAME = 'pixiv:sketch:user'
    _VALID_URL = 'https?://sketch\\.pixiv\\.net/@(?P<id>[a-zA-Z0-9_-]+)/?'

    @classmethod
    def suitable(cls, url):
        return super(PixivSketchUserIE, cls).suitable(url) and not PixivSketchIE.suitable(url)


class PladformIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.pladform'
    IE_NAME = 'Pladform'
    _VALID_URL = '(?x)\n                    https?://\n                        (?:\n                            (?:\n                                out\\.pladform\\.ru/player|\n                                static\\.pladform\\.ru/player\\.swf\n                            )\n                            \\?.*\\bvideoid=|\n                            video\\.pladform\\.ru/catalog/video/videoid/\n                        )\n                        (?P<id>\\d+)\n                    '


class PlanetMarathiIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.planetmarathi'
    IE_NAME = 'PlanetMarathi'
    _VALID_URL = 'https?://(?:www\\.)?planetmarathi\\.com/titles/(?P<id>[^/#&?$]+)'


class PlatziBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.platzi'
    IE_NAME = 'PlatziBase'
    _NETRC_MACHINE = 'platzi'


class PlatziIE(PlatziBaseIE):
    _module = 'yt_dlp.extractor.platzi'
    IE_NAME = 'Platzi'
    _VALID_URL = '(?x)\n                    https?://\n                        (?:\n                            platzi\\.com/clases|           # es version\n                            courses\\.platzi\\.com/classes  # en version\n                        )/[^/]+/(?P<id>\\d+)-[^/?\\#&]+\n                    '
    _NETRC_MACHINE = 'platzi'


class PlatziCourseIE(PlatziBaseIE):
    _module = 'yt_dlp.extractor.platzi'
    IE_NAME = 'PlatziCourse'
    _VALID_URL = '(?x)\n                    https?://\n                        (?:\n                            platzi\\.com/clases|           # es version\n                            courses\\.platzi\\.com/classes  # en version\n                        )/(?P<id>[^/?\\#&]+)\n                    '
    _NETRC_MACHINE = 'platzi'

    @classmethod
    def suitable(cls, url):
        return False if PlatziIE.suitable(url) else super(PlatziCourseIE, cls).suitable(url)


class PlayFMIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.playfm'
    IE_NAME = 'play.fm'
    _VALID_URL = 'https?://(?:www\\.)?play\\.fm/(?P<slug>(?:[^/]+/)+(?P<id>[^/]+))/?(?:$|[?#])'


class PlayPlusTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.playplustv'
    IE_NAME = 'PlayPlusTV'
    _VALID_URL = 'https?://(?:www\\.)?playplus\\.(?:com|tv)/VOD/(?P<project_id>[0-9]+)/(?P<id>[0-9a-f]{32})'
    _NETRC_MACHINE = 'playplustv'


class PlaysTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.plays'
    IE_NAME = 'PlaysTV'
    _VALID_URL = 'https?://(?:www\\.)?plays\\.tv/(?:video|embeds)/(?P<id>[0-9a-f]{18})'


class PlayStuffIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.playstuff'
    IE_NAME = 'PlayStuff'
    _VALID_URL = 'https?://(?:www\\.)?play\\.stuff\\.co\\.nz/details/(?P<id>[^/?#&]+)'


class PlaySuisseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.playsuisse'
    IE_NAME = 'PlaySuisse'
    _VALID_URL = 'https?://(?:www\\.)?playsuisse\\.ch/watch/(?P<id>[0-9]+)'


class PlaytvakIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.playtvak'
    IE_NAME = 'Playtvak'
    IE_DESC = 'Playtvak.cz, iDNES.cz and Lidovky.cz'
    _VALID_URL = 'https?://(?:.+?\\.)?(?:playtvak|idnes|lidovky|metro)\\.cz/.*\\?(?:c|idvideo)=(?P<id>[^&]+)'


class PlayvidIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.playvid'
    IE_NAME = 'Playvid'
    _VALID_URL = 'https?://(?:www\\.)?playvid\\.com/watch(\\?v=|/)(?P<id>.+?)(?:#|$)'
    age_limit = 18


class PlaywireIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.playwire'
    IE_NAME = 'Playwire'
    _VALID_URL = 'https?://(?:config|cdn)\\.playwire\\.com(?:/v2)?/(?P<publisher_id>\\d+)/(?:videos/v2|embed|config)/(?P<id>\\d+)'


class PlutoTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.plutotv'
    IE_NAME = 'PlutoTV'
    _VALID_URL = '(?x)\n        https?://(?:www\\.)?pluto\\.tv(?:/[^/]+)?/on-demand\n        /(?P<video_type>movies|series)\n        /(?P<series_or_movie_slug>[^/]+)\n        (?:\n            (?:/seasons?/(?P<season_no>\\d+))?\n            (?:/episode/(?P<episode_slug>[^/]+))?\n        )?\n        /?(?:$|[#?])'


class PluralsightBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.pluralsight'
    IE_NAME = 'PluralsightBase'


class PluralsightIE(PluralsightBaseIE):
    _module = 'yt_dlp.extractor.pluralsight'
    IE_NAME = 'pluralsight'
    _VALID_URL = 'https?://(?:(?:www|app)\\.)?pluralsight\\.com/(?:training/)?player\\?'
    _NETRC_MACHINE = 'pluralsight'


class PluralsightCourseIE(PluralsightBaseIE):
    _module = 'yt_dlp.extractor.pluralsight'
    IE_NAME = 'pluralsight:course'
    _VALID_URL = 'https?://(?:(?:www|app)\\.)?pluralsight\\.com/(?:library/)?courses/(?P<id>[^/]+)'


class PodbayFMIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.podbayfm'
    IE_NAME = 'PodbayFM'
    _VALID_URL = 'https?://podbay\\.fm/p/[^/]*/e/(?P<id>[^/]*)/?(?:[\\?#].*)?$'


class PodbayFMChannelIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.podbayfm'
    IE_NAME = 'PodbayFMChannel'
    _VALID_URL = 'https?://podbay\\.fm/p/(?P<id>[^/]*)/?(?:[\\?#].*)?$'


class PodchaserIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.podchaser'
    IE_NAME = 'Podchaser'
    _VALID_URL = 'https?://(?:www\\.)?podchaser\\.com/podcasts/[\\w-]+-(?P<podcast_id>\\d+)(?:/episodes/[\\w-]+-(?P<id>\\d+))?'


class PodomaticIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.podomatic'
    IE_NAME = 'podomatic'
    _VALID_URL = '(?x)\n                    (?P<proto>https?)://\n                        (?:\n                            (?P<channel>[^.]+)\\.podomatic\\.com/entry|\n                            (?:www\\.)?podomatic\\.com/podcasts/(?P<channel_2>[^/]+)/episodes\n                        )/\n                        (?P<id>[^/?#&]+)\n                '


class PokemonIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.pokemon'
    IE_NAME = 'Pokemon'
    _VALID_URL = 'https?://(?:www\\.)?pokemon\\.com/[a-z]{2}(?:.*?play=(?P<id>[a-z0-9]{32})|/(?:[^/]+/)+(?P<display_id>[^/?#&]+))'


class PokemonWatchIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.pokemon'
    IE_NAME = 'PokemonWatch'
    _VALID_URL = 'https?://watch\\.pokemon\\.com/[a-z]{2}-[a-z]{2}/(?:#/)?player(?:\\.html)?\\?id=(?P<id>[a-z0-9]{32})'


class PokerGoBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.pokergo'
    IE_NAME = 'PokerGoBase'
    _NETRC_MACHINE = 'pokergo'


class PokerGoIE(PokerGoBaseIE):
    _module = 'yt_dlp.extractor.pokergo'
    IE_NAME = 'PokerGo'
    _VALID_URL = 'https?://(?:www\\.)?pokergo\\.com/videos/(?P<id>[^&$#/?]+)'
    _NETRC_MACHINE = 'pokergo'


class PokerGoCollectionIE(PokerGoBaseIE):
    _module = 'yt_dlp.extractor.pokergo'
    IE_NAME = 'PokerGoCollection'
    _VALID_URL = 'https?://(?:www\\.)?pokergo\\.com/collections/(?P<id>[^&$#/?]+)'
    _NETRC_MACHINE = 'pokergo'


class PolsatGoIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.polsatgo'
    IE_NAME = 'PolsatGo'
    _VALID_URL = 'https?://(?:www\\.)?polsat(?:box)?go\\.pl/.+/(?P<id>[0-9a-fA-F]+)(?:[/#?]|$)'
    age_limit = 12


class PolskieRadioBaseExtractor(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.polskieradio'
    IE_NAME = 'PolskieRadioBaseExtract'


class PolskieRadioIE(PolskieRadioBaseExtractor):
    _module = 'yt_dlp.extractor.polskieradio'
    IE_NAME = 'PolskieRadio'
    _VALID_URL = 'https?://(?:www\\.)?polskieradio(?:24)?\\.pl/\\d+/\\d+/Artykul/(?P<id>[0-9]+)'


class PolskieRadioCategoryIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.polskieradio'
    IE_NAME = 'PolskieRadioCategory'
    _VALID_URL = 'https?://(?:www\\.)?polskieradio\\.pl/\\d+(?:,[^/]+)?/(?P<id>\\d+)'

    @classmethod
    def suitable(cls, url):
        return False if PolskieRadioIE.suitable(url) else super(PolskieRadioCategoryIE, cls).suitable(url)


class PolskieRadioPlayerIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.polskieradio'
    IE_NAME = 'polskieradio:player'
    _VALID_URL = 'https?://player\\.polskieradio\\.pl/anteny/(?P<id>[^/]+)'


class PolskieRadioPodcastBaseExtractor(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.polskieradio'
    IE_NAME = 'PolskieRadioPodcastBaseExtract'


class PolskieRadioPodcastIE(PolskieRadioPodcastBaseExtractor):
    _module = 'yt_dlp.extractor.polskieradio'
    IE_NAME = 'polskieradio:podcast'
    _VALID_URL = 'https?://podcasty\\.polskieradio\\.pl/track/(?P<id>[a-f\\d]{8}(?:-[a-f\\d]{4}){4}[a-f\\d]{8})'


class PolskieRadioPodcastListIE(PolskieRadioPodcastBaseExtractor):
    _module = 'yt_dlp.extractor.polskieradio'
    IE_NAME = 'polskieradio:podcast:list'
    _VALID_URL = 'https?://podcasty\\.polskieradio\\.pl/podcast/(?P<id>\\d+)'


class PolskieRadioRadioKierowcowIE(PolskieRadioBaseExtractor):
    _module = 'yt_dlp.extractor.polskieradio'
    IE_NAME = 'polskieradio:kierowcow'
    _VALID_URL = 'https?://(?:www\\.)?radiokierowcow\\.pl/artykul/(?P<id>[0-9]+)'


class PopcorntimesIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.popcorntimes'
    IE_NAME = 'Popcorntimes'
    _VALID_URL = 'https?://popcorntimes\\.tv/[^/]+/m/(?P<id>[^/]+)/(?P<display_id>[^/?#&]+)'


class PopcornTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.popcorntv'
    IE_NAME = 'PopcornTV'
    _VALID_URL = 'https?://[^/]+\\.popcorntv\\.it/guarda/(?P<display_id>[^/]+)/(?P<id>\\d+)'


class Porn91IE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.porn91'
    IE_NAME = '91porn'
    _VALID_URL = '(?:https?://)(?:www\\.|)91porn\\.com/.+?\\?viewkey=(?P<id>[\\w\\d]+)'
    age_limit = 18


class PornComIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.porncom'
    IE_NAME = 'PornCom'
    _VALID_URL = 'https?://(?:[a-zA-Z]+\\.)?porn\\.com/videos/(?:(?P<display_id>[^/]+)-)?(?P<id>\\d+)'
    age_limit = 18


class PornFlipIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.pornflip'
    IE_NAME = 'PornFlip'
    _VALID_URL = 'https?://(?:www\\.)?pornflip\\.com/(?:(embed|sv|v)/)?(?P<id>[^/]+)'
    age_limit = 18


class PornHdIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.pornhd'
    IE_NAME = 'PornHd'
    _VALID_URL = 'https?://(?:www\\.)?pornhd\\.com/(?:[a-z]{2,4}/)?videos/(?P<id>\\d+)(?:/(?P<display_id>.+))?'
    age_limit = 18


class PornHubBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.pornhub'
    IE_NAME = 'PornHubBase'
    _NETRC_MACHINE = 'pornhub'


class PornHubIE(PornHubBaseIE):
    _module = 'yt_dlp.extractor.pornhub'
    IE_NAME = 'PornHub'
    IE_DESC = 'PornHub and Thumbzilla'
    _VALID_URL = '(?x)\n                    https?://\n                        (?:\n                            (?:[^/]+\\.)?\n                            (?:(?P<host>pornhub(?:premium)?\\.(?:com|net|org))|pornhubvybmsymdol4iibwgwtkpwmeyd6luq2gxajgjzfjvotyt5zhyd\\.onion)\n                            /(?:(?:view_video\\.php|video/show)\\?viewkey=|embed/)|\n                            (?:www\\.)?thumbzilla\\.com/video/\n                        )\n                        (?P<id>[\\da-z]+)\n                    '
    _NETRC_MACHINE = 'pornhub'
    age_limit = 18


class PornHubPlaylistBaseIE(PornHubBaseIE):
    _module = 'yt_dlp.extractor.pornhub'
    IE_NAME = 'PornHubPlaylistBase'
    _NETRC_MACHINE = 'pornhub'


class PornHubUserIE(PornHubPlaylistBaseIE):
    _module = 'yt_dlp.extractor.pornhub'
    IE_NAME = 'PornHubUser'
    _VALID_URL = '(?P<url>https?://(?:[^/]+\\.)?(?:(?P<host>pornhub(?:premium)?\\.(?:com|net|org))|pornhubvybmsymdol4iibwgwtkpwmeyd6luq2gxajgjzfjvotyt5zhyd\\.onion)/(?:(?:user|channel)s|model|pornstar)/(?P<id>[^/?#&]+))(?:[?#&]|/(?!videos)|$)'
    _NETRC_MACHINE = 'pornhub'


class PornHubPlaylistIE(PornHubPlaylistBaseIE):
    _module = 'yt_dlp.extractor.pornhub'
    IE_NAME = 'PornHubPlaylist'
    _VALID_URL = '(?P<url>https?://(?:[^/]+\\.)?(?:(?P<host>pornhub(?:premium)?\\.(?:com|net|org))|pornhubvybmsymdol4iibwgwtkpwmeyd6luq2gxajgjzfjvotyt5zhyd\\.onion)/playlist/(?P<id>[^/?#&]+))'
    _NETRC_MACHINE = 'pornhub'


class PornHubPagedPlaylistBaseIE(PornHubPlaylistBaseIE):
    _module = 'yt_dlp.extractor.pornhub'
    IE_NAME = 'PornHubPagedPlaylistBase'
    _NETRC_MACHINE = 'pornhub'


class PornHubPagedVideoListIE(PornHubPagedPlaylistBaseIE):
    _module = 'yt_dlp.extractor.pornhub'
    IE_NAME = 'PornHubPagedVideoList'
    _VALID_URL = 'https?://(?:[^/]+\\.)?(?:(?P<host>pornhub(?:premium)?\\.(?:com|net|org))|pornhubvybmsymdol4iibwgwtkpwmeyd6luq2gxajgjzfjvotyt5zhyd\\.onion)/(?!playlist/)(?P<id>(?:[^/]+/)*[^/?#&]+)'
    _NETRC_MACHINE = 'pornhub'

    @classmethod
    def suitable(cls, url):
        return (False
                if PornHubIE.suitable(url) or PornHubUserIE.suitable(url) or PornHubUserVideosUploadIE.suitable(url)
                else super(PornHubPagedVideoListIE, cls).suitable(url))


class PornHubUserVideosUploadIE(PornHubPagedPlaylistBaseIE):
    _module = 'yt_dlp.extractor.pornhub'
    IE_NAME = 'PornHubUserVideosUpload'
    _VALID_URL = '(?P<url>https?://(?:[^/]+\\.)?(?:(?P<host>pornhub(?:premium)?\\.(?:com|net|org))|pornhubvybmsymdol4iibwgwtkpwmeyd6luq2gxajgjzfjvotyt5zhyd\\.onion)/(?:(?:user|channel)s|model|pornstar)/(?P<id>[^/]+)/videos/upload)'
    _NETRC_MACHINE = 'pornhub'


class PornotubeIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.pornotube'
    IE_NAME = 'Pornotube'
    _VALID_URL = 'https?://(?:\\w+\\.)?pornotube\\.com/(?:[^?#]*?)/video/(?P<id>[0-9]+)'
    age_limit = 18


class PornoVoisinesIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.pornovoisines'
    IE_NAME = 'PornoVoisines'
    _VALID_URL = 'https?://(?:www\\.)?pornovoisines\\.com/videos/show/(?P<id>\\d+)/(?P<display_id>[^/.]+)'
    age_limit = 18


class PornoXOIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.pornoxo'
    IE_NAME = 'PornoXO'
    _VALID_URL = 'https?://(?:www\\.)?pornoxo\\.com/videos/(?P<id>\\d+)/(?P<display_id>[^/]+)\\.html'
    age_limit = 18


class PornezIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.pornez'
    IE_NAME = 'Pornez'
    _VALID_URL = 'https?://(?:www\\.)?pornez\\.net/video(?P<id>[0-9]+)/'
    age_limit = 18


class PuhuTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.puhutv'
    IE_NAME = 'puhutv'
    _VALID_URL = 'https?://(?:www\\.)?puhutv\\.com/(?P<id>[^/?#&]+)-izle'


class PuhuTVSerieIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.puhutv'
    IE_NAME = 'puhutv:serie'
    _VALID_URL = 'https?://(?:www\\.)?puhutv\\.com/(?P<id>[^/?#&]+)-detay'


class PrankCastIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.prankcast'
    IE_NAME = 'PrankCast'
    _VALID_URL = 'https?://(?:www\\.)?prankcast\\.com/[^/?#]+/showreel/(?P<id>\\d+)-(?P<display_id>[^/?#]+)'


class PremiershipRugbyIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.premiershiprugby'
    IE_NAME = 'PremiershipRugby'
    _VALID_URL = 'https?://(?:\\w+\\.)premiershiprugby\\.(?:com)/watch/(?P<id>[\\w-]+)'


class PressTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.presstv'
    IE_NAME = 'PressTV'
    _VALID_URL = 'https?://(?:www\\.)?presstv\\.ir/[^/]+/(?P<y>\\d+)/(?P<m>\\d+)/(?P<d>\\d+)/(?P<id>\\d+)/(?P<display_id>[^/]+)?'


class ProjectVeritasIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.projectveritas'
    IE_NAME = 'ProjectVeritas'
    _VALID_URL = 'https?://(?:www\\.)?projectveritas\\.com/(?P<type>news|video)/(?P<id>[^/?#]+)'


class ProSiebenSat1BaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.prosiebensat1'
    IE_NAME = 'ProSiebenSat1Base'


class ProSiebenSat1IE(ProSiebenSat1BaseIE):
    _module = 'yt_dlp.extractor.prosiebensat1'
    IE_NAME = 'prosiebensat1'
    IE_DESC = 'ProSiebenSat.1 Digital'
    _VALID_URL = '(?x)\n                    https?://\n                        (?:www\\.)?\n                        (?:\n                            (?:beta\\.)?\n                            (?:\n                                prosieben(?:maxx)?|sixx|sat1(?:gold)?|kabeleins(?:doku)?|the-voice-of-germany|advopedia\n                            )\\.(?:de|at|ch)|\n                            ran\\.de|fem\\.com|advopedia\\.de|galileo\\.tv/video\n                        )\n                        /(?P<id>.+)\n                    '


class PRXBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.prx'
    IE_NAME = 'PRXBase'


class PRXStoryIE(PRXBaseIE):
    _module = 'yt_dlp.extractor.prx'
    IE_NAME = 'PRXStory'
    _VALID_URL = 'https?://(?:(?:beta|listen)\\.)?prx.org/stories/(?P<id>\\d+)'


class PRXSeriesIE(PRXBaseIE):
    _module = 'yt_dlp.extractor.prx'
    IE_NAME = 'PRXSeries'
    _VALID_URL = 'https?://(?:(?:beta|listen)\\.)?prx.org/series/(?P<id>\\d+)'


class PRXAccountIE(PRXBaseIE):
    _module = 'yt_dlp.extractor.prx'
    IE_NAME = 'PRXAccount'
    _VALID_URL = 'https?://(?:(?:beta|listen)\\.)?prx.org/accounts/(?P<id>\\d+)'


class PRXStoriesSearchIE(PRXBaseIE, LazyLoadSearchExtractor):
    _module = 'yt_dlp.extractor.prx'
    IE_NAME = 'prxstories:search'
    IE_DESC = 'PRX Stories Search'
    SEARCH_KEY = 'prxstories'
    _VALID_URL = 'prxstories(?P<prefix>|[1-9][0-9]*|all):(?P<query>[\\s\\S]+)'


class PRXSeriesSearchIE(PRXBaseIE, LazyLoadSearchExtractor):
    _module = 'yt_dlp.extractor.prx'
    IE_NAME = 'prxseries:search'
    IE_DESC = 'PRX Series Search'
    SEARCH_KEY = 'prxseries'
    _VALID_URL = 'prxseries(?P<prefix>|[1-9][0-9]*|all):(?P<query>[\\s\\S]+)'


class Puls4IE(ProSiebenSat1BaseIE):
    _module = 'yt_dlp.extractor.puls4'
    IE_NAME = 'Puls4'
    _VALID_URL = 'https?://(?:www\\.)?puls4\\.com/(?P<id>[^?#&]+)'


class PyvideoIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.pyvideo'
    IE_NAME = 'Pyvideo'
    _VALID_URL = 'https?://(?:www\\.)?pyvideo\\.org/(?P<category>[^/]+)/(?P<id>[^/?#&.]+)'


class QingTingIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.qingting'
    IE_NAME = 'QingTing'
    _VALID_URL = 'https?://(?:www\\.|m\\.)?(?:qingting\\.fm|qtfm\\.cn)/v?channels/(?P<channel>\\d+)/programs/(?P<id>\\d+)'


class QQMusicIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.qqmusic'
    IE_NAME = 'qqmusic'
    IE_DESC = 'QQ音乐'
    _VALID_URL = 'https?://y\\.qq\\.com/n/yqq/song/(?P<id>[0-9A-Za-z]+)\\.html'


class QQPlaylistBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.qqmusic'
    IE_NAME = 'QQPlaylistBase'


class QQMusicSingerIE(QQPlaylistBaseIE):
    _module = 'yt_dlp.extractor.qqmusic'
    IE_NAME = 'qqmusic:singer'
    IE_DESC = 'QQ音乐 - 歌手'
    _VALID_URL = 'https?://y\\.qq\\.com/n/yqq/singer/(?P<id>[0-9A-Za-z]+)\\.html'


class QQMusicAlbumIE(QQPlaylistBaseIE):
    _module = 'yt_dlp.extractor.qqmusic'
    IE_NAME = 'qqmusic:album'
    IE_DESC = 'QQ音乐 - 专辑'
    _VALID_URL = 'https?://y\\.qq\\.com/n/yqq/album/(?P<id>[0-9A-Za-z]+)\\.html'


class QQMusicToplistIE(QQPlaylistBaseIE):
    _module = 'yt_dlp.extractor.qqmusic'
    IE_NAME = 'qqmusic:toplist'
    IE_DESC = 'QQ音乐 - 排行榜'
    _VALID_URL = 'https?://y\\.qq\\.com/n/yqq/toplist/(?P<id>[0-9]+)\\.html'


class QQMusicPlaylistIE(QQPlaylistBaseIE):
    _module = 'yt_dlp.extractor.qqmusic'
    IE_NAME = 'qqmusic:playlist'
    IE_DESC = 'QQ音乐 - 歌单'
    _VALID_URL = 'https?://y\\.qq\\.com/n/yqq/playlist/(?P<id>[0-9]+)\\.html'


class R7IE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.r7'
    IE_NAME = 'R7'
    _VALID_URL = '(?x)\n                        https?://\n                        (?:\n                            (?:[a-zA-Z]+)\\.r7\\.com(?:/[^/]+)+/idmedia/|\n                            noticias\\.r7\\.com(?:/[^/]+)+/[^/]+-|\n                            player\\.r7\\.com/video/i/\n                        )\n                        (?P<id>[\\da-f]{24})\n                    '


class R7ArticleIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.r7'
    IE_NAME = 'R7Article'
    _VALID_URL = 'https?://(?:[a-zA-Z]+)\\.r7\\.com/(?:[^/]+/)+[^/?#&]+-(?P<id>\\d+)'

    @classmethod
    def suitable(cls, url):
        return False if R7IE.suitable(url) else super(R7ArticleIE, cls).suitable(url)


class RadikoBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.radiko'
    IE_NAME = 'RadikoBase'


class RadikoIE(RadikoBaseIE):
    _module = 'yt_dlp.extractor.radiko'
    IE_NAME = 'Radiko'
    _VALID_URL = 'https?://(?:www\\.)?radiko\\.jp/#!/ts/(?P<station>[A-Z0-9-]+)/(?P<id>\\d+)'


class RadikoRadioIE(RadikoBaseIE):
    _module = 'yt_dlp.extractor.radiko'
    IE_NAME = 'RadikoRadio'
    _VALID_URL = 'https?://(?:www\\.)?radiko\\.jp/#!/live/(?P<id>[A-Z0-9-]+)'


class RadioCanadaIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.radiocanada'
    IE_NAME = 'radiocanada'
    _VALID_URL = '(?:radiocanada:|https?://ici\\.radio-canada\\.ca/widgets/mediaconsole/)(?P<app_code>[^:/]+)[:/](?P<id>[0-9]+)'


class RadioCanadaAudioVideoIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.radiocanada'
    IE_NAME = 'radiocanada:audiovideo'
    _VALID_URL = 'https?://ici\\.radio-canada\\.ca/([^/]+/)*media-(?P<id>[0-9]+)'


class RadioDeIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.radiode'
    IE_NAME = 'radio.de'
    _VALID_URL = 'https?://(?P<id>.+?)\\.(?:radio\\.(?:de|at|fr|pt|es|pl|it)|rad\\.io)'


class RadioJavanIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.radiojavan'
    IE_NAME = 'RadioJavan'
    _VALID_URL = 'https?://(?:www\\.)?radiojavan\\.com/videos/video/(?P<id>[^/]+)/?'


class RadioBremenIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.radiobremen'
    IE_NAME = 'radiobremen'
    _VALID_URL = 'http?://(?:www\\.)?radiobremen\\.de/mediathek/(?:index\\.html)?\\?id=(?P<id>[0-9]+)'


class FranceCultureIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.radiofrance'
    IE_NAME = 'FranceCulture'
    _VALID_URL = 'https?://(?:www\\.)?radiofrance\\.fr/(?:franceculture|fip|francemusique|mouv|franceinter)/podcasts/(?:[^?#]+/)?(?P<display_id>[^?#]+)-(?P<id>\\d+)($|[?#])'


class RadioFranceIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.radiofrance'
    IE_NAME = 'radiofrance'
    _VALID_URL = '^https?://maison\\.radiofrance\\.fr/radiovisions/(?P<id>[^?#]+)'


class RadioZetPodcastIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.radiozet'
    IE_NAME = 'RadioZetPodcast'
    _VALID_URL = 'https?://player\\.radiozet\\.pl\\/Podcasty/.*?/(?P<id>.+)'


class RadioKapitalBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.radiokapital'
    IE_NAME = 'RadioKapitalBase'


class RadioKapitalIE(RadioKapitalBaseIE):
    _module = 'yt_dlp.extractor.radiokapital'
    IE_NAME = 'radiokapital'
    _VALID_URL = 'https?://(?:www\\.)?radiokapital\\.pl/shows/[a-z\\d-]+/(?P<id>[a-z\\d-]+)'


class RadioKapitalShowIE(RadioKapitalBaseIE):
    _module = 'yt_dlp.extractor.radiokapital'
    IE_NAME = 'radiokapital:show'
    _VALID_URL = 'https?://(?:www\\.)?radiokapital\\.pl/shows/(?P<id>[a-z\\d-]+)/?(?:$|[?#])'


class RadLiveIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.radlive'
    IE_NAME = 'radlive'
    _VALID_URL = 'https?://(?:www\\.)?rad\\.live/content/(?P<content_type>feature|episode)/(?P<id>[a-f0-9-]+)'


class RadLiveChannelIE(RadLiveIE):
    _module = 'yt_dlp.extractor.radlive'
    IE_NAME = 'radlive:channel'
    _VALID_URL = 'https?://(?:www\\.)?rad\\.live/content/channel/(?P<id>[a-f0-9-]+)'

    @classmethod
    def suitable(cls, url):
        return False if RadLiveIE.suitable(url) else super(RadLiveChannelIE, cls).suitable(url)


class RadLiveSeasonIE(RadLiveIE):
    _module = 'yt_dlp.extractor.radlive'
    IE_NAME = 'radlive:season'
    _VALID_URL = 'https?://(?:www\\.)?rad\\.live/content/season/(?P<id>[a-f0-9-]+)'

    @classmethod
    def suitable(cls, url):
        return False if RadLiveIE.suitable(url) else super(RadLiveSeasonIE, cls).suitable(url)


class RaiBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.rai'
    IE_NAME = 'RaiBase'


class RaiPlayIE(RaiBaseIE):
    _module = 'yt_dlp.extractor.rai'
    IE_NAME = 'RaiPlay'
    _VALID_URL = '(?P<base>https?://(?:www\\.)?raiplay\\.it/.+?-(?P<id>[\\da-f]{8}-[\\da-f]{4}-[\\da-f]{4}-[\\da-f]{4}-[\\da-f]{12}))\\.(?:html|json)'


class RaiPlayLiveIE(RaiPlayIE):
    _module = 'yt_dlp.extractor.rai'
    IE_NAME = 'RaiPlayLive'
    _VALID_URL = '(?P<base>https?://(?:www\\.)?raiplay\\.it/dirette/(?P<id>[^/?#&]+))'


class RaiPlayPlaylistIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.rai'
    IE_NAME = 'RaiPlayPlaylist'
    _VALID_URL = '(?P<base>https?://(?:www\\.)?raiplay\\.it/programmi/(?P<id>[^/?#&]+))(?:/(?P<extra_id>[^?#&]+))?'


class RaiPlaySoundIE(RaiBaseIE):
    _module = 'yt_dlp.extractor.rai'
    IE_NAME = 'RaiPlaySound'
    _VALID_URL = '(?P<base>https?://(?:www\\.)?raiplaysound\\.it/.+?-(?P<id>[\\da-f]{8}-[\\da-f]{4}-[\\da-f]{4}-[\\da-f]{4}-[\\da-f]{12}))\\.(?:html|json)'


class RaiPlaySoundLiveIE(RaiPlaySoundIE):
    _module = 'yt_dlp.extractor.rai'
    IE_NAME = 'RaiPlaySoundLive'
    _VALID_URL = '(?P<base>https?://(?:www\\.)?raiplaysound\\.it/(?P<id>[^/?#&]+)$)'


class RaiPlaySoundPlaylistIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.rai'
    IE_NAME = 'RaiPlaySoundPlaylist'
    _VALID_URL = '(?P<base>https?://(?:www\\.)?raiplaysound\\.it/(?:programmi|playlist|audiolibri)/(?P<id>[^/?#&]+))(?:/(?P<extra_id>[^?#&]+))?'


class RaiSudtirolIE(RaiBaseIE):
    _module = 'yt_dlp.extractor.rai'
    IE_NAME = 'RaiSudtirol'
    _VALID_URL = 'https?://raisudtirol\\.rai\\.it/.+?media=(?P<id>[TP]tv\\d+)'


class RaiIE(RaiBaseIE):
    _module = 'yt_dlp.extractor.rai'
    IE_NAME = 'Rai'
    _VALID_URL = 'https?://[^/]+\\.(?:rai\\.(?:it|tv))/.+?-(?P<id>[\\da-f]{8}-[\\da-f]{4}-[\\da-f]{4}-[\\da-f]{4}-[\\da-f]{12})(?:-.+?)?\\.html'


class RaiNewsIE(RaiIE):
    _module = 'yt_dlp.extractor.rai'
    IE_NAME = 'RaiNews'
    _VALID_URL = 'https?://(www\\.)?rainews\\.it/(?!articoli)[^?#]+-(?P<id>[\\da-f]{8}-[\\da-f]{4}-[\\da-f]{4}-[\\da-f]{4}-[\\da-f]{12})(?:-[^/?#]+)?\\.html'


class RayWenderlichIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.raywenderlich'
    IE_NAME = 'RayWenderlich'
    _VALID_URL = '(?x)\n                    https?://\n                        (?:\n                            videos\\.raywenderlich\\.com/courses|\n                            (?:www\\.)?raywenderlich\\.com\n                        )/\n                        (?P<course_id>[^/]+)/lessons/(?P<id>\\d+)\n                    '


class RayWenderlichCourseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.raywenderlich'
    IE_NAME = 'RayWenderlichCourse'
    _VALID_URL = '(?x)\n                    https?://\n                        (?:\n                            videos\\.raywenderlich\\.com/courses|\n                            (?:www\\.)?raywenderlich\\.com\n                        )/\n                        (?P<id>[^/]+)\n                    '

    @classmethod
    def suitable(cls, url):
        return False if RayWenderlichIE.suitable(url) else super(
            RayWenderlichCourseIE, cls).suitable(url)


class RBMARadioIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.rbmaradio'
    IE_NAME = 'RBMARadio'
    _VALID_URL = 'https?://(?:www\\.)?(?:rbmaradio|redbullradio)\\.com/shows/(?P<show_id>[^/]+)/episodes/(?P<id>[^/?#&]+)'


class RCSBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.rcs'
    IE_NAME = 'RCSBase'


class RCSIE(RCSBaseIE):
    _module = 'yt_dlp.extractor.rcs'
    IE_NAME = 'RCS'
    _VALID_URL = '(?x)https?://(?P<vid>video|viaggi)\\.\n                    (?P<cdn>\n                    (?:\n                        corrieredelmezzogiorno\\.\n                        |corrieredelveneto\\.\n                        |corrieredibologna\\.\n                        |corrierefiorentino\\.\n                    )?corriere\\.it\n                    |(?:gazzanet\\.)?gazzetta\\.it)\n                    /(?!video-embed/).+?/(?P<id>[^/\\?]+)(?=\\?|/$|$)'


class RCSEmbedsIE(RCSBaseIE):
    _module = 'yt_dlp.extractor.rcs'
    IE_NAME = 'RCSEmbeds'
    _VALID_URL = '(?x)\n                    https?://(?P<vid>video)\\.\n                    (?P<cdn>\n                    (?:\n                        rcs|\n                        (?:corriere\\w+\\.)?corriere|\n                        (?:gazzanet\\.)?gazzetta\n                    )\\.it)\n                    /video-embed/(?P<id>[^/=&\\?]+?)(?:$|\\?)'


class RCSVariousIE(RCSBaseIE):
    _module = 'yt_dlp.extractor.rcs'
    IE_NAME = 'RCSVarious'
    _VALID_URL = '(?x)https?://www\\.\n                    (?P<cdn>\n                        leitv\\.it|\n                        youreporter\\.it\n                    )/(?:[^/]+/)?(?P<id>[^/]+?)(?:$|\\?|/)'


class RCTIPlusBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.rcti'
    IE_NAME = 'RCTIPlusBase'


class RCTIPlusIE(RCTIPlusBaseIE):
    _module = 'yt_dlp.extractor.rcti'
    IE_NAME = 'RCTIPlus'
    _VALID_URL = 'https://www\\.rctiplus\\.com/(?:programs/\\d+?/.*?/)?(?P<type>episode|clip|extra|live-event|missed-event)/(?P<id>\\d+)/(?P<display_id>[^/?#&]+)'


class RCTIPlusSeriesIE(RCTIPlusBaseIE):
    _module = 'yt_dlp.extractor.rcti'
    IE_NAME = 'RCTIPlusSeries'
    _VALID_URL = 'https://www\\.rctiplus\\.com/programs/(?P<id>\\d+)/(?P<display_id>[^/?#&]+)(?:/(?P<type>episodes|extras|clips))?'
    age_limit = 2

    @classmethod
    def suitable(cls, url):
        return False if RCTIPlusIE.suitable(url) else super(RCTIPlusSeriesIE, cls).suitable(url)


class RCTIPlusTVIE(RCTIPlusBaseIE):
    _module = 'yt_dlp.extractor.rcti'
    IE_NAME = 'RCTIPlusTV'
    _VALID_URL = 'https://www\\.rctiplus\\.com/((tv/(?P<tvname>\\w+))|(?P<eventname>live-event|missed-event))'

    @classmethod
    def suitable(cls, url):
        return False if RCTIPlusIE.suitable(url) else super(RCTIPlusTVIE, cls).suitable(url)


class RDSIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.rds'
    IE_NAME = 'RDS'
    IE_DESC = 'RDS.ca'
    _VALID_URL = 'https?://(?:www\\.)?rds\\.ca/vid(?:[eé]|%C3%A9)os/(?:[^/]+/)*(?P<id>[^/]+)-\\d+\\.\\d+'


class RedBeeBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.redbee'
    IE_NAME = 'RedBeeBase'


class ParliamentLiveUKIE(RedBeeBaseIE):
    _module = 'yt_dlp.extractor.redbee'
    IE_NAME = 'parliamentlive.tv'
    IE_DESC = 'UK parliament videos'
    _VALID_URL = '(?i)https?://(?:www\\.)?parliamentlive\\.tv/Event/Index/(?P<id>[\\da-f]{8}-[\\da-f]{4}-[\\da-f]{4}-[\\da-f]{4}-[\\da-f]{12})'


class RTBFIE(RedBeeBaseIE):
    _module = 'yt_dlp.extractor.redbee'
    IE_NAME = 'RTBF'
    _VALID_URL = '(?x)\n        https?://(?:www\\.)?rtbf\\.be/\n        (?:\n            video/[^?]+\\?.*\\bid=|\n            ouftivi/(?:[^/]+/)*[^?]+\\?.*\\bvideoId=|\n            auvio/[^/]+\\?.*\\b(?P<live>l)?id=\n        )(?P<id>\\d+)'
    _NETRC_MACHINE = 'rtbf'


class RedBullTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.redbulltv'
    IE_NAME = 'RedBullTV'
    _VALID_URL = 'https?://(?:www\\.)?redbull(?:\\.tv|\\.com(?:/[^/]+)?(?:/tv)?)(?:/events/[^/]+)?/(?:videos?|live|(?:film|episode)s)/(?P<id>AP-\\w+)'


class RedBullEmbedIE(RedBullTVIE):
    _module = 'yt_dlp.extractor.redbulltv'
    IE_NAME = 'RedBullEmbed'
    _VALID_URL = 'https?://(?:www\\.)?redbull\\.com/embed/(?P<id>rrn:content:[^:]+:[\\da-f]{8}-[\\da-f]{4}-[\\da-f]{4}-[\\da-f]{4}-[\\da-f]{12}:[a-z]{2}-[A-Z]{2,3})'


class RedBullTVRrnContentIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.redbulltv'
    IE_NAME = 'RedBullTVRrnContent'
    _VALID_URL = 'https?://(?:www\\.)?redbull\\.com/(?P<region>[a-z]{2,3})-(?P<lang>[a-z]{2})/tv/(?:video|live|film)/(?P<id>rrn:content:[^:]+:[\\da-f]{8}-[\\da-f]{4}-[\\da-f]{4}-[\\da-f]{4}-[\\da-f]{12})'


class RedBullIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.redbulltv'
    IE_NAME = 'RedBull'
    _VALID_URL = 'https?://(?:www\\.)?redbull\\.com/(?P<region>[a-z]{2,3})-(?P<lang>[a-z]{2})/(?P<type>(?:episode|film|(?:(?:recap|trailer)-)?video)s|live)/(?!AP-|rrn:content:)(?P<id>[^/?#&]+)'


class RedditIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.reddit'
    IE_NAME = 'Reddit'
    _VALID_URL = 'https?://(?P<subdomain>[^/]+\\.)?reddit(?:media)?\\.com/r/(?P<slug>[^/]+/comments/(?P<id>[^/?#&]+))'


class RedGifsBaseInfoExtractor(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.redgifs'
    IE_NAME = 'RedGifsBaseInfoExtract'


class RedGifsIE(RedGifsBaseInfoExtractor):
    _module = 'yt_dlp.extractor.redgifs'
    IE_NAME = 'RedGifs'
    _VALID_URL = 'https?://(?:(?:www\\.)?redgifs\\.com/watch/|thumbs2\\.redgifs\\.com/)(?P<id>[^-/?#\\.]+)'
    age_limit = 18


class RedGifsSearchIE(RedGifsBaseInfoExtractor):
    _module = 'yt_dlp.extractor.redgifs'
    IE_NAME = 'RedGifsSearch'
    IE_DESC = 'Redgifs search'
    _VALID_URL = 'https?://(?:www\\.)?redgifs\\.com/browse\\?(?P<query>[^#]+)'


class RedGifsUserIE(RedGifsBaseInfoExtractor):
    _module = 'yt_dlp.extractor.redgifs'
    IE_NAME = 'RedGifsUser'
    IE_DESC = 'Redgifs user'
    _VALID_URL = 'https?://(?:www\\.)?redgifs\\.com/users/(?P<username>[^/?#]+)(?:\\?(?P<query>[^#]+))?'


class RedTubeIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.redtube'
    IE_NAME = 'RedTube'
    _VALID_URL = 'https?://(?:(?:\\w+\\.)?redtube\\.com/|embed\\.redtube\\.com/\\?.*?\\bid=)(?P<id>[0-9]+)'
    age_limit = 18


class RegioTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.regiotv'
    IE_NAME = 'RegioTV'
    _VALID_URL = 'https?://(?:www\\.)?regio-tv\\.de/video/(?P<id>[0-9]+)'


class RENTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.rentv'
    IE_NAME = 'RENTV'
    _VALID_URL = '(?:rentv:|https?://(?:www\\.)?ren\\.tv/(?:player|video/epizod)/)(?P<id>\\d+)'


class RENTVArticleIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.rentv'
    IE_NAME = 'RENTVArticle'
    _VALID_URL = 'https?://(?:www\\.)?ren\\.tv/novosti/\\d{4}-\\d{2}-\\d{2}/(?P<id>[^/?#]+)'


class RestudyIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.restudy'
    IE_NAME = 'Restudy'
    _VALID_URL = 'https?://(?:(?:www|portal)\\.)?restudy\\.dk/video/[^/]+/id/(?P<id>[0-9]+)'


class ReutersIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.reuters'
    IE_NAME = 'Reuters'
    _VALID_URL = 'https?://(?:www\\.)?reuters\\.com/.*?\\?.*?videoId=(?P<id>[0-9]+)'


class ReverbNationIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.reverbnation'
    IE_NAME = 'ReverbNation'
    _VALID_URL = '^https?://(?:www\\.)?reverbnation\\.com/.*?/song/(?P<id>\\d+).*?$'


class RICEIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.rice'
    IE_NAME = 'RICE'
    _VALID_URL = 'https?://mediahub\\.rice\\.edu/app/[Pp]ortal/video\\.aspx\\?(?P<query>.+)'


class RMCDecouverteIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.rmcdecouverte'
    IE_NAME = 'RMCDecouverte'
    _VALID_URL = 'https?://rmcdecouverte\\.bfmtv\\.com/(?:[^?#]*_(?P<id>\\d+)|mediaplayer-direct)/?(?:[#?]|$)'


class RockstarGamesIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.rockstargames'
    IE_NAME = 'RockstarGames'
    _VALID_URL = 'https?://(?:www\\.)?rockstargames\\.com/videos(?:/video/|#?/?\\?.*\\bvideo=)(?P<id>\\d+)'


class RokfinIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.rokfin'
    IE_NAME = 'Rokfin'
    _VALID_URL = 'https?://(?:www\\.)?rokfin\\.com/(?P<id>(?P<type>post|stream)/\\d+)'
    _NETRC_MACHINE = 'rokfin'


class RokfinPlaylistBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.rokfin'
    IE_NAME = 'RokfinPlaylistBase'


class RokfinStackIE(RokfinPlaylistBaseIE):
    _module = 'yt_dlp.extractor.rokfin'
    IE_NAME = 'rokfin:stack'
    IE_DESC = 'Rokfin Stacks'
    _VALID_URL = 'https?://(?:www\\.)?rokfin\\.com/stack/(?P<id>[^/]+)'


class RokfinChannelIE(RokfinPlaylistBaseIE):
    _module = 'yt_dlp.extractor.rokfin'
    IE_NAME = 'rokfin:channel'
    IE_DESC = 'Rokfin Channels'
    _VALID_URL = 'https?://(?:www\\.)?rokfin\\.com/(?!((feed/?)|(discover/?)|(channels/?))$)(?P<id>[^/]+)/?$'


class RokfinSearchIE(LazyLoadSearchExtractor):
    _module = 'yt_dlp.extractor.rokfin'
    IE_NAME = 'rokfin:search'
    IE_DESC = 'Rokfin Search'
    SEARCH_KEY = 'rkfnsearch'
    _VALID_URL = 'rkfnsearch(?P<prefix>|[1-9][0-9]*|all):(?P<query>[\\s\\S]+)'


class RoosterTeethBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.roosterteeth'
    IE_NAME = 'RoosterTeethBase'
    _NETRC_MACHINE = 'roosterteeth'


class RoosterTeethIE(RoosterTeethBaseIE):
    _module = 'yt_dlp.extractor.roosterteeth'
    IE_NAME = 'RoosterTeeth'
    _VALID_URL = 'https?://(?:.+?\\.)?roosterteeth\\.com/(?:episode|watch)/(?P<id>[^/?#&]+)'
    _NETRC_MACHINE = 'roosterteeth'


class RoosterTeethSeriesIE(RoosterTeethBaseIE):
    _module = 'yt_dlp.extractor.roosterteeth'
    IE_NAME = 'RoosterTeethSeries'
    _VALID_URL = 'https?://(?:.+?\\.)?roosterteeth\\.com/series/(?P<id>[^/?#&]+)'
    _NETRC_MACHINE = 'roosterteeth'


class RottenTomatoesIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.rottentomatoes'
    IE_NAME = 'RottenTomatoes'
    _VALID_URL = 'https?://(?:www\\.)?rottentomatoes\\.com/m/[^/]+/trailers/(?P<id>\\d+)'


class RozhlasIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.rozhlas'
    IE_NAME = 'Rozhlas'
    _VALID_URL = 'https?://(?:www\\.)?prehravac\\.rozhlas\\.cz/audio/(?P<id>[0-9]+)'


class RteBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.rte'
    IE_NAME = 'RteBase'


class RteIE(RteBaseIE):
    _module = 'yt_dlp.extractor.rte'
    IE_NAME = 'rte'
    IE_DESC = 'Raidió Teilifís Éireann TV'
    _VALID_URL = 'https?://(?:www\\.)?rte\\.ie/player/[^/]{2,3}/show/[^/]+/(?P<id>[0-9]+)'


class RteRadioIE(RteBaseIE):
    _module = 'yt_dlp.extractor.rte'
    IE_NAME = 'rte:radio'
    IE_DESC = 'Raidió Teilifís Éireann radio'
    _VALID_URL = 'https?://(?:www\\.)?rte\\.ie/radio/utils/radioplayer/rteradioweb\\.html#!rii=(?:b?[0-9]*)(?:%3A|:|%5F|_)(?P<id>[0-9]+)'


class RtlNlIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.rtlnl'
    IE_NAME = 'rtl.nl'
    IE_DESC = 'rtl.nl and rtlxl.nl'
    _VALID_URL = '(?x)\n        https?://(?:(?:www|static)\\.)?\n        (?:\n            rtlxl\\.nl/(?:[^\\#]*\\#!|programma)/[^/]+/|\n            rtl\\.nl/(?:(?:system/videoplayer/(?:[^/]+/)+(?:video_)?embed\\.html|embed)\\b.+?\\buuid=|video/)|\n            embed\\.rtl\\.nl/\\#uuid=\n        )\n        (?P<id>[0-9a-f-]+)'


class RTLLuBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.rtlnl'
    IE_NAME = 'RTLLuBase'


class RTLLuTeleVODIE(RTLLuBaseIE):
    _module = 'yt_dlp.extractor.rtlnl'
    IE_NAME = 'rtl.lu:tele-vod'
    _VALID_URL = 'https?://(?:www\\.)?rtl\\.lu/(tele/(?P<slug>[\\w-]+)/v/|video/)(?P<id>\\d+)(\\.html)?'


class RTLLuArticleIE(RTLLuBaseIE):
    _module = 'yt_dlp.extractor.rtlnl'
    IE_NAME = 'rtl.lu:article'
    _VALID_URL = 'https?://(?:(www|5minutes|today)\\.)rtl\\.lu/(?:[\\w-]+)/(?:[\\w-]+)/a/(?P<id>\\d+)\\.html'


class RTLLuLiveIE(RTLLuBaseIE):
    _module = 'yt_dlp.extractor.rtlnl'
    IE_NAME = 'RTLLuLive'
    _VALID_URL = 'https?://www\\.rtl\\.lu/(?:tele|radio)/(?P<id>live(?:-\\d+)?|lauschteren)'


class RTLLuRadioIE(RTLLuBaseIE):
    _module = 'yt_dlp.extractor.rtlnl'
    IE_NAME = 'RTLLuRadio'
    _VALID_URL = 'https?://www\\.rtl\\.lu/radio/(?:[\\w-]+)/s/(?P<id>\\d+)(\\.html)?'


class RTL2IE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.rtl2'
    IE_NAME = 'rtl2'
    _VALID_URL = 'https?://(?:www\\.)?rtl2\\.de/sendung/[^/]+/(?:video/(?P<vico_id>\\d+)[^/]+/(?P<vivi_id>\\d+)-|folge/)(?P<id>[^/?#]+)'


class RTL2YouBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.rtl2'
    IE_NAME = 'RTL2YouBase'


class RTL2YouIE(RTL2YouBaseIE):
    _module = 'yt_dlp.extractor.rtl2'
    IE_NAME = 'rtl2:you'
    _VALID_URL = 'http?://you\\.rtl2\\.de/(?:video/\\d+/|youplayer/index\\.html\\?.*?\\bvid=)(?P<id>\\d+)'
    age_limit = 12


class RTL2YouSeriesIE(RTL2YouBaseIE):
    _module = 'yt_dlp.extractor.rtl2'
    IE_NAME = 'rtl2:you:series'
    _VALID_URL = 'http?://you\\.rtl2\\.de/videos/(?P<id>\\d+)'


class RTNewsIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.rtnews'
    IE_NAME = 'RTNews'
    _VALID_URL = 'https?://(?:www\\.)?rt\\.com/[^/]+/(?:[^/]+/)?(?P<id>\\d+)'


class RTDocumentryIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.rtnews'
    IE_NAME = 'RTDocumentry'
    _VALID_URL = 'https?://rtd\\.rt\\.com/(?:(?:series|shows)/[^/]+|films)/(?P<id>[^/?$&#]+)'


class RTDocumentryPlaylistIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.rtnews'
    IE_NAME = 'RTDocumentryPlaylist'
    _VALID_URL = 'https?://rtd\\.rt\\.com/(?:series|shows)/(?P<id>[^/]+)/$'


class RuptlyIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.rtnews'
    IE_NAME = 'Ruptly'
    _VALID_URL = 'https?://(?:www\\.)?ruptly\\.tv/[a-z]{2}/videos/(?P<id>\\d+-\\d+)'


class RTPIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.rtp'
    IE_NAME = 'RTP'
    _VALID_URL = 'https?://(?:www\\.)?rtp\\.pt/play/p(?P<program_id>[0-9]+)/(?P<id>[^/?#]+)/?'


class RTRFMIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.rtrfm'
    IE_NAME = 'RTRFM'
    _VALID_URL = 'https?://(?:www\\.)?rtrfm\\.com\\.au/(?:shows|show-episode)/(?P<id>[^/?\\#&]+)'


class RTVEALaCartaIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.rtve'
    IE_NAME = 'rtve.es:alacarta'
    IE_DESC = 'RTVE a la carta'
    _VALID_URL = 'https?://(?:www\\.)?rtve\\.es/(m/)?(alacarta/videos|filmoteca)/[^/]+/[^/]+/(?P<id>\\d+)'


class RTVEAudioIE(RTVEALaCartaIE):
    _module = 'yt_dlp.extractor.rtve'
    IE_NAME = 'rtve.es:audio'
    IE_DESC = 'RTVE audio'
    _VALID_URL = 'https?://(?:www\\.)?rtve\\.es/(alacarta|play)/audios/[^/]+/[^/]+/(?P<id>[0-9]+)'


class RTVELiveIE(RTVEALaCartaIE):
    _module = 'yt_dlp.extractor.rtve'
    IE_NAME = 'rtve.es:live'
    IE_DESC = 'RTVE.es live streams'
    _VALID_URL = 'https?://(?:www\\.)?rtve\\.es/directo/(?P<id>[a-zA-Z0-9-]+)'


class RTVEInfantilIE(RTVEALaCartaIE):
    _module = 'yt_dlp.extractor.rtve'
    IE_NAME = 'rtve.es:infantil'
    IE_DESC = 'RTVE infantil'
    _VALID_URL = 'https?://(?:www\\.)?rtve\\.es/infantil/serie/[^/]+/video/[^/]+/(?P<id>[0-9]+)/'


class RTVETelevisionIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.rtve'
    IE_NAME = 'rtve.es:television'
    _VALID_URL = 'https?://(?:www\\.)?rtve\\.es/television/[^/]+/[^/]+/(?P<id>\\d+).shtml'


class RTVNHIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.rtvnh'
    IE_NAME = 'RTVNH'
    _VALID_URL = 'https?://(?:www\\.)?rtvnh\\.nl/video/(?P<id>[0-9]+)'


class RTVSIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.rtvs'
    IE_NAME = 'RTVS'
    _VALID_URL = 'https?://(?:www\\.)?rtvs\\.sk/(?:radio|televizia)/archiv(?:/\\d+)?/(?P<id>\\d+)/?(?:[#?]|$)'


class RTVSLOIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.rtvslo'
    IE_NAME = 'rtvslo.si'
    _VALID_URL = '(?x)\n        https?://(?:\n            (?:365|4d)\\.rtvslo.si/arhiv/[^/?#&;]+|\n            (?:www\\.)?rtvslo\\.si/rtv365/arhiv\n        )/(?P<id>\\d+)'


class RUHDIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ruhd'
    IE_NAME = 'RUHD'
    _VALID_URL = 'https?://(?:www\\.)?ruhd\\.ru/play\\.php\\?vid=(?P<id>\\d+)'


class Rule34VideoIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.rule34video'
    IE_NAME = 'Rule34Video'
    _VALID_URL = 'https?://(?:www\\.)?rule34video\\.com/videos/(?P<id>\\d+)'
    age_limit = 18


class RumbleEmbedIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.rumble'
    IE_NAME = 'RumbleEmbed'
    _VALID_URL = 'https?://(?:www\\.)?rumble\\.com/embed/(?:[0-9a-z]+\\.)?(?P<id>[0-9a-z]+)'


class RumbleChannelIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.rumble'
    IE_NAME = 'RumbleChannel'
    _VALID_URL = '(?P<url>https?://(?:www\\.)?rumble\\.com/(?:c|user)/(?P<id>[^&?#$/]+))'


class RutubeBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.rutube'
    IE_NAME = 'RutubeBase'


class RutubeIE(RutubeBaseIE):
    _module = 'yt_dlp.extractor.rutube'
    IE_NAME = 'rutube'
    IE_DESC = 'Rutube videos'
    _VALID_URL = 'https?://rutube\\.ru/(?:video|(?:play/)?embed)/(?P<id>[\\da-z]{32})'

    @classmethod
    def suitable(cls, url):
        return False if RutubePlaylistIE.suitable(url) else super(RutubeIE, cls).suitable(url)


class RutubePlaylistBaseIE(RutubeBaseIE):
    _module = 'yt_dlp.extractor.rutube'
    IE_NAME = 'RutubePlaylistBase'


class RutubeChannelIE(RutubePlaylistBaseIE):
    _module = 'yt_dlp.extractor.rutube'
    IE_NAME = 'rutube:channel'
    IE_DESC = 'Rutube channel'
    _VALID_URL = 'https?://rutube\\.ru/channel/(?P<id>\\d+)/videos'


class RutubeEmbedIE(RutubeBaseIE):
    _module = 'yt_dlp.extractor.rutube'
    IE_NAME = 'rutube:embed'
    IE_DESC = 'Rutube embedded videos'
    _VALID_URL = 'https?://rutube\\.ru/(?:video|play)/embed/(?P<id>[0-9]+)'


class RutubeMovieIE(RutubePlaylistBaseIE):
    _module = 'yt_dlp.extractor.rutube'
    IE_NAME = 'rutube:movie'
    IE_DESC = 'Rutube movies'
    _VALID_URL = 'https?://rutube\\.ru/metainfo/tv/(?P<id>\\d+)'


class RutubePersonIE(RutubePlaylistBaseIE):
    _module = 'yt_dlp.extractor.rutube'
    IE_NAME = 'rutube:person'
    IE_DESC = 'Rutube person videos'
    _VALID_URL = 'https?://rutube\\.ru/video/person/(?P<id>\\d+)'


class RutubePlaylistIE(RutubePlaylistBaseIE):
    _module = 'yt_dlp.extractor.rutube'
    IE_NAME = 'rutube:playlist'
    IE_DESC = 'Rutube playlists'
    _VALID_URL = 'https?://rutube\\.ru/(?:video|(?:play/)?embed)/[\\da-z]{32}/\\?.*?\\bpl_id=(?P<id>\\d+)'

    @classmethod
    def suitable(cls, url):
        from ..utils import int_or_none, parse_qs

        if not super(RutubePlaylistIE, cls).suitable(url):
            return False
        params = parse_qs(url)
        return params.get('pl_type', [None])[0] and int_or_none(params.get('pl_id', [None])[0])


class RutubeTagsIE(RutubePlaylistBaseIE):
    _module = 'yt_dlp.extractor.rutube'
    IE_NAME = 'rutube:tags'
    IE_DESC = 'Rutube tags'
    _VALID_URL = 'https?://rutube\\.ru/tags/video/(?P<id>\\d+)'


class GlomexBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.glomex'
    IE_NAME = 'GlomexBase'


class GlomexIE(GlomexBaseIE):
    _module = 'yt_dlp.extractor.glomex'
    IE_NAME = 'glomex'
    IE_DESC = 'Glomex videos'
    _VALID_URL = 'https?://video\\.glomex\\.com/[^/]+/(?P<id>v-[^-]+)'


class GlomexEmbedIE(GlomexBaseIE):
    _module = 'yt_dlp.extractor.glomex'
    IE_NAME = 'glomex:embed'
    IE_DESC = 'Glomex embedded videos'
    _VALID_URL = 'https?://player\\.glomex\\.com/integration/[^/]/iframe\\-player\\.html\\?([^#]+&)?playlistId=(?P<id>[^#&]+)'


class MegaTVComBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.megatvcom'
    IE_NAME = 'MegaTVComBase'


class MegaTVComIE(MegaTVComBaseIE):
    _module = 'yt_dlp.extractor.megatvcom'
    IE_NAME = 'megatvcom'
    IE_DESC = 'megatv.com videos'
    _VALID_URL = 'https?://(?:www\\.)?megatv\\.com/(?:\\d{4}/\\d{2}/\\d{2}|[^/]+/(?P<id>\\d+))/(?P<slug>[^/]+)'


class MegaTVComEmbedIE(MegaTVComBaseIE):
    _module = 'yt_dlp.extractor.megatvcom'
    IE_NAME = 'megatvcom:embed'
    IE_DESC = 'megatv.com embedded videos'
    _VALID_URL = '(?:https?:)?//(?:www\\.)?megatv\\.com/embed/?\\?p=(?P<id>\\d+)'


class Ant1NewsGrBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ant1newsgr'
    IE_NAME = 'Ant1NewsGrBase'


class Ant1NewsGrWatchIE(Ant1NewsGrBaseIE):
    _module = 'yt_dlp.extractor.ant1newsgr'
    IE_NAME = 'ant1newsgr:watch'
    IE_DESC = 'ant1news.gr videos'
    _VALID_URL = 'https?://(?P<netloc>(?:www\\.)?ant1news\\.gr)/watch/(?P<id>\\d+)/'


class Ant1NewsGrArticleIE(Ant1NewsGrBaseIE):
    _module = 'yt_dlp.extractor.ant1newsgr'
    IE_NAME = 'ant1newsgr:article'
    IE_DESC = 'ant1news.gr articles'
    _VALID_URL = 'https?://(?:www\\.)?ant1news\\.gr/[^/]+/article/(?P<id>\\d+)/'


class Ant1NewsGrEmbedIE(Ant1NewsGrBaseIE):
    _module = 'yt_dlp.extractor.ant1newsgr'
    IE_NAME = 'ant1newsgr:embed'
    IE_DESC = 'ant1news.gr embedded videos'
    _VALID_URL = '(?:https?:)?//(?:[a-zA-Z0-9\\-]+\\.)?(?:antenna|ant1news)\\.gr/templates/pages/player\\?([^#]+&)?cid=(?P<id>[^#&]+)'


class RUTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.rutv'
    IE_NAME = 'RUTV'
    IE_DESC = 'RUTV.RU'
    _VALID_URL = '(?x)\n                    https?://\n                        (?:test)?player\\.(?:rutv\\.ru|vgtrk\\.com)/\n                        (?P<path>\n                            flash\\d+v/container\\.swf\\?id=|\n                            iframe/(?P<type>swf|video|live)/id/|\n                            index/iframe/cast_id/\n                        )\n                        (?P<id>\\d+)\n                    '


class RuutuIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ruutu'
    IE_NAME = 'Ruutu'
    _VALID_URL = '(?x)\n                    https?://\n                        (?:\n                            (?:www\\.)?(?:ruutu|supla)\\.fi/(?:video|supla|audio)/|\n                            static\\.nelonenmedia\\.fi/player/misc/embed_player\\.html\\?.*?\\bnid=\n                        )\n                        (?P<id>\\d+)\n                    '
    age_limit = 12


class RuvIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ruv'
    IE_NAME = 'Ruv'
    _VALID_URL = 'https?://(?:www\\.)?ruv\\.is/(?:sarpurinn/[^/]+|node)/(?P<id>[^/]+(?:/\\d+)?)'


class RuvSpilaIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ruv'
    IE_NAME = 'ruv.is:spila'
    _VALID_URL = 'https?://(?:www\\.)?ruv\\.is/(?:(?:sjon|ut)varp|(?:krakka|ung)ruv)/spila/.+/(?P<series_id>[0-9]+)/(?P<id>[a-z0-9]+)'


class SafariBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.safari'
    IE_NAME = 'SafariBase'
    _NETRC_MACHINE = 'safari'


class SafariIE(SafariBaseIE):
    _module = 'yt_dlp.extractor.safari'
    IE_NAME = 'safari'
    IE_DESC = 'safaribooksonline.com online video'
    _VALID_URL = '(?x)\n                        https?://\n                            (?:www\\.)?(?:safaribooksonline|(?:learning\\.)?oreilly)\\.com/\n                            (?:\n                                library/view/[^/]+/(?P<course_id>[^/]+)/(?P<part>[^/?\\#&]+)\\.html|\n                                videos/[^/]+/[^/]+/(?P<reference_id>[^-]+-[^/?\\#&]+)\n                            )\n                    '
    _NETRC_MACHINE = 'safari'


class SafariApiIE(SafariBaseIE):
    _module = 'yt_dlp.extractor.safari'
    IE_NAME = 'safari:api'
    _VALID_URL = 'https?://(?:www\\.)?(?:safaribooksonline|(?:learning\\.)?oreilly)\\.com/api/v1/book/(?P<course_id>[^/]+)/chapter(?:-content)?/(?P<part>[^/?#&]+)\\.html'
    _NETRC_MACHINE = 'safari'


class SafariCourseIE(SafariBaseIE):
    _module = 'yt_dlp.extractor.safari'
    IE_NAME = 'safari:course'
    IE_DESC = 'safaribooksonline.com online courses'
    _VALID_URL = '(?x)\n                    https?://\n                        (?:\n                            (?:www\\.)?(?:safaribooksonline|(?:learning\\.)?oreilly)\\.com/\n                            (?:\n                                library/view/[^/]+|\n                                api/v1/book|\n                                videos/[^/]+\n                            )|\n                            techbus\\.safaribooksonline\\.com\n                        )\n                        /(?P<id>[^/]+)\n                    '
    _NETRC_MACHINE = 'safari'

    @classmethod
    def suitable(cls, url):
        return (False if SafariIE.suitable(url) or SafariApiIE.suitable(url)
                else super(SafariCourseIE, cls).suitable(url))


class SaitosanIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.saitosan'
    IE_NAME = 'Saitosan'
    _VALID_URL = 'https?://(?:www\\.)?saitosan\\.net/bview.html\\?id=(?P<id>[0-9]+)'


class SampleFocusIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.samplefocus'
    IE_NAME = 'SampleFocus'
    _VALID_URL = 'https?://(?:www\\.)?samplefocus\\.com/samples/(?P<id>[^/?&#]+)'


class SapoIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.sapo'
    IE_NAME = 'Sapo'
    IE_DESC = 'SAPO Vídeos'
    _VALID_URL = 'https?://(?:(?:v2|www)\\.)?videos\\.sapo\\.(?:pt|cv|ao|mz|tl)/(?P<id>[\\da-zA-Z]{20})'


class SaveFromIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.savefrom'
    IE_NAME = 'savefrom.net'
    _VALID_URL = 'https?://[^.]+\\.savefrom\\.net/\\#url=(?P<url>.*)$'


class SBSIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.sbs'
    IE_NAME = 'SBS'
    IE_DESC = 'sbs.com.au'
    _VALID_URL = '(?x)\n        https?://(?:www\\.)?sbs\\.com\\.au/(?:\n            ondemand(?:\n                /video/(?:single/)?|\n                /movie/[^/]+/|\n                /(?:tv|news)-series/(?:[^/]+/){3}|\n                .*?\\bplay=|/watch/\n            )|news/(?:embeds/)?video/\n        )(?P<id>[0-9]+)'


class Screen9IE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.screen9'
    IE_NAME = 'Screen9'
    _VALID_URL = 'https?://(?:\\w+\\.screen9\\.(?:tv|com)|play\\.su\\.se)/(?:embed|media)/(?P<id>[^?#/]+)'


class ScreencastIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.screencast'
    IE_NAME = 'Screencast'
    _VALID_URL = 'https?://(?:www\\.)?screencast\\.com/t/(?P<id>[a-zA-Z0-9]+)'


class ScreencastOMaticIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.screencastomatic'
    IE_NAME = 'ScreencastOMatic'
    _VALID_URL = 'https?://screencast-o-matic\\.com/(?:(?:watch|player)/|embed\\?.*?\\bsc=)(?P<id>[0-9a-zA-Z]+)'


class AWSIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.aws'
    IE_NAME = 'AWS'


class ScrippsNetworksWatchIE(AWSIE):
    _module = 'yt_dlp.extractor.scrippsnetworks'
    IE_NAME = 'scrippsnetworks:watch'
    _VALID_URL = '(?x)\n                    https?://\n                        watch\\.\n                        (?P<site>geniuskitchen)\\.com/\n                        (?:\n                            player\\.[A-Z0-9]+\\.html\\#|\n                            show/(?:[^/]+/){2}|\n                            player/\n                        )\n                        (?P<id>\\d+)\n                    '


class ScrippsNetworksIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.scrippsnetworks'
    IE_NAME = 'ScrippsNetworks'
    _VALID_URL = 'https?://(?:www\\.)?(?P<site>cookingchanneltv|discovery|(?:diy|food)network|hgtv|travelchannel)\\.com/videos/[0-9a-z-]+-(?P<id>\\d+)'


class SCTEBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.scte'
    IE_NAME = 'SCTEBase'
    _NETRC_MACHINE = 'scte'


class SCTEIE(SCTEBaseIE):
    _module = 'yt_dlp.extractor.scte'
    IE_NAME = 'SCTE'
    _VALID_URL = 'https?://learning\\.scte\\.org/mod/scorm/view\\.php?.*?\\bid=(?P<id>\\d+)'
    _NETRC_MACHINE = 'scte'


class SCTECourseIE(SCTEBaseIE):
    _module = 'yt_dlp.extractor.scte'
    IE_NAME = 'SCTECourse'
    _VALID_URL = 'https?://learning\\.scte\\.org/(?:mod/sub)?course/view\\.php?.*?\\bid=(?P<id>\\d+)'
    _NETRC_MACHINE = 'scte'


class ScrolllerIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.scrolller'
    IE_NAME = 'Scrolller'
    _VALID_URL = 'https?://(?:www\\.)?scrolller\\.com/(?P<id>[\\w-]+)'
    age_limit = 18


class SeekerIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.seeker'
    IE_NAME = 'Seeker'
    _VALID_URL = 'https?://(?:www\\.)?seeker\\.com/(?P<display_id>.*)-(?P<article_id>\\d+)\\.html'


class SenateISVPIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.senategov'
    IE_NAME = 'SenateISVP'
    _VALID_URL = 'https?://(?:www\\.)?senate\\.gov/isvp/?\\?(?P<qs>.+)'


class SenateGovIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.senategov'
    IE_NAME = 'SenateGov'
    _VALID_URL = 'https?:\\/\\/(?:www\\.)?(help|appropriations|judiciary|banking|armed-services|finance)\\.senate\\.gov'


class SendtoNewsIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.sendtonews'
    IE_NAME = 'SendtoNews'
    _VALID_URL = 'https?://embed\\.sendtonews\\.com/player2/embedplayer\\.php\\?.*\\bSC=(?P<id>[0-9A-Za-z-]+)'


class ServusIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.servus'
    IE_NAME = 'Servus'
    _VALID_URL = '(?x)\n                    https?://\n                        (?:www\\.)?\n                        (?:\n                            servus\\.com/(?:(?:at|de)/p/[^/]+|tv/videos)|\n                            (?:servustv|pm-wissen)\\.com/videos\n                        )\n                        /(?P<id>[aA]{2}-\\w+|\\d+-\\d+)\n                    '


class SevenPlusIE(BrightcoveNewIE):
    _module = 'yt_dlp.extractor.sevenplus'
    IE_NAME = '7plus'
    _VALID_URL = 'https?://(?:www\\.)?7plus\\.com\\.au/(?P<path>[^?]+\\?.*?\\bepisode-id=(?P<id>[^&#]+))'


class SexuIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.sexu'
    IE_NAME = 'Sexu'
    _VALID_URL = 'https?://(?:www\\.)?sexu\\.com/(?P<id>\\d+)'
    age_limit = 18


class SeznamZpravyIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.seznamzpravy'
    IE_NAME = 'SeznamZpravy'
    _VALID_URL = 'https?://(?:www\\.)?seznamzpravy\\.cz/iframe/player\\?.*\\bsrc='


class SeznamZpravyArticleIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.seznamzpravy'
    IE_NAME = 'SeznamZpravyArticle'
    _VALID_URL = 'https?://(?:www\\.)?(?:seznam\\.cz/zpravy|seznamzpravy\\.cz)/clanek/(?:[^/?#&]+)-(?P<id>\\d+)'


class ShahidBaseIE(AWSIE):
    _module = 'yt_dlp.extractor.shahid'
    IE_NAME = 'ShahidBase'


class ShahidIE(ShahidBaseIE):
    _module = 'yt_dlp.extractor.shahid'
    IE_NAME = 'Shahid'
    _VALID_URL = 'https?://shahid\\.mbc\\.net/[a-z]{2}/(?:serie|show|movie)s/[^/]+/(?P<type>episode|clip|movie)-(?P<id>\\d+)'
    _NETRC_MACHINE = 'shahid'


class ShahidShowIE(ShahidBaseIE):
    _module = 'yt_dlp.extractor.shahid'
    IE_NAME = 'ShahidShow'
    _VALID_URL = 'https?://shahid\\.mbc\\.net/[a-z]{2}/(?:show|serie)s/[^/]+/(?:show|series)-(?P<id>\\d+)'


class SharedBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.shared'
    IE_NAME = 'SharedBase'


class SharedIE(SharedBaseIE):
    _module = 'yt_dlp.extractor.shared'
    IE_NAME = 'Shared'
    IE_DESC = 'shared.sx'
    _VALID_URL = 'https?://shared\\.sx/(?P<id>[\\da-z]{10})'


class VivoIE(SharedBaseIE):
    _module = 'yt_dlp.extractor.shared'
    IE_NAME = 'Vivo'
    IE_DESC = 'vivo.sx'
    _VALID_URL = 'https?://vivo\\.s[xt]/(?P<id>[\\da-z]{10})'


class ShareVideosEmbedIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.sharevideos'
    IE_NAME = 'ShareVideosEmbed'
    _VALID_URL = False


class ShemarooMeIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.shemaroome'
    IE_NAME = 'ShemarooMe'
    _VALID_URL = 'https?://(?:www\\.)?shemaroome\\.com/(?:movies|shows)/(?P<id>[^?#]+)'


class ShowRoomLiveIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.showroomlive'
    IE_NAME = 'ShowRoomLive'
    _VALID_URL = 'https?://(?:www\\.)?showroom-live\\.com/(?!onlive|timetable|event|campaign|news|ranking|room)(?P<id>[^/?#&]+)'


class SimplecastBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.simplecast'
    IE_NAME = 'SimplecastBase'


class SimplecastIE(SimplecastBaseIE):
    _module = 'yt_dlp.extractor.simplecast'
    IE_NAME = 'simplecast'
    _VALID_URL = 'https?://(?:api\\.simplecast\\.com/episodes|player\\.simplecast\\.com)/(?P<id>[\\da-f]{8}-(?:[\\da-f]{4}-){3}[\\da-f]{12})'


class SimplecastEpisodeIE(SimplecastBaseIE):
    _module = 'yt_dlp.extractor.simplecast'
    IE_NAME = 'simplecast:episode'
    _VALID_URL = 'https?://(?!api\\.)[^/]+\\.simplecast\\.com/episodes/(?P<id>[^/?&#]+)'


class SimplecastPodcastIE(SimplecastBaseIE):
    _module = 'yt_dlp.extractor.simplecast'
    IE_NAME = 'simplecast:podcast'
    _VALID_URL = 'https?://(?!(?:api|cdn|embed|feeds|player)\\.)(?P<id>[^/]+)\\.simplecast\\.com(?!/episodes/[^/?&#]+)'


class SinaIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.sina'
    IE_NAME = 'Sina'
    _VALID_URL = '(?x)https?://(?:.*?\\.)?video\\.sina\\.com\\.cn/\n                        (?:\n                            (?:view/|.*\\#)(?P<id>\\d+)|\n                            .+?/(?P<pseudo_id>[^/?#]+)(?:\\.s?html)|\n                            # This is used by external sites like Weibo\n                            api/sinawebApi/outplay.php/(?P<token>.+?)\\.swf\n                        )\n                  '


class SixPlayIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.sixplay'
    IE_NAME = '6play'
    _VALID_URL = '(?:6play:|https?://(?:www\\.)?(?P<domain>6play\\.fr|rtlplay\\.be|play\\.rtl\\.hr|rtlmost\\.hu)/.+?-c_)(?P<id>[0-9]+)'


class SkebIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.skeb'
    IE_NAME = 'Skeb'
    _VALID_URL = 'https?://skeb\\.jp/@[^/]+/works/(?P<id>\\d+)'


class SkyItPlayerIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.skyit'
    IE_NAME = 'player.sky.it'
    _VALID_URL = 'https?://player\\.sky\\.it/player/(?:external|social)\\.html\\?.*?\\bid=(?P<id>\\d+)'


class SkyItVideoIE(SkyItPlayerIE):
    _module = 'yt_dlp.extractor.skyit'
    IE_NAME = 'video.sky.it'
    _VALID_URL = 'https?://(?:masterchef|video|xfactor)\\.sky\\.it(?:/[^/]+)*/video/[0-9a-z-]+-(?P<id>\\d+)'


class SkyItVideoLiveIE(SkyItPlayerIE):
    _module = 'yt_dlp.extractor.skyit'
    IE_NAME = 'video.sky.it:live'
    _VALID_URL = 'https?://video\\.sky\\.it/diretta/(?P<id>[^/?&#]+)'


class SkyItIE(SkyItPlayerIE):
    _module = 'yt_dlp.extractor.skyit'
    IE_NAME = 'sky.it'
    _VALID_URL = 'https?://(?:sport|tg24)\\.sky\\.it(?:/[^/]+)*/\\d{4}/\\d{2}/\\d{2}/(?P<id>[^/?&#]+)'


class SkyItArteIE(SkyItIE):
    _module = 'yt_dlp.extractor.skyit'
    IE_NAME = 'arte.sky.it'
    _VALID_URL = 'https?://arte\\.sky\\.it/video/(?P<id>[^/?&#]+)'


class CieloTVItIE(SkyItIE):
    _module = 'yt_dlp.extractor.skyit'
    IE_NAME = 'cielotv.it'
    _VALID_URL = 'https?://(?:www\\.)?cielotv\\.it/video/(?P<id>[^.]+)\\.html'


class TV8ItIE(SkyItVideoIE):
    _module = 'yt_dlp.extractor.skyit'
    IE_NAME = 'tv8.it'
    _VALID_URL = 'https?://(?:www\\.)?tv8\\.it/(?:show)?video/[0-9a-z-]+-(?P<id>\\d+)'


class SkylineWebcamsIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.skylinewebcams'
    IE_NAME = 'SkylineWebcams'
    _VALID_URL = 'https?://(?:www\\.)?skylinewebcams\\.com/[^/]+/webcam/(?:[^/]+/)+(?P<id>[^/]+)\\.html'


class SkyNewsArabiaBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.skynewsarabia'
    IE_NAME = 'SkyNewsArabiaBase'


class SkyNewsArabiaIE(SkyNewsArabiaBaseIE):
    _module = 'yt_dlp.extractor.skynewsarabia'
    IE_NAME = 'skynewsarabia:video'
    _VALID_URL = 'https?://(?:www\\.)?skynewsarabia\\.com/web/video/(?P<id>[0-9]+)'


class SkyNewsArabiaArticleIE(SkyNewsArabiaBaseIE):
    _module = 'yt_dlp.extractor.skynewsarabia'
    IE_NAME = 'skynewsarabia:article'
    _VALID_URL = 'https?://(?:www\\.)?skynewsarabia\\.com/web/article/(?P<id>[0-9]+)'


class SkyNewsAUIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.skynewsau'
    IE_NAME = 'SkyNewsAU'
    _VALID_URL = 'https?://(?:www\\.)?skynews\\.com\\.au/[^/]+/[^/]+/[^/]+/video/(?P<id>[a-z0-9]+)'


class SkyBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.sky'
    IE_NAME = 'SkyBase'


class SkyNewsIE(SkyBaseIE):
    _module = 'yt_dlp.extractor.sky'
    IE_NAME = 'sky:news'
    _VALID_URL = 'https?://news\\.sky\\.com/video/[0-9a-z-]+-(?P<id>[0-9]+)'


class SkyNewsStoryIE(SkyBaseIE):
    _module = 'yt_dlp.extractor.sky'
    IE_NAME = 'sky:news:story'
    _VALID_URL = 'https?://news\\.sky\\.com/story/[0-9a-z-]+-(?P<id>[0-9]+)'


class SkySportsIE(SkyBaseIE):
    _module = 'yt_dlp.extractor.sky'
    IE_NAME = 'sky:sports'
    _VALID_URL = 'https?://(?:www\\.)?skysports\\.com/watch/video/([^/]+/)*(?P<id>[0-9]+)'


class SkySportsNewsIE(SkyBaseIE):
    _module = 'yt_dlp.extractor.sky'
    IE_NAME = 'sky:sports:news'
    _VALID_URL = 'https?://(?:www\\.)?skysports\\.com/([^/]+/)*news/\\d+/(?P<id>\\d+)'


class SlideshareIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.slideshare'
    IE_NAME = 'Slideshare'
    _VALID_URL = 'https?://(?:www\\.)?slideshare\\.net/[^/]+?/(?P<title>.+?)($|\\?)'


class SlidesLiveIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.slideslive'
    IE_NAME = 'SlidesLive'
    _VALID_URL = 'https?://slideslive\\.com/(?P<id>[0-9]+)'
    _WORKING = False


class SlutloadIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.slutload'
    IE_NAME = 'Slutload'
    _VALID_URL = 'https?://(?:\\w+\\.)?slutload\\.com/(?:video/[^/]+|embed_player|watch)/(?P<id>[^/]+)'
    age_limit = 18


class SmotrimIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.smotrim'
    IE_NAME = 'Smotrim'
    _VALID_URL = 'https?://smotrim\\.ru/(?P<type>brand|video|article|live)/(?P<id>[0-9]+)'


class SnotrIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.snotr'
    IE_NAME = 'Snotr'
    _VALID_URL = 'http?://(?:www\\.)?snotr\\.com/video/(?P<id>\\d+)/([\\w]+)'


class SohuIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.sohu'
    IE_NAME = 'Sohu'
    _VALID_URL = 'https?://(?P<mytv>my\\.)?tv\\.sohu\\.com/.+?/(?(mytv)|n)(?P<id>\\d+)\\.shtml.*?'


class SonyLIVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.sonyliv'
    IE_NAME = 'SonyLIV'
    _VALID_URL = '(?x)\n                     (?:\n                        sonyliv:|\n                        https?://(?:www\\.)?sonyliv\\.com/(?:s(?:how|port)s/[^/]+|movies|clip|trailer|music-videos)/[^/?#&]+-\n                    )\n                    (?P<id>\\d+)\n                  '
    _NETRC_MACHINE = 'sonyliv'


class SonyLIVSeriesIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.sonyliv'
    IE_NAME = 'SonyLIVSeries'
    _VALID_URL = 'https?://(?:www\\.)?sonyliv\\.com/shows/[^/?#&]+-(?P<id>\\d{10})$'


class SoundcloudEmbedIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.soundcloud'
    IE_NAME = 'SoundcloudEmbed'
    _VALID_URL = 'https?://(?:w|player|p)\\.soundcloud\\.com/player/?.*?\\burl=(?P<id>.+)'


class SoundcloudBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.soundcloud'
    IE_NAME = 'SoundcloudBase'
    _NETRC_MACHINE = 'soundcloud'


class SoundcloudIE(SoundcloudBaseIE):
    _module = 'yt_dlp.extractor.soundcloud'
    IE_NAME = 'soundcloud'
    _VALID_URL = '(?x)^(?:https?://)?\n                    (?:(?:(?:www\\.|m\\.)?soundcloud\\.com/\n                            (?!stations/track)\n                            (?P<uploader>[\\w\\d-]+)/\n                            (?!(?:tracks|albums|sets(?:/.+?)?|reposts|likes|spotlight)/?(?:$|[?#]))\n                            (?P<title>[\\w\\d-]+)\n                            (?:/(?P<token>(?!(?:albums|sets|recommended))[^?]+?))?\n                            (?:[?].*)?$)\n                       |(?:api(?:-v2)?\\.soundcloud\\.com/tracks/(?P<track_id>\\d+)\n                          (?:/?\\?secret_token=(?P<secret_token>[^&]+))?)\n                    )\n                    '
    _NETRC_MACHINE = 'soundcloud'


class SoundcloudPlaylistBaseIE(SoundcloudBaseIE):
    _module = 'yt_dlp.extractor.soundcloud'
    IE_NAME = 'SoundcloudPlaylistBase'
    _NETRC_MACHINE = 'soundcloud'


class SoundcloudSetIE(SoundcloudPlaylistBaseIE):
    _module = 'yt_dlp.extractor.soundcloud'
    IE_NAME = 'soundcloud:set'
    _VALID_URL = 'https?://(?:(?:www|m)\\.)?soundcloud\\.com/(?P<uploader>[\\w\\d-]+)/sets/(?P<slug_title>[:\\w\\d-]+)(?:/(?P<token>[^?/]+))?'
    _NETRC_MACHINE = 'soundcloud'


class SoundcloudPagedPlaylistBaseIE(SoundcloudBaseIE):
    _module = 'yt_dlp.extractor.soundcloud'
    IE_NAME = 'SoundcloudPagedPlaylistBase'
    _NETRC_MACHINE = 'soundcloud'


class SoundcloudRelatedIE(SoundcloudPagedPlaylistBaseIE):
    _module = 'yt_dlp.extractor.soundcloud'
    IE_NAME = 'soundcloud:related'
    _VALID_URL = 'https?://(?:(?:www|m)\\.)?soundcloud\\.com/(?P<slug>[\\w\\d-]+/[\\w\\d-]+)/(?P<relation>albums|sets|recommended)'
    _NETRC_MACHINE = 'soundcloud'


class SoundcloudUserIE(SoundcloudPagedPlaylistBaseIE):
    _module = 'yt_dlp.extractor.soundcloud'
    IE_NAME = 'soundcloud:user'
    _VALID_URL = '(?x)\n                        https?://\n                            (?:(?:www|m)\\.)?soundcloud\\.com/\n                            (?P<user>[^/]+)\n                            (?:/\n                                (?P<rsrc>tracks|albums|sets|reposts|likes|spotlight)\n                            )?\n                            /?(?:[?#].*)?$\n                    '
    _NETRC_MACHINE = 'soundcloud'


class SoundcloudTrackStationIE(SoundcloudPagedPlaylistBaseIE):
    _module = 'yt_dlp.extractor.soundcloud'
    IE_NAME = 'soundcloud:trackstation'
    _VALID_URL = 'https?://(?:(?:www|m)\\.)?soundcloud\\.com/stations/track/[^/]+/(?P<id>[^/?#&]+)'
    _NETRC_MACHINE = 'soundcloud'


class SoundcloudPlaylistIE(SoundcloudPlaylistBaseIE):
    _module = 'yt_dlp.extractor.soundcloud'
    IE_NAME = 'soundcloud:playlist'
    _VALID_URL = 'https?://api(?:-v2)?\\.soundcloud\\.com/playlists/(?P<id>[0-9]+)(?:/?\\?secret_token=(?P<token>[^&]+?))?$'
    _NETRC_MACHINE = 'soundcloud'


class SoundcloudSearchIE(SoundcloudBaseIE, LazyLoadSearchExtractor):
    _module = 'yt_dlp.extractor.soundcloud'
    IE_NAME = 'soundcloud:search'
    IE_DESC = 'Soundcloud search'
    SEARCH_KEY = 'scsearch'
    _VALID_URL = 'scsearch(?P<prefix>|[1-9][0-9]*|all):(?P<query>[\\s\\S]+)'
    _NETRC_MACHINE = 'soundcloud'


class SoundgasmIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.soundgasm'
    IE_NAME = 'soundgasm'
    _VALID_URL = 'https?://(?:www\\.)?soundgasm\\.net/u/(?P<user>[0-9a-zA-Z_-]+)/(?P<display_id>[0-9a-zA-Z_-]+)'


class SoundgasmProfileIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.soundgasm'
    IE_NAME = 'soundgasm:profile'
    _VALID_URL = 'https?://(?:www\\.)?soundgasm\\.net/u/(?P<id>[^/]+)/?(?:\\#.*)?$'


class SouthParkIE(MTVServicesInfoExtractor):
    _module = 'yt_dlp.extractor.southpark'
    IE_NAME = 'southpark.cc.com'
    _VALID_URL = 'https?://(?:www\\.)?(?P<url>southpark(?:\\.cc|studios)\\.com/((?:video-)?clips|(?:full-)?episodes|collections)/(?P<id>.+?)(\\?|#|$))'


class SouthParkDeIE(SouthParkIE):
    _module = 'yt_dlp.extractor.southpark'
    IE_NAME = 'southpark.de'
    _VALID_URL = 'https?://(?:www\\.)?(?P<url>southpark\\.de/(?:(en/(videoclip|collections|episodes|video-clips))|(videoclip|collections|folgen))/(?P<id>(?P<unique_id>.+?)/.+?)(?:\\?|#|$))'


class SouthParkDkIE(SouthParkIE):
    _module = 'yt_dlp.extractor.southpark'
    IE_NAME = 'southparkstudios.dk'
    _VALID_URL = 'https?://(?:www\\.)?(?P<url>southparkstudios\\.(?:dk|nu)/(?:clips|full-episodes|collections)/(?P<id>.+?)(\\?|#|$))'


class SouthParkEsIE(SouthParkIE):
    _module = 'yt_dlp.extractor.southpark'
    IE_NAME = 'southpark.cc.com:español'
    _VALID_URL = 'https?://(?:www\\.)?(?P<url>southpark\\.cc\\.com/es/episodios/(?P<id>.+?)(\\?|#|$))'


class SouthParkLatIE(SouthParkIE):
    _module = 'yt_dlp.extractor.southpark'
    IE_NAME = 'southpark.lat'
    _VALID_URL = 'https?://(?:www\\.)?southpark\\.lat/(?:en/)?(?:video-?clips?|collections|episod(?:e|io)s)/(?P<id>[^/?#&]+)'


class SouthParkNlIE(SouthParkIE):
    _module = 'yt_dlp.extractor.southpark'
    IE_NAME = 'southpark.nl'
    _VALID_URL = 'https?://(?:www\\.)?(?P<url>southpark\\.nl/(?:clips|(?:full-)?episodes|collections)/(?P<id>.+?)(\\?|#|$))'


class SovietsClosetBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.sovietscloset'
    IE_NAME = 'SovietsClosetBase'


class SovietsClosetIE(SovietsClosetBaseIE):
    _module = 'yt_dlp.extractor.sovietscloset'
    IE_NAME = 'SovietsCloset'
    _VALID_URL = 'https?://(?:www\\.)?sovietscloset\\.com/video/(?P<id>[0-9]+)/?'


class SovietsClosetPlaylistIE(SovietsClosetBaseIE):
    _module = 'yt_dlp.extractor.sovietscloset'
    IE_NAME = 'SovietsClosetPlaylist'
    _VALID_URL = 'https?://(?:www\\.)?sovietscloset\\.com/(?!video)(?P<id>[^#?]+)'


class SpankBangIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.spankbang'
    IE_NAME = 'SpankBang'
    _VALID_URL = '(?x)\n                    https?://\n                        (?:[^/]+\\.)?spankbang\\.com/\n                        (?:\n                            (?P<id>[\\da-z]+)/(?:video|play|embed)\\b|\n                            [\\da-z]+-(?P<id_2>[\\da-z]+)/playlist/[^/?#&]+\n                        )\n                    '
    age_limit = 18


class SpankBangPlaylistIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.spankbang'
    IE_NAME = 'SpankBangPlaylist'
    _VALID_URL = 'https?://(?:[^/]+\\.)?spankbang\\.com/(?P<id>[\\da-z]+)/playlist/(?P<display_id>[^/]+)'


class SpankwireIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.spankwire'
    IE_NAME = 'Spankwire'
    _VALID_URL = '(?x)\n                    https?://\n                        (?:www\\.)?spankwire\\.com/\n                        (?:\n                            [^/]+/video|\n                            EmbedPlayer\\.aspx/?\\?.*?\\bArticleId=\n                        )\n                        (?P<id>\\d+)\n                    '
    age_limit = 18


class SpiegelIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.spiegel'
    IE_NAME = 'Spiegel'
    _VALID_URL = 'https?://(?:www\\.)?(?:spiegel|manager-magazin)\\.de(?:/[^/]+)+/[^/]*-(?P<id>[0-9]+|[\\da-f]{8}-[\\da-f]{4}-[\\da-f]{4}-[\\da-f]{4}-[\\da-f]{12})(?:-embed|-iframe)?(?:\\.html)?(?:$|[#?])'


class BellatorIE(MTVServicesInfoExtractor):
    _module = 'yt_dlp.extractor.spike'
    IE_NAME = 'Bellator'
    _VALID_URL = 'https?://(?:www\\.)?bellator\\.com/[^/]+/[\\da-z]{6}(?:[/?#&]|$)'


class ParamountNetworkIE(MTVServicesInfoExtractor):
    _module = 'yt_dlp.extractor.spike'
    IE_NAME = 'ParamountNetwork'
    _VALID_URL = 'https?://(?:www\\.)?paramountnetwork\\.com/[^/]+/[\\da-z]{6}(?:[/?#&]|$)'


class StarTrekIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.startrek'
    IE_NAME = 'StarTrek'
    _VALID_URL = '(?P<base>https?://(?:intl|www)\\.startrek\\.com)/videos/(?P<id>[^/]+)'


class StitcherBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.stitcher'
    IE_NAME = 'StitcherBase'


class StitcherIE(StitcherBaseIE):
    _module = 'yt_dlp.extractor.stitcher'
    IE_NAME = 'Stitcher'
    _VALID_URL = 'https?://(?:www\\.)?stitcher\\.com/(?:podcast|show)/(?:[^/]+/)+e(?:pisode)?/(?:[^/#?&]+-)?(?P<id>\\d+)'


class StitcherShowIE(StitcherBaseIE):
    _module = 'yt_dlp.extractor.stitcher'
    IE_NAME = 'StitcherShow'
    _VALID_URL = 'https?://(?:www\\.)?stitcher\\.com/(?:podcast|show)/(?P<id>[^/#?&]+)/?(?:[?#&]|$)'


class Sport5IE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.sport5'
    IE_NAME = 'Sport5'
    _VALID_URL = 'https?://(?:www|vod)?\\.sport5\\.co\\.il/.*\\b(?:Vi|docID)=(?P<id>\\d+)'


class SportBoxIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.sportbox'
    IE_NAME = 'SportBox'
    _VALID_URL = 'https?://(?:news\\.sportbox|matchtv)\\.ru/vdl/player(?:/[^/]+/|\\?.*?\\bn?id=)(?P<id>\\d+)'


class SportDeutschlandIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.sportdeutschland'
    IE_NAME = 'SportDeutschland'
    _VALID_URL = 'https?://sportdeutschland\\.tv/(?P<id>(?:[^/]+/)?[^?#/&]+)'


class SpotifyBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.spotify'
    IE_NAME = 'SpotifyBase'
    _WORKING = False


class SpotifyIE(SpotifyBaseIE):
    _module = 'yt_dlp.extractor.spotify'
    IE_NAME = 'spotify'
    IE_DESC = 'Spotify episodes'
    _VALID_URL = 'https?://open\\.spotify\\.com/(?:embed-podcast/|embed/|)episode/(?P<id>[^/?&#]+)'
    _WORKING = False


class SpotifyShowIE(SpotifyBaseIE):
    _module = 'yt_dlp.extractor.spotify'
    IE_NAME = 'spotify:show'
    IE_DESC = 'Spotify shows'
    _VALID_URL = 'https?://open\\.spotify\\.com/(?:embed-podcast/|embed/|)show/(?P<id>[^/?&#]+)'
    _WORKING = False


class SpreakerIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.spreaker'
    IE_NAME = 'Spreaker'
    _VALID_URL = '(?x)\n                    https?://\n                        api\\.spreaker\\.com/\n                        (?:\n                            (?:download/)?episode|\n                            v2/episodes\n                        )/\n                        (?P<id>\\d+)\n                    '


class SpreakerPageIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.spreaker'
    IE_NAME = 'SpreakerPage'
    _VALID_URL = 'https?://(?:www\\.)?spreaker\\.com/user/[^/]+/(?P<id>[^/?#&]+)'


class SpreakerShowIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.spreaker'
    IE_NAME = 'SpreakerShow'
    _VALID_URL = 'https?://api\\.spreaker\\.com/show/(?P<id>\\d+)'


class SpreakerShowPageIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.spreaker'
    IE_NAME = 'SpreakerShowPage'
    _VALID_URL = 'https?://(?:www\\.)?spreaker\\.com/show/(?P<id>[^/?#&]+)'


class SpringboardPlatformIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.springboardplatform'
    IE_NAME = 'SpringboardPlatform'
    _VALID_URL = '(?x)\n                    https?://\n                        cms\\.springboardplatform\\.com/\n                        (?:\n                            (?:previews|embed_iframe)/(?P<index>\\d+)/video/(?P<id>\\d+)|\n                            xml_feeds_advanced/index/(?P<index_2>\\d+)/rss3/(?P<id_2>\\d+)\n                        )\n                    '


class SproutIE(AdobePassIE):
    _module = 'yt_dlp.extractor.sprout'
    IE_NAME = 'Sprout'
    _VALID_URL = 'https?://(?:www\\.)?(?:sproutonline|universalkids)\\.com/(?:watch|(?:[^/]+/)*videos)/(?P<id>[^/?#]+)'


class SRGSSRIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.srgssr'
    IE_NAME = 'SRGSSR'
    _VALID_URL = '(?x)\n                    (?:\n                        https?://tp\\.srgssr\\.ch/p(?:/[^/]+)+\\?urn=urn|\n                        srgssr\n                    ):\n                    (?P<bu>\n                        srf|rts|rsi|rtr|swi\n                    ):(?:[^:]+:)?\n                    (?P<type>\n                        video|audio\n                    ):\n                    (?P<id>\n                        [0-9a-f\\-]{36}|\\d+\n                    )\n                    '


class RTSIE(SRGSSRIE):
    _module = 'yt_dlp.extractor.rts'
    IE_NAME = 'RTS'
    IE_DESC = 'RTS.ch'
    _VALID_URL = 'rts:(?P<rts_id>\\d+)|https?://(?:.+?\\.)?rts\\.ch/(?:[^/]+/){2,}(?P<id>[0-9]+)-(?P<display_id>.+?)\\.html'


class SRGSSRPlayIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.srgssr'
    IE_NAME = 'SRGSSRPlay'
    IE_DESC = 'srf.ch, rts.ch, rsi.ch, rtr.ch and swissinfo.ch play sites'
    _VALID_URL = '(?x)\n                    https?://\n                        (?:(?:www|play)\\.)?\n                        (?P<bu>srf|rts|rsi|rtr|swissinfo)\\.ch/play/(?:tv|radio)/\n                        (?:\n                            [^/]+/(?P<type>video|audio)/[^?]+|\n                            popup(?P<type_2>video|audio)player\n                        )\n                        \\?.*?\\b(?:id=|urn=urn:[^:]+:video:)(?P<id>[0-9a-f\\-]{36}|\\d+)\n                    '


class SRMediathekIE(ARDMediathekBaseIE):
    _module = 'yt_dlp.extractor.srmediathek'
    IE_NAME = 'sr:mediathek'
    IE_DESC = 'Saarländischer Rundfunk'
    _VALID_URL = 'https?://sr-mediathek(?:\\.sr-online)?\\.de/index\\.php\\?.*?&id=(?P<id>[0-9]+)'


class StanfordOpenClassroomIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.stanfordoc'
    IE_NAME = 'stanfordoc'
    IE_DESC = 'Stanford Open ClassRoom'
    _VALID_URL = 'https?://openclassroom\\.stanford\\.edu(?P<path>/?|(/MainFolder/(?:HomePage|CoursePage|VideoPage)\\.php([?]course=(?P<course>[^&]+)(&video=(?P<video>[^&]+))?(&.*)?)?))$'


class StarTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.startv'
    IE_NAME = 'startv'
    _VALID_URL = '(?x)\n        https?://(?:www\\.)?startv\\.com\\.tr/\n        (?:\n            (?:dizi|program)/(?:[^/?#&]+)/(?:bolumler|fragmanlar|ekstralar)|\n            video/arsiv/(?:dizi|program)/(?:[^/?#&]+)\n        )/\n        (?P<id>[^/?#&]+)\n    '


class SteamIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.steam'
    IE_NAME = 'Steam'
    _VALID_URL = '(?x)\n        https?://(?:store\\.steampowered|steamcommunity)\\.com/\n            (?:agecheck/)?\n            (?P<urltype>video|app)/ #If the page is only for videos or for a game\n            (?P<gameID>\\d+)/?\n            (?P<videoID>\\d*)(?P<extra>\\??) # For urltype == video we sometimes get the videoID\n        |\n        https?://(?:www\\.)?steamcommunity\\.com/sharedfiles/filedetails/\\?id=(?P<fileID>[0-9]+)\n    '


class SteamCommunityBroadcastIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.steam'
    IE_NAME = 'SteamCommunityBroadcast'
    _VALID_URL = 'https?://steamcommunity\\.(?:com)/broadcast/watch/(?P<id>\\d+)'


class StoryFireBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.storyfire'
    IE_NAME = 'StoryFireBase'


class StoryFireIE(StoryFireBaseIE):
    _module = 'yt_dlp.extractor.storyfire'
    IE_NAME = 'StoryFire'
    _VALID_URL = 'https?://(?:www\\.)?storyfire\\.com/video-details/(?P<id>[0-9a-f]{24})'


class StoryFireUserIE(StoryFireBaseIE):
    _module = 'yt_dlp.extractor.storyfire'
    IE_NAME = 'StoryFireUser'
    _VALID_URL = 'https?://(?:www\\.)?storyfire\\.com/user/(?P<id>[^/]+)/video'


class StoryFireSeriesIE(StoryFireBaseIE):
    _module = 'yt_dlp.extractor.storyfire'
    IE_NAME = 'StoryFireSeries'
    _VALID_URL = 'https?://(?:www\\.)?storyfire\\.com/write/series/stories/(?P<id>[^/?&#]+)'


class StreamableIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.streamable'
    IE_NAME = 'Streamable'
    _VALID_URL = 'https?://streamable\\.com/(?:[es]/)?(?P<id>\\w+)'


class StreamanityIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.streamanity'
    IE_NAME = 'Streamanity'
    _VALID_URL = 'https?://(?:www\\.)?streamanity\\.com/video/(?P<id>[A-Za-z0-9]+)'


class StreamcloudIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.streamcloud'
    IE_NAME = 'streamcloud.eu'
    _VALID_URL = 'https?://streamcloud\\.eu/(?P<id>[a-zA-Z0-9_-]+)(?:/(?P<fname>[^#?]*)\\.html)?'


class StreamCZIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.streamcz'
    IE_NAME = 'StreamCZ'
    _VALID_URL = 'https?://(?:www\\.)?(?:stream|televizeseznam)\\.cz/[^?#]+/(?P<display_id>[^?#]+)-(?P<id>[0-9]+)'


class StreamFFIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.streamff'
    IE_NAME = 'StreamFF'
    _VALID_URL = 'https?://(?:www\\.)?streamff\\.com/v/(?P<id>[a-zA-Z0-9]+)'


class StreetVoiceIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.streetvoice'
    IE_NAME = 'StreetVoice'
    _VALID_URL = 'https?://(?:.+?\\.)?streetvoice\\.com/[^/]+/songs/(?P<id>[0-9]+)'


class StretchInternetIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.stretchinternet'
    IE_NAME = 'StretchInternet'
    _VALID_URL = 'https?://portal\\.stretchinternet\\.com/[^/]+/(?:portal|full)\\.htm\\?.*?\\beventId=(?P<id>\\d+)'


class StripchatIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.stripchat'
    IE_NAME = 'Stripchat'
    _VALID_URL = 'https?://stripchat\\.com/(?P<id>[^/?#]+)'
    age_limit = 18


class STVPlayerIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.stv'
    IE_NAME = 'stv:player'
    _VALID_URL = 'https?://player\\.stv\\.tv/(?P<type>episode|video)/(?P<id>[a-z0-9]{4})'


class SubstackIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.substack'
    IE_NAME = 'Substack'
    _VALID_URL = 'https?://(?P<username>[\\w-]+)\\.substack\\.com/p/(?P<id>[\\w-]+)'


class SunPornoIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.sunporno'
    IE_NAME = 'SunPorno'
    _VALID_URL = 'https?://(?:(?:www\\.)?sunporno\\.com/videos|embeds\\.sunporno\\.com/embed)/(?P<id>\\d+)'
    age_limit = 18


class SverigesRadioBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.sverigesradio'
    IE_NAME = 'SverigesRadioBase'


class SverigesRadioEpisodeIE(SverigesRadioBaseIE):
    _module = 'yt_dlp.extractor.sverigesradio'
    IE_NAME = 'sverigesradio:episode'
    _VALID_URL = 'https?://(?:www\\.)?sverigesradio\\.se/(?:sida/)?avsnitt/(?P<id>[0-9]+)'


class SverigesRadioPublicationIE(SverigesRadioBaseIE):
    _module = 'yt_dlp.extractor.sverigesradio'
    IE_NAME = 'sverigesradio:publication'
    _VALID_URL = 'https?://(?:www\\.)?sverigesradio\\.se/sida/(?:artikel|gruppsida)\\.aspx\\?.*?\\bartikel=(?P<id>[0-9]+)'


class SVTBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.svt'
    IE_NAME = 'SVTBase'


class SVTIE(SVTBaseIE):
    _module = 'yt_dlp.extractor.svt'
    IE_NAME = 'SVT'
    _VALID_URL = 'https?://(?:www\\.)?svt\\.se/wd\\?(?:.*?&)?widgetId=(?P<widget_id>\\d+)&.*?\\barticleId=(?P<id>\\d+)'


class SVTPageIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.svt'
    IE_NAME = 'SVTPage'
    _VALID_URL = 'https?://(?:www\\.)?svt\\.se/(?P<path>(?:[^/]+/)*(?P<id>[^/?&#]+))'

    @classmethod
    def suitable(cls, url):
        return False if SVTIE.suitable(url) or SVTPlayIE.suitable(url) else super(SVTPageIE, cls).suitable(url)


class SVTPlayBaseIE(SVTBaseIE):
    _module = 'yt_dlp.extractor.svt'
    IE_NAME = 'SVTPlayBase'


class SVTPlayIE(SVTPlayBaseIE):
    _module = 'yt_dlp.extractor.svt'
    IE_NAME = 'SVTPlay'
    IE_DESC = 'SVT Play and Öppet arkiv'
    _VALID_URL = '(?x)\n                    (?:\n                        (?:\n                            svt:|\n                            https?://(?:www\\.)?svt\\.se/barnkanalen/barnplay/[^/]+/\n                        )\n                        (?P<svt_id>[^/?#&]+)|\n                        https?://(?:www\\.)?(?:svtplay|oppetarkiv)\\.se/(?:video|klipp|kanaler)/(?P<id>[^/?#&]+)\n                        (?:.*?(?:modalId|id)=(?P<modal_id>[\\da-zA-Z-]+))?\n                    )\n                    '


class SVTSeriesIE(SVTPlayBaseIE):
    _module = 'yt_dlp.extractor.svt'
    IE_NAME = 'SVTSeries'
    _VALID_URL = 'https?://(?:www\\.)?svtplay\\.se/(?P<id>[^/?&#]+)(?:.+?\\btab=(?P<season_slug>[^&#]+))?'

    @classmethod
    def suitable(cls, url):
        return False if SVTIE.suitable(url) or SVTPlayIE.suitable(url) else super(SVTSeriesIE, cls).suitable(url)


class SwearnetEpisodeIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.swearnet'
    IE_NAME = 'SwearnetEpisode'
    _VALID_URL = 'https?://www\\.swearnet\\.com/shows/(?P<id>[\\w-]+)/seasons/(?P<season_num>\\d+)/episodes/(?P<episode_num>\\d+)'


class SWRMediathekIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.swrmediathek'
    IE_NAME = 'SWRMediathek'
    _VALID_URL = 'https?://(?:www\\.)?swrmediathek\\.de/(?:content/)?player\\.htm\\?show=(?P<id>[\\da-f]{8}-[\\da-f]{4}-[\\da-f]{4}-[\\da-f]{4}-[\\da-f]{12})'


class SYVDKIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.syvdk'
    IE_NAME = 'SYVDK'
    _VALID_URL = 'https?://(?:www\\.)?24syv\\.dk/episode/(?P<id>[\\w-]+)'


class SyfyIE(AdobePassIE):
    _module = 'yt_dlp.extractor.syfy'
    IE_NAME = 'Syfy'
    _VALID_URL = 'https?://(?:www\\.)?syfy\\.com/(?:[^/]+/)?videos/(?P<id>[^/?#]+)'


class SztvHuIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.sztvhu'
    IE_NAME = 'SztvHu'
    _VALID_URL = 'https?://(?:(?:www\\.)?sztv\\.hu|www\\.tvszombathely\\.hu)/(?:[^/]+)/.+-(?P<id>[0-9]+)'


class TagesschauIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tagesschau'
    IE_NAME = 'Tagesschau'
    _VALID_URL = 'https?://(?:www\\.)?tagesschau\\.de/(?P<path>[^/]+/(?:[^/]+/)*?(?P<id>[^/#?]+?(?:-?[0-9]+)?))(?:~_?[^/#?]+?)?\\.html'


class TassIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tass'
    IE_NAME = 'Tass'
    _VALID_URL = 'https?://(?:tass\\.ru|itar-tass\\.com)/[^/]+/(?P<id>\\d+)'


class TBSIE(TurnerBaseIE):
    _module = 'yt_dlp.extractor.tbs'
    IE_NAME = 'TBS'
    _VALID_URL = 'https?://(?:www\\.)?(?P<site>tbs|tntdrama)\\.com(?P<path>/(?:movies|watchtnt|watchtbs|shows/[^/]+/(?:clips|season-\\d+/episode-\\d+))/(?P<id>[^/?#]+))'


class TDSLifewayIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tdslifeway'
    IE_NAME = 'TDSLifeway'
    _VALID_URL = 'https?://tds\\.lifeway\\.com/v1/trainingdeliverysystem/courses/(?P<id>\\d+)/index\\.html'


class TeachableBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.teachable'
    IE_NAME = 'TeachableBase'
    _NETRC_MACHINE = 'teachable'


class TeachableIE(TeachableBaseIE):
    _module = 'yt_dlp.extractor.teachable'
    IE_NAME = 'Teachable'
    _VALID_URL = '(?x)\n                    (?:\n                        teachable:https?://(?P<site_t>[^/]+)|\n                        https?://(?:www\\.)?(?P<site>v1\\.upskillcourses\\.com|gns3\\.teachable\\.com|academyhacker\\.com|stackskills\\.com|market\\.saleshacker\\.com|learnability\\.org|edurila\\.com|courses\\.workitdaily\\.com)\n                    )\n                    /courses/[^/]+/lectures/(?P<id>\\d+)\n                    '
    _NETRC_MACHINE = 'teachable'


class TeachableCourseIE(TeachableBaseIE):
    _module = 'yt_dlp.extractor.teachable'
    IE_NAME = 'TeachableCourse'
    _VALID_URL = '(?x)\n                        (?:\n                            teachable:https?://(?P<site_t>[^/]+)|\n                            https?://(?:www\\.)?(?P<site>v1\\.upskillcourses\\.com|gns3\\.teachable\\.com|academyhacker\\.com|stackskills\\.com|market\\.saleshacker\\.com|learnability\\.org|edurila\\.com|courses\\.workitdaily\\.com)\n                        )\n                        /(?:courses|p)/(?:enrolled/)?(?P<id>[^/?#&]+)\n                    '
    _NETRC_MACHINE = 'teachable'

    @classmethod
    def suitable(cls, url):
        return False if TeachableIE.suitable(url) else super(
            TeachableCourseIE, cls).suitable(url)


class TeacherTubeIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.teachertube'
    IE_NAME = 'teachertube'
    IE_DESC = 'teachertube.com videos'
    _VALID_URL = 'https?://(?:www\\.)?teachertube\\.com/(viewVideo\\.php\\?video_id=|music\\.php\\?music_id=|video/(?:[\\da-z-]+-)?|audio/)(?P<id>\\d+)'


class TeacherTubeUserIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.teachertube'
    IE_NAME = 'teachertube:user:collection'
    IE_DESC = 'teachertube.com user and collection videos'
    _VALID_URL = 'https?://(?:www\\.)?teachertube\\.com/(user/profile|collection)/(?P<user>[0-9a-zA-Z]+)/?'


class TeachingChannelIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.teachingchannel'
    IE_NAME = 'TeachingChannel'
    _VALID_URL = 'https?://(?:www\\.)?teachingchannel\\.org/videos?/(?P<id>[^/?&#]+)'


class TeamcocoIE(TurnerBaseIE):
    _module = 'yt_dlp.extractor.teamcoco'
    IE_NAME = 'Teamcoco'
    _VALID_URL = 'https?://(?:\\w+\\.)?teamcoco\\.com/(?P<id>([^/]+/)*[^/?#]+)'


class TeamTreeHouseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.teamtreehouse'
    IE_NAME = 'TeamTreeHouse'
    _VALID_URL = 'https?://(?:www\\.)?teamtreehouse\\.com/library/(?P<id>[^/]+)'
    _NETRC_MACHINE = 'teamtreehouse'


class TechTalksIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.techtalks'
    IE_NAME = 'TechTalks'
    _VALID_URL = 'https?://techtalks\\.tv/talks/(?:[^/]+/)?(?P<id>\\d+)'


class TedEmbedIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ted'
    IE_NAME = 'TedEmbed'
    _VALID_URL = 'https?://embed(?:-ssl)?\\.ted\\.com/'


class TedBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ted'
    IE_NAME = 'TedBase'


class TedPlaylistIE(TedBaseIE):
    _module = 'yt_dlp.extractor.ted'
    IE_NAME = 'TedPlaylist'
    _VALID_URL = 'https?://www\\.ted\\.com/(?:playlists(?:/\\d+)?)(?:/lang/[^/#?]+)?/(?P<id>[\\w-]+)'


class TedSeriesIE(TedBaseIE):
    _module = 'yt_dlp.extractor.ted'
    IE_NAME = 'TedSeries'
    _VALID_URL = 'https?://www\\.ted\\.com/(?:series)(?:/lang/[^/#?]+)?/(?P<id>[\\w-]+)(?:#season_(?P<season>\\d+))?'


class TedTalkIE(TedBaseIE):
    _module = 'yt_dlp.extractor.ted'
    IE_NAME = 'TedTalk'
    _VALID_URL = 'https?://www\\.ted\\.com/(?:talks)(?:/lang/[^/#?]+)?/(?P<id>[\\w-]+)'


class Tele5IE(DPlayIE):
    _module = 'yt_dlp.extractor.tele5'
    IE_NAME = 'Tele5'
    _VALID_URL = 'https?://(?:www\\.)?tele5\\.de/(?:[^/]+/)*(?P<id>[^/?#&]+)'


class Tele13IE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tele13'
    IE_NAME = 'Tele13'
    _VALID_URL = '^https?://(?:www\\.)?t13\\.cl/videos(?:/[^/]+)+/(?P<id>[\\w-]+)'


class TeleBruxellesIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.telebruxelles'
    IE_NAME = 'TeleBruxelles'
    _VALID_URL = 'https?://(?:www\\.)?(?:telebruxelles|bx1)\\.be/(?:[^/]+/)*(?P<id>[^/#?]+)'


class TelecincoIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.telecinco'
    IE_NAME = 'Telecinco'
    IE_DESC = 'telecinco.es, cuatro.com and mediaset.es'
    _VALID_URL = 'https?://(?:www\\.)?(?:telecinco\\.es|cuatro\\.com|mediaset\\.es)/(?:[^/]+/)+(?P<id>.+?)\\.html'


class MiTeleIE(TelecincoIE):
    _module = 'yt_dlp.extractor.mitele'
    IE_NAME = 'MiTele'
    IE_DESC = 'mitele.es'
    _VALID_URL = 'https?://(?:www\\.)?mitele\\.es/(?:[^/]+/)+(?P<id>[^/]+)/player'
    age_limit = 16


class TelegraafIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.telegraaf'
    IE_NAME = 'Telegraaf'
    _VALID_URL = 'https?://(?:www\\.)?telegraaf\\.nl/video/(?P<id>\\d+)'


class TelegramEmbedIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.telegram'
    IE_NAME = 'telegram:embed'
    _VALID_URL = 'https?://t\\.me/(?P<channel_id>[^/]+)/(?P<id>\\d+)'


class TeleMBIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.telemb'
    IE_NAME = 'TeleMB'
    _VALID_URL = 'https?://(?:www\\.)?telemb\\.be/(?P<display_id>.+?)_d_(?P<id>\\d+)\\.html'


class TelemundoIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.telemundo'
    IE_NAME = 'Telemundo'
    _VALID_URL = 'https?:\\/\\/(?:www\\.)?telemundo\\.com\\/.+?video\\/[^\\/]+(?P<id>tmvo\\d{7})'


class TeleQuebecBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.telequebec'
    IE_NAME = 'TeleQuebecBase'


class TeleQuebecIE(TeleQuebecBaseIE):
    _module = 'yt_dlp.extractor.telequebec'
    IE_NAME = 'TeleQuebec'
    _VALID_URL = '(?x)\n                    https?://\n                        (?:\n                            zonevideo\\.telequebec\\.tv/media|\n                            coucou\\.telequebec\\.tv/videos\n                        )/(?P<id>\\d+)\n                    '


class TeleQuebecSquatIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.telequebec'
    IE_NAME = 'TeleQuebecSquat'
    _VALID_URL = 'https://squat\\.telequebec\\.tv/videos/(?P<id>\\d+)'


class TeleQuebecEmissionIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.telequebec'
    IE_NAME = 'TeleQuebecEmission'
    _VALID_URL = '(?x)\n                    https?://\n                        (?:\n                            [^/]+\\.telequebec\\.tv/emissions/|\n                            (?:www\\.)?telequebec\\.tv/\n                        )\n                        (?P<id>[^?#&]+)\n                    '


class TeleQuebecLiveIE(TeleQuebecBaseIE):
    _module = 'yt_dlp.extractor.telequebec'
    IE_NAME = 'TeleQuebecLive'
    _VALID_URL = 'https?://zonevideo\\.telequebec\\.tv/(?P<id>endirect)'


class TeleQuebecVideoIE(TeleQuebecBaseIE):
    _module = 'yt_dlp.extractor.telequebec'
    IE_NAME = 'TeleQuebecVideo'
    _VALID_URL = 'https?://video\\.telequebec\\.tv/player(?:-live)?/(?P<id>\\d+)'


class TeleTaskIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.teletask'
    IE_NAME = 'TeleTask'
    _VALID_URL = 'https?://(?:www\\.)?tele-task\\.de/archive/video/html5/(?P<id>[0-9]+)'


class TelewebionIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.telewebion'
    IE_NAME = 'Telewebion'
    _VALID_URL = 'https?://(?:www\\.)?telewebion\\.com/#!/episode/(?P<id>\\d+)'


class TempoIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tempo'
    IE_NAME = 'Tempo'
    _VALID_URL = 'https?://video\\.tempo\\.co/\\w+/\\d+/(?P<id>[\\w-]+)'


class TencentBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tencent'
    IE_NAME = 'TencentBase'


class WeTvBaseIE(TencentBaseIE):
    _module = 'yt_dlp.extractor.tencent'
    IE_NAME = 'WeTvBase'


class IflixBaseIE(WeTvBaseIE):
    _module = 'yt_dlp.extractor.tencent'
    IE_NAME = 'IflixBase'


class IflixEpisodeIE(IflixBaseIE):
    _module = 'yt_dlp.extractor.tencent'
    IE_NAME = 'iflix:episode'
    _VALID_URL = 'https?://(?:www\\.)?iflix\\.com/(?:[^?#]+/)?play/(?P<series_id>\\w+)(?:-[^?#]+)?/(?P<id>\\w+)(?:-[^?#]+)?'


class IflixSeriesIE(IflixBaseIE):
    _module = 'yt_dlp.extractor.tencent'
    IE_NAME = 'IflixSeries'
    _VALID_URL = 'https?://(?:www\\.)?iflix\\.com/(?:[^?#]+/)?play/(?P<id>\\w+)(?:-[^/?#]+)?/?(?:[?#]|$)'


class VQQBaseIE(TencentBaseIE):
    _module = 'yt_dlp.extractor.tencent'
    IE_NAME = 'VQQBase'


class VQQSeriesIE(VQQBaseIE):
    _module = 'yt_dlp.extractor.tencent'
    IE_NAME = 'vqq:series'
    _VALID_URL = 'https?://v\\.qq\\.com/x/cover/(?P<id>\\w+)\\.html/?(?:[?#]|$)'


class VQQVideoIE(VQQBaseIE):
    _module = 'yt_dlp.extractor.tencent'
    IE_NAME = 'vqq:video'
    _VALID_URL = 'https?://v\\.qq\\.com/x/(?:page|cover/(?P<series_id>\\w+))/(?P<id>\\w+)'


class WeTvEpisodeIE(WeTvBaseIE):
    _module = 'yt_dlp.extractor.tencent'
    IE_NAME = 'wetv:episode'
    _VALID_URL = 'https?://(?:www\\.)?wetv\\.vip/(?:[^?#]+/)?play/(?P<series_id>\\w+)(?:-[^?#]+)?/(?P<id>\\w+)(?:-[^?#]+)?'


class WeTvSeriesIE(WeTvBaseIE):
    _module = 'yt_dlp.extractor.tencent'
    IE_NAME = 'WeTvSeries'
    _VALID_URL = 'https?://(?:www\\.)?wetv\\.vip/(?:[^?#]+/)?play/(?P<id>\\w+)(?:-[^/?#]+)?/?(?:[?#]|$)'


class TennisTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tennistv'
    IE_NAME = 'TennisTV'
    _VALID_URL = 'https?://(?:www\\.)?tennistv\\.com/videos/(?P<id>[-a-z0-9]+)'
    _NETRC_MACHINE = 'tennistv'


class TenPlayIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tenplay'
    IE_NAME = 'TenPlay'
    _VALID_URL = 'https?://(?:www\\.)?10play\\.com\\.au/(?:[^/]+/)+(?P<id>tpv\\d{6}[a-z]{5})'
    _NETRC_MACHINE = '10play'
    age_limit = 15


class TestURLIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.testurl'
    IE_NAME = 'TestURL'
    IE_DESC = False
    _VALID_URL = 'test(?:url)?:(?P<extractor>.*?)(?:_(?P<num>[0-9]+))?$'


class TF1IE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tf1'
    IE_NAME = 'TF1'
    _VALID_URL = 'https?://(?:www\\.)?tf1\\.fr/[^/]+/(?P<program_slug>[^/]+)/videos/(?P<id>[^/?&#]+)\\.html'


class TFOIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tfo'
    IE_NAME = 'TFO'
    _VALID_URL = 'https?://(?:www\\.)?tfo\\.org/(?:en|fr)/(?:[^/]+/){2}(?P<id>\\d+)'


class TheHoleTvIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.theholetv'
    IE_NAME = 'TheHoleTv'
    _VALID_URL = 'https?://(?:www\\.)?the-hole\\.tv/episodes/(?P<id>[\\w-]+)'


class TheInterceptIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.theintercept'
    IE_NAME = 'TheIntercept'
    _VALID_URL = 'https?://theintercept\\.com/fieldofvision/(?P<id>[^/?#]+)'


class ThePlatformIE(ThePlatformBaseIE, AdobePassIE):
    _module = 'yt_dlp.extractor.theplatform'
    IE_NAME = 'ThePlatform'
    _VALID_URL = '(?x)\n        (?:https?://(?:link|player)\\.theplatform\\.com/[sp]/(?P<provider_id>[^/]+)/\n           (?:(?:(?:[^/]+/)+select/)?(?P<media>media/(?:guid/\\d+/)?)?|(?P<config>(?:[^/\\?]+/(?:swf|config)|onsite)/select/))?\n         |theplatform:)(?P<id>[^/\\?&]+)'


class AENetworksBaseIE(ThePlatformIE):
    _module = 'yt_dlp.extractor.aenetworks'
    IE_NAME = 'AENetworksBase'
    _VALID_URL = '(?x)\n        (?:https?://(?:link|player)\\.theplatform\\.com/[sp]/(?P<provider_id>[^/]+)/\n           (?:(?:(?:[^/]+/)+select/)?(?P<media>media/(?:guid/\\d+/)?)?|(?P<config>(?:[^/\\?]+/(?:swf|config)|onsite)/select/))?\n         |theplatform:)(?P<id>[^/\\?&]+)'


class AENetworksListBaseIE(AENetworksBaseIE):
    _module = 'yt_dlp.extractor.aenetworks'
    IE_NAME = 'AENetworksListBase'
    _VALID_URL = '(?x)\n        (?:https?://(?:link|player)\\.theplatform\\.com/[sp]/(?P<provider_id>[^/]+)/\n           (?:(?:(?:[^/]+/)+select/)?(?P<media>media/(?:guid/\\d+/)?)?|(?P<config>(?:[^/\\?]+/(?:swf|config)|onsite)/select/))?\n         |theplatform:)(?P<id>[^/\\?&]+)'


class AENetworksIE(AENetworksBaseIE):
    _module = 'yt_dlp.extractor.aenetworks'
    IE_NAME = 'aenetworks'
    IE_DESC = 'A+E Networks: A&E, Lifetime, History.com, FYI Network and History Vault'
    _VALID_URL = '(?x)https?://\n        (?:(?:www|play|watch)\\.)?\n        (?P<domain>\n            (?:history(?:vault)?|aetv|mylifetime|lifetimemovieclub)\\.com|\n            fyi\\.tv\n        )/(?P<id>\n        shows/[^/]+/season-\\d+/episode-\\d+|\n        (?:\n            (?:movie|special)s/[^/]+|\n            (?:shows/[^/]+/)?videos\n        )/[^/?#&]+\n    )'


class AENetworksCollectionIE(AENetworksListBaseIE):
    _module = 'yt_dlp.extractor.aenetworks'
    IE_NAME = 'aenetworks:collection'
    _VALID_URL = '(?x)https?://\n        (?:(?:www|play|watch)\\.)?\n        (?P<domain>\n            (?:history(?:vault)?|aetv|mylifetime|lifetimemovieclub)\\.com|\n            fyi\\.tv\n        )/(?:[^/]+/)*(?:list|collections)/(?P<id>[^/?#&]+)/?(?:[?#&]|$)'


class AENetworksShowIE(AENetworksListBaseIE):
    _module = 'yt_dlp.extractor.aenetworks'
    IE_NAME = 'aenetworks:show'
    _VALID_URL = '(?x)https?://\n        (?:(?:www|play|watch)\\.)?\n        (?P<domain>\n            (?:history(?:vault)?|aetv|mylifetime|lifetimemovieclub)\\.com|\n            fyi\\.tv\n        )/shows/(?P<id>[^/?#&]+)/?(?:[?#&]|$)'


class HistoryTopicIE(AENetworksBaseIE):
    _module = 'yt_dlp.extractor.aenetworks'
    IE_NAME = 'history:topic'
    IE_DESC = 'History.com Topic'
    _VALID_URL = 'https?://(?:www\\.)?history\\.com/topics/[^/]+/(?P<id>[\\w+-]+?)-video'


class HistoryPlayerIE(AENetworksBaseIE):
    _module = 'yt_dlp.extractor.aenetworks'
    IE_NAME = 'history:player'
    _VALID_URL = 'https?://(?:www\\.)?(?P<domain>(?:history|biography)\\.com)/player/(?P<id>\\d+)'


class BiographyIE(AENetworksBaseIE):
    _module = 'yt_dlp.extractor.aenetworks'
    IE_NAME = 'Biography'
    _VALID_URL = 'https?://(?:www\\.)?biography\\.com/video/(?P<id>[^/?#&]+)'


class AMCNetworksIE(ThePlatformIE):
    _module = 'yt_dlp.extractor.amcnetworks'
    IE_NAME = 'AMCNetworks'
    _VALID_URL = 'https?://(?:www\\.)?(?P<site>amc|bbcamerica|ifc|(?:we|sundance)tv)\\.com/(?P<id>(?:movies|shows(?:/[^/]+)+)/[^/?#&]+)'


class NBCIE(ThePlatformIE):
    _module = 'yt_dlp.extractor.nbc'
    IE_NAME = 'NBC'
    _VALID_URL = 'https?(?P<permalink>://(?:www\\.)?nbc\\.com/(?:classic-tv/)?[^/]+/video/[^/]+/(?P<id>n?\\d+))'


class NBCNewsIE(ThePlatformIE):
    _module = 'yt_dlp.extractor.nbc'
    IE_NAME = 'NBCNews'
    _VALID_URL = '(?x)https?://(?:www\\.)?(?:nbcnews|today|msnbc)\\.com/([^/]+/)*(?:.*-)?(?P<id>[^/?]+)'


class ThePlatformFeedIE(ThePlatformBaseIE):
    _module = 'yt_dlp.extractor.theplatform'
    IE_NAME = 'ThePlatformFeed'
    _VALID_URL = 'https?://feed\\.theplatform\\.com/f/(?P<provider_id>[^/]+)/(?P<feed_id>[^?/]+)\\?(?:[^&]+&)*(?P<filter>by(?:Gui|I)d=(?P<id>[^&]+))'


class CBSBaseIE(ThePlatformFeedIE):
    _module = 'yt_dlp.extractor.cbs'
    IE_NAME = 'CBSBase'
    _VALID_URL = 'https?://feed\\.theplatform\\.com/f/(?P<provider_id>[^/]+)/(?P<feed_id>[^?/]+)\\?(?:[^&]+&)*(?P<filter>by(?:Gui|I)d=(?P<id>[^&]+))'


class CBSIE(CBSBaseIE):
    _module = 'yt_dlp.extractor.cbs'
    IE_NAME = 'CBS'
    _VALID_URL = '(?x)\n        (?:\n            cbs:|\n            https?://(?:www\\.)?(?:\n                cbs\\.com/(?:shows|movies)/(?:video|[^/]+/video|[^/]+)/|\n                colbertlateshow\\.com/(?:video|podcasts)/)\n        )(?P<id>[\\w-]+)'


class CBSInteractiveIE(CBSIE):
    _module = 'yt_dlp.extractor.cbsinteractive'
    IE_NAME = 'CBSInteractive'
    _VALID_URL = 'https?://(?:www\\.)?(?P<site>cnet|zdnet)\\.com/(?:videos|video(?:/share)?)/(?P<id>[^/?]+)'


class CBSNewsEmbedIE(CBSIE):
    _module = 'yt_dlp.extractor.cbsnews'
    IE_NAME = 'cbsnews:embed'
    _VALID_URL = 'https?://(?:www\\.)?cbsnews\\.com/embed/video[^#]*#(?P<id>.+)'


class CBSNewsIE(CBSIE):
    _module = 'yt_dlp.extractor.cbsnews'
    IE_NAME = 'cbsnews'
    IE_DESC = 'CBS News'
    _VALID_URL = 'https?://(?:www\\.)?cbsnews\\.com/(?:news|video)/(?P<id>[\\da-z_-]+)'


class CorusIE(ThePlatformFeedIE):
    _module = 'yt_dlp.extractor.corus'
    IE_NAME = 'Corus'
    _VALID_URL = '(?x)\n                    https?://\n                        (?:www\\.)?\n                        (?P<domain>\n                            (?:\n                                globaltv|\n                                etcanada|\n                                seriesplus|\n                                wnetwork|\n                                ytv\n                            )\\.com|\n                            (?:\n                                hgtv|\n                                foodnetwork|\n                                slice|\n                                history|\n                                showcase|\n                                bigbrothercanada|\n                                abcspark|\n                                disney(?:channel|lachaine)\n                            )\\.ca\n                        )\n                        /(?:[^/]+/)*\n                        (?:\n                            video\\.html\\?.*?\\bv=|\n                            videos?/(?:[^/]+/)*(?:[a-z0-9-]+-)?\n                        )\n                        (?P<id>\n                            [\\da-f]{8}-[\\da-f]{4}-[\\da-f]{4}-[\\da-f]{4}-[\\da-f]{12}|\n                            (?:[A-Z]{4})?\\d{12,20}\n                        )\n                    '


class ParamountPlusIE(CBSBaseIE):
    _module = 'yt_dlp.extractor.paramountplus'
    IE_NAME = 'ParamountPlus'
    _VALID_URL = '(?x)\n        (?:\n            paramountplus:|\n            https?://(?:www\\.)?(?:\n                paramountplus\\.com/(?:shows|movies)/(?:video|[^/]+/video|[^/]+)/\n        )(?P<id>[\\w-]+))'


class TheStarIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.thestar'
    IE_NAME = 'TheStar'
    _VALID_URL = 'https?://(?:www\\.)?thestar\\.com/(?:[^/]+/)*(?P<id>.+)\\.html'


class TheSunIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.thesun'
    IE_NAME = 'TheSun'
    _VALID_URL = 'https://(?:www\\.)?thesun\\.co\\.uk/[^/]+/(?P<id>\\d+)'


class ThetaVideoIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.theta'
    IE_NAME = 'ThetaVideo'
    _VALID_URL = 'https?://(?:www\\.)?theta\\.tv/video/(?P<id>vid[a-z0-9]+)'


class ThetaStreamIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.theta'
    IE_NAME = 'ThetaStream'
    _VALID_URL = 'https?://(?:www\\.)?theta\\.tv/(?!video/)(?P<id>[a-z0-9-]+)'


class TheWeatherChannelIE(ThePlatformIE):
    _module = 'yt_dlp.extractor.theweatherchannel'
    IE_NAME = 'TheWeatherChannel'
    _VALID_URL = 'https?://(?:www\\.)?weather\\.com(?P<asset_name>(?:/(?P<locale>[a-z]{2}-[A-Z]{2}))?/(?:[^/]+/)*video/(?P<id>[^/?#]+))'


class ThisAmericanLifeIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.thisamericanlife'
    IE_NAME = 'ThisAmericanLife'
    _VALID_URL = 'https?://(?:www\\.)?thisamericanlife\\.org/(?:radio-archives/episode/|play_full\\.php\\?play=)(?P<id>\\d+)'


class ThisAVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.thisav'
    IE_NAME = 'ThisAV'
    _VALID_URL = 'https?://(?:www\\.)?thisav\\.com/video/(?P<id>[0-9]+)/.*'


class ThisOldHouseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.thisoldhouse'
    IE_NAME = 'ThisOldHouse'
    _VALID_URL = 'https?://(?:www\\.)?thisoldhouse\\.com/(?:watch|how-to|tv-episode|(?:[^/]+/)?\\d+)/(?P<id>[^/?#]+)'


class ThreeSpeakIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.threespeak'
    IE_NAME = 'ThreeSpeak'
    _VALID_URL = 'https?://(?:www\\.)?3speak\\.tv/watch\\?v\\=[^/]+/(?P<id>[^/$&#?]+)'


class ThreeSpeakUserIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.threespeak'
    IE_NAME = 'ThreeSpeakUser'
    _VALID_URL = 'https?://(?:www\\.)?3speak\\.tv/user/(?P<id>[^/$&?#]+)'


class ThreeQSDNIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.threeqsdn'
    IE_NAME = '3qsdn'
    IE_DESC = '3Q SDN'
    _VALID_URL = 'https?://playout\\.3qsdn\\.com/(?P<id>[\\da-f]{8}-[\\da-f]{4}-[\\da-f]{4}-[\\da-f]{4}-[\\da-f]{12})'


class TikTokBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tiktok'
    IE_NAME = 'TikTokBase'


class TikTokIE(TikTokBaseIE):
    _module = 'yt_dlp.extractor.tiktok'
    IE_NAME = 'TikTok'
    _VALID_URL = 'https?://www\\.tiktok\\.com/(?:embed|@(?P<user_id>[\\w\\.-]+)/video)/(?P<id>\\d+)'


class TikTokUserIE(TikTokBaseIE):
    _module = 'yt_dlp.extractor.tiktok'
    IE_NAME = 'tiktok:user'
    _VALID_URL = 'https?://(?:www\\.)?tiktok\\.com/@(?P<id>[\\w\\.-]+)/?(?:$|[#?])'
    _WORKING = False


class TikTokBaseListIE(TikTokBaseIE):
    _module = 'yt_dlp.extractor.tiktok'
    IE_NAME = 'TikTokBaseList'


class TikTokSoundIE(TikTokBaseListIE):
    _module = 'yt_dlp.extractor.tiktok'
    IE_NAME = 'tiktok:sound'
    _VALID_URL = 'https?://(?:www\\.)?tiktok\\.com/music/[\\w\\.-]+-(?P<id>[\\d]+)[/?#&]?'
    _WORKING = False


class TikTokEffectIE(TikTokBaseListIE):
    _module = 'yt_dlp.extractor.tiktok'
    IE_NAME = 'tiktok:effect'
    _VALID_URL = 'https?://(?:www\\.)?tiktok\\.com/sticker/[\\w\\.-]+-(?P<id>[\\d]+)[/?#&]?'
    _WORKING = False


class TikTokTagIE(TikTokBaseListIE):
    _module = 'yt_dlp.extractor.tiktok'
    IE_NAME = 'tiktok:tag'
    _VALID_URL = 'https?://(?:www\\.)?tiktok\\.com/tag/(?P<id>[^/?#&]+)'
    _WORKING = False


class TikTokVMIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tiktok'
    IE_NAME = 'vm.tiktok'
    _VALID_URL = 'https?://(?:vm|vt)\\.tiktok\\.com/(?P<id>\\w+)'


class DouyinIE(TikTokIE):
    _module = 'yt_dlp.extractor.tiktok'
    IE_NAME = 'Douyin'
    _VALID_URL = 'https?://(?:www\\.)?douyin\\.com/video/(?P<id>[0-9]+)'


class TinyPicIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tinypic'
    IE_NAME = 'tinypic'
    IE_DESC = 'tinypic.com videos'
    _VALID_URL = 'https?://(?:.+?\\.)?tinypic\\.com/player\\.php\\?v=(?P<id>[^&]+)&s=\\d+'


class TMZIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tmz'
    IE_NAME = 'TMZ'
    _VALID_URL = 'https?://(?:www\\.)?tmz\\.com/.*'


class TNAFlixNetworkBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tnaflix'
    IE_NAME = 'TNAFlixNetworkBase'


class TNAFlixNetworkEmbedIE(TNAFlixNetworkBaseIE):
    _module = 'yt_dlp.extractor.tnaflix'
    IE_NAME = 'TNAFlixNetworkEmbed'
    _VALID_URL = 'https?://player\\.(?P<host>tnaflix|empflix)\\.com/video/(?P<id>\\d+)'
    age_limit = 18


class TNAEMPFlixBaseIE(TNAFlixNetworkBaseIE):
    _module = 'yt_dlp.extractor.tnaflix'
    IE_NAME = 'TNAEMPFlixBase'


class TNAFlixIE(TNAEMPFlixBaseIE):
    _module = 'yt_dlp.extractor.tnaflix'
    IE_NAME = 'TNAFlix'
    _VALID_URL = 'https?://(?:www\\.)?(?P<host>tnaflix)\\.com/[^/]+/(?P<display_id>[^/]+)/video(?P<id>\\d+)'
    age_limit = 18


class EMPFlixIE(TNAEMPFlixBaseIE):
    _module = 'yt_dlp.extractor.tnaflix'
    IE_NAME = 'EMPFlix'
    _VALID_URL = 'https?://(?:www\\.)?(?P<host>empflix)\\.com/(?:videos/(?P<display_id>.+?)-|[^/]+/(?P<display_id_2>[^/]+)/video)(?P<id>[0-9]+)'
    age_limit = 18


class MovieFapIE(TNAFlixNetworkBaseIE):
    _module = 'yt_dlp.extractor.tnaflix'
    IE_NAME = 'MovieFap'
    _VALID_URL = 'https?://(?:www\\.)?(?P<host>moviefap)\\.com/videos/(?P<id>[0-9a-f]+)/(?P<display_id>[^/]+)\\.html'
    age_limit = 18


class ToggleIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.toggle'
    IE_NAME = 'toggle'
    _VALID_URL = '(?:https?://(?:(?:www\\.)?mewatch|video\\.toggle)\\.sg/(?:en|zh)/(?:[^/]+/){2,}|toggle:)(?P<id>[0-9]+)'


class MeWatchIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.toggle'
    IE_NAME = 'mewatch'
    _VALID_URL = 'https?://(?:(?:www|live)\\.)?mewatch\\.sg/watch/[^/?#&]+-(?P<id>[0-9]+)'


class ToggoIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.toggo'
    IE_NAME = 'toggo'
    _VALID_URL = 'https?://(?:www\\.)?toggo\\.de/(?:toggolino/)?[^/?#]+/(?:folge|video)/(?P<id>[^/?#]+)'


class TokentubeIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tokentube'
    IE_NAME = 'Tokentube'
    _VALID_URL = 'https?://(?:www\\.)?tokentube\\.net/(?:view\\?[vl]=|[vl]/)(?P<id>\\d+)'


class TokentubeChannelIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tokentube'
    IE_NAME = 'Tokentube:channel'
    _VALID_URL = 'https?://(?:www\\.)?tokentube\\.net/channel/(?P<id>\\d+)/[^/]+(?:/videos)?'


class TOnlineIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tonline'
    IE_NAME = 't-online.de'
    _VALID_URL = 'https?://(?:www\\.)?t-online\\.de/tv/(?:[^/]+/)*id_(?P<id>\\d+)'


class ToonGogglesIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.toongoggles'
    IE_NAME = 'ToonGoggles'
    _VALID_URL = 'https?://(?:www\\.)?toongoggles\\.com/shows/(?P<show_id>\\d+)(?:/[^/]+/episodes/(?P<episode_id>\\d+))?'


class TouTvIE(RadioCanadaIE):
    _module = 'yt_dlp.extractor.toutv'
    IE_NAME = 'tou.tv'
    _VALID_URL = 'https?://ici\\.tou\\.tv/(?P<id>[a-zA-Z0-9_-]+(?:/S[0-9]+[EC][0-9]+)?)'
    _NETRC_MACHINE = 'toutv'


class ToypicsUserIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.toypics'
    IE_NAME = 'ToypicsUser'
    IE_DESC = 'Toypics user profile'
    _VALID_URL = 'https?://videos\\.toypics\\.net/(?!view)(?P<id>[^/?#&]+)'


class ToypicsIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.toypics'
    IE_NAME = 'Toypics'
    IE_DESC = 'Toypics video'
    _VALID_URL = 'https?://videos\\.toypics\\.net/view/(?P<id>[0-9]+)'
    age_limit = 18


class TrailerAddictIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.traileraddict'
    IE_NAME = 'TrailerAddict'
    _VALID_URL = '(?:https?://)?(?:www\\.)?traileraddict\\.com/(?:trailer|clip)/(?P<movie>.+?)/(?P<trailer_name>.+)'
    _WORKING = False


class TrillerBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.triller'
    IE_NAME = 'TrillerBase'
    _NETRC_MACHINE = 'triller'


class TrillerIE(TrillerBaseIE):
    _module = 'yt_dlp.extractor.triller'
    IE_NAME = 'Triller'
    _VALID_URL = '(?x)\n            https?://(?:www\\.)?triller\\.co/\n            @(?P<username>[\\w\\._]+)/video/\n            (?P<id>[\\da-f]{8}-[\\da-f]{4}-[\\da-f]{4}-[\\da-f]{4}-[\\da-f]{12})\n        '
    _NETRC_MACHINE = 'triller'


class TrillerUserIE(TrillerBaseIE):
    _module = 'yt_dlp.extractor.triller'
    IE_NAME = 'TrillerUser'
    _VALID_URL = 'https?://(?:www\\.)?triller\\.co/@(?P<id>[\\w\\._]+)/?(?:$|[#?])'
    _NETRC_MACHINE = 'triller'


class TriluliluIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.trilulilu'
    IE_NAME = 'Trilulilu'
    _VALID_URL = 'https?://(?:(?:www|m)\\.)?trilulilu\\.ro/(?:[^/]+/)?(?P<id>[^/#\\?]+)'


class TrovoBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.trovo'
    IE_NAME = 'TrovoBase'


class TrovoIE(TrovoBaseIE):
    _module = 'yt_dlp.extractor.trovo'
    IE_NAME = 'Trovo'
    _VALID_URL = 'https?://(?:www\\.)?trovo\\.live/(?:s/)?(?!(?:clip|video)/)(?P<id>(?!s/)[^/?&#]+(?![^#]+[?&]vid=))'


class TrovoVodIE(TrovoBaseIE):
    _module = 'yt_dlp.extractor.trovo'
    IE_NAME = 'TrovoVod'
    _VALID_URL = 'https?://(?:www\\.)?trovo\\.live/(?:clip|video|s)/(?:[^/]+/\\d+[^#]*[?&]vid=)?(?P<id>(?<!/s/)[^/?&#]+)'


class TrovoChannelBaseIE(TrovoBaseIE):
    _module = 'yt_dlp.extractor.trovo'
    IE_NAME = 'TrovoChannelBase'


class TrovoChannelVodIE(TrovoChannelBaseIE):
    _module = 'yt_dlp.extractor.trovo'
    IE_NAME = 'TrovoChannelVod'
    IE_DESC = 'All VODs of a trovo.live channel; "trovovod:" prefix'
    _VALID_URL = 'trovovod:(?P<id>[^\\s]+)'


class TrovoChannelClipIE(TrovoChannelBaseIE):
    _module = 'yt_dlp.extractor.trovo'
    IE_NAME = 'TrovoChannelClip'
    IE_DESC = 'All Clips of a trovo.live channel; "trovoclip:" prefix'
    _VALID_URL = 'trovoclip:(?P<id>[^\\s]+)'


class TrueIDIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.trueid'
    IE_NAME = 'TrueID'
    _VALID_URL = 'https?://(?P<domain>vn\\.trueid\\.net|trueid\\.(?:id|ph))/(?:movie|series/[^/]+)/(?P<id>[^/?#&]+)'
    age_limit = 13


class TruNewsIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.trunews'
    IE_NAME = 'TruNews'
    _VALID_URL = 'https?://(?:www\\.)?trunews\\.com/stream/(?P<id>[^/?#&]+)'


class TruthIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.truth'
    IE_NAME = 'Truth'
    _VALID_URL = 'https?://truthsocial\\.com/@[^/]+/posts/(?P<id>\\d+)'


class TruTVIE(TurnerBaseIE):
    _module = 'yt_dlp.extractor.trutv'
    IE_NAME = 'TruTV'
    _VALID_URL = 'https?://(?:www\\.)?trutv\\.com/(?:shows|full-episodes)/(?P<series_slug>[0-9A-Za-z-]+)/(?:videos/(?P<clip_slug>[0-9A-Za-z-]+)|(?P<id>\\d+))'


class Tube8IE(KeezMoviesIE):
    _module = 'yt_dlp.extractor.tube8'
    IE_NAME = 'Tube8'
    _VALID_URL = 'https?://(?:www\\.)?tube8\\.com/(?:[^/]+/)+(?P<display_id>[^/]+)/(?P<id>\\d+)'
    age_limit = 18


class TubeTuGrazBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tubetugraz'
    IE_NAME = 'TubeTuGrazBase'
    _NETRC_MACHINE = 'tubetugraz'


class TubeTuGrazIE(TubeTuGrazBaseIE):
    _module = 'yt_dlp.extractor.tubetugraz'
    IE_NAME = 'TubeTuGraz'
    IE_DESC = 'tube.tugraz.at'
    _VALID_URL = '(?x)\n        https?://tube\\.tugraz\\.at/paella/ui/watch.html\\?id=\n        (?P<id>[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12})\n    '
    _NETRC_MACHINE = 'tubetugraz'


class TubeTuGrazSeriesIE(TubeTuGrazBaseIE):
    _module = 'yt_dlp.extractor.tubetugraz'
    IE_NAME = 'TubeTuGrazSeries'
    _VALID_URL = '(?x)\n        https?://tube\\.tugraz\\.at/paella/ui/browse\\.html\\?series=\n        (?P<id>[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12})\n    '
    _NETRC_MACHINE = 'tubetugraz'


class TubiTvIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tubitv'
    IE_NAME = 'TubiTv'
    _VALID_URL = '(?x)\n                    (?:\n                        tubitv:|\n                        https?://(?:www\\.)?tubitv\\.com/(?:video|movies|tv-shows)/\n                    )\n                    (?P<id>[0-9]+)'
    _NETRC_MACHINE = 'tubitv'


class TubiTvShowIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tubitv'
    IE_NAME = 'TubiTvShow'
    _VALID_URL = 'https?://(?:www\\.)?tubitv\\.com/series/[0-9]+/(?P<show_name>[^/?#]+)'


class TumblrIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tumblr'
    IE_NAME = 'Tumblr'
    _VALID_URL = 'https?://(?P<blog_name>[^/?#&]+)\\.tumblr\\.com/(?:post|video)/(?P<id>[0-9]+)(?:$|[/?#])'
    _NETRC_MACHINE = 'tumblr'
    age_limit = 18


class TuneInBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tunein'
    IE_NAME = 'TuneInBase'


class TuneInClipIE(TuneInBaseIE):
    _module = 'yt_dlp.extractor.tunein'
    IE_NAME = 'tunein:clip'
    _VALID_URL = 'https?://(?:www\\.)?tunein\\.com/station/.*?audioClipId\\=(?P<id>\\d+)'


class TuneInStationIE(TuneInBaseIE):
    _module = 'yt_dlp.extractor.tunein'
    IE_NAME = 'tunein:station'
    _VALID_URL = 'https?://(?:www\\.)?tunein\\.com/(?:radio/.*?-s|station/.*?StationId=|embed/player/s)(?P<id>\\d+)'

    @classmethod
    def suitable(cls, url):
        return False if TuneInClipIE.suitable(url) else super(TuneInStationIE, cls).suitable(url)


class TuneInProgramIE(TuneInBaseIE):
    _module = 'yt_dlp.extractor.tunein'
    IE_NAME = 'tunein:program'
    _VALID_URL = 'https?://(?:www\\.)?tunein\\.com/(?:radio/.*?-p|program/.*?ProgramId=|embed/player/p)(?P<id>\\d+)'


class TuneInTopicIE(TuneInBaseIE):
    _module = 'yt_dlp.extractor.tunein'
    IE_NAME = 'tunein:topic'
    _VALID_URL = 'https?://(?:www\\.)?tunein\\.com/(?:topic/.*?TopicId=|embed/player/t)(?P<id>\\d+)'


class TuneInShortenerIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tunein'
    IE_NAME = 'tunein:shortener'
    IE_DESC = False
    _VALID_URL = 'https?://tun\\.in/(?P<id>[A-Za-z0-9]+)'


class TunePkIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tunepk'
    IE_NAME = 'TunePk'
    _VALID_URL = '(?x)\n                    https?://\n                        (?:\n                            (?:www\\.)?tune\\.pk/(?:video/|player/embed_player.php?.*?\\bvid=)|\n                            embed\\.tune\\.pk/play/\n                        )\n                        (?P<id>\\d+)\n                    '


class TurboIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.turbo'
    IE_NAME = 'Turbo'
    _VALID_URL = 'https?://(?:www\\.)?turbo\\.fr/videos-voiture/(?P<id>[0-9]+)-'


class TV2IE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tv2'
    IE_NAME = 'TV2'
    _VALID_URL = 'https?://(?:www\\.)?tv2\\.no/v(?:ideo)?\\d*/(?:[^?#]+/)*(?P<id>\\d+)'


class TV2ArticleIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tv2'
    IE_NAME = 'TV2Article'
    _VALID_URL = 'https?://(?:www\\.)?tv2\\.no/(?!v(?:ideo)?\\d*/)[^?#]+/(?P<id>\\d+)'


class KatsomoIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tv2'
    IE_NAME = 'Katsomo'
    _VALID_URL = 'https?://(?:www\\.)?(?:katsomo|mtv(uutiset)?)\\.fi/(?:sarja/[0-9a-z-]+-\\d+/[0-9a-z-]+-|(?:#!/)?jakso/(?:\\d+/[^/]+/)?|video/prog)(?P<id>\\d+)'


class MTVUutisetArticleIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tv2'
    IE_NAME = 'MTVUutisetArticle'
    _VALID_URL = 'https?://(?:www\\.)mtvuutiset\\.fi/artikkeli/[^/]+/(?P<id>\\d+)'


class TV24UAVideoIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tv24ua'
    IE_NAME = '24tv.ua'
    _VALID_URL = 'https?://24tv\\.ua/news/showPlayer\\.do.*?(?:\\?|&)objectId=(?P<id>\\d+)'


class TV2DKIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tv2dk'
    IE_NAME = 'TV2DK'
    _VALID_URL = '(?x)\n                    https?://\n                        (?:www\\.)?\n                        (?:\n                            tvsyd|\n                            tv2ostjylland|\n                            tvmidtvest|\n                            tv2fyn|\n                            tv2east|\n                            tv2lorry|\n                            tv2nord\n                        )\\.dk/\n                        (:[^/]+/)*\n                        (?P<id>[^/?\\#&]+)\n                    '


class TV2DKBornholmPlayIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tv2dk'
    IE_NAME = 'TV2DKBornholmPlay'
    _VALID_URL = 'https?://play\\.tv2bornholm\\.dk/\\?.*?\\bid=(?P<id>\\d+)'


class TV2HuIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tv2hu'
    IE_NAME = 'tv2play.hu'
    _VALID_URL = 'https?://(?:www\\.)?tv2play\\.hu/(?!szalag/)(?P<id>[^#&?]+)'


class TV2HuSeriesIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tv2hu'
    IE_NAME = 'tv2playseries.hu'
    _VALID_URL = 'https?://(?:www\\.)?tv2play\\.hu/szalag/(?P<id>[^#&?]+)'


class TV4IE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tv4'
    IE_NAME = 'TV4'
    IE_DESC = 'tv4.se and tv4play.se'
    _VALID_URL = '(?x)https?://(?:www\\.)?\n        (?:\n            tv4\\.se/(?:[^/]+)/klipp/(?:.*)-|\n            tv4play\\.se/\n            (?:\n                (?:program|barn)/(?:(?:[^/]+/){1,2}|(?:[^\\?]+)\\?video_id=)|\n                iframe/video/|\n                film/|\n                sport/|\n            )\n        )(?P<id>[0-9]+)'


class TV5MondePlusIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tv5mondeplus'
    IE_NAME = 'TV5MondePlus'
    IE_DESC = 'TV5MONDE+'
    _VALID_URL = 'https?://(?:www\\.)?(?:tv5mondeplus|revoir\\.tv5monde)\\.com/toutes-les-videos/[^/]+/(?P<id>[^/?#]+)'


class TV5UnisBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tv5unis'
    IE_NAME = 'TV5UnisBase'


class TV5UnisVideoIE(TV5UnisBaseIE):
    _module = 'yt_dlp.extractor.tv5unis'
    IE_NAME = 'tv5unis:video'
    _VALID_URL = 'https?://(?:www\\.)?tv5unis\\.ca/videos/[^/]+/(?P<id>\\d+)'


class TV5UnisIE(TV5UnisBaseIE):
    _module = 'yt_dlp.extractor.tv5unis'
    IE_NAME = 'tv5unis'
    _VALID_URL = 'https?://(?:www\\.)?tv5unis\\.ca/videos/(?P<id>[^/]+)(?:/saisons/(?P<season_number>\\d+)/episodes/(?P<episode_number>\\d+))?/?(?:[?#&]|$)'
    age_limit = 8


class TVAIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tva'
    IE_NAME = 'TVA'
    _VALID_URL = 'https?://videos?\\.tva\\.ca/details/_(?P<id>\\d+)'


class QubIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tva'
    IE_NAME = 'Qub'
    _VALID_URL = 'https?://(?:www\\.)?qub\\.ca/(?:[^/]+/)*[0-9a-z-]+-(?P<id>\\d+)'


class TVANouvellesIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tvanouvelles'
    IE_NAME = 'TVANouvelles'
    _VALID_URL = 'https?://(?:www\\.)?tvanouvelles\\.ca/videos/(?P<id>\\d+)'


class TVANouvellesArticleIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tvanouvelles'
    IE_NAME = 'TVANouvellesArticle'
    _VALID_URL = 'https?://(?:www\\.)?tvanouvelles\\.ca/(?:[^/]+/)+(?P<id>[^/?#&]+)'

    @classmethod
    def suitable(cls, url):
        return False if TVANouvellesIE.suitable(url) else super(TVANouvellesArticleIE, cls).suitable(url)


class TVCIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tvc'
    IE_NAME = 'TVC'
    _VALID_URL = 'https?://(?:www\\.)?tvc\\.ru/video/iframe/id/(?P<id>\\d+)'


class TVCArticleIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tvc'
    IE_NAME = 'TVCArticle'
    _VALID_URL = 'https?://(?:www\\.)?tvc\\.ru/(?!video/iframe/id/)(?P<id>[^?#]+)'


class TVerIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tver'
    IE_NAME = 'TVer'
    _VALID_URL = 'https?://(?:www\\.)?tver\\.jp/(?:(?P<type>lp|corner|series|episodes?|feature|tokyo2020/video)/)+(?P<id>[a-zA-Z0-9]+)'


class TvigleIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tvigle'
    IE_NAME = 'tvigle'
    IE_DESC = 'Интернет-телевидение Tvigle.ru'
    _VALID_URL = 'https?://(?:www\\.)?(?:tvigle\\.ru/(?:[^/]+/)+(?P<display_id>[^/]+)/$|cloud\\.tvigle\\.ru/video/(?P<id>\\d+))'
    age_limit = 12


class TVIPlayerIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tviplayer'
    IE_NAME = 'TVIPlayer'
    _VALID_URL = 'https?://tviplayer\\.iol\\.pt(/programa/[\\w-]+/[a-f0-9]+)?/\\w+/(?P<id>\\w+)'


class TVLandIE(MTVServicesInfoExtractor):
    _module = 'yt_dlp.extractor.tvland'
    IE_NAME = 'tvland.com'
    _VALID_URL = 'https?://(?:www\\.)?tvland\\.com/(?:video-clips|(?:full-)?episodes)/(?P<id>[^/?#.]+)'


class TVN24IE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tvn24'
    IE_NAME = 'TVN24'
    _VALID_URL = 'https?://(?:(?:[^/]+)\\.)?tvn24(?:bis)?\\.pl/(?:[^/]+/)*(?P<id>[^/]+)'


class TVNetIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tvnet'
    IE_NAME = 'TVNet'
    _VALID_URL = 'https?://(?:[^/]+)\\.tvnet\\.gov\\.vn/[^/]+/(?:\\d+/)?(?P<id>\\d+)(?:/|$)'


class TVNoeIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tvnoe'
    IE_NAME = 'TVNoe'
    _VALID_URL = 'https?://(?:www\\.)?tvnoe\\.cz/video/(?P<id>[0-9]+)'


class TVNowBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tvnow'
    IE_NAME = 'TVNowBase'


class TVNowIE(TVNowBaseIE):
    _module = 'yt_dlp.extractor.tvnow'
    IE_NAME = 'TVNow'
    _VALID_URL = '(?x)\n                    https?://\n                        (?:www\\.)?tvnow\\.(?:de|at|ch)/(?P<station>[^/]+)/\n                        (?P<show_id>[^/]+)/\n                        (?!(?:list|jahr)(?:/|$))(?P<id>[^/?\\#&]+)\n                    '

    @classmethod
    def suitable(cls, url):
        return (False if TVNowNewIE.suitable(url) or TVNowSeasonIE.suitable(url) or TVNowAnnualIE.suitable(url) or TVNowShowIE.suitable(url)
                else super(TVNowIE, cls).suitable(url))


class TVNowFilmIE(TVNowBaseIE):
    _module = 'yt_dlp.extractor.tvnow'
    IE_NAME = 'TVNowFilm'
    _VALID_URL = '(?x)\n                    (?P<base_url>https?://\n                        (?:www\\.)?tvnow\\.(?:de|at|ch)/\n                        (?:filme))/\n                        (?P<title>[^/?$&]+)-(?P<id>\\d+)\n                    '


class TVNowNewIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tvnow'
    IE_NAME = 'TVNowNew'
    _VALID_URL = '(?x)\n                    (?P<base_url>https?://\n                        (?:www\\.)?tvnow\\.(?:de|at|ch)/\n                        (?:shows|serien))/\n                        (?P<show>[^/]+)-\\d+/\n                        [^/]+/\n                        episode-\\d+-(?P<episode>[^/?$&]+)-(?P<id>\\d+)\n                    '


class TVNowNewBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tvnow'
    IE_NAME = 'TVNowNewBase'


class TVNowListBaseIE(TVNowNewBaseIE):
    _module = 'yt_dlp.extractor.tvnow'
    IE_NAME = 'TVNowListBase'

    @classmethod
    def suitable(cls, url):
        return (False if TVNowNewIE.suitable(url)
                else super(TVNowListBaseIE, cls).suitable(url))


class TVNowSeasonIE(TVNowListBaseIE):
    _module = 'yt_dlp.extractor.tvnow'
    IE_NAME = 'TVNowSeason'
    _VALID_URL = '(?x)\n                    (?P<base_url>\n                        https?://\n                            (?:www\\.)?tvnow\\.(?:de|at|ch)/(?:shows|serien)/\n                            [^/?#&]+-(?P<show_id>\\d+)\n                    )\n                    /staffel-(?P<id>\\d+)'

    @classmethod
    def suitable(cls, url):
        return (False if TVNowNewIE.suitable(url)
                else super(TVNowListBaseIE, cls).suitable(url))


class TVNowAnnualIE(TVNowListBaseIE):
    _module = 'yt_dlp.extractor.tvnow'
    IE_NAME = 'TVNowAnnual'
    _VALID_URL = '(?x)\n                    (?P<base_url>\n                        https?://\n                            (?:www\\.)?tvnow\\.(?:de|at|ch)/(?:shows|serien)/\n                            [^/?#&]+-(?P<show_id>\\d+)\n                    )\n                    /(?P<year>\\d{4})-(?P<month>\\d{2})'

    @classmethod
    def suitable(cls, url):
        return (False if TVNowNewIE.suitable(url)
                else super(TVNowListBaseIE, cls).suitable(url))


class TVNowShowIE(TVNowListBaseIE):
    _module = 'yt_dlp.extractor.tvnow'
    IE_NAME = 'TVNowShow'
    _VALID_URL = '(?x)\n                    (?P<base_url>\n                        https?://\n                            (?:www\\.)?tvnow\\.(?:de|at|ch)/(?:shows|serien)/\n                            [^/?#&]+-(?P<show_id>\\d+)\n                    )\n                    '

    @classmethod
    def suitable(cls, url):
        return (False if TVNowNewIE.suitable(url) or TVNowSeasonIE.suitable(url) or TVNowAnnualIE.suitable(url)
                else super(TVNowShowIE, cls).suitable(url))


class TVOpenGrBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tvopengr'
    IE_NAME = 'TVOpenGrBase'


class TVOpenGrWatchIE(TVOpenGrBaseIE):
    _module = 'yt_dlp.extractor.tvopengr'
    IE_NAME = 'tvopengr:watch'
    IE_DESC = 'tvopen.gr (and ethnos.gr) videos'
    _VALID_URL = 'https?://(?P<netloc>(?:www\\.)?(?:tvopen|ethnos)\\.gr)/watch/(?P<id>\\d+)/(?P<slug>[^/]+)'


class TVOpenGrEmbedIE(TVOpenGrBaseIE):
    _module = 'yt_dlp.extractor.tvopengr'
    IE_NAME = 'tvopengr:embed'
    IE_DESC = 'tvopen.gr embedded videos'
    _VALID_URL = '(?:https?:)?//(?:www\\.|cdn\\.|)(?:tvopen|ethnos).gr/embed/(?P<id>\\d+)'


class TVPEmbedIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tvp'
    IE_NAME = 'tvp:embed'
    IE_DESC = 'Telewizja Polska'
    _VALID_URL = '(?x)\n        (?:\n            tvp:\n            |https?://\n                (?:[^/]+\\.)?\n                (?:tvp(?:parlament)?\\.pl|tvp\\.info|tvpworld\\.com|swipeto\\.pl)/\n                (?:sess/\n                        (?:tvplayer\\.php\\?.*?object_id\n                        |TVPlayer2/(?:embed|api)\\.php\\?.*[Ii][Dd])\n                    |shared/details\\.php\\?.*?object_id)\n                =)\n        (?P<id>\\d+)\n    '
    age_limit = 12


class TVPIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tvp'
    IE_NAME = 'tvp'
    IE_DESC = 'Telewizja Polska'
    _VALID_URL = 'https?://(?:[^/]+\\.)?(?:tvp(?:parlament)?\\.(?:pl|info)|tvpworld\\.com|swipeto\\.pl)/(?:(?!\\d+/)[^/]+/)*(?P<id>\\d+)'
    age_limit = 12


class TVPStreamIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tvp'
    IE_NAME = 'tvp:stream'
    _VALID_URL = '(?:tvpstream:|https?://tvpstream\\.vod\\.tvp\\.pl/(?:\\?(?:[^&]+[&;])*channel_id=)?)(?P<id>\\d*)'


class TVPVODBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tvp'
    IE_NAME = 'TVPVODBase'


class TVPVODSeriesIE(TVPVODBaseIE):
    _module = 'yt_dlp.extractor.tvp'
    IE_NAME = 'tvp:vod:series'
    _VALID_URL = 'https?://vod\\.tvp\\.pl/[a-z\\d-]+,\\d+/[a-z\\d-]+-odcinki,(?P<id>\\d+)(?:\\?[^#]+)?(?:#.+)?$'
    age_limit = 12


class TVPVODVideoIE(TVPVODBaseIE):
    _module = 'yt_dlp.extractor.tvp'
    IE_NAME = 'tvp:vod'
    _VALID_URL = 'https?://vod\\.tvp\\.pl/[a-z\\d-]+,\\d+/[a-z\\d-]+(?<!-odcinki)(?:-odcinki,\\d+/odcinek-\\d+,S\\d+E\\d+)?,(?P<id>\\d+)(?:\\?[^#]+)?(?:#.+)?$'
    age_limit = 12


class TVPlayIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tvplay'
    IE_NAME = 'mtg'
    IE_DESC = 'MTG services'
    _VALID_URL = '(?x)\n                    (?:\n                        mtg:|\n                        https?://\n                            (?:www\\.)?\n                            (?:\n                                tvplay(?:\\.skaties)?\\.lv(?:/parraides)?|\n                                (?:tv3play|play\\.tv3)\\.lt(?:/programos)?|\n                                tv3play(?:\\.tv3)?\\.ee/sisu|\n                                (?:tv(?:3|6|8|10)play)\\.se/program|\n                                (?:(?:tv3play|viasat4play|tv6play)\\.no|(?:tv3play)\\.dk)/programmer|\n                                play\\.nova(?:tv)?\\.bg/programi\n                            )\n                            /(?:[^/]+/)+\n                        )\n                        (?P<id>\\d+)\n                    '
    age_limit = 18


class ViafreeIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tvplay'
    IE_NAME = 'Viafree'
    _VALID_URL = '(?x)\n                    https?://\n                        (?:www\\.)?\n                        viafree\\.(?P<country>dk|no|se|fi)\n                        /(?P<id>(?:program(?:mer)?|ohjelmat)?/(?:[^/]+/)+[^/?#&]+)\n                    '


class TVPlayHomeIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tvplay'
    IE_NAME = 'TVPlayHome'
    _VALID_URL = '(?x)\n            https?://\n            (?:tv3?)?\n            play\\.(?:tv3|skaties)\\.(?P<country>lv|lt|ee)/\n            (?P<live>lives/)?\n            [^?#&]+(?:episode|programme|clip)-(?P<id>\\d+)\n    '


class TVPlayerIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tvplayer'
    IE_NAME = 'TVPlayer'
    _VALID_URL = 'https?://(?:www\\.)?tvplayer\\.com/watch/(?P<id>[^/?#]+)'


class TweakersIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.tweakers'
    IE_NAME = 'Tweakers'
    _VALID_URL = 'https?://tweakers\\.net/video/(?P<id>\\d+)'


class TwentyFourVideoIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.twentyfourvideo'
    IE_NAME = '24video'
    _VALID_URL = '(?x)\n                    https?://\n                        (?P<host>\n                            (?:(?:www|porno?)\\.)?24video\\.\n                            (?:net|me|xxx|sexy?|tube|adult|site|vip)\n                        )/\n                        (?:\n                            video/(?:(?:view|xml)/)?|\n                            player/new24_play\\.swf\\?id=\n                        )\n                        (?P<id>\\d+)\n                    '
    age_limit = 18


class TwentyMinutenIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.twentymin'
    IE_NAME = '20min'
    _VALID_URL = '(?x)\n                    https?://\n                        (?:www\\.)?20min\\.ch/\n                        (?:\n                            videotv/*\\?.*?\\bvid=|\n                            videoplayer/videoplayer\\.html\\?.*?\\bvideoId@\n                        )\n                        (?P<id>\\d+)\n                    '


class TwentyThreeVideoIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.twentythreevideo'
    IE_NAME = '23video'
    _VALID_URL = 'https?://(?P<domain>[^.]+\\.(?:twentythree\\.net|23video\\.com|filmweb\\.no))/v\\.ihtml/player\\.html\\?(?P<query>.*?\\bphoto(?:_|%5f)id=(?P<id>\\d+).*)'


class TwitCastingIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.twitcasting'
    IE_NAME = 'TwitCasting'
    _VALID_URL = 'https?://(?:[^/]+\\.)?twitcasting\\.tv/(?P<uploader_id>[^/]+)/(?:movie|twplayer)/(?P<id>\\d+)'


class TwitCastingLiveIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.twitcasting'
    IE_NAME = 'TwitCastingLive'
    _VALID_URL = 'https?://(?:[^/]+\\.)?twitcasting\\.tv/(?P<id>[^/]+)/?(?:[#?]|$)'


class TwitCastingUserIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.twitcasting'
    IE_NAME = 'TwitCastingUser'
    _VALID_URL = 'https?://(?:[^/]+\\.)?twitcasting\\.tv/(?P<id>[^/]+)/show/?(?:[#?]|$)'


class TwitchBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.twitch'
    IE_NAME = 'TwitchBase'
    _NETRC_MACHINE = 'twitch'


class TwitchVodIE(TwitchBaseIE):
    _module = 'yt_dlp.extractor.twitch'
    IE_NAME = 'twitch:vod'
    _VALID_URL = '(?x)\n                    https?://\n                        (?:\n                            (?:(?:www|go|m)\\.)?twitch\\.tv/(?:[^/]+/v(?:ideo)?|videos)/|\n                            player\\.twitch\\.tv/\\?.*?\\bvideo=v?\n                        )\n                        (?P<id>\\d+)\n                    '
    _NETRC_MACHINE = 'twitch'


class TwitchCollectionIE(TwitchBaseIE):
    _module = 'yt_dlp.extractor.twitch'
    IE_NAME = 'TwitchCollection'
    _VALID_URL = 'https?://(?:(?:www|go|m)\\.)?twitch\\.tv/collections/(?P<id>[^/]+)'
    _NETRC_MACHINE = 'twitch'


class TwitchPlaylistBaseIE(TwitchBaseIE):
    _module = 'yt_dlp.extractor.twitch'
    IE_NAME = 'TwitchPlaylistBase'
    _NETRC_MACHINE = 'twitch'


class TwitchVideosIE(TwitchPlaylistBaseIE):
    _module = 'yt_dlp.extractor.twitch'
    IE_NAME = 'TwitchVideos'
    _VALID_URL = 'https?://(?:(?:www|go|m)\\.)?twitch\\.tv/(?P<id>[^/]+)/(?:videos|profile)'
    _NETRC_MACHINE = 'twitch'

    @classmethod
    def suitable(cls, url):
        return (False
                if any(ie.suitable(url) for ie in (
                    TwitchVideosClipsIE,
                    TwitchVideosCollectionsIE))
                else super(TwitchVideosIE, cls).suitable(url))


class TwitchVideosClipsIE(TwitchPlaylistBaseIE):
    _module = 'yt_dlp.extractor.twitch'
    IE_NAME = 'TwitchVideosClips'
    _VALID_URL = 'https?://(?:(?:www|go|m)\\.)?twitch\\.tv/(?P<id>[^/]+)/(?:clips|videos/*?\\?.*?\\bfilter=clips)'
    _NETRC_MACHINE = 'twitch'


class TwitchVideosCollectionsIE(TwitchPlaylistBaseIE):
    _module = 'yt_dlp.extractor.twitch'
    IE_NAME = 'TwitchVideosCollections'
    _VALID_URL = 'https?://(?:(?:www|go|m)\\.)?twitch\\.tv/(?P<id>[^/]+)/videos/*?\\?.*?\\bfilter=collections'
    _NETRC_MACHINE = 'twitch'


class TwitchStreamIE(TwitchBaseIE):
    _module = 'yt_dlp.extractor.twitch'
    IE_NAME = 'twitch:stream'
    _VALID_URL = '(?x)\n                    https?://\n                        (?:\n                            (?:(?:www|go|m)\\.)?twitch\\.tv/|\n                            player\\.twitch\\.tv/\\?.*?\\bchannel=\n                        )\n                        (?P<id>[^/#?]+)\n                    '
    _NETRC_MACHINE = 'twitch'

    @classmethod
    def suitable(cls, url):
        return (False
                if any(ie.suitable(url) for ie in (
                    TwitchVodIE,
                    TwitchCollectionIE,
                    TwitchVideosIE,
                    TwitchVideosClipsIE,
                    TwitchVideosCollectionsIE,
                    TwitchClipsIE))
                else super(TwitchStreamIE, cls).suitable(url))


class TwitchClipsIE(TwitchBaseIE):
    _module = 'yt_dlp.extractor.twitch'
    IE_NAME = 'twitch:clips'
    _VALID_URL = '(?x)\n                    https?://\n                        (?:\n                            clips\\.twitch\\.tv/(?:embed\\?.*?\\bclip=|(?:[^/]+/)*)|\n                            (?:(?:www|go|m)\\.)?twitch\\.tv/[^/]+/clip/\n                        )\n                        (?P<id>[^/?#&]+)\n                    '
    _NETRC_MACHINE = 'twitch'


class TwitterCardIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.twitter'
    IE_NAME = 'twitter:card'
    _VALID_URL = 'https?://(?:(?:www|m(?:obile)?)\\.)?(?:twitter\\.com|twitter3e4tixl4xyajtrzo62zg5vztmjuricljdp2c5kshju4avyoid\\.onion)/i/(?:cards/tfw/v1|videos(?:/tweet)?)/(?P<id>\\d+)'


class TwitterBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.twitter'
    IE_NAME = 'TwitterBase'


class TwitterIE(TwitterBaseIE):
    _module = 'yt_dlp.extractor.twitter'
    IE_NAME = 'twitter'
    _VALID_URL = 'https?://(?:(?:www|m(?:obile)?)\\.)?(?:twitter\\.com|twitter3e4tixl4xyajtrzo62zg5vztmjuricljdp2c5kshju4avyoid\\.onion)/(?:(?:i/web|[^/]+)/status|statuses)/(?P<id>\\d+)'
    age_limit = 18


class TwitterAmplifyIE(TwitterBaseIE):
    _module = 'yt_dlp.extractor.twitter'
    IE_NAME = 'twitter:amplify'
    _VALID_URL = 'https?://amp\\.twimg\\.com/v/(?P<id>[0-9a-f\\-]{36})'


class TwitterBroadcastIE(TwitterBaseIE, PeriscopeBaseIE):
    _module = 'yt_dlp.extractor.twitter'
    IE_NAME = 'twitter:broadcast'
    _VALID_URL = 'https?://(?:(?:www|m(?:obile)?)\\.)?(?:twitter\\.com|twitter3e4tixl4xyajtrzo62zg5vztmjuricljdp2c5kshju4avyoid\\.onion)/i/broadcasts/(?P<id>[0-9a-zA-Z]{13})'


class TwitterSpacesIE(TwitterBaseIE):
    _module = 'yt_dlp.extractor.twitter'
    IE_NAME = 'twitter:spaces'
    _VALID_URL = 'https?://(?:(?:www|m(?:obile)?)\\.)?(?:twitter\\.com|twitter3e4tixl4xyajtrzo62zg5vztmjuricljdp2c5kshju4avyoid\\.onion)/i/spaces/(?P<id>[0-9a-zA-Z]{13})'


class TwitterShortenerIE(TwitterBaseIE):
    _module = 'yt_dlp.extractor.twitter'
    IE_NAME = 'twitter:shortener'
    _VALID_URL = 'https?://t.co/(?P<id>[^?]+)|tco:(?P<eid>[^?]+)'


class UdemyIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.udemy'
    IE_NAME = 'udemy'
    _VALID_URL = '(?x)\n                    https?://\n                        (?:[^/]+\\.)?udemy\\.com/\n                        (?:\n                            [^#]+\\#/lecture/|\n                            lecture/view/?\\?lectureId=|\n                            [^/]+/learn/v4/t/lecture/\n                        )\n                        (?P<id>\\d+)\n                    '
    _NETRC_MACHINE = 'udemy'


class UdemyCourseIE(UdemyIE):
    _module = 'yt_dlp.extractor.udemy'
    IE_NAME = 'udemy:course'
    _VALID_URL = 'https?://(?:[^/]+\\.)?udemy\\.com/(?P<id>[^/?#&]+)'
    _NETRC_MACHINE = 'udemy'

    @classmethod
    def suitable(cls, url):
        return False if UdemyIE.suitable(url) else super(UdemyCourseIE, cls).suitable(url)


class UDNEmbedIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.udn'
    IE_NAME = 'UDNEmbed'
    IE_DESC = '聯合影音'
    _VALID_URL = 'https?://video\\.udn\\.com/(?:embed|play)/news/(?P<id>\\d+)'


class ImgGamingBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.imggaming'
    IE_NAME = 'ImgGamingBase'


class UFCTVIE(ImgGamingBaseIE):
    _module = 'yt_dlp.extractor.ufctv'
    IE_NAME = 'UFCTV'
    _VALID_URL = 'https?://(?P<domain>(?:(?:app|www)\\.)?(?:ufc\\.tv|(?:ufc)?fightpass\\.com)|ufcfightpass\\.img(?:dge|gaming)\\.com)/(?P<type>live|playlist|video)/(?P<id>\\d+)(?:\\?.*?\\bplaylistId=(?P<playlist_id>\\d+))?'
    _NETRC_MACHINE = 'ufctv'


class UFCArabiaIE(ImgGamingBaseIE):
    _module = 'yt_dlp.extractor.ufctv'
    IE_NAME = 'UFCArabia'
    _VALID_URL = 'https?://(?P<domain>(?:(?:app|www)\\.)?ufcarabia\\.(?:ae|com))/(?P<type>live|playlist|video)/(?P<id>\\d+)(?:\\?.*?\\bplaylistId=(?P<playlist_id>\\d+))?'
    _NETRC_MACHINE = 'ufcarabia'


class UkColumnIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ukcolumn'
    IE_NAME = 'ukcolumn'
    _VALID_URL = '(?i)https?://(?:www\\.)?ukcolumn\\.org(/index\\.php)?/(?:video|ukcolumn-news)/(?P<id>[-a-z0-9]+)'


class UKTVPlayIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.uktvplay'
    IE_NAME = 'UKTVPlay'
    _VALID_URL = 'https?://uktvplay\\.(?:uktv\\.)?co\\.uk/(?:.+?\\?.*?\\bvideo=|([^/]+/)*)(?P<id>\\d+)'


class DigitekaIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.digiteka'
    IE_NAME = 'Digiteka'
    _VALID_URL = '(?x)\n        https?://(?:www\\.)?(?:digiteka\\.net|ultimedia\\.com)/\n        (?:\n            deliver/\n            (?P<embed_type>\n                generic|\n                musique\n            )\n            (?:/[^/]+)*/\n            (?:\n                src|\n                article\n            )|\n            default/index/video\n            (?P<site_type>\n                generic|\n                music\n            )\n            /id\n        )/(?P<id>[\\d+a-z]+)'


class DLiveVODIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.dlive'
    IE_NAME = 'dlive:vod'
    _VALID_URL = 'https?://(?:www\\.)?dlive\\.tv/p/(?P<uploader_id>.+?)\\+(?P<id>[^/?#&]+)'


class DLiveStreamIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.dlive'
    IE_NAME = 'dlive:stream'
    _VALID_URL = 'https?://(?:www\\.)?dlive\\.tv/(?!p/)(?P<id>[\\w.-]+)'


class DroobleIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.drooble'
    IE_NAME = 'Drooble'
    _VALID_URL = '(?x)https?://drooble\\.com/(?:\n        (?:(?P<user>[^/]+)/)?(?P<kind>song|videos|music/albums)/(?P<id>\\d+)|\n        (?P<user_2>[^/]+)/(?P<kind_2>videos|music))\n    '


class UMGDeIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.umg'
    IE_NAME = 'umg:de'
    IE_DESC = 'Universal Music Deutschland'
    _VALID_URL = 'https?://(?:www\\.)?universal-music\\.de/[^/]+/videos/[^/?#]+-(?P<id>\\d+)'


class UnistraIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.unistra'
    IE_NAME = 'Unistra'
    _VALID_URL = 'https?://utv\\.unistra\\.fr/(?:index|video)\\.php\\?id_video\\=(?P<id>\\d+)'


class UnityIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.unity'
    IE_NAME = 'Unity'
    _VALID_URL = 'https?://(?:www\\.)?unity3d\\.com/learn/tutorials/(?:[^/]+/)*(?P<id>[^/?#&]+)'


class UnscriptedNewsVideoIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.unscripted'
    IE_NAME = 'UnscriptedNewsVideo'
    _VALID_URL = 'https?://www\\.unscripted\\.news/videos/(?P<id>[\\w-]+)'


class UnsupportedInfoExtractor(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.unsupported'
    IE_NAME = 'UnsupportedInfoExtract'
    IE_DESC = False
    _VALID_URL = 'https?://(?:www\\.)?(?:)'


class KnownDRMIE(UnsupportedInfoExtractor):
    _module = 'yt_dlp.extractor.unsupported'
    IE_NAME = 'DRM'
    IE_DESC = False
    _VALID_URL = 'https?://(?:www\\.)?(?:play\\.hbomax\\.com|channel(?:4|5)\\.com|peacocktv\\.com|(?:[\\w\\.]+\\.)?disneyplus\\.com|open\\.spotify\\.com/(?:track|playlist|album|artist)|tvnz\\.co\\.nz|oneplus\\.ch|artstation\\.com/learning/courses|philo\\.com|(?:[\\w\\.]+\\.)?mech-plus\\.com|aha\\.video|mubi\\.com|vootkids\\.com)'


class KnownPiracyIE(UnsupportedInfoExtractor):
    _module = 'yt_dlp.extractor.unsupported'
    IE_NAME = 'Piracy'
    IE_DESC = False
    _VALID_URL = 'https?://(?:www\\.)?(?:dood\\.(?:to|watch|so|pm|wf|ru))'


class UOLIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.uol'
    IE_NAME = 'uol.com.br'
    _VALID_URL = 'https?://(?:.+?\\.)?uol\\.com\\.br/.*?(?:(?:mediaId|v)=|view/(?:[a-z0-9]+/)?|video(?:=|/(?:\\d{4}/\\d{2}/\\d{2}/)?))(?P<id>\\d+|[\\w-]+-[A-Z0-9]+)'


class UplynkIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.uplynk'
    IE_NAME = 'uplynk'
    _VALID_URL = 'https?://.*?\\.uplynk\\.com/(?P<path>ext/[0-9a-f]{32}/(?P<external_id>[^/?&]+)|(?P<id>[0-9a-f]{32}))\\.(?:m3u8|json)(?:.*?\\bpbs=(?P<session_id>[^&]+))?'


class UplynkPreplayIE(UplynkIE):
    _module = 'yt_dlp.extractor.uplynk'
    IE_NAME = 'uplynk:preplay'
    _VALID_URL = 'https?://.*?\\.uplynk\\.com/preplay2?/(?P<path>ext/[0-9a-f]{32}/(?P<external_id>[^/?&]+)|(?P<id>[0-9a-f]{32}))\\.json'


class UrortIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.urort'
    IE_NAME = 'Urort'
    IE_DESC = 'NRK P3 Urørt'
    _VALID_URL = 'https?://(?:www\\.)?urort\\.p3\\.no/#!/Band/(?P<id>[^/]+)$'


class URPlayIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.urplay'
    IE_NAME = 'URPlay'
    _VALID_URL = 'https?://(?:www\\.)?ur(?:play|skola)\\.se/(?:program|Produkter)/(?P<id>[0-9]+)'
    age_limit = 15


class USANetworkIE(NBCIE):
    _module = 'yt_dlp.extractor.usanetwork'
    IE_NAME = 'USANetwork'
    _VALID_URL = 'https?(?P<permalink>://(?:www\\.)?usanetwork\\.com/(?:[^/]+/videos?|movies?)/(?:[^/]+/)?(?P<id>\\d+))'


class USATodayIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.usatoday'
    IE_NAME = 'USAToday'
    _VALID_URL = 'https?://(?:www\\.)?usatoday\\.com/(?:[^/]+/)*(?P<id>[^?/#]+)'


class UstreamIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ustream'
    IE_NAME = 'ustream'
    _VALID_URL = 'https?://(?:www\\.)?(?:ustream\\.tv|video\\.ibm\\.com)/(?P<type>recorded|embed|embed/recorded)/(?P<id>\\d+)'


class UstreamChannelIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ustream'
    IE_NAME = 'ustream:channel'
    _VALID_URL = 'https?://(?:www\\.)?ustream\\.tv/channel/(?P<slug>.+)'


class UstudioIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ustudio'
    IE_NAME = 'ustudio'
    _VALID_URL = 'https?://(?:(?:www|v1)\\.)?ustudio\\.com/video/(?P<id>[^/]+)/(?P<display_id>[^/?#&]+)'


class UstudioEmbedIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ustudio'
    IE_NAME = 'ustudio:embed'
    _VALID_URL = 'https?://(?:(?:app|embed)\\.)?ustudio\\.com/embed/(?P<uid>[^/]+)/(?P<id>[^/]+)'


class UtreonIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.utreon'
    IE_NAME = 'Utreon'
    _VALID_URL = 'https?://(?:www\\.)?utreon.com/v/(?P<id>[a-zA-Z0-9_-]+)'


class Varzesh3IE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.varzesh3'
    IE_NAME = 'Varzesh3'
    _VALID_URL = 'https?://(?:www\\.)?video\\.varzesh3\\.com/(?:[^/]+/)+(?P<id>[^/]+)/?'


class Vbox7IE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.vbox7'
    IE_NAME = 'Vbox7'
    _VALID_URL = '(?x)\n                    https?://\n                        (?:[^/]+\\.)?vbox7\\.com/\n                        (?:\n                            play:|\n                            (?:\n                                emb/external\\.php|\n                                player/ext\\.swf\n                            )\\?.*?\\bvid=\n                        )\n                        (?P<id>[\\da-fA-F]+)\n                    '


class VeeHDIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.veehd'
    IE_NAME = 'VeeHD'
    _VALID_URL = 'https?://veehd\\.com/video/(?P<id>\\d+)'


class VeoIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.veo'
    IE_NAME = 'Veo'
    _VALID_URL = 'https?://app\\.veo\\.co/matches/(?P<id>[0-9A-Za-z-_]+)'


class VeohIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.veoh'
    IE_NAME = 'Veoh'
    _VALID_URL = 'https?://(?:www\\.)?veoh\\.com/(?:watch|videos|embed|iphone/#_Watch)/(?P<id>(?:v|e|yapi-)[\\da-zA-Z]+)'
    age_limit = 18


class VestiIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.vesti'
    IE_NAME = 'Vesti'
    IE_DESC = 'Вести.Ru'
    _VALID_URL = 'https?://(?:.+?\\.)?vesti\\.ru/(?P<id>.+)'


class VevoBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.vevo'
    IE_NAME = 'VevoBase'


class VevoIE(VevoBaseIE):
    _module = 'yt_dlp.extractor.vevo'
    IE_NAME = 'Vevo'
    _VALID_URL = '(?x)\n        (?:https?://(?:www\\.)?vevo\\.com/watch/(?!playlist|genre)(?:[^/]+/(?:[^/]+/)?)?|\n           https?://cache\\.vevo\\.com/m/html/embed\\.html\\?video=|\n           https?://videoplayer\\.vevo\\.com/embed/embedded\\?videoId=|\n           https?://embed\\.vevo\\.com/.*?[?&]isrc=|\n           https?://tv\\.vevo\\.com/watch/artist/(?:[^/]+)/|\n           vevo:)\n        (?P<id>[^&?#]+)'
    age_limit = 18


class VevoPlaylistIE(VevoBaseIE):
    _module = 'yt_dlp.extractor.vevo'
    IE_NAME = 'VevoPlaylist'
    _VALID_URL = 'https?://(?:www\\.)?vevo\\.com/watch/(?P<kind>playlist|genre)/(?P<id>[^/?#&]+)'


class BTArticleIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.vgtv'
    IE_NAME = 'bt:article'
    IE_DESC = 'Bergens Tidende Articles'
    _VALID_URL = 'https?://(?:www\\.)?bt\\.no/(?:[^/]+/)+(?P<id>[^/]+)-\\d+\\.html'


class BTVestlendingenIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.vgtv'
    IE_NAME = 'bt:vestlendingen'
    IE_DESC = 'Bergens Tidende - Vestlendingen'
    _VALID_URL = 'https?://(?:www\\.)?bt\\.no/spesial/vestlendingen/#!/(?P<id>\\d+)'


class VH1IE(MTVServicesInfoExtractor):
    _module = 'yt_dlp.extractor.vh1'
    IE_NAME = 'vh1.com'
    _VALID_URL = 'https?://(?:www\\.)?vh1\\.com/(?:video-clips|episodes)/(?P<id>[^/?#.]+)'


class ViceBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.vice'
    IE_NAME = 'ViceBase'


class ViceIE(ViceBaseIE, AdobePassIE):
    _module = 'yt_dlp.extractor.vice'
    IE_NAME = 'vice'
    _VALID_URL = 'https?://(?:(?:video|vms)\\.vice|(?:www\\.)?vice(?:land|tv))\\.com/(?P<locale>[^/]+)/(?:video/[^/]+|embed)/(?P<id>[\\da-f]{24})'
    age_limit = 14


class ViceArticleIE(ViceBaseIE):
    _module = 'yt_dlp.extractor.vice'
    IE_NAME = 'vice:article'
    _VALID_URL = 'https://(?:www\\.)?vice\\.com/(?P<locale>[^/]+)/article/(?:[0-9a-z]{6}/)?(?P<id>[^?#]+)'
    age_limit = 17


class ViceShowIE(ViceBaseIE):
    _module = 'yt_dlp.extractor.vice'
    IE_NAME = 'vice:show'
    _VALID_URL = 'https?://(?:video\\.vice|(?:www\\.)?vice(?:land|tv))\\.com/(?P<locale>[^/]+)/show/(?P<id>[^/?#&]+)'


class VidbitIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.vidbit'
    IE_NAME = 'Vidbit'
    _VALID_URL = 'https?://(?:www\\.)?vidbit\\.co/(?:watch|embed)\\?.*?\\bv=(?P<id>[\\da-zA-Z]+)'


class ViddlerIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.viddler'
    IE_NAME = 'Viddler'
    _VALID_URL = 'https?://(?:www\\.)?viddler\\.com/(?:v|embed|player)/(?P<id>[a-z0-9]+)(?:.+?\\bsecret=(\\d+))?'


class VideaIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.videa'
    IE_NAME = 'Videa'
    _VALID_URL = '(?x)\n                    https?://\n                        videa(?:kid)?\\.hu/\n                        (?:\n                            videok/(?:[^/]+/)*[^?#&]+-|\n                            (?:videojs_)?player\\?.*?\\bv=|\n                            player/v/\n                        )\n                        (?P<id>[^?#&]+)\n                    '


class VideocampusSachsenIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.videocampus_sachsen'
    IE_NAME = 'ViMP'
    _VALID_URL = '(?x)https?://(?P<host>bergauf\\.tv|campus\\.demo\\.vimp\\.com|corporate\\.demo\\.vimp\\.com|dancehalldatabase\\.com|drehzahl\\.tv|educhannel\\.hs\\-gesundheit\\.de|emedia\\.ls\\.haw\\-hamburg\\.de|globale\\-evolution\\.net|hohu\\.tv|htvideos\\.hightechhigh\\.org|k210039\\.vimp\\.mivitec\\.net|media\\.cmslegal\\.com|media\\.hs\\-furtwangen\\.de|media\\.hwr\\-berlin\\.de|mediathek\\.dkfz\\.de|mediathek\\.htw\\-berlin\\.de|mediathek\\.polizei\\-bw\\.de|medien\\.hs\\-merseburg\\.de|mportal\\.europa\\-uni\\.de|pacific\\.demo\\.vimp\\.com|slctv\\.com|streaming\\.prairiesouth\\.ca|tube\\.isbonline\\.cn|univideo\\.uni\\-kassel\\.de|ursula2\\.genetics\\.emory\\.edu|ursulablicklevideoarchiv\\.com|v\\.agrarumweltpaedagogik\\.at|video\\.eplay\\-tv\\.de|video\\.fh\\-dortmund\\.de|video\\.hs\\-offenburg\\.de|video\\.hs\\-pforzheim\\.de|video\\.hspv\\.nrw\\.de|video\\.irtshdf\\.fr|video\\.pareygo\\.de|video\\.tu\\-freiberg\\.de|videocampus\\.sachsen\\.de|videoportal\\.uni\\-freiburg\\.de|videoportal\\.vm\\.uni\\-freiburg\\.de|videos\\.duoc\\.cl|videos\\.uni\\-paderborn\\.de|vimp\\-bemus\\.udk\\-berlin\\.de|vimp\\.aekwl\\.de|vimp\\.hs\\-mittweida\\.de|vimp\\.oth\\-regensburg\\.de|vimp\\.ph\\-heidelberg\\.de|vimp\\.sma\\-events\\.com|vimp\\.weka\\-fachmedien\\.de|webtv\\.univ\\-montp3\\.fr|www\\.b\\-tu\\.de/media|www\\.bergauf\\.tv|www\\.bigcitytv\\.de|www\\.cad\\-videos\\.de|www\\.drehzahl\\.tv|www\\.fh\\-bielefeld\\.de/medienportal|www\\.hohu\\.tv|www\\.orvovideo\\.com|www\\.rwe\\.tv|www\\.salzi\\.tv|www\\.wenglor\\-media\\.com|www2\\.univ\\-sba\\.dz)/(?:\n        m/(?P<tmp_id>[0-9a-f]+)|\n        (?:category/)?video/(?P<display_id>[\\w-]+)/(?P<id>[0-9a-f]{32})|\n        media/embed.*(?:\\?|&)key=(?P<embed_id>[0-9a-f]{32}&?)\n    )'


class ViMPPlaylistIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.videocampus_sachsen'
    IE_NAME = 'ViMP:Playlist'
    _VALID_URL = '(?x)(?P<host>https?://(?:bergauf\\.tv|campus\\.demo\\.vimp\\.com|corporate\\.demo\\.vimp\\.com|dancehalldatabase\\.com|drehzahl\\.tv|educhannel\\.hs\\-gesundheit\\.de|emedia\\.ls\\.haw\\-hamburg\\.de|globale\\-evolution\\.net|hohu\\.tv|htvideos\\.hightechhigh\\.org|k210039\\.vimp\\.mivitec\\.net|media\\.cmslegal\\.com|media\\.hs\\-furtwangen\\.de|media\\.hwr\\-berlin\\.de|mediathek\\.dkfz\\.de|mediathek\\.htw\\-berlin\\.de|mediathek\\.polizei\\-bw\\.de|medien\\.hs\\-merseburg\\.de|mportal\\.europa\\-uni\\.de|pacific\\.demo\\.vimp\\.com|slctv\\.com|streaming\\.prairiesouth\\.ca|tube\\.isbonline\\.cn|univideo\\.uni\\-kassel\\.de|ursula2\\.genetics\\.emory\\.edu|ursulablicklevideoarchiv\\.com|v\\.agrarumweltpaedagogik\\.at|video\\.eplay\\-tv\\.de|video\\.fh\\-dortmund\\.de|video\\.hs\\-offenburg\\.de|video\\.hs\\-pforzheim\\.de|video\\.hspv\\.nrw\\.de|video\\.irtshdf\\.fr|video\\.pareygo\\.de|video\\.tu\\-freiberg\\.de|videocampus\\.sachsen\\.de|videoportal\\.uni\\-freiburg\\.de|videoportal\\.vm\\.uni\\-freiburg\\.de|videos\\.duoc\\.cl|videos\\.uni\\-paderborn\\.de|vimp\\-bemus\\.udk\\-berlin\\.de|vimp\\.aekwl\\.de|vimp\\.hs\\-mittweida\\.de|vimp\\.oth\\-regensburg\\.de|vimp\\.ph\\-heidelberg\\.de|vimp\\.sma\\-events\\.com|vimp\\.weka\\-fachmedien\\.de|webtv\\.univ\\-montp3\\.fr|www\\.b\\-tu\\.de/media|www\\.bergauf\\.tv|www\\.bigcitytv\\.de|www\\.cad\\-videos\\.de|www\\.drehzahl\\.tv|www\\.fh\\-bielefeld\\.de/medienportal|www\\.hohu\\.tv|www\\.orvovideo\\.com|www\\.rwe\\.tv|www\\.salzi\\.tv|www\\.wenglor\\-media\\.com|www2\\.univ\\-sba\\.dz))/(?:\n        album/view/aid/(?P<album_id>[0-9]+)|\n        (?P<mode>category|channel)/(?P<name>[\\w-]+)/(?P<id>[0-9]+)\n    )'


class VideoDetectiveIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.videodetective'
    IE_NAME = 'VideoDetective'
    _VALID_URL = 'https?://(?:www\\.)?videodetective\\.com/[^/]+/[^/]+/(?P<id>\\d+)'


class VideofyMeIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.videofyme'
    IE_NAME = 'videofy.me'
    _VALID_URL = 'https?://(?:www\\.videofy\\.me/.+?|p\\.videofy\\.me/v)/(?P<id>\\d+)(&|#|$)'


class VideomoreIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.videomore'
    IE_NAME = 'videomore'
    _VALID_URL = '(?x)\n                    videomore:(?P<sid>\\d+)$|\n                    https?://\n                        (?:\n                            videomore\\.ru/\n                            (?:\n                                embed|\n                                [^/]+/[^/]+\n                            )/|\n                            (?:\n                                (?:player\\.)?videomore\\.ru|\n                                siren\\.more\\.tv/player\n                            )/[^/]*\\?.*?\\btrack_id=|\n                            odysseus\\.more.tv/player/(?P<partner_id>\\d+)/\n                        )\n                        (?P<id>\\d+)\n                        (?:[/?#&]|\\.(?:xml|json)|$)\n                    '
    age_limit = 16


class VideomoreBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.videomore'
    IE_NAME = 'VideomoreBase'


class VideomoreVideoIE(VideomoreBaseIE):
    _module = 'yt_dlp.extractor.videomore'
    IE_NAME = 'videomore:video'
    _VALID_URL = 'https?://(?:videomore\\.ru|more\\.tv)/(?P<id>(?:(?:[^/]+/){2})?[^/?#&]+)(?:/*|[?#&].*?)$'
    age_limit = 16

    @classmethod
    def suitable(cls, url):
        return False if VideomoreIE.suitable(url) else super(VideomoreVideoIE, cls).suitable(url)


class VideomoreSeasonIE(VideomoreBaseIE):
    _module = 'yt_dlp.extractor.videomore'
    IE_NAME = 'videomore:season'
    _VALID_URL = 'https?://(?:videomore\\.ru|more\\.tv)/(?!embed)(?P<id>[^/]+/[^/?#&]+)(?:/*|[?#&].*?)$'

    @classmethod
    def suitable(cls, url):
        return (False if (VideomoreIE.suitable(url) or VideomoreVideoIE.suitable(url))
                else super(VideomoreSeasonIE, cls).suitable(url))


class VideoPressIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.videopress'
    IE_NAME = 'VideoPress'
    _VALID_URL = 'https?://video(?:\\.word)?press\\.com/embed/(?P<id>[\\da-zA-Z]{8})'


class VidioBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.vidio'
    IE_NAME = 'VidioBase'
    _NETRC_MACHINE = 'vidio'


class VidioIE(VidioBaseIE):
    _module = 'yt_dlp.extractor.vidio'
    IE_NAME = 'Vidio'
    _VALID_URL = 'https?://(?:www\\.)?vidio\\.com/(watch|embed)/(?P<id>\\d+)-(?P<display_id>[^/?#&]+)'
    _NETRC_MACHINE = 'vidio'


class VidioPremierIE(VidioBaseIE):
    _module = 'yt_dlp.extractor.vidio'
    IE_NAME = 'VidioPremier'
    _VALID_URL = 'https?://(?:www\\.)?vidio\\.com/premier/(?P<id>\\d+)/(?P<display_id>[^/?#&]+)'
    _NETRC_MACHINE = 'vidio'


class VidioLiveIE(VidioBaseIE):
    _module = 'yt_dlp.extractor.vidio'
    IE_NAME = 'VidioLive'
    _VALID_URL = 'https?://(?:www\\.)?vidio\\.com/live/(?P<id>\\d+)-(?P<display_id>[^/?#&]+)'
    _NETRC_MACHINE = 'vidio'


class VidLiiIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.vidlii'
    IE_NAME = 'VidLii'
    _VALID_URL = 'https?://(?:www\\.)?vidlii\\.com/(?:watch|embed)\\?.*?\\bv=(?P<id>[0-9A-Za-z_-]{11})'


class ViewLiftBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.viewlift'
    IE_NAME = 'ViewLiftBase'


class ViewLiftIE(ViewLiftBaseIE):
    _module = 'yt_dlp.extractor.viewlift'
    IE_NAME = 'viewlift'
    _VALID_URL = 'https?://(?:www\\.)?(?P<domain>(?:(?:main\\.)?snagfilms|snagxtreme|funnyforfree|kiddovid|winnersview|(?:monumental|lax)sportsnetwork|vayafilm|failarmy|ftfnext|lnppass\\.legapallacanestro|moviespree|app\\.myoutdoortv|neoufitness|pflmma|theidentitytb)\\.com|(?:hoichoi|app\\.horseandcountry|kronon|marquee|supercrosslive)\\.tv)(?P<path>(?:/(?:films/title|show|(?:news/)?videos?|watch))?/(?P<id>[^?#]+))'
    age_limit = 17

    @classmethod
    def suitable(cls, url):
        return False if ViewLiftEmbedIE.suitable(url) else super(ViewLiftIE, cls).suitable(url)


class ViewLiftEmbedIE(ViewLiftBaseIE):
    _module = 'yt_dlp.extractor.viewlift'
    IE_NAME = 'viewlift:embed'
    _VALID_URL = 'https?://(?:(?:www|embed)\\.)?(?P<domain>(?:(?:main\\.)?snagfilms|snagxtreme|funnyforfree|kiddovid|winnersview|(?:monumental|lax)sportsnetwork|vayafilm|failarmy|ftfnext|lnppass\\.legapallacanestro|moviespree|app\\.myoutdoortv|neoufitness|pflmma|theidentitytb)\\.com|(?:hoichoi|app\\.horseandcountry|kronon|marquee|supercrosslive)\\.tv)/embed/player\\?.*\\bfilmId=(?P<id>[\\da-f]{8}-(?:[\\da-f]{4}-){3}[\\da-f]{12})'


class ViideaIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.viidea'
    IE_NAME = 'Viidea'
    _VALID_URL = '(?x)https?://(?:www\\.)?(?:\n            videolectures\\.net|\n            flexilearn\\.viidea\\.net|\n            presentations\\.ocwconsortium\\.org|\n            video\\.travel-zoom\\.si|\n            video\\.pomp-forum\\.si|\n            tv\\.nil\\.si|\n            video\\.hekovnik.com|\n            video\\.szko\\.si|\n            kpk\\.viidea\\.com|\n            inside\\.viidea\\.net|\n            video\\.kiberpipa\\.org|\n            bvvideo\\.si|\n            kongres\\.viidea\\.net|\n            edemokracija\\.viidea\\.com\n        )(?:/lecture)?/(?P<id>[^/]+)(?:/video/(?P<part>\\d+))?/*(?:[#?].*)?$'


class VimeoBaseInfoExtractor(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.vimeo'
    IE_NAME = 'VimeoBaseInfoExtract'
    _NETRC_MACHINE = 'vimeo'


class VimeoIE(VimeoBaseInfoExtractor):
    _module = 'yt_dlp.extractor.vimeo'
    IE_NAME = 'vimeo'
    _VALID_URL = '(?x)\n                    https?://\n                        (?:\n                            (?:\n                                www|\n                                player\n                            )\n                            \\.\n                        )?\n                        vimeo(?:pro)?\\.com/\n                        (?!(?:channels|album|showcase)/[^/?#]+/?(?:$|[?#])|[^/]+/review/|ondemand/)\n                        (?:[^/]+/)*?\n                        (?:\n                            (?:\n                                play_redirect_hls|\n                                moogaloop\\.swf)\\?clip_id=\n                            )?\n                        (?:videos?/)?\n                        (?P<id>[0-9]+)\n                        (?:/(?P<unlisted_hash>[\\da-f]{10}))?\n                        /?(?:[?&].*)?(?:[#].*)?$\n                    '
    _NETRC_MACHINE = 'vimeo'


class VimeoAlbumIE(VimeoBaseInfoExtractor):
    _module = 'yt_dlp.extractor.vimeo'
    IE_NAME = 'vimeo:album'
    _VALID_URL = 'https://vimeo\\.com/(?:album|showcase)/(?P<id>\\d+)(?:$|[?#]|/(?!video))'
    _NETRC_MACHINE = 'vimeo'


class VimeoChannelIE(VimeoBaseInfoExtractor):
    _module = 'yt_dlp.extractor.vimeo'
    IE_NAME = 'vimeo:channel'
    _VALID_URL = 'https://vimeo\\.com/channels/(?P<id>[^/?#]+)/?(?:$|[?#])'
    _NETRC_MACHINE = 'vimeo'


class VimeoGroupsIE(VimeoChannelIE):
    _module = 'yt_dlp.extractor.vimeo'
    IE_NAME = 'vimeo:group'
    _VALID_URL = 'https://vimeo\\.com/groups/(?P<id>[^/]+)(?:/(?!videos?/\\d+)|$)'
    _NETRC_MACHINE = 'vimeo'


class VimeoLikesIE(VimeoChannelIE):
    _module = 'yt_dlp.extractor.vimeo'
    IE_NAME = 'vimeo:likes'
    IE_DESC = 'Vimeo user likes'
    _VALID_URL = 'https://(?:www\\.)?vimeo\\.com/(?P<id>[^/]+)/likes/?(?:$|[?#]|sort:)'
    _NETRC_MACHINE = 'vimeo'


class VimeoOndemandIE(VimeoIE):
    _module = 'yt_dlp.extractor.vimeo'
    IE_NAME = 'vimeo:ondemand'
    _VALID_URL = 'https?://(?:www\\.)?vimeo\\.com/ondemand/(?:[^/]+/)?(?P<id>[^/?#&]+)'
    _NETRC_MACHINE = 'vimeo'


class VimeoReviewIE(VimeoBaseInfoExtractor):
    _module = 'yt_dlp.extractor.vimeo'
    IE_NAME = 'vimeo:review'
    IE_DESC = 'Review pages on vimeo'
    _VALID_URL = '(?P<url>https://vimeo\\.com/[^/]+/review/(?P<id>[^/]+)/[0-9a-f]{10})'
    _NETRC_MACHINE = 'vimeo'


class VimeoUserIE(VimeoChannelIE):
    _module = 'yt_dlp.extractor.vimeo'
    IE_NAME = 'vimeo:user'
    _VALID_URL = 'https://vimeo\\.com/(?!(?:[0-9]+|watchlater)(?:$|[?#/]))(?P<id>[^/]+)(?:/videos)?/?(?:$|[?#])'
    _NETRC_MACHINE = 'vimeo'


class VimeoWatchLaterIE(VimeoChannelIE):
    _module = 'yt_dlp.extractor.vimeo'
    IE_NAME = 'vimeo:watchlater'
    IE_DESC = 'Vimeo watch later list, ":vimeowatchlater" keyword (requires authentication)'
    _VALID_URL = 'https://vimeo\\.com/(?:home/)?watchlater|:vimeowatchlater'
    _NETRC_MACHINE = 'vimeo'


class VHXEmbedIE(VimeoBaseInfoExtractor):
    _module = 'yt_dlp.extractor.vimeo'
    IE_NAME = 'vhx:embed'
    _VALID_URL = 'https?://embed\\.vhx\\.tv/videos/(?P<id>\\d+)'
    _NETRC_MACHINE = 'vimeo'


class VimmIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.vimm'
    IE_NAME = 'Vimm:stream'
    _VALID_URL = 'https?://(?:www\\.)?vimm\\.tv/(?:c/)?(?P<id>[0-9a-z-]+)$'


class VimmRecordingIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.vimm'
    IE_NAME = 'Vimm:recording'
    _VALID_URL = 'https?://(?:www\\.)?vimm\\.tv/c/(?P<channel_id>[0-9a-z-]+)\\?v=(?P<video_id>[0-9A-Za-z]+)'


class VimpleIE(SprutoBaseIE):
    _module = 'yt_dlp.extractor.vimple'
    IE_NAME = 'Vimple'
    IE_DESC = 'Vimple - one-click video hosting'
    _VALID_URL = 'https?://(?:player\\.vimple\\.(?:ru|co)/iframe|vimple\\.(?:ru|co))/(?P<id>[\\da-f-]{32,36})'


class VineIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.vine'
    IE_NAME = 'Vine'
    _VALID_URL = 'https?://(?:www\\.)?vine\\.co/(?:v|oembed)/(?P<id>\\w+)'


class VineUserIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.vine'
    IE_NAME = 'vine:user'
    _VALID_URL = 'https?://vine\\.co/(?P<u>u/)?(?P<user>[^/]+)'

    @classmethod
    def suitable(cls, url):
        return False if VineIE.suitable(url) else super(VineUserIE, cls).suitable(url)


class VikiBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.viki'
    IE_NAME = 'VikiBase'
    _NETRC_MACHINE = 'viki'


class VikiIE(VikiBaseIE):
    _module = 'yt_dlp.extractor.viki'
    IE_NAME = 'viki'
    _VALID_URL = 'https?://(?:www\\.)?viki\\.(?:com|net|mx|jp|fr)/(?:videos|player)/(?P<id>[0-9]+v)'
    _NETRC_MACHINE = 'viki'
    age_limit = 13


class VikiChannelIE(VikiBaseIE):
    _module = 'yt_dlp.extractor.viki'
    IE_NAME = 'viki:channel'
    _VALID_URL = 'https?://(?:www\\.)?viki\\.(?:com|net|mx|jp|fr)/(?:tv|news|movies|artists)/(?P<id>[0-9]+c)'
    _NETRC_MACHINE = 'viki'


class ViqeoIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.viqeo'
    IE_NAME = 'Viqeo'
    _VALID_URL = '(?x)\n                        (?:\n                            viqeo:|\n                            https?://cdn\\.viqeo\\.tv/embed/*\\?.*?\\bvid=|\n                            https?://api\\.viqeo\\.tv/v\\d+/data/startup?.*?\\bvideo(?:%5B%5D|\\[\\])=\n                        )\n                        (?P<id>[\\da-f]+)\n                    '


class ViuBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.viu'
    IE_NAME = 'ViuBase'


class ViuIE(ViuBaseIE):
    _module = 'yt_dlp.extractor.viu'
    IE_NAME = 'Viu'
    _VALID_URL = '(?:viu:|https?://[^/]+\\.viu\\.com/[a-z]{2}/media/)(?P<id>\\d+)'


class ViuPlaylistIE(ViuBaseIE):
    _module = 'yt_dlp.extractor.viu'
    IE_NAME = 'viu:playlist'
    _VALID_URL = 'https?://www\\.viu\\.com/[^/]+/listing/playlist-(?P<id>\\d+)'


class ViuOTTIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.viu'
    IE_NAME = 'viu:ott'
    _VALID_URL = 'https?://(?:www\\.)?viu\\.com/ott/(?P<country_code>[a-z]{2})/(?P<lang_code>[a-z]{2}-[a-z]{2})/vod/(?P<id>\\d+)'
    _NETRC_MACHINE = 'viu'


class VKBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.vk'
    IE_NAME = 'VKBase'
    _NETRC_MACHINE = 'vk'


class VKIE(VKBaseIE):
    _module = 'yt_dlp.extractor.vk'
    IE_NAME = 'vk'
    IE_DESC = 'VK'
    _VALID_URL = '(?x)\n                    https?://\n                        (?:\n                            (?:\n                                (?:(?:m|new)\\.)?vk\\.com/video_|\n                                (?:www\\.)?daxab.com/\n                            )\n                            ext\\.php\\?(?P<embed_query>.*?\\boid=(?P<oid>-?\\d+).*?\\bid=(?P<id>\\d+).*)|\n                            (?:\n                                (?:(?:m|new)\\.)?vk\\.com/(?:.+?\\?.*?z=)?(?:video|clip)|\n                                (?:www\\.)?daxab.com/embed/\n                            )\n                            (?P<videoid>-?\\d+_\\d+)(?:.*\\blist=(?P<list_id>([\\da-f]+)|(ln-[\\da-zA-Z]+)))?\n                        )\n                    '
    _NETRC_MACHINE = 'vk'


class VKUserVideosIE(VKBaseIE):
    _module = 'yt_dlp.extractor.vk'
    IE_NAME = 'vk:uservideos'
    IE_DESC = "VK - User's Videos"
    _VALID_URL = 'https?://(?:(?:m|new)\\.)?vk\\.com/video/(?:playlist/)?(?P<id>[^?$#/&]+)(?!\\?.*\\bz=video)(?:[/?#&](?:.*?\\bsection=(?P<section>\\w+))?|$)'
    _NETRC_MACHINE = 'vk'


class VKWallPostIE(VKBaseIE):
    _module = 'yt_dlp.extractor.vk'
    IE_NAME = 'vk:wallpost'
    _VALID_URL = 'https?://(?:(?:(?:(?:m|new)\\.)?vk\\.com/(?:[^?]+\\?.*\\bw=)?wall(?P<id>-?\\d+_\\d+)))'
    _NETRC_MACHINE = 'vk'


class VLiveBaseIE(NaverBaseIE):
    _module = 'yt_dlp.extractor.vlive'
    IE_NAME = 'VLiveBase'
    _NETRC_MACHINE = 'vlive'


class VLiveIE(VLiveBaseIE):
    _module = 'yt_dlp.extractor.vlive'
    IE_NAME = 'vlive'
    _VALID_URL = 'https?://(?:(?:www|m)\\.)?vlive\\.tv/(?:video|embed)/(?P<id>[0-9]+)'
    _NETRC_MACHINE = 'vlive'


class VLivePostIE(VLiveBaseIE):
    _module = 'yt_dlp.extractor.vlive'
    IE_NAME = 'vlive:post'
    _VALID_URL = 'https?://(?:(?:www|m)\\.)?vlive\\.tv/post/(?P<id>\\d-\\d+)'
    _NETRC_MACHINE = 'vlive'


class VLiveChannelIE(VLiveBaseIE):
    _module = 'yt_dlp.extractor.vlive'
    IE_NAME = 'vlive:channel'
    _VALID_URL = 'https?://(?:channels\\.vlive\\.tv|(?:(?:www|m)\\.)?vlive\\.tv/channel)/(?P<channel_id>[0-9A-Z]+)(?:/board/(?P<posts_id>\\d+))?'
    _NETRC_MACHINE = 'vlive'


class VodlockerIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.vodlocker'
    IE_NAME = 'Vodlocker'
    _VALID_URL = 'https?://(?:www\\.)?vodlocker\\.(?:com|city)/(?:embed-)?(?P<id>[0-9a-zA-Z]+)(?:\\..*?)?'


class VODPlIE(OnetBaseIE):
    _module = 'yt_dlp.extractor.vodpl'
    IE_NAME = 'VODPl'
    _VALID_URL = 'https?://vod\\.pl/(?:[^/]+/)+(?P<id>[0-9a-zA-Z]+)'


class VODPlatformIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.vodplatform'
    IE_NAME = 'VODPlatform'
    _VALID_URL = 'https?://(?:(?:www\\.)?vod-platform\\.net|embed\\.kwikmotion\\.com)/[eE]mbed/(?P<id>[^/?#]+)'


class VoiceRepublicIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.voicerepublic'
    IE_NAME = 'VoiceRepublic'
    _VALID_URL = 'https?://voicerepublic\\.com/(?:talks|embed)/(?P<id>[0-9a-z-]+)'


class VoicyBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.voicy'
    IE_NAME = 'VoicyBase'


class VoicyIE(VoicyBaseIE):
    _module = 'yt_dlp.extractor.voicy'
    IE_NAME = 'voicy'
    _VALID_URL = 'https?://voicy\\.jp/channel/(?P<channel_id>\\d+)/(?P<id>\\d+)'


class VoicyChannelIE(VoicyBaseIE):
    _module = 'yt_dlp.extractor.voicy'
    IE_NAME = 'voicy:channel'
    _VALID_URL = 'https?://voicy\\.jp/channel/(?P<id>\\d+)'

    @classmethod
    def suitable(cls, url):
        return not VoicyIE.suitable(url) and super().suitable(url)


class VootIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.voot'
    IE_NAME = 'Voot'
    _VALID_URL = '(?x)\n                    (?:\n                        voot:|\n                        https?://(?:www\\.)?voot\\.com/?\n                        (?:\n                            movies?/[^/]+/|\n                            (?:shows|kids)/(?:[^/]+/){4}\n                        )\n                     )\n                    (?P<id>\\d{3,})\n                    '


class VootSeriesIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.voot'
    IE_NAME = 'VootSeries'
    _VALID_URL = 'https?://(?:www\\.)?voot\\.com/shows/[^/]+/(?P<id>\\d{3,})'


class VoxMediaVolumeIE(OnceIE):
    _module = 'yt_dlp.extractor.voxmedia'
    IE_NAME = 'VoxMediaVolume'
    _VALID_URL = 'https?://volume\\.vox-cdn\\.com/embed/(?P<id>[0-9a-f]{9})'


class VoxMediaIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.voxmedia'
    IE_NAME = 'VoxMedia'
    _VALID_URL = 'https?://(?:www\\.)?(?:(?:theverge|vox|sbnation|eater|polygon|curbed|racked|funnyordie)\\.com|recode\\.net)/(?:[^/]+/)*(?P<id>[^/?]+)'


class VRTIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.vrt'
    IE_NAME = 'VRT'
    IE_DESC = 'VRT NWS, Flanders News, Flandern Info and Sporza'
    _VALID_URL = 'https?://(?:www\\.)?(?P<site>vrt\\.be/vrtnws|sporza\\.be)/[a-z]{2}/\\d{4}/\\d{2}/\\d{2}/(?P<id>[^/?&#]+)'


class VrakIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.vrak'
    IE_NAME = 'Vrak'
    _VALID_URL = 'https?://(?:www\\.)?vrak\\.tv/videos\\?.*?\\btarget=(?P<id>[\\d.]+)'
    age_limit = 8


class VRVBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.vrv'
    IE_NAME = 'VRVBase'


class VRVIE(VRVBaseIE):
    _module = 'yt_dlp.extractor.vrv'
    IE_NAME = 'vrv'
    _VALID_URL = 'https?://(?:www\\.)?vrv\\.co/watch/(?P<id>[A-Z0-9]+)'
    _NETRC_MACHINE = 'vrv'


class VRVSeriesIE(VRVBaseIE):
    _module = 'yt_dlp.extractor.vrv'
    IE_NAME = 'vrv:series'
    _VALID_URL = 'https?://(?:www\\.)?vrv\\.co/series/(?P<id>[A-Z0-9]+)'


class VShareIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.vshare'
    IE_NAME = 'VShare'
    _VALID_URL = 'https?://(?:www\\.)?vshare\\.io/[dv]/(?P<id>[^/?#&]+)'


class VTMIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.vtm'
    IE_NAME = 'VTM'
    _VALID_URL = 'https?://(?:www\\.)?vtm\\.be/([^/?&#]+)~v(?P<id>[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})'


class MedialaanIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.medialaan'
    IE_NAME = 'Medialaan'
    _VALID_URL = '(?x)\n                    https?://\n                        (?:\n                            (?:embed\\.)?mychannels.video/embed/|\n                            embed\\.mychannels\\.video/(?:s(?:dk|cript)/)?production/|\n                            (?:www\\.)?(?:\n                                (?:\n                                    7sur7|\n                                    demorgen|\n                                    hln|\n                                    joe|\n                                    qmusic\n                                )\\.be|\n                                (?:\n                                    [abe]d|\n                                    bndestem|\n                                    destentor|\n                                    gelderlander|\n                                    pzc|\n                                    tubantia|\n                                    volkskrant\n                                )\\.nl\n                            )/video/(?:[^/]+/)*[^/?&#]+~p\n                        )\n                        (?P<id>\\d+)\n                    '


class VuClipIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.vuclip'
    IE_NAME = 'VuClip'
    _VALID_URL = 'https?://(?:m\\.)?vuclip\\.com/w\\?.*?cid=(?P<id>[0-9]+)'


class VuploadIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.vupload'
    IE_NAME = 'Vupload'
    _VALID_URL = 'https://vupload\\.com/v/(?P<id>[a-z0-9]+)'


class VVVVIDIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.vvvvid'
    IE_NAME = 'VVVVID'
    _VALID_URL = 'https?://(?:www\\.)?vvvvid\\.it/(?:#!)?(?:show|anime|film|series)/(?P<show_id>\\d+)/[^/]+/(?P<season_id>\\d+)/(?P<id>[0-9]+)'


class VVVVIDShowIE(VVVVIDIE):
    _module = 'yt_dlp.extractor.vvvvid'
    IE_NAME = 'VVVVIDShow'
    _VALID_URL = '(?P<base_url>https?://(?:www\\.)?vvvvid\\.it/(?:#!)?(?:show|anime|film|series)/(?P<id>\\d+)(?:/(?P<show_title>[^/?&#]+))?)/?(?:[?#&]|$)'


class VyboryMosIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.vyborymos'
    IE_NAME = 'VyboryMos'
    _VALID_URL = 'https?://vybory\\.mos\\.ru/(?:#precinct/|account/channels\\?.*?\\bstation_id=)(?P<id>\\d+)'


class VzaarIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.vzaar'
    IE_NAME = 'Vzaar'
    _VALID_URL = 'https?://(?:(?:www|view)\\.)?vzaar\\.com/(?:videos/)?(?P<id>\\d+)'


class WakanimIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.wakanim'
    IE_NAME = 'Wakanim'
    _VALID_URL = 'https://(?:www\\.)?wakanim\\.tv/[^/]+/v2/catalogue/episode/(?P<id>\\d+)'


class WallaIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.walla'
    IE_NAME = 'Walla'
    _VALID_URL = 'https?://vod\\.walla\\.co\\.il/[^/]+/(?P<id>\\d+)/(?P<display_id>.+)'


class WashingtonPostIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.washingtonpost'
    IE_NAME = 'washingtonpost'
    _VALID_URL = '(?:washingtonpost:|https?://(?:www\\.)?washingtonpost\\.com/(?:video|posttv)/(?:[^/]+/)*)(?P<id>[\\da-f]{8}-[\\da-f]{4}-[\\da-f]{4}-[\\da-f]{4}-[\\da-f]{12})'


class WashingtonPostArticleIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.washingtonpost'
    IE_NAME = 'washingtonpost:article'
    _VALID_URL = 'https?://(?:www\\.)?washingtonpost\\.com/(?:[^/]+/)*(?P<id>[^/?#]+)'

    @classmethod
    def suitable(cls, url):
        return False if WashingtonPostIE.suitable(url) else super(WashingtonPostArticleIE, cls).suitable(url)


class WASDTVBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.wasdtv'
    IE_NAME = 'WASDTVBase'


class WASDTVStreamIE(WASDTVBaseIE):
    _module = 'yt_dlp.extractor.wasdtv'
    IE_NAME = 'wasdtv:stream'
    _VALID_URL = 'https?://wasd\\.tv/(?P<id>[^/#?]+)$'


class WASDTVRecordIE(WASDTVBaseIE):
    _module = 'yt_dlp.extractor.wasdtv'
    IE_NAME = 'wasdtv:record'
    _VALID_URL = 'https?://wasd\\.tv/[^/#?]+(?:/videos)?\\?record=(?P<id>\\d+)$'


class WASDTVClipIE(WASDTVBaseIE):
    _module = 'yt_dlp.extractor.wasdtv'
    IE_NAME = 'wasdtv:clip'
    _VALID_URL = 'https?://wasd\\.tv/[^/#?]+/clips\\?clip=(?P<id>\\d+)$'


class WatIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.wat'
    IE_NAME = 'wat.tv'
    _VALID_URL = '(?:wat:|https?://(?:www\\.)?wat\\.tv/video/.*-)(?P<id>[0-9a-z]+)'


class WatchBoxIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.watchbox'
    IE_NAME = 'WatchBox'
    _VALID_URL = 'https?://(?:www\\.)?watchbox\\.de/(?P<kind>serien|filme)/(?:[^/]+/)*[^/]+-(?P<id>\\d+)'
    age_limit = 16


class WatchIndianPornIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.watchindianporn'
    IE_NAME = 'WatchIndianPorn'
    IE_DESC = 'Watch Indian Porn'
    _VALID_URL = 'https?://(?:www\\.)?watchindianporn\\.net/(?:[^/]+/)*video/(?P<display_id>[^/]+)-(?P<id>[a-zA-Z0-9]+)\\.html'
    age_limit = 18


class WDRIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.wdr'
    IE_NAME = 'WDR'
    _VALID_URL = '(?x)https?://\n        (?:deviceids-medp\\.wdr\\.de/ondemand/\\d+/|\n           kinder\\.wdr\\.de/(?!mediathek/)[^#?]+-)\n        (?P<id>\\d+)\\.(?:js|assetjsonp)\n    '


class WDRPageIE(WDRIE):
    _module = 'yt_dlp.extractor.wdr'
    IE_NAME = 'WDRPage'
    _VALID_URL = 'https?://(?:www\\d?\\.)?(?:(?:kinder\\.)?wdr\\d?|sportschau)\\.de/(?:mediathek/)?(?:[^/]+/)*(?P<display_id>[^/]+)\\.html|https?://(?:www\\.)wdrmaus.de/(?:[^/]+/)*?(?P<maus_id>[^/?#.]+)(?:/?|/index\\.php5|\\.php5)$'


class WDRElefantIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.wdr'
    IE_NAME = 'WDRElefant'
    _VALID_URL = 'https?://(?:www\\.)wdrmaus\\.de/elefantenseite/#(?P<id>.+)'


class WDRMobileIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.wdr'
    IE_NAME = 'wdr:mobile'
    _VALID_URL = '(?x)\n        https?://mobile-ondemand\\.wdr\\.de/\n        .*?/fsk(?P<age_limit>[0-9]+)\n        /[0-9]+/[0-9]+/\n        (?P<id>[0-9]+)_(?P<title>[0-9]+)'
    _WORKING = False


class WebcasterIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.webcaster'
    IE_NAME = 'Webcaster'
    _VALID_URL = 'https?://bl\\.webcaster\\.pro/(?:quote|media)/start/free_(?P<id>[^/]+)'


class WebcasterFeedIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.webcaster'
    IE_NAME = 'WebcasterFeed'
    _VALID_URL = 'https?://bl\\.webcaster\\.pro/feed/start/free_(?P<id>[^/]+)'


class WebOfStoriesIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.webofstories'
    IE_NAME = 'WebOfStories'
    _VALID_URL = 'https?://(?:www\\.)?webofstories\\.com/play/(?:[^/]+/)?(?P<id>[0-9]+)'


class WebOfStoriesPlaylistIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.webofstories'
    IE_NAME = 'WebOfStoriesPlaylist'
    _VALID_URL = 'https?://(?:www\\.)?webofstories\\.com/playAll/(?P<id>[^/]+)'


class WeiboIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.weibo'
    IE_NAME = 'Weibo'
    _VALID_URL = 'https?://(?:www\\.)?weibo\\.com/[0-9]+/(?P<id>[a-zA-Z0-9]+)'


class WeiboMobileIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.weibo'
    IE_NAME = 'WeiboMobile'
    _VALID_URL = 'https?://m\\.weibo\\.cn/status/(?P<id>[0-9]+)(\\?.+)?'


class WeiqiTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.weiqitv'
    IE_NAME = 'WeiqiTV'
    IE_DESC = 'WQTV'
    _VALID_URL = 'https?://(?:www\\.)?weiqitv\\.com/index/video_play\\?videoId=(?P<id>[A-Za-z0-9]+)'


class WikimediaIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.wikimedia'
    IE_NAME = 'wikimedia.org'
    _VALID_URL = 'https?://commons\\.wikimedia\\.org/wiki/File:(?P<id>[^/#?]+)\\.\\w+'


class WillowIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.willow'
    IE_NAME = 'Willow'
    _VALID_URL = 'https?://(www\\.)?willow\\.tv/videos/(?P<id>[0-9a-z-_]+)'


class WimTVIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.wimtv'
    IE_NAME = 'WimTV'
    _VALID_URL = '(?x:\n        https?://platform.wim.tv/\n        (?:\n            (?:embed/)?\\?\n            |\\#/webtv/.+?/\n        )\n        (?P<type>vod|live|cast)[=/]\n        (?P<id>[\\da-f]{8}-[\\da-f]{4}-[\\da-f]{4}-[\\da-f]{4}-[\\da-f]{12}).*?)'


class WhoWatchIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.whowatch'
    IE_NAME = 'whowatch'
    _VALID_URL = 'https?://whowatch\\.tv/viewer/(?P<id>\\d+)'


class WistiaBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.wistia'
    IE_NAME = 'WistiaBase'


class WistiaIE(WistiaBaseIE):
    _module = 'yt_dlp.extractor.wistia'
    IE_NAME = 'Wistia'
    _VALID_URL = '(?:wistia:|https?://(?:\\w+\\.)?wistia\\.(?:net|com)/(?:embed/)?(?:iframe|medias)/)(?P<id>[a-z0-9]{10})'


class WistiaPlaylistIE(WistiaBaseIE):
    _module = 'yt_dlp.extractor.wistia'
    IE_NAME = 'WistiaPlaylist'
    _VALID_URL = 'https?://(?:\\w+\\.)?wistia\\.(?:net|com)/(?:embed/)?playlists/(?P<id>[a-z0-9]{10})'


class WistiaChannelIE(WistiaBaseIE):
    _module = 'yt_dlp.extractor.wistia'
    IE_NAME = 'WistiaChannel'
    _VALID_URL = '(?:wistiachannel:|https?://(?:\\w+\\.)?wistia\\.(?:net|com)/(?:embed/)?channel/)(?P<id>[a-z0-9]{10})'


class WordpressPlaylistEmbedIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.wordpress'
    IE_NAME = 'wordpress:playlist'
    _VALID_URL = False


class WordpressMiniAudioPlayerEmbedIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.wordpress'
    IE_NAME = 'wordpress:mb.miniAudioPlayer'
    _VALID_URL = False


class WorldStarHipHopIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.worldstarhiphop'
    IE_NAME = 'WorldStarHipHop'
    _VALID_URL = 'https?://(?:www|m)\\.worldstar(?:candy|hiphop)\\.com/(?:videos|android)/video\\.php\\?.*?\\bv=(?P<id>[^&]+)'


class WPPilotBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.wppilot'
    IE_NAME = 'WPPilotBase'


class WPPilotIE(WPPilotBaseIE):
    _module = 'yt_dlp.extractor.wppilot'
    IE_NAME = 'wppilot'
    _VALID_URL = '(?:https?://pilot\\.wp\\.pl/tv/?#|wppilot:)(?P<id>[a-z\\d-]+)'


class WPPilotChannelsIE(WPPilotBaseIE):
    _module = 'yt_dlp.extractor.wppilot'
    IE_NAME = 'wppilot:channels'
    _VALID_URL = '(?:https?://pilot\\.wp\\.pl/(?:tv/?)?(?:\\?[^#]*)?#?|wppilot:)$'


class WSJIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.wsj'
    IE_NAME = 'WSJ'
    IE_DESC = 'Wall Street Journal'
    _VALID_URL = '(?x)\n                        (?:\n                            https?://video-api\\.wsj\\.com/api-video/player/iframe\\.html\\?.*?\\bguid=|\n                            https?://(?:www\\.)?(?:wsj|barrons)\\.com/video/(?:[^/]+/)+|\n                            wsj:\n                        )\n                        (?P<id>[a-fA-F0-9-]{36})\n                    '


class WSJArticleIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.wsj'
    IE_NAME = 'WSJArticle'
    _VALID_URL = '(?i)https?://(?:www\\.)?wsj\\.com/articles/(?P<id>[^/?#&]+)'


class WWEBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.wwe'
    IE_NAME = 'WWEBase'


class WWEIE(WWEBaseIE):
    _module = 'yt_dlp.extractor.wwe'
    IE_NAME = 'WWE'
    _VALID_URL = 'https?://(?:[^/]+\\.)?wwe\\.com/(?:[^/]+/)*videos/(?P<id>[^/?#&]+)'


class XBefIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.xbef'
    IE_NAME = 'XBef'
    _VALID_URL = 'https?://(?:www\\.)?xbef\\.com/video/(?P<id>[0-9]+)'
    age_limit = 18


class XboxClipsIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.xboxclips'
    IE_NAME = 'XboxClips'
    _VALID_URL = 'https?://(?:www\\.)?(?:xboxclips\\.com|gameclips\\.io)/(?:video\\.php\\?.*vid=|[^/]+/)(?P<id>[\\da-f]{8}-(?:[\\da-f]{4}-){3}[\\da-f]{12})'


class XFileShareIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.xfileshare'
    IE_NAME = 'XFileShare'
    IE_DESC = 'XFileShare based sites: Aparat, ClipWatching, GoUnlimited, GoVid, HolaVid, Streamty, TheVideoBee, Uqload, VidBom, vidlo, VidLocker, VidShare, VUp, WolfStream, XVideoSharing'
    _VALID_URL = 'https?://(?:www\\.)?(?P<host>aparat\\.cam|clipwatching\\.com|gounlimited\\.to|govid\\.me|holavid\\.com|streamty\\.com|thevideobee\\.to|uqload\\.com|vidbom\\.com|vidlo\\.us|vidlocker\\.xyz|vidshare\\.tv|vup\\.to|wolfstream\\.tv|xvideosharing\\.com)/(?:embed-)?(?P<id>[0-9a-zA-Z]+)'


class XHamsterIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.xhamster'
    IE_NAME = 'XHamster'
    _VALID_URL = '(?x)\n                    https?://\n                        (?:.+?\\.)?(?:xhamster\\.(?:com|one|desi)|xhms\\.pro|xhamster\\d+\\.com|xhday\\.com)/\n                        (?:\n                            movies/(?P<id>[\\dA-Za-z]+)/(?P<display_id>[^/]*)\\.html|\n                            videos/(?P<display_id_2>[^/]*)-(?P<id_2>[\\dA-Za-z]+)\n                        )\n                    '
    age_limit = 18


class XHamsterEmbedIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.xhamster'
    IE_NAME = 'XHamsterEmbed'
    _VALID_URL = 'https?://(?:.+?\\.)?(?:xhamster\\.(?:com|one|desi)|xhms\\.pro|xhamster\\d+\\.com|xhday\\.com)/xembed\\.php\\?video=(?P<id>\\d+)'
    age_limit = 18


class XHamsterUserIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.xhamster'
    IE_NAME = 'XHamsterUser'
    _VALID_URL = 'https?://(?:.+?\\.)?(?:xhamster\\.(?:com|one|desi)|xhms\\.pro|xhamster\\d+\\.com|xhday\\.com)/users/(?P<id>[^/?#&]+)'


class XiamiBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.xiami'
    IE_NAME = 'XiamiBase'


class XiamiSongIE(XiamiBaseIE):
    _module = 'yt_dlp.extractor.xiami'
    IE_NAME = 'xiami:song'
    IE_DESC = '虾米音乐'
    _VALID_URL = 'https?://(?:www\\.)?xiami\\.com/song/(?P<id>[^/?#&]+)'


class XiamiPlaylistBaseIE(XiamiBaseIE):
    _module = 'yt_dlp.extractor.xiami'
    IE_NAME = 'XiamiPlaylistBase'


class XiamiAlbumIE(XiamiPlaylistBaseIE):
    _module = 'yt_dlp.extractor.xiami'
    IE_NAME = 'xiami:album'
    IE_DESC = '虾米音乐 - 专辑'
    _VALID_URL = 'https?://(?:www\\.)?xiami\\.com/album/(?P<id>[^/?#&]+)'


class XiamiArtistIE(XiamiPlaylistBaseIE):
    _module = 'yt_dlp.extractor.xiami'
    IE_NAME = 'xiami:artist'
    IE_DESC = '虾米音乐 - 歌手'
    _VALID_URL = 'https?://(?:www\\.)?xiami\\.com/artist/(?P<id>[^/?#&]+)'


class XiamiCollectionIE(XiamiPlaylistBaseIE):
    _module = 'yt_dlp.extractor.xiami'
    IE_NAME = 'xiami:collection'
    IE_DESC = '虾米音乐 - 精选集'
    _VALID_URL = 'https?://(?:www\\.)?xiami\\.com/collect/(?P<id>[^/?#&]+)'


class XimalayaBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ximalaya'
    IE_NAME = 'XimalayaBase'


class XimalayaIE(XimalayaBaseIE):
    _module = 'yt_dlp.extractor.ximalaya'
    IE_NAME = 'ximalaya'
    IE_DESC = '喜马拉雅FM'
    _VALID_URL = 'https?://(?:www\\.|m\\.)?ximalaya\\.com/(:?(?P<uid>\\d+)/)?sound/(?P<id>[0-9]+)'


class XimalayaAlbumIE(XimalayaBaseIE):
    _module = 'yt_dlp.extractor.ximalaya'
    IE_NAME = 'ximalaya:album'
    IE_DESC = '喜马拉雅FM 专辑'
    _VALID_URL = 'https?://(?:www\\.|m\\.)?ximalaya\\.com/\\d+/album/(?P<id>[0-9]+)'


class XinpianchangIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.xinpianchang'
    IE_NAME = 'xinpianchang'
    IE_DESC = 'xinpianchang.com'
    _VALID_URL = 'https?://www\\.xinpianchang\\.com/(?P<id>[^/]+?)(?:\\D|$)'


class XMinusIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.xminus'
    IE_NAME = 'XMinus'
    _VALID_URL = 'https?://(?:www\\.)?x-minus\\.org/track/(?P<id>[0-9]+)'


class XNXXIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.xnxx'
    IE_NAME = 'XNXX'
    _VALID_URL = 'https?://(?:video|www)\\.xnxx3?\\.com/video-?(?P<id>[0-9a-z]+)/'
    age_limit = 18


class XstreamIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.xstream'
    IE_NAME = 'Xstream'
    _VALID_URL = '(?x)\n                    (?:\n                        xstream:|\n                        https?://frontend\\.xstream\\.(?:dk|net)/\n                    )\n                    (?P<partner_id>[^/]+)\n                    (?:\n                        :|\n                        /feed/video/\\?.*?\\bid=\n                    )\n                    (?P<id>\\d+)\n                    '


class VGTVIE(XstreamIE):
    _module = 'yt_dlp.extractor.vgtv'
    IE_NAME = 'VGTV'
    IE_DESC = 'VGTV, BTTV, FTV, Aftenposten and Aftonbladet'
    _VALID_URL = '(?x)\n                    (?:https?://(?:www\\.)?\n                    (?P<host>\n                        tv.vg.no|vgtv.no|bt.no/tv|aftenbladet.no/tv|fvn.no/fvntv|aftenposten.no/webtv|ap.vgtv.no/webtv|tv.aftonbladet.se|tv.aftonbladet.se/abtv|www.aftonbladet.se/tv\n                    )\n                    /?\n                    (?:\n                        (?:\\#!/)?(?:video|live)/|\n                        embed?.*id=|\n                        a(?:rticles)?/\n                    )|\n                    (?P<appname>\n                        vgtv|bttv|satv|fvntv|aptv|abtv\n                    ):)\n                    (?P<id>\\d+)\n                    '


class XTubeUserIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.xtube'
    IE_NAME = 'XTubeUser'
    IE_DESC = 'XTube user profile'
    _VALID_URL = 'https?://(?:www\\.)?xtube\\.com/profile/(?P<id>[^/]+-\\d+)'
    age_limit = 18


class XTubeIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.xtube'
    IE_NAME = 'XTube'
    _VALID_URL = '(?x)\n                        (?:\n                            xtube:|\n                            https?://(?:www\\.)?xtube\\.com/(?:watch\\.php\\?.*\\bv=|video-watch/(?:embedded/)?(?P<display_id>[^/]+)-)\n                        )\n                        (?P<id>[^/?&#]+)\n                    '
    age_limit = 18


class XuiteIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.xuite'
    IE_NAME = 'Xuite'
    IE_DESC = '隨意窩Xuite影音'
    _VALID_URL = 'https?://vlog\\.xuite\\.net/(?:play|embed)/(?P<id>(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?)'


class XVideosIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.xvideos'
    IE_NAME = 'XVideos'
    _VALID_URL = '(?x)\n                    https?://\n                        (?:\n                            (?:[^/]+\\.)?xvideos2?\\.com/video|\n                            (?:www\\.)?xvideos\\.es/video|\n                            (?:www|flashservice)\\.xvideos\\.com/embedframe/|\n                            static-hw\\.xvideos\\.com/swf/xv-player\\.swf\\?.*?\\bid_video=\n                        )\n                        (?P<id>[0-9]+)\n                    '
    age_limit = 18


class XXXYMoviesIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.xxxymovies'
    IE_NAME = 'XXXYMovies'
    _VALID_URL = 'https?://(?:www\\.)?xxxymovies\\.com/videos/(?P<id>\\d+)/(?P<display_id>[^/]+)'
    age_limit = 18


class YahooIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.yahoo'
    IE_NAME = 'Yahoo'
    IE_DESC = 'Yahoo screen and movies'
    _VALID_URL = '(?P<url>https?://(?:(?P<country>[a-zA-Z]{2}(?:-[a-zA-Z]{2})?|malaysia)\\.)?(?:[\\da-zA-Z_-]+\\.)?yahoo\\.com/(?:[^/]+/)*(?P<id>[^?&#]*-[0-9]+(?:-[a-z]+)?)\\.html)'


class AolIE(YahooIE):
    _module = 'yt_dlp.extractor.aol'
    IE_NAME = 'aol.com'
    IE_DESC = 'Yahoo screen and movies'
    _VALID_URL = '(?:aol-video:|https?://(?:www\\.)?aol\\.(?:com|ca|co\\.uk|de|jp)/video/(?:[^/]+/)*)(?P<id>\\d{9}|[0-9a-f]{24}|[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12})'


class YahooSearchIE(LazyLoadSearchExtractor):
    _module = 'yt_dlp.extractor.yahoo'
    IE_NAME = 'screen.yahoo:search'
    IE_DESC = 'Yahoo screen search'
    SEARCH_KEY = 'yvsearch'
    _VALID_URL = 'yvsearch(?P<prefix>|[1-9][0-9]*|all):(?P<query>[\\s\\S]+)'


class YahooGyaOPlayerIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.yahoo'
    IE_NAME = 'yahoo:gyao:player'
    _VALID_URL = 'https?://(?:gyao\\.yahoo\\.co\\.jp/(?:player|episode(?:/[^/]+)?)|streaming\\.yahoo\\.co\\.jp/c/y)/(?P<id>\\d+/v\\d+/v\\d+|[\\da-f]{8}-[\\da-f]{4}-[\\da-f]{4}-[\\da-f]{4}-[\\da-f]{12})'


class YahooGyaOIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.yahoo'
    IE_NAME = 'yahoo:gyao'
    _VALID_URL = 'https?://(?:gyao\\.yahoo\\.co\\.jp/(?:p|title(?:/[^/]+)?)|streaming\\.yahoo\\.co\\.jp/p/y)/(?P<id>\\d+/v\\d+|[\\da-f]{8}-[\\da-f]{4}-[\\da-f]{4}-[\\da-f]{4}-[\\da-f]{12})'


class YahooJapanNewsIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.yahoo'
    IE_NAME = 'yahoo:japannews'
    IE_DESC = 'Yahoo! Japan News'
    _VALID_URL = 'https?://news\\.yahoo\\.co\\.jp/(?:articles|feature)/(?P<id>[a-zA-Z0-9]+)'


class YandexDiskIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.yandexdisk'
    IE_NAME = 'YandexDisk'
    _VALID_URL = '(?x)https?://\n        (?P<domain>\n            yadi\\.sk|\n            disk\\.yandex\\.\n                (?:\n                    az|\n                    by|\n                    co(?:m(?:\\.(?:am|ge|tr))?|\\.il)|\n                    ee|\n                    fr|\n                    k[gz]|\n                    l[tv]|\n                    md|\n                    t[jm]|\n                    u[az]|\n                    ru\n                )\n        )/(?:[di]/|public.*?\\bhash=)(?P<id>[^/?#&]+)'


class YandexMusicBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.yandexmusic'
    IE_NAME = 'YandexMusicBase'


class YandexMusicTrackIE(YandexMusicBaseIE):
    _module = 'yt_dlp.extractor.yandexmusic'
    IE_NAME = 'yandexmusic:track'
    IE_DESC = 'Яндекс.Музыка - Трек'
    _VALID_URL = 'https?://music\\.yandex\\.(?P<tld>ru|kz|ua|by|com)/album/(?P<album_id>\\d+)/track/(?P<id>\\d+)'


class YandexMusicPlaylistBaseIE(YandexMusicBaseIE):
    _module = 'yt_dlp.extractor.yandexmusic'
    IE_NAME = 'YandexMusicPlaylistBase'


class YandexMusicAlbumIE(YandexMusicPlaylistBaseIE):
    _module = 'yt_dlp.extractor.yandexmusic'
    IE_NAME = 'yandexmusic:album'
    IE_DESC = 'Яндекс.Музыка - Альбом'
    _VALID_URL = 'https?://music\\.yandex\\.(?P<tld>ru|kz|ua|by|com)/album/(?P<id>\\d+)'

    @classmethod
    def suitable(cls, url):
        return False if YandexMusicTrackIE.suitable(url) else super(YandexMusicAlbumIE, cls).suitable(url)


class YandexMusicPlaylistIE(YandexMusicPlaylistBaseIE):
    _module = 'yt_dlp.extractor.yandexmusic'
    IE_NAME = 'yandexmusic:playlist'
    IE_DESC = 'Яндекс.Музыка - Плейлист'
    _VALID_URL = 'https?://music\\.yandex\\.(?P<tld>ru|kz|ua|by|com)/users/(?P<user>[^/]+)/playlists/(?P<id>\\d+)'


class YandexMusicArtistBaseIE(YandexMusicPlaylistBaseIE):
    _module = 'yt_dlp.extractor.yandexmusic'
    IE_NAME = 'YandexMusicArtistBase'


class YandexMusicArtistTracksIE(YandexMusicArtistBaseIE):
    _module = 'yt_dlp.extractor.yandexmusic'
    IE_NAME = 'yandexmusic:artist:tracks'
    IE_DESC = 'Яндекс.Музыка - Артист - Треки'
    _VALID_URL = 'https?://music\\.yandex\\.(?P<tld>ru|kz|ua|by|com)/artist/(?P<id>\\d+)/tracks'


class YandexMusicArtistAlbumsIE(YandexMusicArtistBaseIE):
    _module = 'yt_dlp.extractor.yandexmusic'
    IE_NAME = 'yandexmusic:artist:albums'
    IE_DESC = 'Яндекс.Музыка - Артист - Альбомы'
    _VALID_URL = 'https?://music\\.yandex\\.(?P<tld>ru|kz|ua|by|com)/artist/(?P<id>\\d+)/albums'


class YandexVideoIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.yandexvideo'
    IE_NAME = 'YandexVideo'
    _VALID_URL = '(?x)\n                    https?://\n                        (?:\n                            yandex\\.ru(?:/(?:portal/(?:video|efir)|efir))?/?\\?.*?stream_id=|\n                            frontend\\.vh\\.yandex\\.ru/player/\n                        )\n                        (?P<id>(?:[\\da-f]{32}|[\\w-]{12}))\n                    '
    age_limit = 18


class YandexVideoPreviewIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.yandexvideo'
    IE_NAME = 'YandexVideoPreview'
    _VALID_URL = 'https?://(?:www\\.)?yandex\\.\\w{2,3}(?:\\.(?:am|ge|il|tr))?/video/preview(?:/?\\?.*?filmId=|/)(?P<id>\\d+)'


class ZenYandexIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.yandexvideo'
    IE_NAME = 'ZenYandex'
    _VALID_URL = 'https?://(zen\\.yandex|dzen)\\.ru(?:/video)?/(media|watch)/(?:(?:id/[^/]+/|[^/]+/)(?:[a-z0-9-]+)-)?(?P<id>[a-z0-9-]+)'


class ZenYandexChannelIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.yandexvideo'
    IE_NAME = 'ZenYandexChannel'
    _VALID_URL = 'https?://(zen\\.yandex|dzen)\\.ru/(?!media|video)(?:id/)?(?P<id>[a-z0-9-_]+)'


class YapFilesIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.yapfiles'
    IE_NAME = 'YapFiles'
    _VALID_URL = 'https?://(?:(?:www|api)\\.)?yapfiles\\.ru/get_player/*\\?.*?\\bv=(?P<id>\\w+)'


class YesJapanIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.yesjapan'
    IE_NAME = 'YesJapan'
    _VALID_URL = 'https?://(?:www\\.)?yesjapan\\.com/video/(?P<slug>[A-Za-z0-9\\-]*)_(?P<id>[A-Za-z0-9]+)\\.html'


class YinYueTaiIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.yinyuetai'
    IE_NAME = 'yinyuetai:video'
    IE_DESC = '音悦Tai'
    _VALID_URL = 'https?://v\\.yinyuetai\\.com/video(?:/h5)?/(?P<id>[0-9]+)'


class YleAreenaIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.yle_areena'
    IE_NAME = 'YleAreena'
    _VALID_URL = 'https?://areena\\.yle\\.fi/(?P<id>[\\d-]+)'
    age_limit = 7


class YnetIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.ynet'
    IE_NAME = 'Ynet'
    _VALID_URL = 'https?://(?:.+?\\.)?ynet\\.co\\.il/(?:.+?/)?0,7340,(?P<id>L(?:-[0-9]+)+),00\\.html'


class YouJizzIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.youjizz'
    IE_NAME = 'YouJizz'
    _VALID_URL = 'https?://(?:\\w+\\.)?youjizz\\.com/videos/(?:[^/#?]*-(?P<id>\\d+)\\.html|embed/(?P<embed_id>\\d+))'
    age_limit = 18


class YoukuIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.youku'
    IE_NAME = 'youku'
    IE_DESC = '优酷'
    _VALID_URL = '(?x)\n        (?:\n            https?://(\n                (?:v|player)\\.youku\\.com/(?:v_show/id_|player\\.php/sid/)|\n                video\\.tudou\\.com/v/)|\n            youku:)\n        (?P<id>[A-Za-z0-9]+)(?:\\.html|/v\\.swf|)\n    '


class YoukuShowIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.youku'
    IE_NAME = 'youku:show'
    _VALID_URL = 'https?://list\\.youku\\.com/show/id_(?P<id>[0-9a-z]+)\\.html'


class YouNowLiveIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.younow'
    IE_NAME = 'YouNowLive'
    _VALID_URL = 'https?://(?:www\\.)?younow\\.com/(?P<id>[^/?#&]+)'

    @classmethod
    def suitable(cls, url):
        return (False
                if YouNowChannelIE.suitable(url) or YouNowMomentIE.suitable(url)
                else super(YouNowLiveIE, cls).suitable(url))


class YouNowChannelIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.younow'
    IE_NAME = 'YouNowChannel'
    _VALID_URL = 'https?://(?:www\\.)?younow\\.com/(?P<id>[^/]+)/channel'


class YouNowMomentIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.younow'
    IE_NAME = 'YouNowMoment'
    _VALID_URL = 'https?://(?:www\\.)?younow\\.com/[^/]+/(?P<id>[^/?#&]+)'

    @classmethod
    def suitable(cls, url):
        return (False
                if YouNowChannelIE.suitable(url)
                else super(YouNowMomentIE, cls).suitable(url))


class YouPornIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.youporn'
    IE_NAME = 'YouPorn'
    _VALID_URL = 'https?://(?:www\\.)?youporn\\.com/(?:watch|embed)/(?P<id>\\d+)(?:/(?P<display_id>[^/?#&]+))?'
    age_limit = 18


class YourPornIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.yourporn'
    IE_NAME = 'YourPorn'
    _VALID_URL = 'https?://(?:www\\.)?sxyprn\\.com/post/(?P<id>[^/?#&.]+)'
    age_limit = 18


class YourUploadIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.yourupload'
    IE_NAME = 'YourUpload'
    _VALID_URL = 'https?://(?:www\\.)?(?:yourupload\\.com/(?:watch|embed)|embed\\.yourupload\\.com)/(?P<id>[A-Za-z0-9]+)'


class ZapiksIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.zapiks'
    IE_NAME = 'Zapiks'
    _VALID_URL = 'https?://(?:www\\.)?zapiks\\.(?:fr|com)/(?:(?:[a-z]{2}/)?(?P<display_id>.+?)\\.html|index\\.php\\?.*\\bmedia_id=(?P<id>\\d+))'


class ZattooPlatformBaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'ZattooPlatformBase'


class BBVTVBaseIE(ZattooPlatformBaseIE):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'BBVTVBase'
    _NETRC_MACHINE = 'bbvtv'


class BBVTVIE(BBVTVBaseIE):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'BBVTV'
    _VALID_URL = '(?x)https?://(?:www\\.)?bbv\\-tv\\.net/(?:\n        [^?#]+\\?(?:[^#]+&)?program=(?P<vid2>\\d+)\n        |(?:program|watch)/[^/]+/(?P<vid1>\\d+)\n    )'
    _NETRC_MACHINE = 'bbvtv'


class BBVTVLiveIE(BBVTVBaseIE):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'BBVTVLive'
    _VALID_URL = '(?x)https?://(?:www\\.)?bbv\\-tv\\.net/(?:\n        [^?#]+\\?(?:[^#]+&)?channel=(?P<vid2>[^/?&#]+)\n        |live/(?P<vid1>[^/?&#]+)\n    )'
    _NETRC_MACHINE = 'bbvtv'

    @classmethod
    def suitable(cls, url):
        return False if BBVTVIE.suitable(url) else super().suitable(url)


class BBVTVRecordingsIE(BBVTVBaseIE):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'BBVTVRecordings'
    _VALID_URL = '(?x)https?://(?:www\\.)?bbv\\-tv\\.net/(?:\n        [^?#]+\\?(?:[^#]+&)?recording=(?P<vid2>\\d+)\n        (?P<vid1>)\n    )'
    _NETRC_MACHINE = 'bbvtv'


class EinsUndEinsTVBaseIE(ZattooPlatformBaseIE):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'EinsUndEinsTVBase'
    _NETRC_MACHINE = '1und1tv'


class EinsUndEinsTVIE(EinsUndEinsTVBaseIE):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'EinsUndEinsTV'
    _VALID_URL = '(?x)https?://(?:www\\.)?1und1\\.tv/(?:\n        [^?#]+\\?(?:[^#]+&)?program=(?P<vid2>\\d+)\n        |(?:program|watch)/[^/]+/(?P<vid1>\\d+)\n    )'
    _NETRC_MACHINE = '1und1tv'


class EinsUndEinsTVLiveIE(EinsUndEinsTVBaseIE):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'EinsUndEinsTVLive'
    _VALID_URL = '(?x)https?://(?:www\\.)?1und1\\.tv/(?:\n        [^?#]+\\?(?:[^#]+&)?channel=(?P<vid2>[^/?&#]+)\n        |live/(?P<vid1>[^/?&#]+)\n    )'
    _NETRC_MACHINE = '1und1tv'

    @classmethod
    def suitable(cls, url):
        return False if EinsUndEinsTVIE.suitable(url) else super().suitable(url)


class EinsUndEinsTVRecordingsIE(EinsUndEinsTVBaseIE):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'EinsUndEinsTVRecordings'
    _VALID_URL = '(?x)https?://(?:www\\.)?1und1\\.tv/(?:\n        [^?#]+\\?(?:[^#]+&)?recording=(?P<vid2>\\d+)\n        (?P<vid1>)\n    )'
    _NETRC_MACHINE = '1und1tv'


class EWETVBaseIE(ZattooPlatformBaseIE):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'EWETVBase'
    _NETRC_MACHINE = 'ewetv'


class EWETVIE(EWETVBaseIE):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'EWETV'
    _VALID_URL = '(?x)https?://(?:www\\.)?tvonline\\.ewe\\.de/(?:\n        [^?#]+\\?(?:[^#]+&)?program=(?P<vid2>\\d+)\n        |(?:program|watch)/[^/]+/(?P<vid1>\\d+)\n    )'
    _NETRC_MACHINE = 'ewetv'


class EWETVLiveIE(EWETVBaseIE):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'EWETVLive'
    _VALID_URL = '(?x)https?://(?:www\\.)?tvonline\\.ewe\\.de/(?:\n        [^?#]+\\?(?:[^#]+&)?channel=(?P<vid2>[^/?&#]+)\n        |live/(?P<vid1>[^/?&#]+)\n    )'
    _NETRC_MACHINE = 'ewetv'

    @classmethod
    def suitable(cls, url):
        return False if EWETVIE.suitable(url) else super().suitable(url)


class EWETVRecordingsIE(EWETVBaseIE):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'EWETVRecordings'
    _VALID_URL = '(?x)https?://(?:www\\.)?tvonline\\.ewe\\.de/(?:\n        [^?#]+\\?(?:[^#]+&)?recording=(?P<vid2>\\d+)\n        (?P<vid1>)\n    )'
    _NETRC_MACHINE = 'ewetv'


class GlattvisionTVBaseIE(ZattooPlatformBaseIE):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'GlattvisionTVBase'
    _NETRC_MACHINE = 'glattvisiontv'


class GlattvisionTVIE(GlattvisionTVBaseIE):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'GlattvisionTV'
    _VALID_URL = '(?x)https?://(?:www\\.)?iptv\\.glattvision\\.ch/(?:\n        [^?#]+\\?(?:[^#]+&)?program=(?P<vid2>\\d+)\n        |(?:program|watch)/[^/]+/(?P<vid1>\\d+)\n    )'
    _NETRC_MACHINE = 'glattvisiontv'


class GlattvisionTVLiveIE(GlattvisionTVBaseIE):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'GlattvisionTVLive'
    _VALID_URL = '(?x)https?://(?:www\\.)?iptv\\.glattvision\\.ch/(?:\n        [^?#]+\\?(?:[^#]+&)?channel=(?P<vid2>[^/?&#]+)\n        |live/(?P<vid1>[^/?&#]+)\n    )'
    _NETRC_MACHINE = 'glattvisiontv'

    @classmethod
    def suitable(cls, url):
        return False if GlattvisionTVIE.suitable(url) else super().suitable(url)


class GlattvisionTVRecordingsIE(GlattvisionTVBaseIE):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'GlattvisionTVRecordings'
    _VALID_URL = '(?x)https?://(?:www\\.)?iptv\\.glattvision\\.ch/(?:\n        [^?#]+\\?(?:[^#]+&)?recording=(?P<vid2>\\d+)\n        (?P<vid1>)\n    )'
    _NETRC_MACHINE = 'glattvisiontv'


class MNetTVBaseIE(ZattooPlatformBaseIE):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'MNetTVBase'
    _NETRC_MACHINE = 'mnettv'


class MNetTVIE(MNetTVBaseIE):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'MNetTV'
    _VALID_URL = '(?x)https?://(?:www\\.)?tvplus\\.m\\-net\\.de/(?:\n        [^?#]+\\?(?:[^#]+&)?program=(?P<vid2>\\d+)\n        |(?:program|watch)/[^/]+/(?P<vid1>\\d+)\n    )'
    _NETRC_MACHINE = 'mnettv'


class MNetTVLiveIE(MNetTVBaseIE):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'MNetTVLive'
    _VALID_URL = '(?x)https?://(?:www\\.)?tvplus\\.m\\-net\\.de/(?:\n        [^?#]+\\?(?:[^#]+&)?channel=(?P<vid2>[^/?&#]+)\n        |live/(?P<vid1>[^/?&#]+)\n    )'
    _NETRC_MACHINE = 'mnettv'

    @classmethod
    def suitable(cls, url):
        return False if MNetTVIE.suitable(url) else super().suitable(url)


class MNetTVRecordingsIE(MNetTVBaseIE):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'MNetTVRecordings'
    _VALID_URL = '(?x)https?://(?:www\\.)?tvplus\\.m\\-net\\.de/(?:\n        [^?#]+\\?(?:[^#]+&)?recording=(?P<vid2>\\d+)\n        (?P<vid1>)\n    )'
    _NETRC_MACHINE = 'mnettv'


class NetPlusTVBaseIE(ZattooPlatformBaseIE):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'NetPlusTVBase'
    _NETRC_MACHINE = 'netplus'


class NetPlusTVIE(NetPlusTVBaseIE):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'NetPlusTV'
    _VALID_URL = '(?x)https?://(?:www\\.)?netplus\\.tv/(?:\n        [^?#]+\\?(?:[^#]+&)?program=(?P<vid2>\\d+)\n        |(?:program|watch)/[^/]+/(?P<vid1>\\d+)\n    )'
    _NETRC_MACHINE = 'netplus'


class NetPlusTVLiveIE(NetPlusTVBaseIE):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'NetPlusTVLive'
    _VALID_URL = '(?x)https?://(?:www\\.)?netplus\\.tv/(?:\n        [^?#]+\\?(?:[^#]+&)?channel=(?P<vid2>[^/?&#]+)\n        |live/(?P<vid1>[^/?&#]+)\n    )'
    _NETRC_MACHINE = 'netplus'

    @classmethod
    def suitable(cls, url):
        return False if NetPlusTVIE.suitable(url) else super().suitable(url)


class NetPlusTVRecordingsIE(NetPlusTVBaseIE):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'NetPlusTVRecordings'
    _VALID_URL = '(?x)https?://(?:www\\.)?netplus\\.tv/(?:\n        [^?#]+\\?(?:[^#]+&)?recording=(?P<vid2>\\d+)\n        (?P<vid1>)\n    )'
    _NETRC_MACHINE = 'netplus'


class OsnatelTVBaseIE(ZattooPlatformBaseIE):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'OsnatelTVBase'
    _NETRC_MACHINE = 'osnateltv'


class OsnatelTVIE(OsnatelTVBaseIE):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'OsnatelTV'
    _VALID_URL = '(?x)https?://(?:www\\.)?tvonline\\.osnatel\\.de/(?:\n        [^?#]+\\?(?:[^#]+&)?program=(?P<vid2>\\d+)\n        |(?:program|watch)/[^/]+/(?P<vid1>\\d+)\n    )'
    _NETRC_MACHINE = 'osnateltv'


class OsnatelTVLiveIE(OsnatelTVBaseIE):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'OsnatelTVLive'
    _VALID_URL = '(?x)https?://(?:www\\.)?tvonline\\.osnatel\\.de/(?:\n        [^?#]+\\?(?:[^#]+&)?channel=(?P<vid2>[^/?&#]+)\n        |live/(?P<vid1>[^/?&#]+)\n    )'
    _NETRC_MACHINE = 'osnateltv'

    @classmethod
    def suitable(cls, url):
        return False if OsnatelTVIE.suitable(url) else super().suitable(url)


class OsnatelTVRecordingsIE(OsnatelTVBaseIE):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'OsnatelTVRecordings'
    _VALID_URL = '(?x)https?://(?:www\\.)?tvonline\\.osnatel\\.de/(?:\n        [^?#]+\\?(?:[^#]+&)?recording=(?P<vid2>\\d+)\n        (?P<vid1>)\n    )'
    _NETRC_MACHINE = 'osnateltv'


class QuantumTVBaseIE(ZattooPlatformBaseIE):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'QuantumTVBase'
    _NETRC_MACHINE = 'quantumtv'


class QuantumTVIE(QuantumTVBaseIE):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'QuantumTV'
    _VALID_URL = '(?x)https?://(?:www\\.)?quantum\\-tv\\.com/(?:\n        [^?#]+\\?(?:[^#]+&)?program=(?P<vid2>\\d+)\n        |(?:program|watch)/[^/]+/(?P<vid1>\\d+)\n    )'
    _NETRC_MACHINE = 'quantumtv'


class QuantumTVLiveIE(QuantumTVBaseIE):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'QuantumTVLive'
    _VALID_URL = '(?x)https?://(?:www\\.)?quantum\\-tv\\.com/(?:\n        [^?#]+\\?(?:[^#]+&)?channel=(?P<vid2>[^/?&#]+)\n        |live/(?P<vid1>[^/?&#]+)\n    )'
    _NETRC_MACHINE = 'quantumtv'

    @classmethod
    def suitable(cls, url):
        return False if QuantumTVIE.suitable(url) else super().suitable(url)


class QuantumTVRecordingsIE(QuantumTVBaseIE):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'QuantumTVRecordings'
    _VALID_URL = '(?x)https?://(?:www\\.)?quantum\\-tv\\.com/(?:\n        [^?#]+\\?(?:[^#]+&)?recording=(?P<vid2>\\d+)\n        (?P<vid1>)\n    )'
    _NETRC_MACHINE = 'quantumtv'


class SaltTVBaseIE(ZattooPlatformBaseIE):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'SaltTVBase'
    _NETRC_MACHINE = 'salttv'


class SaltTVIE(SaltTVBaseIE):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'SaltTV'
    _VALID_URL = '(?x)https?://(?:www\\.)?tv\\.salt\\.ch/(?:\n        [^?#]+\\?(?:[^#]+&)?program=(?P<vid2>\\d+)\n        |(?:program|watch)/[^/]+/(?P<vid1>\\d+)\n    )'
    _NETRC_MACHINE = 'salttv'


class SaltTVLiveIE(SaltTVBaseIE):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'SaltTVLive'
    _VALID_URL = '(?x)https?://(?:www\\.)?tv\\.salt\\.ch/(?:\n        [^?#]+\\?(?:[^#]+&)?channel=(?P<vid2>[^/?&#]+)\n        |live/(?P<vid1>[^/?&#]+)\n    )'
    _NETRC_MACHINE = 'salttv'

    @classmethod
    def suitable(cls, url):
        return False if SaltTVIE.suitable(url) else super().suitable(url)


class SaltTVRecordingsIE(SaltTVBaseIE):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'SaltTVRecordings'
    _VALID_URL = '(?x)https?://(?:www\\.)?tv\\.salt\\.ch/(?:\n        [^?#]+\\?(?:[^#]+&)?recording=(?P<vid2>\\d+)\n        (?P<vid1>)\n    )'
    _NETRC_MACHINE = 'salttv'


class SAKTVBaseIE(ZattooPlatformBaseIE):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'SAKTVBase'
    _NETRC_MACHINE = 'saktv'


class SAKTVIE(SAKTVBaseIE):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'SAKTV'
    _VALID_URL = '(?x)https?://(?:www\\.)?saktv\\.ch/(?:\n        [^?#]+\\?(?:[^#]+&)?program=(?P<vid2>\\d+)\n        |(?:program|watch)/[^/]+/(?P<vid1>\\d+)\n    )'
    _NETRC_MACHINE = 'saktv'


class SAKTVLiveIE(SAKTVBaseIE):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'SAKTVLive'
    _VALID_URL = '(?x)https?://(?:www\\.)?saktv\\.ch/(?:\n        [^?#]+\\?(?:[^#]+&)?channel=(?P<vid2>[^/?&#]+)\n        |live/(?P<vid1>[^/?&#]+)\n    )'
    _NETRC_MACHINE = 'saktv'

    @classmethod
    def suitable(cls, url):
        return False if SAKTVIE.suitable(url) else super().suitable(url)


class SAKTVRecordingsIE(SAKTVBaseIE):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'SAKTVRecordings'
    _VALID_URL = '(?x)https?://(?:www\\.)?saktv\\.ch/(?:\n        [^?#]+\\?(?:[^#]+&)?recording=(?P<vid2>\\d+)\n        (?P<vid1>)\n    )'
    _NETRC_MACHINE = 'saktv'


class VTXTVBaseIE(ZattooPlatformBaseIE):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'VTXTVBase'
    _NETRC_MACHINE = 'vtxtv'


class VTXTVIE(VTXTVBaseIE):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'VTXTV'
    _VALID_URL = '(?x)https?://(?:www\\.)?vtxtv\\.ch/(?:\n        [^?#]+\\?(?:[^#]+&)?program=(?P<vid2>\\d+)\n        |(?:program|watch)/[^/]+/(?P<vid1>\\d+)\n    )'
    _NETRC_MACHINE = 'vtxtv'


class VTXTVLiveIE(VTXTVBaseIE):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'VTXTVLive'
    _VALID_URL = '(?x)https?://(?:www\\.)?vtxtv\\.ch/(?:\n        [^?#]+\\?(?:[^#]+&)?channel=(?P<vid2>[^/?&#]+)\n        |live/(?P<vid1>[^/?&#]+)\n    )'
    _NETRC_MACHINE = 'vtxtv'

    @classmethod
    def suitable(cls, url):
        return False if VTXTVIE.suitable(url) else super().suitable(url)


class VTXTVRecordingsIE(VTXTVBaseIE):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'VTXTVRecordings'
    _VALID_URL = '(?x)https?://(?:www\\.)?vtxtv\\.ch/(?:\n        [^?#]+\\?(?:[^#]+&)?recording=(?P<vid2>\\d+)\n        (?P<vid1>)\n    )'
    _NETRC_MACHINE = 'vtxtv'


class WalyTVBaseIE(ZattooPlatformBaseIE):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'WalyTVBase'
    _NETRC_MACHINE = 'walytv'


class WalyTVIE(WalyTVBaseIE):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'WalyTV'
    _VALID_URL = '(?x)https?://(?:www\\.)?player\\.waly\\.tv/(?:\n        [^?#]+\\?(?:[^#]+&)?program=(?P<vid2>\\d+)\n        |(?:program|watch)/[^/]+/(?P<vid1>\\d+)\n    )'
    _NETRC_MACHINE = 'walytv'


class WalyTVLiveIE(WalyTVBaseIE):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'WalyTVLive'
    _VALID_URL = '(?x)https?://(?:www\\.)?player\\.waly\\.tv/(?:\n        [^?#]+\\?(?:[^#]+&)?channel=(?P<vid2>[^/?&#]+)\n        |live/(?P<vid1>[^/?&#]+)\n    )'
    _NETRC_MACHINE = 'walytv'

    @classmethod
    def suitable(cls, url):
        return False if WalyTVIE.suitable(url) else super().suitable(url)


class WalyTVRecordingsIE(WalyTVBaseIE):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'WalyTVRecordings'
    _VALID_URL = '(?x)https?://(?:www\\.)?player\\.waly\\.tv/(?:\n        [^?#]+\\?(?:[^#]+&)?recording=(?P<vid2>\\d+)\n        (?P<vid1>)\n    )'
    _NETRC_MACHINE = 'walytv'


class ZattooBaseIE(ZattooPlatformBaseIE):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'ZattooBase'
    _NETRC_MACHINE = 'zattoo'


class ZattooIE(ZattooBaseIE):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'Zattoo'
    _VALID_URL = '(?x)https?://(?:www\\.)?zattoo\\.com/(?:\n        [^?#]+\\?(?:[^#]+&)?program=(?P<vid2>\\d+)\n        |(?:program|watch)/[^/]+/(?P<vid1>\\d+)\n    )'
    _NETRC_MACHINE = 'zattoo'


class ZattooLiveIE(ZattooBaseIE):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'ZattooLive'
    _VALID_URL = '(?x)https?://(?:www\\.)?zattoo\\.com/(?:\n        [^?#]+\\?(?:[^#]+&)?channel=(?P<vid2>[^/?&#]+)\n        |live/(?P<vid1>[^/?&#]+)\n    )'
    _NETRC_MACHINE = 'zattoo'

    @classmethod
    def suitable(cls, url):
        return False if ZattooIE.suitable(url) else super().suitable(url)


class ZattooMoviesIE(ZattooBaseIE):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'ZattooMovies'
    _VALID_URL = '(?x)https?://(?:www\\.)?zattoo\\.com/(?:\n        [^?#]+\\?(?:[^#]+&)?movie_id=(?P<vid2>\\w+)\n        |vod/movies/(?P<vid1>\\w+)\n    )'
    _NETRC_MACHINE = 'zattoo'


class ZattooRecordingsIE(ZattooBaseIE):
    _module = 'yt_dlp.extractor.zattoo'
    IE_NAME = 'ZattooRecordings'
    _VALID_URL = '(?x)https?://(?:www\\.)?zattoo\\.com/(?:\n        [^?#]+\\?(?:[^#]+&)?recording=(?P<vid2>\\d+)\n        (?P<vid1>)\n    )'
    _NETRC_MACHINE = 'zattoo'


class ZDFIE(ZDFBaseIE):
    _module = 'yt_dlp.extractor.zdf'
    IE_NAME = 'ZDF'
    _VALID_URL = 'https?://www\\.zdf\\.de/(?:[^/]+/)*(?P<id>[^/?#&]+)\\.html'


class DreiSatIE(ZDFIE):
    _module = 'yt_dlp.extractor.dreisat'
    IE_NAME = '3sat'
    _VALID_URL = 'https?://(?:www\\.)?3sat\\.de/(?:[^/]+/)*(?P<id>[^/?#&]+)\\.html'


class ZDFChannelIE(ZDFBaseIE):
    _module = 'yt_dlp.extractor.zdf'
    IE_NAME = 'ZDFChannel'
    _VALID_URL = 'https?://www\\.zdf\\.de/(?:[^/]+/)*(?P<id>[^/?#&]+)'

    @classmethod
    def suitable(cls, url):
        return False if ZDFIE.suitable(url) else super(ZDFChannelIE, cls).suitable(url)


class Zee5IE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.zee5'
    IE_NAME = 'Zee5'
    _VALID_URL = '(?x)\n                     (?:\n                        zee5:|\n                        https?://(?:www\\.)?zee5\\.com/(?:[^#?]+/)?\n                        (?:\n                            (?:tv-shows|kids|web-series|zee5originals)(?:/[^#/?]+){3}\n                            |(?:movies|kids|videos|news|music-videos)/(?!kids-shows)[^#/?]+\n                        )/(?P<display_id>[^#/?]+)/\n                     )\n                     (?P<id>[^#/?]+)/?(?:$|[?#])\n                     '
    _NETRC_MACHINE = 'zee5'


class Zee5SeriesIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.zee5'
    IE_NAME = 'zee5:series'
    _VALID_URL = '(?x)\n                     (?:\n                        zee5:series:|\n                        https?://(?:www\\.)?zee5\\.com/(?:[^#?]+/)?\n                        (?:tv-shows|web-series|kids|zee5originals)/(?!kids-movies)(?:[^#/?]+/){2}\n                     )\n                     (?P<id>[^#/?]+)(?:/episodes)?/?(?:$|[?#])\n                     '


class ZeeNewsIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.zeenews'
    IE_NAME = 'ZeeNews'
    _VALID_URL = 'https?://zeenews\\.india\\.com/[^#?]+/video/(?P<display_id>[^#/?]+)/(?P<id>\\d+)'


class ZhihuIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.zhihu'
    IE_NAME = 'Zhihu'
    _VALID_URL = 'https?://(?:www\\.)?zhihu\\.com/zvideo/(?P<id>[0-9]+)'


class ZingMp3BaseIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.zingmp3'
    IE_NAME = 'ZingMp3Base'


class ZingMp3IE(ZingMp3BaseIE):
    _module = 'yt_dlp.extractor.zingmp3'
    IE_NAME = 'zingmp3'
    IE_DESC = 'zingmp3.vn'
    _VALID_URL = 'https?://(?:mp3\\.zing|zingmp3)\\.vn/(?P<type>(?:bai-hat|video-clip|embed))/[^/?#]+/(?P<id>\\w+)(?:\\.html|\\?)'


class ZingMp3AlbumIE(ZingMp3BaseIE):
    _module = 'yt_dlp.extractor.zingmp3'
    IE_NAME = 'zingmp3:album'
    _VALID_URL = 'https?://(?:mp3\\.zing|zingmp3)\\.vn/(?P<type>(?:album|playlist))/[^/?#]+/(?P<id>\\w+)(?:\\.html|\\?)'


class ZingMp3ChartHomeIE(ZingMp3BaseIE):
    _module = 'yt_dlp.extractor.zingmp3'
    IE_NAME = 'zingmp3:chart-home'
    _VALID_URL = 'https?://(?:mp3\\.zing|zingmp3)\\.vn/(?P<id>(?:zing-chart|moi-phat-hanh))/?(?:[#?]|$)'


class ZingMp3WeekChartIE(ZingMp3BaseIE):
    _module = 'yt_dlp.extractor.zingmp3'
    IE_NAME = 'zingmp3:week-chart'
    _VALID_URL = 'https?://(?:mp3\\.zing|zingmp3)\\.vn/(?P<type>(?:zing-chart-tuan))/[^/?#]+/(?P<id>\\w+)(?:\\.html|\\?)'


class ZingMp3ChartMusicVideoIE(ZingMp3BaseIE):
    _module = 'yt_dlp.extractor.zingmp3'
    IE_NAME = 'zingmp3:chart-music-video'
    _VALID_URL = 'https?://(?:mp3\\.zing|zingmp3)\\.vn/(?P<type>the-loai-video)/(?P<regions>[^/]+)/(?P<id>[^\\.]+)'


class ZingMp3UserIE(ZingMp3BaseIE):
    _module = 'yt_dlp.extractor.zingmp3'
    IE_NAME = 'zingmp3:user'
    _VALID_URL = 'https?://(?:mp3\\.zing|zingmp3)\\.vn/(?P<user>[^/]+)/(?P<type>bai-hat|single|album|video)/?(?:[?#]|$)'


class ZoomIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.zoom'
    IE_NAME = 'zoom'
    _VALID_URL = '(?P<base_url>https?://(?:[^.]+\\.)?zoom.us/)rec(?:ording)?/(?:play|share)/(?P<id>[A-Za-z0-9_.-]+)'


class ZypeIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.zype'
    IE_NAME = 'Zype'
    _VALID_URL = 'https?://player\\.zype\\.com/embed/(?P<id>[\\da-fA-F]+)\\.(?:js|json|html)\\?.*?(?:access_token|(?:ap[ip]|player)_key)=[^&]+'


class GenericIE(LazyLoadExtractor):
    _module = 'yt_dlp.extractor.generic'
    IE_NAME = 'generic'
    IE_DESC = 'Generic downloader that works on some sites'
    _VALID_URL = '.*'
    _NETRC_MACHINE = False
    age_limit = 18


_ALL_CLASSES = [YoutubeIE, YoutubeClipIE, YoutubeFavouritesIE, YoutubeNotificationsIE, YoutubeHistoryIE, YoutubeTabIE, YoutubeLivestreamEmbedIE, YoutubePlaylistIE, YoutubeRecommendedIE, YoutubeSearchDateIE, YoutubeSearchIE, YoutubeSearchURLIE, YoutubeMusicSearchURLIE, YoutubeSubscriptionsIE, YoutubeStoriesIE, YoutubeTruncatedIDIE, YoutubeTruncatedURLIE, YoutubeYtBeIE, YoutubeYtUserIE, YoutubeWatchLaterIE, YoutubeShortsAudioPivotIE, ABCIE, ABCIViewIE, ABCIViewShowSeriesIE, AbcNewsIE, AbcNewsVideoIE, ABCOTVSIE, ABCOTVSClipsIE, AbemaTVIE, AbemaTVTitleIE, AcademicEarthCourseIE, ACastIE, ACastChannelIE, AcFunVideoIE, AcFunBangumiIE, ADNIE, AdobeConnectIE, AdobeTVEmbedIE, AdobeTVIE, AdobeTVShowIE, AdobeTVChannelIE, AdobeTVVideoIE, AdultSwimIE, AeonCoIE, AfreecaTVIE, AfreecaTVLiveIE, AfreecaTVUserIE, TokFMAuditionIE, TokFMPodcastIE, WyborczaPodcastIE, WyborczaVideoIE, AirMozillaIE, AlJazeeraIE, AlphaPornoIE, AmaraIE, AluraIE, AluraCourseIE, AmazonStoreIE, AmericasTestKitchenIE, AmericasTestKitchenSeasonIE, AngelIE, AnvatoIE, AllocineIE, AliExpressLiveIE, Alsace20TVIE, Alsace20TVEmbedIE, APAIE, AparatIE, AppleConnectIE, AppleTrailersIE, AppleTrailersSectionIE, ApplePodcastsIE, ArchiveOrgIE, YoutubeWebArchiveIE, ArcPublishingIE, ArkenaIE, ARDBetaMediathekIE, ARDIE, ARDMediathekIE, ArteTVIE, ArteTVEmbedIE, ArteTVPlaylistIE, ArteTVCategoryIE, ArnesIE, AsianCrushIE, AsianCrushPlaylistIE, AtresPlayerIE, AtScaleConfEventIE, ATTTechChannelIE, ATVAtIE, AudiMediaIE, AudioBoomIE, AudiodraftCustomIE, AudiodraftGenericIE, AudiomackIE, AudiomackAlbumIE, AudiusIE, AudiusTrackIE, AudiusPlaylistIE, AudiusProfileIE, AWAANIE, AWAANVideoIE, AWAANLiveIE, AWAANSeasonIE, AZMedienIE, BaiduVideoIE, BanByeIE, BanByeChannelIE, BandcampIE, BandcampAlbumIE, BandcampWeeklyIE, BandcampUserIE, BannedVideoIE, BBCCoUkIE, BBCCoUkArticleIE, BBCCoUkIPlayerEpisodesIE, BBCCoUkIPlayerGroupIE, BBCCoUkPlaylistIE, BBCIE, BeegIE, BehindKinkIE, BellMediaIE, BeatportIE, BerufeTVIE, BetIE, BFIPlayerIE, BFMTVIE, BFMTVLiveIE, BFMTVArticleIE, BibelTVIE, BigflixIE, BigoIE, BildIE, BiliBiliIE, BiliBiliBangumiIE, BiliBiliBangumiMediaIE, BiliBiliSearchIE, BilibiliCategoryIE, BilibiliAudioIE, BilibiliAudioAlbumIE, BiliBiliPlayerIE, BilibiliSpaceVideoIE, BilibiliSpaceAudioIE, BilibiliSpacePlaylistIE, BiliIntlIE, BiliIntlSeriesIE, BiliLiveIE, BioBioChileTVIE, BitChuteIE, BitChuteChannelIE, BitwaveReplayIE, BitwaveStreamIE, BIQLEIE, BlackboardCollaborateIE, BleacherReportIE, BleacherReportCMSIE, BloggerIE, BloombergIE, BokeCCIE, BongaCamsIE, BostonGlobeIE, BoxIE, BooyahClipsIE, BpbIE, BRIE, BRMediathekIE, BravoTVIE, BreakIE, BreitBartIE, BrightcoveLegacyIE, BrightcoveNewIE, BandaiChannelIE, BusinessInsiderIE, BundesligaIE, BuzzFeedIE, BYUtvIE, C56IE, CableAVIE, CallinIE, CaltransIE, CAM4IE, CamdemyIE, CamdemyFolderIE, CamModelsIE, CamsodaIE, CamtasiaEmbedIE, CamWithHerIE, CanalAlphaIE, CanalplusIE, Canalc2IE, CanvasIE, CanvasEenIE, VrtNUIE, DagelijkseKostIE, CarambaTVIE, CarambaTVPageIE, CartoonNetworkIE, CBCIE, CBCPlayerIE, CBCGemIE, CBCGemPlaylistIE, CBCGemLiveIE, CBSLocalIE, CBSLocalArticleIE, CBSNewsLiveVideoIE, CBSSportsEmbedIE, CBSSportsIE, TwentyFourSevenSportsIE, CCCIE, CCCPlaylistIE, CCMAIE, CCTVIE, CDAIE, CellebriteIE, CeskaTelevizeIE, CGTNIE, Channel9IE, CharlieRoseIE, ChaturbateIE, ChilloutzoneIE, ChingariIE, ChingariUserIE, ChirbitIE, ChirbitProfileIE, CinchcastIE, CinemaxIE, CinetecaMilanoIE, CiscoLiveSessionIE, CiscoLiveSearchIE, CiscoWebexIE, CJSWIE, CliphunterIE, ClippitIE, ClipRsIE, ClipsyndicateIE, CloserToTruthIE, CloudflareStreamIE, CloudyIE, ClubicIE, ClypIE, CNBCIE, CNBCVideoIE, CNNIE, CNNBlogsIE, CNNArticleIE, CNNIndonesiaIE, CoubIE, ComedyCentralIE, ComedyCentralTVIE, CommonMistakesIE, UnicodeBOMIE, MmsIE, RtmpIE, ViewSourceIE, CondeNastIE, CONtvIE, CPACIE, CPACPlaylistIE, CozyTVIE, CrackedIE, CrackleIE, CraftsyIE, CrooksAndLiarsIE, CrowdBunkerIE, CrowdBunkerChannelIE, CrunchyrollBetaIE, CrunchyrollBetaShowIE, CSpanIE, CSpanCongressIE, CtsNewsIE, CTVIE, CTVNewsIE, CultureUnpluggedIE, CuriosityStreamIE, CuriosityStreamCollectionsIE, CuriosityStreamSeriesIE, CWTVIE, CybraryIE, CybraryCourseIE, DaftsexIE, DailyMailIE, DailymotionIE, DailymotionPlaylistIE, DailymotionUserIE, DailyWireIE, DailyWirePodcastIE, DamtomoRecordIE, DamtomoVideoIE, DaumIE, DaumClipIE, DaumPlaylistIE, DaumUserIE, DaystarClipIE, DBTVIE, DctpTvIE, DeezerPlaylistIE, DeezerAlbumIE, DemocracynowIE, DetikEmbedIE, DFBIE, DHMIE, DiggIE, DotsubIE, DouyuShowIE, DouyuTVIE, DPlayIE, DiscoveryPlusIE, HGTVDeIE, GoDiscoveryIE, TravelChannelIE, CookingChannelIE, HGTVUsaIE, FoodNetworkIE, InvestigationDiscoveryIE, DestinationAmericaIE, AmHistoryChannelIE, ScienceChannelIE, DIYNetworkIE, DiscoveryLifeIE, AnimalPlanetIE, TLCIE, MotorTrendIE, MotorTrendOnDemandIE, DiscoveryPlusIndiaIE, DiscoveryNetworksDeIE, DiscoveryPlusItalyIE, DiscoveryPlusItalyShowIE, DiscoveryPlusIndiaShowIE, DRBonanzaIE, DrTuberIE, DRTVIE, DRTVLiveIE, DTubeIE, DVTVIE, DubokuIE, DubokuPlaylistIE, DumpertIE, DefenseGouvFrIE, DeuxMIE, DeuxMNewsIE, DigitalConcertHallIE, DiscoveryIE, DisneyIE, DigitallySpeakingIE, DropboxIE, DropoutSeasonIE, DropoutIE, DWIE, DWArticleIE, EaglePlatformIE, ClipYouEmbedIE, EbaumsWorldIE, EchoMskIE, EggheadCourseIE, EggheadLessonIE, EHowIE, EightTracksIE, EinthusanIE, EitbIE, EllenTubeIE, EllenTubeVideoIE, EllenTubePlaylistIE, ElonetIE, ElPaisIE, EmbedlyIE, EngadgetIE, EpiconIE, EpiconSeriesIE, EpochIE, EpornerIE, EroProfileIE, EroProfileAlbumIE, ERTFlixCodenameIE, ERTFlixIE, ERTWebtvEmbedIE, EscapistIE, ESPNIE, WatchESPNIE, ESPNArticleIE, FiveThirtyEightIE, ESPNCricInfoIE, EsriVideoIE, EuropaIE, EuropeanTourIE, EurosportIE, EUScreenIE, ExpoTVIE, ExpressenIE, EyedoTVIE, FacebookIE, FacebookPluginsVideoIE, FacebookRedirectURLIE, FacebookReelIE, FancodeVodIE, FancodeLiveIE, FazIE, FC2IE, FC2EmbedIE, FC2LiveIE, FczenitIE, FifaIE, FilmmoduIE, FilmOnIE, FilmOnChannelIE, FilmwebIE, FirstTVIE, FiveTVIE, FlickrIE, FolketingetIE, FootyRoomIE, Formula1IE, FourTubeIE, PornTubeIE, PornerBrosIE, FuxIE, FourZeroStudioArchiveIE, FourZeroStudioClipIE, FOXIE, FOX9IE, FOX9NewsIE, FoxgayIE, FoxNewsIE, FoxNewsArticleIE, FoxNewsVideoIE, FoxSportsIE, FptplayIE, FranceInterIE, FranceTVIE, FranceTVSiteIE, FranceTVInfoIE, FreesoundIE, FreespeechIE, FrontendMastersIE, FrontendMastersLessonIE, FrontendMastersCourseIE, FreeTvIE, FreeTvMoviesIE, FujiTVFODPlus7IE, FunimationIE, FunimationPageIE, FunimationShowIE, FunkIE, FusionIE, FuyinTVIE, GabTVIE, GabIE, GaiaIE, GameInformerIE, GameJoltIE, GameJoltUserIE, GameJoltGameIE, GameJoltGameSoundtrackIE, GameJoltCommunityIE, GameJoltSearchIE, GameSpotIE, GameStarIE, GaskrankIE, GazetaIE, GDCVaultIE, GediDigitalIE, GeniusIE, GeniusLyricsIE, GettrIE, GettrStreamingIE, GfycatIE, GiantBombIE, GigaIE, GlideIE, GloboIE, GloboArticleIE, GoIE, GodTubeIE, GofileIE, GolemIE, GoodGameIE, GoogleDriveIE, GoogleDriveFolderIE, GooglePodcastsIE, GooglePodcastsFeedIE, GoogleSearchIE, GoProIE, GoPlayIE, GoshgayIE, GoToStageIE, GPUTechConfIE, GronkhIE, GronkhFeedIE, GronkhVodsIE, GrouponIE, HarpodeonIE, HBOIE, HearThisAtIE, HeiseIE, HellPornoIE, HelsinkiIE, HentaiStigmaIE, HGTVComShowIE, HKETVIE, HiDiveIE, HistoricFilmsIE, HitboxIE, HitboxLiveIE, HitRecordIE, HolodexIE, HotNewHipHopIE, HotStarIE, HotStarPrefixIE, HotStarPlaylistIE, HotStarSeasonIE, HotStarSeriesIE, HowcastIE, HowStuffWorksIE, HRFernsehenIE, HRTiIE, HRTiPlaylistIE, HSEShowIE, HSEProductIE, HTML5MediaEmbedIE, QuotedHTMLIE, HuajiaoIE, HuyaLiveIE, HuffPostIE, HungamaIE, HungamaSongIE, HungamaAlbumPlaylistIE, HypemIE, HytaleIE, IcareusIE, IchinanaLiveIE, IchinanaLiveClipIE, IGNIE, IGNVideoIE, IGNArticleIE, IHeartRadioIE, IHeartRadioPodcastIE, IltalehtiIE, ImdbIE, ImdbListIE, ImgurIE, ImgurGalleryIE, ImgurAlbumIE, InaIE, IncIE, IndavideoEmbedIE, InfoQIE, InstagramIE, InstagramIOSIE, InstagramUserIE, InstagramTagIE, InstagramStoryIE, InternazionaleIE, InternetVideoArchiveIE, IPrimaIE, IPrimaCNNIE, IqiyiIE, IqIE, IqAlbumIE, IslamChannelIE, IslamChannelSeriesIE, IsraelNationalNewsIE, ITProTVIE, ITProTVCourseIE, ITVIE, ITVBTCCIE, IviIE, IviCompilationIE, IvideonIE, IwaraIE, IwaraPlaylistIE, IwaraUserIE, IxiguaIE, IzleseneIE, JableIE, JablePlaylistIE, JamendoIE, JamendoAlbumIE, ShugiinItvLiveIE, ShugiinItvLiveRoomIE, ShugiinItvVodIE, SangiinInstructionIE, SangiinIE, JeuxVideoIE, JoveIE, JojIE, JWPlatformIE, KakaoIE, KalturaIE, KaraoketvIE, KarriereVideosIE, KeezMoviesIE, ExtremeTubeIE, KelbyOneIE, KetnetIE, KhanAcademyIE, KhanAcademyUnitIE, KickerIE, KickStarterIE, KinjaEmbedIE, KinoPoiskIE, KompasVideoIE, KonserthusetPlayIE, KooIE, KTHIE, KrasViewIE, Ku6IE, KUSIIE, KuwoIE, KuwoAlbumIE, KuwoChartIE, KuwoSingerIE, KuwoCategoryIE, KuwoMvIE, LA7IE, LA7PodcastEpisodeIE, LA7PodcastIE, Laola1TvEmbedIE, Laola1TvIE, EHFTVIE, ITTFIE, LastFMIE, LastFMPlaylistIE, LastFMUserIE, LBRYIE, LBRYChannelIE, LCIIE, LcpPlayIE, LcpIE, Lecture2GoIE, LecturioIE, LecturioCourseIE, LecturioDeCourseIE, LeIE, LePlaylistIE, LetvCloudIE, LEGOIE, LemondeIE, LentaIE, LibraryOfCongressIE, LibsynIE, LifeNewsIE, LifeEmbedIE, LikeeIE, LikeeUserIE, LimelightMediaIE, LimelightChannelIE, LimelightChannelListIE, LineLiveIE, LineLiveChannelIE, LinkedInIE, LinkedInLearningIE, LinkedInLearningCourseIE, LinuxAcademyIE, Liputan6IE, ListenNotesIE, LiTVIE, LiveJournalIE, LivestreamIE, LivestreamOriginalIE, LivestreamShortenerIE, LivestreamfailsIE, LnkGoIE, LnkIE, LocalNews8IE, LoveHomePornIE, LRTVODIE, LRTStreamIE, LyndaIE, LyndaCourseIE, M6IE, MagentaMusik360IE, MailRuIE, MailRuMusicIE, MailRuMusicSearchIE, MainStreamingIE, MallTVIE, MangomoloVideoIE, MangomoloLiveIE, ManotoTVIE, ManotoTVShowIE, ManotoTVLiveIE, ManyVidsIE, MaoriTVIE, MarkizaIE, MarkizaPageIE, MassengeschmackTVIE, MastersIE, MatchTVIE, MDRIE, MedalTVIE, MediaiteIE, MediaKlikkIE, MediasetIE, MediasetShowIE, MediasiteIE, MediasiteCatalogIE, MediasiteNamedCatalogIE, MediaWorksNZVODIE, MediciIE, MegaphoneIE, MeipaiIE, MelonVODIE, METAIE, MetacafeIE, MetacriticIE, MgoonIE, MGTVIE, MiaoPaiIE, MicrosoftStreamIE, MicrosoftVirtualAcademyIE, MicrosoftVirtualAcademyCourseIE, MicrosoftEmbedIE, MildomIE, MildomVodIE, MildomClipIE, MildomUserVodIE, MindsIE, MindsChannelIE, MindsGroupIE, MinistryGridIE, MinotoIE, MioMioIE, MirrativIE, MirrativUserIE, MirrorCoUKIE, TechTVMITIE, OCWMITIE, MixchIE, MixchArchiveIE, MixcloudIE, MixcloudUserIE, MixcloudPlaylistIE, MLBIE, MLBVideoIE, MLBTVIE, MLBArticleIE, MLSSoccerIE, MnetIE, MochaVideoIE, MoeVideoIE, MofosexIE, MofosexEmbedIE, MojvideoIE, MorningstarIE, MotherlessIE, MotherlessGroupIE, MotorsportIE, MovieClipsIE, MoviepilotIE, MoviewPlayIE, MoviezineIE, MovingImageIE, MSNIE, MTVIE, CMTIE, MTVVideoIE, MTVServicesEmbeddedIE, MTVDEIE, MTVJapanIE, MTVItaliaIE, MTVItaliaProgrammaIE, MuenchenTVIE, MurrtubeIE, MurrtubeUserIE, MuseScoreIE, MusicdexSongIE, MusicdexAlbumIE, MusicdexArtistIE, MusicdexPlaylistIE, MwaveIE, MwaveMeetGreetIE, MxplayerIE, MxplayerShowIE, MyChannelsIE, MySpaceIE, MySpaceAlbumIE, MySpassIE, MyviIE, MyviEmbedIE, MyVideoGeIE, MyVidsterIE, N1InfoAssetIE, N1InfoIIE, NateIE, NateProgramIE, NationalGeographicVideoIE, NationalGeographicTVIE, NaverIE, NaverLiveIE, NaverNowIE, NBAWatchEmbedIE, NBAWatchIE, NBAWatchCollectionIE, NBAEmbedIE, NBAIE, NBAChannelIE, NBCOlympicsIE, NBCOlympicsStreamIE, NBCSportsIE, NBCSportsStreamIE, NBCSportsVPlayerIE, NBCStationsIE, NDRIE, NJoyIE, NDREmbedBaseIE, NDREmbedIE, NJoyEmbedIE, NDTVIE, NebulaIE, NebulaSubscriptionsIE, NebulaChannelIE, NerdCubedFeedIE, NetzkinoIE, NetEaseMusicIE, NetEaseMusicAlbumIE, NetEaseMusicSingerIE, NetEaseMusicListIE, NetEaseMusicMvIE, NetEaseMusicProgramIE, NetEaseMusicDjRadioIE, NetverseIE, NetversePlaylistIE, NewgroundsIE, NewgroundsPlaylistIE, NewgroundsUserIE, NewsPicksIE, NewstubeIE, NewsyIE, NextMediaIE, NextMediaActionNewsIE, AppleDailyIE, NextTVIE, NexxIE, NexxEmbedIE, NFBIE, NFHSNetworkIE, NFLIE, NFLArticleIE, NhkVodIE, NhkVodProgramIE, NhkForSchoolBangumiIE, NhkForSchoolSubjectIE, NhkForSchoolProgramListIE, NHLIE, NickIE, NickBrIE, NickDeIE, NickNightIE, NickRuIE, NiconicoIE, NiconicoPlaylistIE, NiconicoUserIE, NiconicoSeriesIE, NiconicoHistoryIE, NicovideoSearchDateIE, NicovideoSearchIE, NicovideoSearchURLIE, NicovideoTagURLIE, NineCNineMediaIE, CPTwentyFourIE, NineGagIE, NineNowIE, NintendoIE, NitterIE, NJPWWorldIE, NobelPrizeIE, NonkTubeIE, NoodleMagazineIE, NoovoIE, NormalbootsIE, NosVideoIE, NOSNLArticleIE, NovaEmbedIE, NovaIE, NovaPlayIE, NownessIE, NownessPlaylistIE, NownessSeriesIE, NozIE, NPOIE, AndereTijdenIE, NPOLiveIE, NPORadioIE, NPORadioFragmentIE, SchoolTVIE, HetKlokhuisIE, VPROIE, WNLIE, NprIE, NRKIE, NRKPlaylistIE, NRKSkoleIE, NRKTVIE, NRKTVDirekteIE, NRKRadioPodkastIE, NRKTVEpisodeIE, NRKTVEpisodesIE, NRKTVSeasonIE, NRKTVSeriesIE, NRLTVIE, NTVCoJpCUIE, NTVDeIE, NTVRuIE, NYTimesIE, NYTimesArticleIE, NYTimesCookingIE, NuvidIE, NZHeraldIE, NZZIE, OdaTVIE, OdnoklassnikiIE, OfTVIE, OfTVPlaylistIE, OktoberfestTVIE, OlympicsReplayIE, On24IE, OnDemandKoreaIE, OneFootballIE, OneNewsNZIE, OnetIE, OnetChannelIE, OnetMVPIE, OnetPlIE, OnionStudiosIE, OoyalaIE, OoyalaExternalIE, OpencastIE, OpencastPlaylistIE, OpenRecIE, OpenRecCaptureIE, OpenRecMovieIE, OraTVIE, ORFTVthekIE, ORFFM4StoryIE, ORFRadioIE, ORFIPTVIE, OutsideTVIE, PacktPubIE, PacktPubCourseIE, PalcoMP3IE, PalcoMP3ArtistIE, PalcoMP3VideoIE, PandoraTVIE, PanoptoIE, PanoptoListIE, PanoptoPlaylistIE, ParamountPlusSeriesIE, ParlerIE, ParlviewIE, PatreonIE, PatreonCampaignIE, PBSIE, PearVideoIE, PeekVidsIE, PlayVidsIE, PeerTubeIE, PeerTubePlaylistIE, PeerTVIE, PelotonIE, PelotonLiveIE, PeopleIE, PerformGroupIE, PeriscopeIE, PeriscopeUserIE, PhilharmonieDeParisIE, PhoenixIE, PhotobucketIE, PiaproIE, PicartoIE, PicartoVodIE, PikselIE, PinkbikeIE, PinterestIE, PinterestCollectionIE, PixivSketchIE, PixivSketchUserIE, PladformIE, PlanetMarathiIE, PlatziIE, PlatziCourseIE, PlayFMIE, PlayPlusTVIE, PlaysTVIE, PlayStuffIE, PlaySuisseIE, PlaytvakIE, PlayvidIE, PlaywireIE, PlutoTVIE, PluralsightIE, PluralsightCourseIE, PodbayFMIE, PodbayFMChannelIE, PodchaserIE, PodomaticIE, PokemonIE, PokemonWatchIE, PokerGoIE, PokerGoCollectionIE, PolsatGoIE, PolskieRadioIE, PolskieRadioCategoryIE, PolskieRadioPlayerIE, PolskieRadioPodcastIE, PolskieRadioPodcastListIE, PolskieRadioRadioKierowcowIE, PopcorntimesIE, PopcornTVIE, Porn91IE, PornComIE, PornFlipIE, PornHdIE, PornHubIE, PornHubUserIE, PornHubPlaylistIE, PornHubPagedVideoListIE, PornHubUserVideosUploadIE, PornotubeIE, PornoVoisinesIE, PornoXOIE, PornezIE, PuhuTVIE, PuhuTVSerieIE, PrankCastIE, PremiershipRugbyIE, PressTVIE, ProjectVeritasIE, ProSiebenSat1IE, PRXStoryIE, PRXSeriesIE, PRXAccountIE, PRXStoriesSearchIE, PRXSeriesSearchIE, Puls4IE, PyvideoIE, QingTingIE, QQMusicIE, QQMusicSingerIE, QQMusicAlbumIE, QQMusicToplistIE, QQMusicPlaylistIE, R7IE, R7ArticleIE, RadikoIE, RadikoRadioIE, RadioCanadaIE, RadioCanadaAudioVideoIE, RadioDeIE, RadioJavanIE, RadioBremenIE, FranceCultureIE, RadioFranceIE, RadioZetPodcastIE, RadioKapitalIE, RadioKapitalShowIE, RadLiveIE, RadLiveChannelIE, RadLiveSeasonIE, RaiPlayIE, RaiPlayLiveIE, RaiPlayPlaylistIE, RaiPlaySoundIE, RaiPlaySoundLiveIE, RaiPlaySoundPlaylistIE, RaiSudtirolIE, RaiIE, RaiNewsIE, RayWenderlichIE, RayWenderlichCourseIE, RBMARadioIE, RCSIE, RCSEmbedsIE, RCSVariousIE, RCTIPlusIE, RCTIPlusSeriesIE, RCTIPlusTVIE, RDSIE, ParliamentLiveUKIE, RTBFIE, RedBullTVIE, RedBullEmbedIE, RedBullTVRrnContentIE, RedBullIE, RedditIE, RedGifsIE, RedGifsSearchIE, RedGifsUserIE, RedTubeIE, RegioTVIE, RENTVIE, RENTVArticleIE, RestudyIE, ReutersIE, ReverbNationIE, RICEIE, RMCDecouverteIE, RockstarGamesIE, RokfinIE, RokfinStackIE, RokfinChannelIE, RokfinSearchIE, RoosterTeethIE, RoosterTeethSeriesIE, RottenTomatoesIE, RozhlasIE, RteIE, RteRadioIE, RtlNlIE, RTLLuTeleVODIE, RTLLuArticleIE, RTLLuLiveIE, RTLLuRadioIE, RTL2IE, RTL2YouIE, RTL2YouSeriesIE, RTNewsIE, RTDocumentryIE, RTDocumentryPlaylistIE, RuptlyIE, RTPIE, RTRFMIE, RTVEALaCartaIE, RTVEAudioIE, RTVELiveIE, RTVEInfantilIE, RTVETelevisionIE, RTVNHIE, RTVSIE, RTVSLOIE, RUHDIE, Rule34VideoIE, RumbleEmbedIE, RumbleChannelIE, RutubeIE, RutubeChannelIE, RutubeEmbedIE, RutubeMovieIE, RutubePersonIE, RutubePlaylistIE, RutubeTagsIE, GlomexIE, GlomexEmbedIE, MegaTVComIE, MegaTVComEmbedIE, Ant1NewsGrWatchIE, Ant1NewsGrArticleIE, Ant1NewsGrEmbedIE, RUTVIE, RuutuIE, RuvIE, RuvSpilaIE, SafariIE, SafariApiIE, SafariCourseIE, SaitosanIE, SampleFocusIE, SapoIE, SaveFromIE, SBSIE, Screen9IE, ScreencastIE, ScreencastOMaticIE, ScrippsNetworksWatchIE, ScrippsNetworksIE, SCTEIE, SCTECourseIE, ScrolllerIE, SeekerIE, SenateISVPIE, SenateGovIE, SendtoNewsIE, ServusIE, SevenPlusIE, SexuIE, SeznamZpravyIE, SeznamZpravyArticleIE, ShahidIE, ShahidShowIE, SharedIE, VivoIE, ShareVideosEmbedIE, ShemarooMeIE, ShowRoomLiveIE, SimplecastIE, SimplecastEpisodeIE, SimplecastPodcastIE, SinaIE, SixPlayIE, SkebIE, SkyItPlayerIE, SkyItVideoIE, SkyItVideoLiveIE, SkyItIE, SkyItArteIE, CieloTVItIE, TV8ItIE, SkylineWebcamsIE, SkyNewsArabiaIE, SkyNewsArabiaArticleIE, SkyNewsAUIE, SkyNewsIE, SkyNewsStoryIE, SkySportsIE, SkySportsNewsIE, SlideshareIE, SlidesLiveIE, SlutloadIE, SmotrimIE, SnotrIE, SohuIE, SonyLIVIE, SonyLIVSeriesIE, SoundcloudEmbedIE, SoundcloudIE, SoundcloudSetIE, SoundcloudRelatedIE, SoundcloudUserIE, SoundcloudTrackStationIE, SoundcloudPlaylistIE, SoundcloudSearchIE, SoundgasmIE, SoundgasmProfileIE, SouthParkIE, SouthParkDeIE, SouthParkDkIE, SouthParkEsIE, SouthParkLatIE, SouthParkNlIE, SovietsClosetIE, SovietsClosetPlaylistIE, SpankBangIE, SpankBangPlaylistIE, SpankwireIE, SpiegelIE, BellatorIE, ParamountNetworkIE, StarTrekIE, StitcherIE, StitcherShowIE, Sport5IE, SportBoxIE, SportDeutschlandIE, SpotifyIE, SpotifyShowIE, SpreakerIE, SpreakerPageIE, SpreakerShowIE, SpreakerShowPageIE, SpringboardPlatformIE, SproutIE, SRGSSRIE, RTSIE, SRGSSRPlayIE, SRMediathekIE, StanfordOpenClassroomIE, StarTVIE, SteamIE, SteamCommunityBroadcastIE, StoryFireIE, StoryFireUserIE, StoryFireSeriesIE, StreamableIE, StreamanityIE, StreamcloudIE, StreamCZIE, StreamFFIE, StreetVoiceIE, StretchInternetIE, StripchatIE, STVPlayerIE, SubstackIE, SunPornoIE, SverigesRadioEpisodeIE, SverigesRadioPublicationIE, SVTIE, SVTPageIE, SVTPlayIE, SVTSeriesIE, SwearnetEpisodeIE, SWRMediathekIE, SYVDKIE, SyfyIE, SztvHuIE, TagesschauIE, TassIE, TBSIE, TDSLifewayIE, TeachableIE, TeachableCourseIE, TeacherTubeIE, TeacherTubeUserIE, TeachingChannelIE, TeamcocoIE, TeamTreeHouseIE, TechTalksIE, TedEmbedIE, TedPlaylistIE, TedSeriesIE, TedTalkIE, Tele5IE, Tele13IE, TeleBruxellesIE, TelecincoIE, MiTeleIE, TelegraafIE, TelegramEmbedIE, TeleMBIE, TelemundoIE, TeleQuebecIE, TeleQuebecSquatIE, TeleQuebecEmissionIE, TeleQuebecLiveIE, TeleQuebecVideoIE, TeleTaskIE, TelewebionIE, TempoIE, IflixEpisodeIE, IflixSeriesIE, VQQSeriesIE, VQQVideoIE, WeTvEpisodeIE, WeTvSeriesIE, TennisTVIE, TenPlayIE, TestURLIE, TF1IE, TFOIE, TheHoleTvIE, TheInterceptIE, ThePlatformIE, AENetworksIE, AENetworksCollectionIE, AENetworksShowIE, HistoryTopicIE, HistoryPlayerIE, BiographyIE, AMCNetworksIE, NBCIE, NBCNewsIE, ThePlatformFeedIE, CBSIE, CBSInteractiveIE, CBSNewsEmbedIE, CBSNewsIE, CorusIE, ParamountPlusIE, TheStarIE, TheSunIE, ThetaVideoIE, ThetaStreamIE, TheWeatherChannelIE, ThisAmericanLifeIE, ThisAVIE, ThisOldHouseIE, ThreeSpeakIE, ThreeSpeakUserIE, ThreeQSDNIE, TikTokIE, TikTokUserIE, TikTokSoundIE, TikTokEffectIE, TikTokTagIE, TikTokVMIE, DouyinIE, TinyPicIE, TMZIE, TNAFlixNetworkEmbedIE, TNAFlixIE, EMPFlixIE, MovieFapIE, ToggleIE, MeWatchIE, ToggoIE, TokentubeIE, TokentubeChannelIE, TOnlineIE, ToonGogglesIE, TouTvIE, ToypicsUserIE, ToypicsIE, TrailerAddictIE, TrillerIE, TrillerUserIE, TriluliluIE, TrovoIE, TrovoVodIE, TrovoChannelVodIE, TrovoChannelClipIE, TrueIDIE, TruNewsIE, TruthIE, TruTVIE, Tube8IE, TubeTuGrazIE, TubeTuGrazSeriesIE, TubiTvIE, TubiTvShowIE, TumblrIE, TuneInClipIE, TuneInStationIE, TuneInProgramIE, TuneInTopicIE, TuneInShortenerIE, TunePkIE, TurboIE, TV2IE, TV2ArticleIE, KatsomoIE, MTVUutisetArticleIE, TV24UAVideoIE, TV2DKIE, TV2DKBornholmPlayIE, TV2HuIE, TV2HuSeriesIE, TV4IE, TV5MondePlusIE, TV5UnisVideoIE, TV5UnisIE, TVAIE, QubIE, TVANouvellesIE, TVANouvellesArticleIE, TVCIE, TVCArticleIE, TVerIE, TvigleIE, TVIPlayerIE, TVLandIE, TVN24IE, TVNetIE, TVNoeIE, TVNowIE, TVNowFilmIE, TVNowNewIE, TVNowSeasonIE, TVNowAnnualIE, TVNowShowIE, TVOpenGrWatchIE, TVOpenGrEmbedIE, TVPEmbedIE, TVPIE, TVPStreamIE, TVPVODSeriesIE, TVPVODVideoIE, TVPlayIE, ViafreeIE, TVPlayHomeIE, TVPlayerIE, TweakersIE, TwentyFourVideoIE, TwentyMinutenIE, TwentyThreeVideoIE, TwitCastingIE, TwitCastingLiveIE, TwitCastingUserIE, TwitchVodIE, TwitchCollectionIE, TwitchVideosIE, TwitchVideosClipsIE, TwitchVideosCollectionsIE, TwitchStreamIE, TwitchClipsIE, TwitterCardIE, TwitterIE, TwitterAmplifyIE, TwitterBroadcastIE, TwitterSpacesIE, TwitterShortenerIE, UdemyIE, UdemyCourseIE, UDNEmbedIE, UFCTVIE, UFCArabiaIE, UkColumnIE, UKTVPlayIE, DigitekaIE, DLiveVODIE, DLiveStreamIE, DroobleIE, UMGDeIE, UnistraIE, UnityIE, UnscriptedNewsVideoIE, KnownDRMIE, KnownPiracyIE, UOLIE, UplynkIE, UplynkPreplayIE, UrortIE, URPlayIE, USANetworkIE, USATodayIE, UstreamIE, UstreamChannelIE, UstudioIE, UstudioEmbedIE, UtreonIE, Varzesh3IE, Vbox7IE, VeeHDIE, VeoIE, VeohIE, VestiIE, VevoIE, VevoPlaylistIE, BTArticleIE, BTVestlendingenIE, VH1IE, ViceIE, ViceArticleIE, ViceShowIE, VidbitIE, ViddlerIE, VideaIE, VideocampusSachsenIE, ViMPPlaylistIE, VideoDetectiveIE, VideofyMeIE, VideomoreIE, VideomoreVideoIE, VideomoreSeasonIE, VideoPressIE, VidioIE, VidioPremierIE, VidioLiveIE, VidLiiIE, ViewLiftIE, ViewLiftEmbedIE, ViideaIE, VimeoIE, VimeoAlbumIE, VimeoChannelIE, VimeoGroupsIE, VimeoLikesIE, VimeoOndemandIE, VimeoReviewIE, VimeoUserIE, VimeoWatchLaterIE, VHXEmbedIE, VimmIE, VimmRecordingIE, VimpleIE, VineIE, VineUserIE, VikiIE, VikiChannelIE, ViqeoIE, ViuIE, ViuPlaylistIE, ViuOTTIE, VKIE, VKUserVideosIE, VKWallPostIE, VLiveIE, VLivePostIE, VLiveChannelIE, VodlockerIE, VODPlIE, VODPlatformIE, VoiceRepublicIE, VoicyIE, VoicyChannelIE, VootIE, VootSeriesIE, VoxMediaVolumeIE, VoxMediaIE, VRTIE, VrakIE, VRVIE, VRVSeriesIE, VShareIE, VTMIE, MedialaanIE, VuClipIE, VuploadIE, VVVVIDIE, VVVVIDShowIE, VyboryMosIE, VzaarIE, WakanimIE, WallaIE, WashingtonPostIE, WashingtonPostArticleIE, WASDTVStreamIE, WASDTVRecordIE, WASDTVClipIE, WatIE, WatchBoxIE, WatchIndianPornIE, WDRIE, WDRPageIE, WDRElefantIE, WDRMobileIE, WebcasterIE, WebcasterFeedIE, WebOfStoriesIE, WebOfStoriesPlaylistIE, WeiboIE, WeiboMobileIE, WeiqiTVIE, WikimediaIE, WillowIE, WimTVIE, WhoWatchIE, WistiaIE, WistiaPlaylistIE, WistiaChannelIE, WordpressPlaylistEmbedIE, WordpressMiniAudioPlayerEmbedIE, WorldStarHipHopIE, WPPilotIE, WPPilotChannelsIE, WSJIE, WSJArticleIE, WWEIE, XBefIE, XboxClipsIE, XFileShareIE, XHamsterIE, XHamsterEmbedIE, XHamsterUserIE, XiamiSongIE, XiamiAlbumIE, XiamiArtistIE, XiamiCollectionIE, XimalayaIE, XimalayaAlbumIE, XinpianchangIE, XMinusIE, XNXXIE, XstreamIE, VGTVIE, XTubeUserIE, XTubeIE, XuiteIE, XVideosIE, XXXYMoviesIE, YahooIE, AolIE, YahooSearchIE, YahooGyaOPlayerIE, YahooGyaOIE, YahooJapanNewsIE, YandexDiskIE, YandexMusicTrackIE, YandexMusicAlbumIE, YandexMusicPlaylistIE, YandexMusicArtistTracksIE, YandexMusicArtistAlbumsIE, YandexVideoIE, YandexVideoPreviewIE, ZenYandexIE, ZenYandexChannelIE, YapFilesIE, YesJapanIE, YinYueTaiIE, YleAreenaIE, YnetIE, YouJizzIE, YoukuIE, YoukuShowIE, YouNowLiveIE, YouNowChannelIE, YouNowMomentIE, YouPornIE, YourPornIE, YourUploadIE, ZapiksIE, BBVTVIE, BBVTVLiveIE, BBVTVRecordingsIE, EinsUndEinsTVIE, EinsUndEinsTVLiveIE, EinsUndEinsTVRecordingsIE, EWETVIE, EWETVLiveIE, EWETVRecordingsIE, GlattvisionTVIE, GlattvisionTVLiveIE, GlattvisionTVRecordingsIE, MNetTVIE, MNetTVLiveIE, MNetTVRecordingsIE, NetPlusTVIE, NetPlusTVLiveIE, NetPlusTVRecordingsIE, OsnatelTVIE, OsnatelTVLiveIE, OsnatelTVRecordingsIE, QuantumTVIE, QuantumTVLiveIE, QuantumTVRecordingsIE, SaltTVIE, SaltTVLiveIE, SaltTVRecordingsIE, SAKTVIE, SAKTVLiveIE, SAKTVRecordingsIE, VTXTVIE, VTXTVLiveIE, VTXTVRecordingsIE, WalyTVIE, WalyTVLiveIE, WalyTVRecordingsIE, ZattooIE, ZattooLiveIE, ZattooMoviesIE, ZattooRecordingsIE, ZDFIE, DreiSatIE, ZDFChannelIE, Zee5IE, Zee5SeriesIE, ZeeNewsIE, ZhihuIE, ZingMp3IE, ZingMp3AlbumIE, ZingMp3ChartHomeIE, ZingMp3WeekChartIE, ZingMp3ChartMusicVideoIE, ZingMp3UserIE, ZoomIE, ZypeIE, GenericIE]
