import contextlib

from pluggy import HookimplMarker

import keyring
from keyring.errors import KeyringError


hookimpl = HookimplMarker("devpiclient")


# https://github.com/jaraco/jaraco.context/blob/c3a9b739/jaraco/context.py#L205
suppress = type('suppress', (contextlib.suppress, contextlib.ContextDecorator), {})


@hookimpl()
@suppress(KeyringError)
def devpiclient_get_password(url, username):
    return keyring.get_password(url, username)
