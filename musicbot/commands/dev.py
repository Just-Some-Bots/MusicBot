import logging
import asyncio
import traceback
from functools import wraps
from io import StringIO

from ..utils import _get_variable
from .. import exceptions
from ..constructs import Response

log = logging.getLogger(__name__)

cog_name = 'dev'

# @TheerapakG: TODO: move wrappers into one place
def dev_only(func):
        @wraps(func)
        async def wrapper(bot, *args, **kwargs):
            orig_msg = _get_variable('message')

            if str(orig_msg.author.id) in bot.config.dev_ids:
                # noinspection PyCallingNonCallable
                return await func(bot, *args, **kwargs)
            else:
                raise exceptions.PermissionsError("Only dev users can use this command.", expire_in=30)

        wrapper.dev_cmd = True
        return wrapper

@dev_only
async def cmd_breakpoint(bot, message):
    log.critical("Activating debug breakpoint")
    return

@dev_only
async def cmd_objgraph(bot, channel, func='most_common_types()'):
    import objgraph

    await bot.send_typing(channel)

    if func == 'growth':
        f = StringIO()
        objgraph.show_growth(limit=10, file=f)
        f.seek(0)
        data = f.read()
        f.close()

    elif func == 'leaks':
        f = StringIO()
        objgraph.show_most_common_types(objects=objgraph.get_leaking_objects(), file=f)
        f.seek(0)
        data = f.read()
        f.close()

    elif func == 'leakstats':
        data = objgraph.typestats(objects=objgraph.get_leaking_objects())

    else:
        data = eval('objgraph.' + func)

    return Response(data, codeblock='py')

@dev_only
async def cmd_debug(bot, message, _player, *, data):
    codeblock = "```py\n{}\n```"
    result = None

    if data.startswith('```') and data.endswith('```'):
        data = '\n'.join(data.rstrip('`\n').split('\n')[1:])

    code = data.strip('` \n')

    try:
        result = eval(code)
    except:
        try:
            exec(code)
        except Exception as e:
            traceback.print_exc(chain=False)
            return Response("{}: {}".format(type(e).__name__, e))

    if asyncio.iscoroutine(result):
        result = await result

    return Response(codeblock.format(result))