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

import datetime
from typing import TYPE_CHECKING, Any, Final, Mapping, Protocol, TypeVar, Union

from . import utils
from .colour import Colour

__all__ = (
    "Embed",
    "EmbedField",
)


class _EmptyEmbed:
    def __bool__(self) -> bool:
        return False

    def __repr__(self) -> str:
        return "Embed.Empty"

    def __len__(self) -> int:
        return 0


EmptyEmbed: Final = _EmptyEmbed()


class EmbedProxy:
    def __init__(self, layer: dict[str, Any]):
        self.__dict__.update(layer)

    def __len__(self) -> int:
        return len(self.__dict__)

    def __repr__(self) -> str:
        inner = ", ".join(
            (f"{k}={v!r}" for k, v in self.__dict__.items() if not k.startswith("_"))
        )
        return f"EmbedProxy({inner})"

    def __getattr__(self, attr: str) -> _EmptyEmbed:
        return EmptyEmbed


E = TypeVar("E", bound="Embed")

if TYPE_CHECKING:
    from discord.types.embed import Embed as EmbedData
    from discord.types.embed import EmbedType

    T = TypeVar("T")
    MaybeEmpty = Union[T, _EmptyEmbed]

    class _EmbedFooterProxy(Protocol):
        text: MaybeEmpty[str]
        icon_url: MaybeEmpty[str]

    class _EmbedMediaProxy(Protocol):
        url: MaybeEmpty[str]
        proxy_url: MaybeEmpty[str]
        height: MaybeEmpty[int]
        width: MaybeEmpty[int]

    class _EmbedVideoProxy(Protocol):
        url: MaybeEmpty[str]
        height: MaybeEmpty[int]
        width: MaybeEmpty[int]

    class _EmbedProviderProxy(Protocol):
        name: MaybeEmpty[str]
        url: MaybeEmpty[str]

    class _EmbedAuthorProxy(Protocol):
        name: MaybeEmpty[str]
        url: MaybeEmpty[str]
        icon_url: MaybeEmpty[str]
        proxy_icon_url: MaybeEmpty[str]


class EmbedField:
    """Represents a field on the :class:`Embed` object.

    .. versionadded:: 2.0

    Attributes
    ----------
    name: :class:`str`
        The name of the field.
    value: :class:`str`
        The value of the field.
    inline: :class:`bool`
        Whether the field should be displayed inline.
    """

    def __init__(self, name: str, value: str, inline: bool | None = False):
        self.name = name
        self.value = value
        self.inline = inline

    @classmethod
    def from_dict(cls: type[E], data: Mapping[str, Any]) -> E:
        """Converts a :class:`dict` to a :class:`EmbedField` provided it is in the
        format that Discord expects it to be in.

        You can find out about this format in the `official Discord documentation`__.

        .. _DiscordDocsEF: https://discord.com/developers/docs/resources/channel#embed-object-embed-field-structure

        __ DiscordDocsEF_

        Parameters
        ----------
        data: :class:`dict`
            The dictionary to convert into an EmbedField object.
        """
        self: E = cls.__new__(cls)

        self.name = data["name"]
        self.value = data["value"]
        self.inline = data.get("inline", False)

        return self

    def to_dict(self) -> dict[str, str | bool]:
        """Converts this EmbedField object into a dict.

        Returns
        -------
        Dict[:class:`str`, Union[:class:`str`, :class:`bool`]]
            A dictionary of :class:`str` embed field keys bound to the respective value.
        """
        return {
            "name": self.name,
            "value": self.value,
            "inline": self.inline,
        }


