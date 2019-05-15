from functools import wraps

from . import exceptions
from .utils import _get_variable

# TODO: Add some sort of `denied` argument for a message to send when someone else tries to use it
def owner_only(func):
    @wraps(func)
    async def wrapper(fself, ctx, *args, **kwargs):
        # Only allow the owner to use these commands
        author = ctx.author

        if author.id == ctx.bot.config.owner_id:
            # noinspection PyCallingNonCallable
            return await func(fself, ctx, *args, **kwargs)
        else:
            raise exceptions.PermissionsError("Only the owner can use this command.", expire_in=30)

    return wrapper

def dev_only(func):
    @wraps(func)
    async def wrapper(fself, ctx, *args, **kwargs):
        author = ctx.author

        if str(author.id) in ctx.bot.config.dev_ids:
            # noinspection PyCallingNonCallable
            return await func(fself, ctx, *args, **kwargs)
        else:
            raise exceptions.PermissionsError("Only dev users can use this command.", expire_in=30)

    wrapper.dev_cmd = True
    return wrapper

def ensure_appinfo(func):
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        await self._cache_app_info()
        # noinspection PyCallingNonCallable
        return await func(self, *args, **kwargs)

    return wrapper

def loop_delay(delay):
    def decorator(func):
        @wraps(func)
        async def wrapper(bot, *args, **kwargs):
            return await func(bot, *args, **kwargs)
        wrapper.delay = delay
        if func.__name__.startswith('asyncloop_'):
            return wrapper
        else:
            raise exceptions.WrapperUnmatchedError("'loop_delay' wrapper can only be used on 'asyncloop_' functions")
    return decorator