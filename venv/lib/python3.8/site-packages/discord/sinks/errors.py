"""
The MIT License (MIT)

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
from discord.errors import DiscordException


class SinkException(DiscordException):
    """Raised when a Sink error occurs.

    .. versionadded:: 2.0
    """


class RecordingException(SinkException):
    """Exception that's thrown when there is an error while trying to record
    audio from a voice channel.

    .. versionadded:: 2.0
    """


class MP3SinkError(SinkException):
    """Exception thrown when an exception occurs with :class:`MP3Sink`

    .. versionadded:: 2.0
    """


class MP4SinkError(SinkException):
    """Exception thrown when an exception occurs with :class:`MP4Sink`

    .. versionadded:: 2.0
    """


class OGGSinkError(SinkException):
    """Exception thrown when an exception occurs with :class:`OGGSink`

    .. versionadded:: 2.0
    """


class MKVSinkError(SinkException):
    """Exception thrown when an exception occurs with :class:`MKVSink`

    .. versionadded:: 2.0
    """


class WaveSinkError(SinkException):
    """Exception thrown when an exception occurs with :class:`WaveSink`

    .. versionadded:: 2.0
    """


class M4ASinkError(SinkException):
    """Exception thrown when an exception occurs with :class:`M4ASink`

    .. versionadded:: 2.0
    """


class MKASinkError(SinkException):
    """Exception thrown when an exception occurs with :class:`MKASink`

    .. versionadded:: 2.0
    """
