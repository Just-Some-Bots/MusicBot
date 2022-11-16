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

import inspect
from typing import TYPE_CHECKING, Any, Callable

import discord.commands.options
from discord import (
    ApplicationCommand,
    Attachment,
    Option,
    Permissions,
    SlashCommand,
    SlashCommandGroup,
    SlashCommandOptionType,
)

from ...utils import filter_params, find, get
from ..commands import BadArgument
from ..commands import Bot as ExtBot
from ..commands import (
    Command,
    Context,
    Converter,
    Group,
    GuildChannelConverter,
    RoleConverter,
    UserConverter,
)
from ..commands.converter import _convert_to_bool, run_converters

if TYPE_CHECKING:
    from .context import BridgeApplicationContext, BridgeExtContext


__all__ = (
    "BridgeCommand",
    "BridgeCommandGroup",
    "bridge_command",
    "bridge_group",
    "BridgeExtCommand",
    "BridgeSlashCommand",
    "BridgeExtGroup",
    "BridgeSlashGroup",
    "map_to",
    "guild_only",
    "has_permissions",
)


class BridgeSlashCommand(SlashCommand):
    """A subclass of :class:`.SlashCommand` that is used for bridge commands."""

    def __init__(self, func, **kwargs):
        kwargs = filter_params(kwargs, brief="description")
        super().__init__(func, **kwargs)


class BridgeExtCommand(Command):
    """A subclass of :class:`.ext.commands.Command` that is used for bridge commands."""

    def __init__(self, func, **kwargs):
        kwargs = filter_params(kwargs, description="brief")
        super().__init__(func, **kwargs)

    async def transform(self, ctx: Context, param: inspect.Parameter) -> Any:
        if param.annotation is Attachment:
            # skip the parameter checks for bridge attachments
            return await run_converters(ctx, AttachmentConverter, None, param)
        else:
            return await super().transform(ctx, param)


