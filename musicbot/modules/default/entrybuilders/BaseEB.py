class BaseEB:
    def __init__(self, bot):
        self.bot = bot

    async def suitable(self, ctx, url):
        '''
        figure out if EB is suitable for the given context and url
        '''
        raise NotImplementedError()

    async def get_entry(self, ctx, url, process = True):
        '''
        get entry (or entries) for given url
        return tuple of length 2 or None
        first value represents expected number of entries
        # IF PY35 DEPRECATED
        # second value is an async iterable that yield entries/Nones
        second value is an awaitable returning list containing 
        1. awaitables each returning an entry or 
        2. None
        # END IF DEPRECATED
        '''
        raise NotImplementedError()