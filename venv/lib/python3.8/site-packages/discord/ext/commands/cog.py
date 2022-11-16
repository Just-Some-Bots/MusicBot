"""
The MIT License (MIT)

Copyright (c) 2015-2021 Rapptz
Copyright (c) 2021-present Pycord Development

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Generator, TypeVar

import discord

from ...cog import Cog
from ...commands import ApplicationCommand, SlashCommandGroup

if TYPE_CHECKING:
    from .core import Command

__all__ = ("Cog",)

CogT = TypeVar("CogT", bound="Cog")
FuncT = TypeVar("FuncT", bound=Callable[..., Any])

MISSING: Any = discord.utils.MISSING


class Cog(Cog):
    def __new__(cls: type[CogT], *args: Any, **kwargs: Any) -> CogT:
        # For issue 426, we need to store a copy of the command objects
        # since we modify them to inject `self` to them.
        # To do this, we need to interfere with the Cog creation process.
        return super().__new__(cls)

    def walk_commands(self) -> Generator[Command, None, None]:
        """An iterator that recursively walks through this cog's commands and subcommands.

        Yields
        ------
        Union[:class:`.Command`, :class:`.Group`]
            A command or group from the cog.
        """
        from .core import GroupMixin

        for command in self.__cog_commands__:
            if not isinstance(command, ApplicationCommand):
                if command.parent is None:
                    yield command
                    if isinstance(command, GroupMixin):
                        yield from command.walk_commands()
            elif isinstance(command, SlashCommandGroup):
                yield from command.walk_commands()
            else:
                yield command

    def get_commands(self) -> list[ApplicationCommand | Command]:
        r"""
        Returns
        --------
        List[Union[:class:`~discord.ApplicationCommand`, :class:`.Command`]]
            A :class:`list` of commands that are defined inside this cog.

            .. note::

                This does not include subcommands.
        """
        return [c for c in self.__cog_commands__ if c.parent is None]
