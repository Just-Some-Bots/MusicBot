import logging
import asyncio
import traceback
from typing import Optional
from functools import wraps
from io import StringIO

from discord.ext.commands import Cog, command

from ...utils import _get_variable
from ... import exceptions
from ...wrappers import dev_only

from ... import messagemanager

log = logging.getLogger(__name__)

class Dev(Cog):
    @command()
    @dev_only
    async def breakpoint(self, ctx):
        log.critical("Activating debug breakpoint")
        return

    @command()
    @dev_only
    async def objgraph(self, ctx, *, func:Optional[str]='most_common_types()'):
        import objgraph

        async with ctx.typing():

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

            await messagemanager.safe_send_message(ctx, '```py{}```'.format(data))

    @command()
    @dev_only
    async def debug(self, ctx, *, data: str):
        codeblock = "```py\n{}\n```"
        result = None

        if data.startswith('```') and data.endswith('```'):
            data = '\n'.join(data.rstrip('`\n').split('\n')[1:])

        code = data.strip('` \n')

        try:
            result = await ctx.bot.eval_bot(code)
        except:
            try:
                await ctx.bot.exec_bot(code)
            except Exception as e:
                traceback.print_exc(chain=False)
                await messagemanager.safe_send_message(ctx, "{}: {}".format(type(e).__name__, e))
                return

        if asyncio.iscoroutine(result):
            result = await result

        await messagemanager.safe_send_message(ctx, codeblock.format(result))

cogs = [Dev]