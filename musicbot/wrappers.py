from functools import wraps

from . import exceptions
from .utils import _get_variable

# TODO: Add some sort of `denied` argument for a message to send when someone else tries to use it
def owner_only(func):
    @wraps(func)
    async def wrapper(fself, ctx, *args, **kwargs):
        # Only allow the owner to use these commands
        author = ctx.author

        if author.id in ctx.bot.config.owner_id:
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