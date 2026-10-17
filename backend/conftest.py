"""Pytest configuration — isolate the persistence store from the repo data dir."""

import os
import tempfile

os.environ.setdefault(
    "AGENTVERSE_DATA_DIR",
    os.path.join(tempfile.gettempdir(), f"agentverse-test-data-{os.getpid()}"),
)