class Embed:
    """Represents a Discord embed.

    .. container:: operations

        .. describe:: len(x)

            Returns the total size of the embed.
            Useful for checking if it's within the 6000 character limit.

        .. describe:: bool(b)

            Returns whether the embed has any data set.

            .. versionadded:: 2.0

    Certain properties return an ``EmbedProxy``, a type
    that acts similar to a regular :class:`dict` except using dotted access,
    e.g. ``embed.author.icon_url``. If the attribute
    is invalid or empty, then a special sentinel value is returned,
    :attr:`Embed.Empty`.

    For ease of use, all parameters that expect a :class:`str` are implicitly
    cast to :class:`str` for you.

    Attributes
    ----------
    title: :class:`str`
        The title of the embed.
        This can be set during initialisation.
        Must be 256 characters or fewer.
    type: :class:`str`
        The type of embed. Usually "rich".
        This can be set during initialisation.
        Possible strings for embed types can be found on discord's
        `api docs <https://discord.com/developers/docs/resources/channel#embed-object-embed-types>`_
    description: :class:`str`
        The description of the embed.
        This can be set during initialisation.
        Must be 4096 characters or fewer.
    url: :class:`str`
        The URL of the embed.
        This can be set during initialisation.
    timestamp: :class:`datetime.datetime`
        The timestamp of the embed content. This is an aware datetime.
        If a naive datetime is passed, it is converted to an aware
        datetime with the local timezone.
    colour: Union[:class:`Colour`, :class:`int`]
        The colour code of the embed. Aliased to ``color`` as well.
        This can be set during initialisation.
    Empty
        A special sentinel value used by ``EmbedProxy`` and this class
        to denote that the value or attribute is empty.
    """

    __slots__ = (
        "title",
        "url",
        "type",
        "_timestamp",
        "_colour",
        "_footer",
        "_image",
        "_thumbnail",
        "_video",
        "_provider",
        "_author",
        "_fields",
        "description",
    )

    Empty: Final = EmptyEmbed

    def __init__(
        self,
        *,
        colour: int | Colour | _EmptyEmbed = EmptyEmbed,
        color: int | Colour | _EmptyEmbed = EmptyEmbed,
        title: MaybeEmpty[Any] = EmptyEmbed,
        type: EmbedType = "rich",
        url: MaybeEmpty[Any] = EmptyEmbed,
        description: MaybeEmpty[Any] = EmptyEmbed,
        timestamp: datetime.datetime = None,
        fields: list[EmbedField] | None = None,
    ):

        self.colour = colour if colour is not EmptyEmbed else color
        self.title = title
        self.type = type
        self.url = url
        self.description = description

        if self.title is not EmptyEmbed and self.title is not None:
            self.title = str(self.title)

        if self.description is not EmptyEmbed and self.description is not None:
            self.description = str(self.description)

        if self.url is not EmptyEmbed and self.url is not None:
            self.url = str(self.url)

        if timestamp:
            self.timestamp = timestamp
        self._fields: list[EmbedField] = fields or []

    @classmethod
    def from_dict(cls: type[E], data: Mapping[str, Any]) -> E:
        """Converts a :class:`dict` to a :class:`Embed` provided it is in the
        format that Discord expects it to be in.

        You can find out about this format in the `official Discord documentation`__.

        .. _DiscordDocs: https://discord.com/developers/docs/resources/channel#embed-object

        __ DiscordDocs_

        Parameters
        ----------
        data: :class:`dict`
            The dictionary to convert into an embed.

        Returns
        -------
        :class:`Embed`
            The converted embed object.
        """
        # we are bypassing __init__ here since it doesn't apply here
        self: E = cls.__new__(cls)

        # fill in the basic fields

        self.title = data.get("title", EmptyEmbed)
        self.type = data.get("type", EmptyEmbed)
        self.description = data.get("description", EmptyEmbed)
        self.url = data.get("url", EmptyEmbed)

        if self.title is not EmptyEmbed:
            self.title = str(self.title)

        if self.description is not EmptyEmbed:
            self.description = str(self.description)

        if self.url is not EmptyEmbed:
            self.url = str(self.url)

        # try to fill in the more rich fields

        try:
            self._colour = Colour(value=data["color"])
        except KeyError:
            pass

        try:
            self._timestamp = utils.parse_time(data["timestamp"])
        except KeyError:
            pass

        for attr in (
            "thumbnail",
            "video",
            "provider",
            "author",
            "fields",
            "image",
            "footer",
        ):
            if attr == "fields":
                value = data.get(attr, [])
                self._fields = [EmbedField.from_dict(d) for d in value] if value else []
            else:
                try:
                    value = data[attr]
                except KeyError:
                    continue
                else:
                    setattr(self, f"_{attr}", value)

        return self

    def copy(self: E) -> E:
        """Creates a shallow copy of the :class:`Embed` object.

        Returns
        -------
        :class:`Embed`
            The copied embed object.
        """
        return self.__class__.from_dict(self.to_dict())

    def __len__(self) -> int:
        total = len(self.title) + len(self.description)
        for field in getattr(self, "_fields", []):
            total += len(field.name) + len(field.value)

        try:
            footer_text = self._footer["text"]
        except (AttributeError, KeyError):
            pass
        else:
            total += len(footer_text)

        try:
            author = self._author
        except AttributeError:
            pass
        else:
            total += len(author["name"])

        return total

    def __bool__(self) -> bool:
        return any(
            (
                self.title,
                self.url,
                self.description,
                self.colour,
                self.fields,
                self.timestamp,
                self.author,
                self.thumbnail,
                self.footer,
                self.image,
                self.provider,
                self.video,
            )
        )

    @property
    def colour(self) -> MaybeEmpty[Colour]:
        return getattr(self, "_colour", EmptyEmbed)

    @colour.setter
    def colour(self, value: int | Colour | _EmptyEmbed):  # type: ignore
        if isinstance(value, (Colour, _EmptyEmbed)):
            self._colour = value
        elif isinstance(value, int):
            self._colour = Colour(value=value)
        else:
            raise TypeError(
                f"Expected discord.Colour, int, or Embed.Empty but received {value.__class__.__name__} instead."
            )

    color = colour

    @property
    def timestamp(self) -> MaybeEmpty[datetime.datetime]:
        return getattr(self, "_timestamp", EmptyEmbed)

    @timestamp.setter
    def timestamp(self, value: MaybeEmpty[datetime.datetime]):
        if isinstance(value, datetime.datetime):
            if value.tzinfo is None:
                value = value.astimezone()
            self._timestamp = value
        elif isinstance(value, _EmptyEmbed):
            self._timestamp = value
        else:
            raise TypeError(
                f"Expected datetime.datetime or Embed.Empty received {value.__class__.__name__} instead"
            )

    @property
    def footer(self) -> _EmbedFooterProxy:
        """Returns an ``EmbedProxy`` denoting the footer contents.

        See :meth:`set_footer` for possible values you can access.

        If the attribute has no value then :attr:`Empty` is returned.
        """
        return EmbedProxy(getattr(self, "_footer", {}))  # type: ignore

    def set_footer(
        self: E,
        *,
        text: MaybeEmpty[Any] = EmptyEmbed,
        icon_url: MaybeEmpty[Any] = EmptyEmbed,
    ) -> E:
        """Sets the footer for the embed content.

        This function returns the class instance to allow for fluent-style
        chaining.

        Parameters
        ----------
        text: :class:`str`
            The footer text.
            Must be 2048 characters or fewer.
        icon_url: :class:`str`
            The URL of the footer icon. Only HTTP(S) is supported.
        """

        self._footer = {}
        if text is not EmptyEmbed:
            self._footer["text"] = str(text)

        if icon_url is not EmptyEmbed:
            self._footer["icon_url"] = str(icon_url)

        return self

    def remove_footer(self: E) -> E:
        """Clears embed's footer information.

        This function returns the class instance to allow for fluent-style
        chaining.

        .. versionadded:: 2.0
        """
        try:
            del self._footer
        except AttributeError:
            pass

        return self

    @property
    def image(self) -> _EmbedMediaProxy:
        """Returns an ``EmbedProxy`` denoting the image contents.

        Possible attributes you can access are:

        - ``url``
        - ``proxy_url``
        - ``width``
        - ``height``

        If the attribute has no value then :attr:`Empty` is returned.
        """
        return EmbedProxy(getattr(self, "_image", {}))  # type: ignore

    def set_image(self: E, *, url: MaybeEmpty[Any]) -> E:
        """Sets the image for the embed content.

        This function returns the class instance to allow for fluent-style
        chaining.

        .. versionchanged:: 1.4
            Passing :attr:`Empty` removes the image.

        Parameters
        ----------
        url: :class:`str`
            The source URL for the image. Only HTTP(S) is supported.
        """

        if url is EmptyEmbed:
            try:
                del self._image
            except AttributeError:
                pass
        else:
            self._image = {
                "url": str(url),
            }

        return self

    def remove_image(self: E) -> E:
        """Removes the embed's image.

        This function returns the class instance to allow for fluent-style
        chaining.

        .. versionadded:: 2.0
        """
        try:
            del self._image
        except AttributeError:
            pass

        return self

    @property
    def thumbnail(self) -> _EmbedMediaProxy:
        """Returns an ``EmbedProxy`` denoting the thumbnail contents.

        Possible attributes you can access are:

        - ``url``
        - ``proxy_url``
        - ``width``
        - ``height``

        If the attribute has no value then :attr:`Empty` is returned.
        """
        return EmbedProxy(getattr(self, "_thumbnail", {}))  # type: ignore

    def set_thumbnail(self: E, *, url: MaybeEmpty[Any]) -> E:
        """Sets the thumbnail for the embed content.

        This function returns the class instance to allow for fluent-style
        chaining.

        .. versionchanged:: 1.4
            Passing :attr:`Empty` removes the thumbnail.

        Parameters
        ----------
        url: :class:`str`
            The source URL for the thumbnail. Only HTTP(S) is supported.
        """

        if url is EmptyEmbed:
            try:
                del self._thumbnail
            except AttributeError:
                pass
        else:
            self._thumbnail = {
                "url": str(url),
            }

        return self

    def remove_thumbnail(self: E) -> E:
        """Removes the embed's thumbnail.

        This function returns the class instance to allow for fluent-style
        chaining.

        .. versionadded:: 2.0
        """
        try:
            del self._thumbnail
        except AttributeError:
            pass

        return self

    @property
    def video(self) -> _EmbedVideoProxy:
        """Returns an ``EmbedProxy`` denoting the video contents.

        Possible attributes include:

        - ``url`` for the video URL.
        - ``height`` for the video height.
        - ``width`` for the video width.

        If the attribute has no value then :attr:`Empty` is returned.
        """
        return EmbedProxy(getattr(self, "_video", {}))  # type: ignore

    @property
    def provider(self) -> _EmbedProviderProxy:
        """Returns an ``EmbedProxy`` denoting the provider contents.

        The only attributes that might be accessed are ``name`` and ``url``.

        If the attribute has no value then :attr:`Empty` is returned.
        """
        return EmbedProxy(getattr(self, "_provider", {}))  # type: ignore

    @property
    def author(self) -> _EmbedAuthorProxy:
        """Returns an ``EmbedProxy`` denoting the author contents.

        See :meth:`set_author` for possible values you can access.

        If the attribute has no value then :attr:`Empty` is returned.
        """
        return EmbedProxy(getattr(self, "_author", {}))  # type: ignore

    def set_author(
        self: E,
        *,
        name: Any,
        url: MaybeEmpty[Any] = EmptyEmbed,
        icon_url: MaybeEmpty[Any] = EmptyEmbed,
    ) -> E:
        """Sets the author for the embed content.

        This function returns the class instance to allow for fluent-style
        chaining.

        Parameters
        ----------
        name: :class:`str`
            The name of the author.
            Must be 256 characters or fewer.
        url: :class:`str`
            The URL for the author.
        icon_url: :class:`str`
            The URL of the author icon. Only HTTP(S) is supported.
        """

        self._author = {
            "name": str(name),
        }

        if url is not EmptyEmbed:
            self._author["url"] = str(url)

        if icon_url is not EmptyEmbed:
            self._author["icon_url"] = str(icon_url)

        return self

    def remove_author(self: E) -> E:
        """Clears embed's author information.

        This function returns the class instance to allow for fluent-style
        chaining.

        .. versionadded:: 1.4
        """
        try:
            del self._author
        except AttributeError:
            pass

        return self

    @property
    def fields(self) -> list[EmbedField]:
        """Returns a :class:`list` of :class:`EmbedField` objects denoting the field contents.

        See :meth:`add_field` for possible values you can access.

        If the attribute has no value then ``None`` is returned.
        """
        return self._fields

    @fields.setter
    def fields(self, value: list[EmbedField]) -> None:
        """Sets the fields for the embed. This overwrites any existing fields.

        Parameters
        ----------
        value: List[:class:`EmbedField`]
            The list of :class:`EmbedField` objects to include in the embed.
        """
        if not all(isinstance(x, EmbedField) for x in value):
            raise TypeError("Expected a list of EmbedField objects.")

        self._fields = value

    def append_field(self, field: EmbedField) -> None:
        """Appends an :class:`EmbedField` object to the embed.

        .. versionadded:: 2.0

        Parameters
        ----------
        field: :class:`EmbedField`
            The field to add.
        """
        if not isinstance(field, EmbedField):
            raise TypeError("Expected an EmbedField object.")

        self._fields.append(field)

    def add_field(self: E, *, name: str, value: str, inline: bool = True) -> E:
        """Adds a field to the embed object.

        This function returns the class instance to allow for fluent-style
        chaining. There must be 25 fields or fewer.

        Parameters
        ----------
        name: :class:`str`
            The name of the field.
            Must be 256 characters or fewer.
        value: :class:`str`
            The value of the field.
            Must be 1024 characters or fewer.
        inline: :class:`bool`
            Whether the field should be displayed inline.
        """
        self._fields.append(EmbedField(name=str(name), value=str(value), inline=inline))

        return self

    def insert_field_at(
        self: E, index: int, *, name: Any, value: Any, inline: bool = True
    ) -> E:
        """Inserts a field before a specified index to the embed.

        This function returns the class instance to allow for fluent-style
        chaining. There must be 25 fields or fewer.

        .. versionadded:: 1.2

        Parameters
        ----------
        index: :class:`int`
            The index of where to insert the field.
        name: :class:`str`
            The name of the field.
            Must be 256 characters or fewer.
        value: :class:`str`
            The value of the field.
            Must be 1024 characters or fewer.
        inline: :class:`bool`
            Whether the field should be displayed inline.
        """

        field = EmbedField(name=str(name), value=str(value), inline=inline)

        self._fields.insert(index, field)

        return self

    def clear_fields(self) -> None:
        """Removes all fields from this embed."""
        self._fields.clear()

    def remove_field(self, index: int) -> None:
        """Removes a field at a specified index.

        If the index is invalid or out of bounds then the error is
        silently swallowed.

        .. note::

            When deleting a field by index, the index of the other fields
            shift to fill the gap just like a regular list.

        Parameters
        ----------
        index: :class:`int`
            The index of the field to remove.
        """
        try:
            del self._fields[index]
        except IndexError:
            pass

    def set_field_at(
        self: E, index: int, *, name: Any, value: Any, inline: bool = True
    ) -> E:
        """Modifies a field to the embed object.

        The index must point to a valid pre-existing field. There must be 25 fields or fewer.

        This function returns the class instance to allow for fluent-style
        chaining.

        Parameters
        ----------
        index: :class:`int`
            The index of the field to modify.
        name: :class:`str`
            The name of the field.
            Must be 256 characters or fewer.
        value: :class:`str`
            The value of the field.
            Must be 1024 characters or fewer.
        inline: :class:`bool`
            Whether the field should be displayed inline.

        Raises
        ------
        IndexError
            An invalid index was provided.
        """

        try:
            field = self._fields[index]
        except (TypeError, IndexError):
            raise IndexError("field index out of range")

        field.name = str(name)
        field.value = str(value)
        field.inline = inline
        return self

    def to_dict(self) -> EmbedData:
        """Converts this embed object into a dict.

        Returns
        -------
        Dict[:class:`str`, Union[:class:`str`, :class:`int`, :class:`bool`]]
            A dictionary of :class:`str` embed keys bound to the respective value.
        """

        # add in the raw data into the dict
        result = {
            key[1:]: getattr(self, key)
            for key in self.__slots__
            if key != "_fields" and key[0] == "_" and hasattr(self, key)
        }

        # add in the fields
        result["fields"] = [field.to_dict() for field in self._fields]

        # deal with basic convenience wrappers

        try:
            colour = result.pop("colour")
        except KeyError:
            pass
        else:
            if colour:
                result["color"] = colour.value

        try:
            timestamp = result.pop("timestamp")
        except KeyError:
            pass
        else:
            if timestamp:
                if timestamp.tzinfo:
                    result["timestamp"] = timestamp.astimezone(
                        tz=datetime.timezone.utc
                    ).isoformat()
                else:
                    result["timestamp"] = timestamp.replace(
                        tzinfo=datetime.timezone.utc
                    ).isoformat()

        # add in the non-raw attribute ones
        if self.type:
            result["type"] = self.type

        if self.description:
            result["description"] = self.description

        if self.url:
            result["url"] = self.url

        if self.title:
            result["title"] = self.title

        return result  # type: ignore
