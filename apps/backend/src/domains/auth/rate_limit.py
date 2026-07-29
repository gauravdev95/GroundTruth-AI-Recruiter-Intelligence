"""Shared slowapi rate limiter for the auth domain.

Uses the in-memory backend (slowapi's default), which is correct for a
single-instance deployment; swapping to a Redis storage backend later is
a one-line change here with no call-site changes.
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
