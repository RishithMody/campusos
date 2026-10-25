"""One fresh authorization check per update. No cached summary may be retried.

**The timing limit, stated plainly.** Authorization lives in the backend; the post lives
in Discord. Between the moment `channel-summary` answers 200 and the moment Discord
accepts the message there is a window in which a participant can withdraw consent, and
no arrangement of these two systems closes it: a distributed authorization check and an
external send cannot be made atomic, and this code does not pretend otherwise.

What is guaranteed instead:

* Every post is preceded by its own authorization check -- there is no cached or queued
  summary, and a summary is never re-sent after a refusal.
* The check is not racy *inside* the backend. `channel_summary` reads the negotiation
  with `SELECT ... FOR UPDATE` inside the request transaction, so a concurrent withdrawal
  either lands before the check and refuses it, or waits behind it.
* A message that does escape in that window is one the room was already consented to
  receive: a frozen `ChannelSummary` template over fields the binding already authorized.
  Nothing new is disclosed by the late arrival of an authorized sentence.
* A refusal is final and local. Once this publisher has been refused, it will not send
  again even if it is called again -- the caller does not have to honour the return value
  for publishing to stop.
"""

import logging
from collections.abc import Awaitable, Callable

from groupchat.api import API, APIError
from groupchat.render import render

LOG = logging.getLogger(__name__)


class Publisher:
    def __init__(self, api: API):
        self.api = api
        self.last: str | None = None
        self.stopped = False

    def halt(self, reason: str | None = None) -> bool:
        """Latch. `update` returning False is advice; this makes it binding.

        A refused publisher is spent. Resuming after consent is granted, or after
        re-consent, is a new `Publisher` -- which re-reads `last` from nothing and so
        cannot re-send a sentence authorized under the old audience.
        """
        self.stopped = True
        if reason:
            LOG.warning("Channel update stopped: %s.", reason)
        return False

    async def update(
        self, negotiation: str, channel: str, send: Callable[[str], Awaitable[None]]
    ) -> bool:
        """Return False to stop watching; never explain a denial to the room."""
        if self.stopped:
            return False
        try:
            data = await self.api.summary(negotiation, channel)
            text = render(data, negotiation)
        except APIError:
            return self.halt("API unavailable or unauthorized")
        except (ValueError, KeyError, TypeError, OverflowError):
            return self.halt("invalid summary")
        if text != self.last:
            await send(text)
            self.last = text
        if data["status"] in {"converged", "failed", "expired", "cancelled"}:
            return self.halt()
        return True