class BridgeSlashGroup(SlashCommandGroup):
    """A subclass of :class:`.SlashCommandGroup` that is used for bridge commands."""

    __slots__ = ("module",)

    def __init__(self, callback, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.callback = callback
        self.__original_kwargs__["callback"] = callback
        self.__command = None

    async def _invoke(self, ctx: BridgeApplicationContext) -> None:
        if not (options := ctx.interaction.data.get("options")):
            if not self.__command:
                self.__command = BridgeSlashCommand(self.callback)
            ctx.command = self.__command
            return await ctx.command.invoke(ctx)
        option = options[0]
        resolved = ctx.interaction.data.get("resolved", None)
        command = find(lambda x: x.name == option["name"], self.subcommands)
        option["resolved"] = resolved
        ctx.interaction.data = option
        await command.invoke(ctx)


class BridgeExtGroup(BridgeExtCommand, Group):
    """A subclass of :class:`.ext.commands.Group` that is used for bridge commands."""


class BridgeCommand:
    """Compatibility class between prefixed-based commands and slash commands.

    Parameters
    ----------
    callback: Callable[[:class:`.BridgeContext`, ...], Awaitable[Any]]
        The callback to invoke when the command is executed. The first argument will be a :class:`BridgeContext`,
        and any additional arguments will be passed to the callback. This callback must be a coroutine.
    parent: Optional[:class:`.BridgeCommandGroup`]:
        Parent of the BridgeCommand.
    kwargs: Optional[Dict[:class:`str`, Any]]
        Keyword arguments that are directly passed to the respective command constructors. (:class:`.SlashCommand` and :class:`.ext.commands.Command`)

    Attributes
    ----------
    slash_variant: :class:`.BridgeSlashCommand`
        The slash command version of this bridge command.
    ext_variant: :class:`.BridgeExtCommand`
        The prefix-based version of this bridge command.
    """

    def __init__(self, callback, **kwargs):
        self.parent = kwargs.pop("parent", None)
        self.slash_variant: BridgeSlashCommand = kwargs.pop(
            "slash_variant", None
        ) or BridgeSlashCommand(callback, **kwargs)
        self.ext_variant: BridgeExtCommand = kwargs.pop(
            "ext_variant", None
        ) or BridgeExtCommand(callback, **kwargs)

    @property
    def name_localizations(self):
        """Dict[:class:`str`, :class:`str`]: Returns name_localizations from :attr:`slash_variant`

        You can edit/set name_localizations directly with

        .. code-block:: python3

            bridge_command.name_localizations["en-UK"] = ...  # or any other locale
            # or
            bridge_command.name_localizations = {"en-UK": ..., "fr-FR": ...}
        """
        return self.slash_variant.name_localizations

    @name_localizations.setter
    def name_localizations(self, value):
        self.slash_variant.name_localizations = value

    @property
    def description_localizations(self):
        """Dict[:class:`str`, :class:`str`]: Returns description_localizations from :attr:`slash_variant`

        You can edit/set description_localizations directly with

        .. code-block:: python3

            bridge_command.description_localizations["en-UK"] = ...  # or any other locale
            # or
            bridge_command.description_localizations = {"en-UK": ..., "fr-FR": ...}
        """
        return self.slash_variant.description_localizations

    @description_localizations.setter
    def description_localizations(self, value):
        self.slash_variant.description_localizations = value

    def add_to(self, bot: ExtBot) -> None:
        """Adds the command to a bot. This method is inherited by :class:`.BridgeCommandGroup`.

        Parameters
        ----------
        bot: Union[:class:`.Bot`, :class:`.AutoShardedBot`]
            The bot to add the command to.
        """
        bot.add_application_command(self.slash_variant)
        bot.add_command(self.ext_variant)

    async def invoke(
        self, ctx: BridgeExtContext | BridgeApplicationContext, /, *args, **kwargs
    ):
        if ctx.is_app:
            return await self.slash_variant.invoke(ctx)
        return await self.ext_variant.invoke(ctx)

    def error(self, coro):
        """A decorator that registers a coroutine as a local error handler.

        This error handler is limited to the command it is defined to.
        However, higher scope handlers (per-cog and global) are still
        invoked afterwards as a catch-all. This handler also functions as
        the handler for both the prefixed and slash versions of the command.

        This error handler takes two parameters, a :class:`.BridgeContext` and
        a :class:`~discord.DiscordException`.

        Parameters
        ----------
        coro: :ref:`coroutine <coroutine>`
            The coroutine to register as the local error handler.

        Raises
        ------
        TypeError
            The coroutine passed is not actually a coroutine.
        """
        self.slash_variant.error(coro)
        self.ext_variant.on_error = coro

        return coro

    def before_invoke(self, coro):
        """A decorator that registers a coroutine as a pre-invoke hook.

        This hook is called directly before the command is called, making
        it useful for any sort of set up required. This hook is called
        for both the prefixed and slash versions of the command.

        This pre-invoke hook takes a sole parameter, a :class:`.BridgeContext`.

        Parameters
        ----------
        coro: :ref:`coroutine <coroutine>`
            The coroutine to register as the pre-invoke hook.

        Raises
        ------
        TypeError
            The coroutine passed is not actually a coroutine.
        """
        self.slash_variant.before_invoke(coro)
        self.ext_variant._before_invoke = coro

        return coro

    def after_invoke(self, coro):
        """A decorator that registers a coroutine as a post-invoke hook.

        This hook is called directly after the command is called, making it
        useful for any sort of clean up required. This hook is called for
        both the prefixed and slash versions of the command.

        This post-invoke hook takes a sole parameter, a :class:`.BridgeContext`.

        Parameters
        ----------
        coro: :ref:`coroutine <coroutine>`
            The coroutine to register as the post-invoke hook.

        Raises
        ------
        TypeError
            The coroutine passed is not actually a coroutine.
        """
        self.slash_variant.after_invoke(coro)
        self.ext_variant._after_invoke = coro

        return coro


class BridgeCommandGroup(BridgeCommand):
    """Compatibility class between prefixed-based commands and slash commands.

    Parameters
    ----------
    callback: Callable[[:class:`.BridgeContext`, ...], Awaitable[Any]]
        The callback to invoke when the command is executed. The first argument will be a :class:`BridgeContext`,
        and any additional arguments will be passed to the callback. This callback must be a coroutine.
    kwargs: Optional[Dict[:class:`str`, Any]]
        Keyword arguments that are directly passed to the respective command constructors. (:class:`.SlashCommand` and :class:`.ext.commands.Command`)

    Attributes
    ----------
    slash_variant: :class:`.SlashCommandGroup`
        The slash command version of this command group.
    ext_variant: :class:`.ext.commands.Group`
        The prefix-based version of this command group.
    subcommands: List[:class:`.BridgeCommand`]
        List of bridge commands in this group
    mapped: Optional[:class:`.SlashCommand`]
        If :func:`map_to` is used, the mapped slash command.
    """

    def __init__(self, callback, *args, **kwargs):
        self.ext_variant: BridgeExtGroup = BridgeExtGroup(callback, *args, **kwargs)
        name = kwargs.pop("name", self.ext_variant.name)
        self.slash_variant: BridgeSlashGroup = BridgeSlashGroup(
            callback, name, *args, **kwargs
        )
        self.subcommands: list[BridgeCommand] = []

        self.mapped: SlashCommand | None = None
        if map_to := getattr(callback, "__custom_map_to__", None):
            kwargs.update(map_to)
            self.mapped = self.slash_variant.command(**kwargs)(callback)

    def command(self, *args, **kwargs):
        """A decorator to register a function as a subcommand.

        Parameters
        ----------
        kwargs: Optional[Dict[:class:`str`, Any]]
            Keyword arguments that are directly passed to the respective command constructors. (:class:`.SlashCommand` and :class:`.ext.commands.Command`)
        """

        def wrap(callback):
            slash = self.slash_variant.command(
                *args,
                **filter_params(kwargs, brief="description"),
                cls=BridgeSlashCommand,
            )(callback)
            ext = self.ext_variant.command(
                *args,
                **filter_params(kwargs, description="brief"),
                cls=BridgeExtCommand,
            )(callback)
            command = BridgeCommand(
                callback, parent=self, slash_variant=slash, ext_variant=ext
            )
            self.subcommands.append(command)
            return command

        return wrap


def bridge_command(**kwargs):
    """A decorator that is used to wrap a function as a bridge command.

    Parameters
    ----------
    kwargs: Optional[Dict[:class:`str`, Any]]
        Keyword arguments that are directly passed to the respective command constructors. (:class:`.SlashCommand` and :class:`.ext.commands.Command`)
    """

    def decorator(callback):
        return BridgeCommand(callback, **kwargs)

    return decorator


def bridge_group(**kwargs):
    """A decorator that is used to wrap a function as a bridge command group.

    Parameters
    ----------
    kwargs: Optional[Dict[:class:`str`, Any]]
        Keyword arguments that are directly passed to the respective command constructors (:class:`.SlashCommandGroup` and :class:`.ext.commands.Group`).
    """

    def decorator(callback):
        return BridgeCommandGroup(callback, **kwargs)

    return decorator


def map_to(name, description=None):
    """To be used with bridge command groups, map the main command to a slash subcommand.

    Parameters
    ----------
    name: :class:`str`
        The new name of the mapped command.
    description: Optional[:class:`str`]
        The new description of the mapped command.

    Example
    -------

    .. code-block:: python3

        @bot.bridge_group()
        @bridge.map_to("show")
        async def config(ctx: BridgeContext):
            ...

        @config.command()
        async def toggle(ctx: BridgeContext):
            ...

    Prefixed commands will not be affected, but slash commands will appear as:

    .. code-block::

        /config show
        /config toggle
    """

    def decorator(callback):
        callback.__custom_map_to__ = {"name": name, "description": description}
        return callback

    return decorator


def guild_only():
    """Intended to work with :class:`.ApplicationCommand` and :class:`BridgeCommand`, adds a :func:`~ext.commands.check`
    that locks the command to only run in guilds, and also registers the command as guild only client-side (on discord).

    Basically a utility function that wraps both :func:`discord.ext.commands.guild_only` and :func:`discord.commands.guild_only`.
    """

    def predicate(func: Callable | ApplicationCommand):
        if isinstance(func, ApplicationCommand):
            func.guild_only = True
        else:
            func.__guild_only__ = True

        from ..commands import guild_only

        return guild_only()(func)

    return predicate


def has_permissions(**perms: dict[str, bool]):
    r"""Intended to work with :class:`.SlashCommand` and :class:`BridgeCommand`, adds a
    :func:`~ext.commands.check` that locks the command to be run by people with certain
    permissions inside guilds, and also registers the command as locked behind said permissions.

    Basically a utility function that wraps both :func:`discord.ext.commands.has_permissions`
    and :func:`discord.commands.default_permissions`.

    Parameters
    ----------
    \*\*perms: Dict[:class:`str`, :class:`bool`]
        An argument list of permissions to check for.
    """

    def predicate(func: Callable | ApplicationCommand):
        from ..commands import has_permissions

        func = has_permissions(**perms)(func)
        Permissions(**perms)
        if isinstance(func, ApplicationCommand):
            func.default_member_permissions = perms
        else:
            func.__default_member_permissions__ = perms

        return perms

    return predicate


class MentionableConverter(Converter):
    """A converter that can convert a mention to a user or a role."""

    async def convert(self, ctx, argument):
        try:
            return await RoleConverter().convert(ctx, argument)
        except BadArgument:
            return await UserConverter().convert(ctx, argument)


class AttachmentConverter(Converter):
    async def convert(self, ctx: Context, arg: str):
        try:
            attach = ctx.message.attachments[0]
        except IndexError:
            raise BadArgument("At least 1 attachment is needed")
        else:
            return attach


BRIDGE_CONVERTER_MAPPING = {
    SlashCommandOptionType.string: str,
    SlashCommandOptionType.integer: int,
    SlashCommandOptionType.boolean: lambda val: _convert_to_bool(str(val)),
    SlashCommandOptionType.user: UserConverter,
    SlashCommandOptionType.channel: GuildChannelConverter,
    SlashCommandOptionType.role: RoleConverter,
    SlashCommandOptionType.mentionable: MentionableConverter,
    SlashCommandOptionType.number: float,
    SlashCommandOptionType.attachment: AttachmentConverter,
}


class BridgeOption(Option, Converter):
    async def convert(self, ctx, argument: str) -> Any:
        try:
            if self.converter is not None:
                converted = await self.converter.convert(ctx, argument)
            else:
                converter = BRIDGE_CONVERTER_MAPPING[self.input_type]
                if issubclass(converter, Converter):
                    converted = await converter().convert(ctx, argument)  # type: ignore # protocol class
                else:
                    converted = converter(argument)

            if self.choices:
                choices_names: list[str | int | float] = [
                    choice.name for choice in self.choices
                ]
                if converted in choices_names and (
                    choice := get(self.choices, name=converted)
                ):
                    converted = choice.value
                else:
                    choices = [choice.value for choice in self.choices]
                    if converted not in choices:
                        raise ValueError(
                            f"{argument} is not a valid choice. Valid choices: {list(set(choices_names + choices))}"
                        )

            return converted
        except ValueError as exc:
            raise BadArgument() from exc


discord.commands.options.Option = BridgeOption
