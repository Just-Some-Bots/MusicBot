from .BaseEB import BaseEB
from urllib.parse import urlparse, urljoin
import re
import os

from ....ytdldownloader import get_local_entry

class LocalEB(BaseEB):
    @classmethod
    async def _get_entry_iterator(cls, ctx, path):
        # IF PY35 DEPRECATED
        # yield await get_local_entry(path, ctx.author.id, {'channel_id':ctx.channel.id})
        return [get_local_entry(path, ctx.author.id, {'channel_id':ctx.channel.id})]
        # END IF DEPRECATED

    @classmethod
    async def suitable(cls, ctx, url):
        if not (ctx.bot.config.local and ctx.bot.permissions.for_user(ctx.author).allow_locals):
            return False

        # remove windows drive letter
        url = re.sub(r'([A-Z]:)', '', url)

        # changes backward slashes to forward slashes
        url = url.replace('\\', '/')

        parsed = urlparse(url)
        
        if parsed.query or parsed.fragment or parsed.scheme not in ['file', '']:
            return False
        
        # hopefully there won't be anyone who use dot as the root folder
        if len(parsed.path) > 1 and '.' in parsed.path.split('/'):
            return False

        return True

    @classmethod
    async def get_entry(cls, ctx, url):
        '''
        get entry (or entries) for given url
        '''
        if not ctx.bot.config.local_dir_only:
            _path = [url]
        else:
            _path = [urljoin(d, url) for d in ctx.bot.config.local_dir]

        _good_path = [path for path in _path if os.path.exists(path)]

        if _good_path:
            # @TheerapakG: TODO: show ambiguity
            return (1, LocalEB._get_entry_iterator(ctx, _good_path[0]))

        return None