from __future__ import annotations

import asyncio
import os
import sys
import traceback
import time
from functools import partial
from itertools import groupby
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Callable

from .input_text import InputText

__all__ = (
    "Modal",
    "ModalStore",
)


if TYPE_CHECKING:
    from ..interactions import Interaction
    from ..state import ConnectionState


class Modal:
    """Represents a UI Modal dialog.

    This object must be inherited to create a UI within Discord.

    .. versionadded:: 2.0

    Parameters
    ----------
    children: :class:`InputText`
        The initial InputText fields that are displayed in the modal dialog.
    title: :class:`str`
        The title of the modal dialog.
        Must be 45 characters or fewer.
    custom_id: Optional[:class:`str`]
        The ID of the modal dialog that gets received during an interaction.
        Must be 100 characters or fewer.
    timeout: Optional[:class:`float`]
        Timeout in seconds from last interaction with the UI before no longer accepting input.
        If ``None`` then there is no timeout.
    """

    def __init__(self, *children: InputText, title: str, custom_id: Optional[str] = None,
                 timeout: Optional[float] = None) -> None:
        self.timeout: Optional[float] = timeout
        if not isinstance(custom_id, str) and custom_id is not None:
            raise TypeError(f"expected custom_id to be str, not {custom_id.__class__.__name__}")
        self._custom_id: Optional[str] = custom_id or os.urandom(16).hex()
        if len(title) > 45:
            raise ValueError("title must be 45 characters or fewer")
        self._title = title
        self._children: List[InputText] = list(children)
        self._weights = _ModalWeights(self._children)
        loop = asyncio.get_running_loop()
        self._stopped: asyncio.Future[bool] = loop.create_future()
        self.__cancel_callback: Optional[Callable[[Modal], None]] = None
        self.__timeout_expiry: Optional[float] = None
        self.__timeout_task: Optional[asyncio.Task[None]] = None
        self.loop = asyncio.get_event_loop()

    def _start_listening_from_store(self, store: ModalStore) -> None:
        self.__cancel_callback = partial(store.remove_modal)
        if self.timeout:
            loop = asyncio.get_running_loop()
            if self.__timeout_task is not None:
                self.__timeout_task.cancel()

            self.__timeout_expiry = time.monotonic() + self.timeout
            self.__timeout_task = loop.create_task(self.__timeout_task_impl())

    async def __timeout_task_impl(self) -> None:
        while True:
            # Guard just in case someone changes the value of the timeout at runtime
            if self.timeout is None:
                return

            if self.__timeout_expiry is None:
                return self._dispatch_timeout()

            # Check if we've elapsed our currently set timeout
            now = time.monotonic()
            if now >= self.__timeout_expiry:
                return self._dispatch_timeout()

            # Wait N seconds to see if timeout data has been refreshed
            await asyncio.sleep(self.__timeout_expiry - now)

    @property
    def _expires_at(self) -> Optional[float]:
        if self.timeout:
            return time.monotonic() + self.timeout
        return None

    def _dispatch_timeout(self):
        if self._stopped.done():
            return

        self._stopped.set_result(True)
        self.loop.create_task(self.on_timeout(), name=f"discord-ui-view-timeout-{self.id}")

    @property
    def title(self) -> str:
        """The title of the modal dialog."""
        return self._title

    @title.setter
    def title(self, value: str):
        if len(value) > 45:
            raise ValueError("title must be 45 characters or fewer")
        if not isinstance(value, str):
            raise TypeError(f"expected title to be str, not {value.__class__.__name__}")
        self._title = value

    @property
    def children(self) -> List[InputText]:
        """The child components associated with the modal dialog."""
        return self._children

    @children.setter
    def children(self, value: List[InputText]):
        for item in value:
            if not isinstance(item, InputText):
                raise TypeError(f"all Modal children must be InputText, not {item.__class__.__name__}")
        self._weights = _ModalWeights(self._children)
        self._children = value

    @property
    def custom_id(self) -> str:
        """The ID of the modal dialog that gets received during an interaction."""
        return self._custom_id

    @custom_id.setter
    def custom_id(self, value: str):
        if not isinstance(value, str):
            raise TypeError(f"expected custom_id to be str, not {value.__class__.__name__}")
        if len(value) > 100:
            raise ValueError("custom_id must be 100 characters or fewer")
        self._custom_id = value

    async def callback(self, interaction: Interaction):
        """|coro|

        The coroutine that is called when the modal dialog is submitted.
        Should be overridden to handle the values submitted by the user.

        Parameters
        -----------
        interaction: :class:`~discord.Interaction`
            The interaction that submitted the modal dialog.
        """
        self.stop()

    def to_components(self) -> List[Dict[str, Any]]:
        def key(item: InputText) -> int:
            return item._rendered_row or 0

        children = sorted(self._children, key=key)
        components: List[Dict[str, Any]] = []
        for _, group in groupby(children, key=key):
            children = [item.to_component_dict() for item in group]
            if not children:
                continue

            components.append(
                {
                    "type": 1,
                    "components": children,
                }
            )

        return components

    def add_item(self, item: InputText):
        """Adds an InputText component to the modal dialog.

        Parameters
        ----------
        item: :class:`InputText`
            The item to add to the modal dialog
        """

        if len(self._children) > 5:
            raise ValueError("You can only have up to 5 items in a modal dialog.")

        if not isinstance(item, InputText):
            raise TypeError(f"expected InputText not {item.__class__!r}")

        self._weights.add_item(item)
        self._children.append(item)

    def remove_item(self, item: InputText):
        """Removes an InputText component from the modal dialog.

        Parameters
        ----------
        item: :class:`InputText`
            The item to remove from the modal dialog.
        """
        try:
            self._children.remove(item)
        except ValueError:
            pass

    def stop(self) -> None:
        """Stops listening to interaction events from the modal dialog."""
        if not self._stopped.done():
            self._stopped.set_result(True)
        self.__timeout_expiry = None
        if self.__timeout_task is not None:
            self.__timeout_task.cancel()
            self.__timeout_task = None

    async def wait(self) -> bool:
        """Waits for the modal dialog to be submitted."""
        return await self._stopped

    def to_dict(self):
        return {
            "title": self.title,
            "custom_id": self.custom_id,
            "components": self.to_components(),
        }

    async def on_error(self, error: Exception, interaction: Interaction) -> None:
        """|coro|

        A callback that is called when the modal's callback fails with an error.

        The default implementation prints the traceback to stderr.

        Parameters
        -----------
        error: :class:`Exception`
            The exception that was raised.
        interaction: :class:`~discord.Interaction`
            The interaction that led to the failure.
        """
        print(f"Ignoring exception in modal {self}:", file=sys.stderr)
        traceback.print_exception(error.__class__, error, error.__traceback__, file=sys.stderr)

    async def on_timeout(self) -> None:
        """|coro|

        A callback that is called when a modal's timeout elapses without being explicitly stopped.
        """
        pass


