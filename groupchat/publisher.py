"""One fresh authorization check per update. No cached summary may be retried."""

import logging
from collections.abc import Awaitable, Callable

from groupchat.api import API, APIError
from groupchat.render import render

LOG = logging.getLogger(__name__)


class Publisher:
    def __init__(self, api: API):
        self.api = api
        self.last: str | None = None

    async def update(
        self, negotiation: str, channel: str, send: Callable[[str], Awaitable[None]]
    ) -> bool:
        """Return False to stop watching; never explain a denial to the room."""
        try:
            data = await self.api.summary(negotiation, channel)
            text = render(data, negotiation)
        except APIError:
            LOG.warning("Channel update stopped: API unavailable or unauthorized.")
            return False
        except (ValueError, KeyError, TypeError, OverflowError):
            LOG.warning("Channel update stopped: invalid summary.")
            return False
        if text != self.last:
            await send(text)
            self.last = text
        return data["status"] not in {"converged", "failed", "expired", "cancelled"}
