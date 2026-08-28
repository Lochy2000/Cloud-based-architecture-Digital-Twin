"""
ests for src/twin/storage_writer.py.

covers the three pieces that are testable without a live broker or database:
payload-to-point mapping, sequence gap detection, and the guarantee
that a bad message or a failed write never escapes the MQTT callback.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from twin.payload import build_payload, serialize
from twin.storage_writer import SequenceTracker, handle_message, to_point, topic_for