class _ModalWeights:
    __slots__ = ("weights",)

    def __init__(self, children: List[InputText]):
        self.weights: List[int] = [0, 0, 0, 0, 0]

        key = lambda i: sys.maxsize if i.row is None else i.row
        children = sorted(children, key=key)
        for row, group in groupby(children, key=key):
            for item in group:
                self.add_item(item)

    def find_open_space(self, item: InputText) -> int:
        for index, weight in enumerate(self.weights):
            if weight + item.width <= 5:
                return index

        raise ValueError("could not find open space for item")

    def add_item(self, item: InputText) -> None:
        if item.row is not None:
            total = self.weights[item.row] + item.width
            if total > 5:
                raise ValueError(f"item would not fit at row {item.row} ({total} > 5 width)")
            self.weights[item.row] = total
            item._rendered_row = item.row
        else:
            index = self.find_open_space(item)
            self.weights[index] += item.width
            item._rendered_row = index

    def remove_item(self, item: InputText) -> None:
        if item._rendered_row is not None:
            self.weights[item._rendered_row] -= item.width
            item._rendered_row = None

    def clear(self) -> None:
        self.weights = [0, 0, 0, 0, 0]


class ModalStore:
    def __init__(self, state: ConnectionState) -> None:
        # (user_id, custom_id) : Modal
        self._modals: Dict[Tuple[int, str], Modal] = {}
        self._state: ConnectionState = state

    def add_modal(self, modal: Modal, user_id: int):
        self._modals[(user_id, modal.custom_id)] = modal
        modal._start_listening_from_store(self)

    def remove_modal(self, modal: Modal, user_id):
        modal.stop()
        self._modals.pop((user_id, modal.custom_id))

    async def dispatch(self, user_id: int, custom_id: str, interaction: Interaction):
        key = (user_id, custom_id)
        value = self._modals.get(key)
        if value is None:
            return

        try:
            components = [
                component
                for parent_component in interaction.data["components"]
                for component in parent_component["components"]
            ]
            for component in components:
                for child in value.children:
                    if child.custom_id == component["custom_id"]:  # type: ignore
                        child.refresh_state(component)
                        break
            await value.callback(interaction)
            self.remove_modal(value, user_id)
        except Exception as e:
            return await value.on_error(e, interaction)
